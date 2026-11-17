#!/usr/bin/env python3
"""Read what happened in one G1 run, and write one CSV row per job.

usage: collect.py RUN_ID OUT_CSV

For each job: its name, rep and result from the jobs API; each later step's result; the check-run annotations; and,
from the job log, the second at which things happened, counted from the step's own first line:
  signal_*_s    when a signal reached the victim, from the victim's own first line (the victim prints "got SIGINT" ...)
  signal_*_from_job_start_s   the same moment, from the first line of the job's log
  last_beat_s   the last heartbeat the victim printed, so the last second it was alive
  error_s       when the runner wrote its ##[error] line (its decision that the limit was reached)
  step_s        the victim step's duration, from the API (whole seconds)
  job_s         the job's duration from the API (whole seconds)
  limit_to_end  error_s: the time from the victim's start to the runner's error line
"""
import csv, datetime, json, re, subprocess, sys, time

R = "runners-io/ci-measurements"
run_id, out = sys.argv[1], sys.argv[2]


def gh(*args):
    for attempt in range(5):  # a log may not be ready the moment a job completes
        p = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
        if p.returncode == 0:
            return p.stdout
        time.sleep(3 * (attempt + 1))
    raise SystemExit(f"gh api {' '.join(args)} failed: {p.stderr.strip()}")


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


raw = gh(f"repos/{R}/actions/runs/{run_id}/jobs?per_page=100")
jobs = json.loads(raw)["jobs"]
rows = []
for j in jobs:
    m = re.match(r"(?P<variant>.+) (?:#|\()(?P<rep>\d+)\)?$", j["name"])
    variant, rep = m["variant"], int(m["rep"])
    steps = {s["name"]: s for s in j["steps"]}
    victim = steps["the step that never finishes"]
    log = gh(f"repos/{R}/actions/jobs/{j['id']}/logs", "--allow-escape-sequences")
    log = re.sub(r"\x1b\[[0-9;]*m", "", log).replace("﻿", "")
    lines = [(l[:28], l[29:]) for l in log.splitlines() if re.match(r"\d{4}-\d\d-\d\dT", l)]

    def at(pred):
        for t, text in lines:
            if pred(text):
                return datetime.datetime.fromisoformat(t[:26] + "+00:00").timestamp()
        return None

    first = at(lambda s: True)
    start = at(lambda s: s.startswith("##[group]Run ") and "victim.sh" in s)
    sig = {}
    for name in ("SIGINT", "SIGTERM"):
        t = at(lambda s, n=name: f"got {n}" in s)
        sig[name] = round(t - start, 1) if t and start else ""
        sig[name + "_job"] = round(t - first, 1) if t and first else ""
    beats = [text for _, text in lines if text.startswith("heartbeat ")]
    last_beat = re.search(r"\+([\d.]+)s", beats[-1])[1] if beats else ""
    err = at(lambda s: s.startswith("##[error]"))
    ann = json.loads(gh(f"repos/{R}/check-runs/{j['id']}/annotations"))
    ran = {k: steps[f"next step, {k}"]["conclusion"] for k in ("no condition", "if success()", "if failure()", "if cancelled()", "if always()")}
    rows.append({
        "date": datetime.datetime.fromisoformat(j["started_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d"),
        "run_id": run_id, "job_id": j["id"], "variant": variant, "rep": rep,
        "job_conclusion": j["conclusion"], "victim_step_conclusion": victim["conclusion"],
        "no_condition": ran["no condition"], "if_success": ran["if success()"], "if_failure": ran["if failure()"],
        "if_cancelled": ran["if cancelled()"], "if_always": ran["if always()"],
        "annotations": " | ".join(a["message"] for a in ann),
        "signal_int_s": sig["SIGINT"], "signal_term_s": sig["SIGTERM"],
        "signal_int_from_job_start_s": sig["SIGINT_job"], "signal_term_from_job_start_s": sig["SIGTERM_job"], "last_beat_s": last_beat,
        "error_s": round(err - start, 1) if err and start else "",
        "job_first_log_to_error_s": round(err - first, 1) if err and first else "",
        "step_s": round(ts(victim["completed_at"]) - ts(victim["started_at"])),
        "job_s": round(ts(j["completed_at"]) - ts(j["started_at"])),
    })
rows.sort(key=lambda r: (r["variant"], r["rep"]))
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} rows -> {out}")
