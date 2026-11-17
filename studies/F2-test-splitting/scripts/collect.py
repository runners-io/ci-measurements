#!/usr/bin/env python3
"""Collect one F2 run's jobs into rows.

usage: collect.py RUN_ID [RUN_ID ...] > rows.csv

Reads the jobs API (job and step start and completion, to the second) and each job's pytest summary line
from its uploaded artifact (r-<strategy>-<shards>-<index>-<rep>/summary.txt). One row per test job.
Needs `gh` logged in; writes nothing but the CSV on stdout.
"""
import csv, datetime as dt, json, re, subprocess, sys, tempfile, pathlib

REPO = "runners-io/ci-measurements"

def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout

def secs(a, b):
    f = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return int((f(b) - f(a)).total_seconds())

w = csv.writer(sys.stdout)
w.writerow(["date", "run_id", "strategy", "shards", "shard", "rep", "files", "job_seconds", "billed_minutes",
            "checkout_measurements_s", "checkout_networkx_s", "setup_python_s", "install_s", "select_s", "pytest_s", "pytest_reported_s", "passed", "skipped", "xfailed", "failed"])
for run_id in sys.argv[1:]:
    run = json.loads(gh("api", f"repos/{REPO}/actions/runs/{run_id}"))
    jobs = json.loads(gh("api", "--paginate", "--slurp", f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100"))
    jobs = [j for page in jobs for j in page["jobs"]]
    with tempfile.TemporaryDirectory() as d:
        for attempt in range(4):  # a download of 90 artifacts sometimes fails once on a rate limit
            if subprocess.run(["gh", "run", "download", run_id, "-R", REPO, "-D", d, "-p", "r-*"], capture_output=True).returncode == 0:
                break
        else:
            sys.exit(f"could not download the artifacts of run {run_id}")
        for j in jobs:
            m = re.match(r"^(\S+) (\d+) shard (\d+) rep (\d+)$", j["name"])
            if not m:
                continue
            strategy, shards, shard, rep = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
            steps = {s["name"]: s for s in j["steps"] if s.get("completed_at")}
            step_s = lambda n: secs(steps[n]["started_at"], steps[n]["completed_at"]) if n in steps else ""
            art = pathlib.Path(d, f"r-{strategy}-{shards}-{shard}-{rep}")
            summary = (art / "summary.txt").read_text() if (art / "summary.txt").exists() else ""
            files = len((art / "shard-files.txt").read_text().split()) if (art / "shard-files.txt").exists() else ""
            num = lambda word: (int(re.search(rf"(\d+) {word}", summary).group(1)) if re.search(rf"(\d+) {word}", summary) else 0)
            rep_s = re.search(r" in ([\d.]+)s", summary)
            job_s = secs(j["started_at"], j["completed_at"])
            w.writerow([run["created_at"][:10], run_id, strategy, shards, shard, rep, files, job_s, -(-job_s // 60),
                        step_s("checkout measurements"), step_s("checkout networkx"), step_s("setup-python"), step_s("install"), step_s("select tests"), step_s("pytest"),
                        rep_s.group(1) if rep_s else "", num("passed"), num("skipped"), num("xfailed"), num("failed")])
