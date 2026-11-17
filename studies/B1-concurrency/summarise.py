#!/usr/bin/env python3
"""B1: turn results/runs-<scenario>.csv into results/summary.csv and print it.

For each scenario and rep, every push is labelled by what happened to its run:
  ok       the run's job(s) ran to success
  cut      the run started a job and was cancelled while it ran
  dropped  the run was cancelled before any job started (it cost no minutes)
  invalid  the run never started: the workflow was refused as invalid
  other    anything else (named in the CSV)
The pattern is those labels for pushes 1..5 in order. A matrix scenario has three jobs per run; a run is `ok` when all
succeeded, `cut` when any started and was cancelled, `dropped` when none started.
Minutes are computed, not billed: each job's seconds rounded up to a whole minute, as GitHub's pricing reference says it
rounds. This repository is public, so nothing here was charged.
"""
import csv, collections, glob, os, statistics, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")


def ts(t):
    return datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%fZ" if "." in t else "%Y-%m-%dT%H:%M:%SZ") if t else None


def label(runs):
    jobs = [r for r in runs if r["job"]]
    if not jobs:
        return "invalid" if runs[0]["run_conclusion"] in ("failure", "startup_failure") else "dropped"
    started = [j for j in jobs if j["job_started"]]
    if not started:
        return "dropped"
    if all(j["job_conclusion"] == "success" for j in jobs):
        return "ok"
    if any(j["job_conclusion"] == "cancelled" for j in started):
        return "cut"
    return "other"


def med(xs):
    return statistics.median(xs) if xs else ""


out = []
for path in sorted(glob.glob(os.path.join(RES, "runs-*.csv"))):
    scenario = os.path.basename(path)[5:-4]
    rows = list(csv.DictReader(open(path)))
    pushes = {(p["rep"], p["push_n"]): p for p in csv.DictReader(open(os.path.join(RES, f"pushes-{scenario}.csv")))}
    reps = sorted({r["rep"] for r in rows}, key=int)
    patterns, minutes, secs, spans, started_counts, push_spans = collections.Counter(), [], [], [], [], []
    for rep in reps:
        rrows = [r for r in rows if r["rep"] == rep]
        by_push = collections.defaultdict(list)
        for r in rrows:
            by_push[int(r["push_n"])].append(r)
        pat = " ".join(f"{n}:{label(by_push[n])}" for n in sorted(by_push))
        patterns[pat] += 1
        minutes.append(sum(int(r["job_billed_minutes"] or 0) for r in rrows))
        secs.append(sum(int(r["job_seconds"] or 0) for r in rrows))
        started_counts.append(sum(1 for n in by_push if label(by_push[n]) in ("ok", "cut")))
        first_push = ts(pushes[(rep, "1")]["push_started"])
        last_push = ts(pushes[(rep, "5")]["push_finished"])
        push_spans.append((last_push - first_push).total_seconds())
        done = [ts(r["job_completed"]) for r in rrows if r["job_completed"]]
        if done:
            spans.append((max(done) - first_push).total_seconds())
    out.append({
        "scenario": scenario, "reps": len(reps),
        "pushes_span_seconds_median": round(med(push_spans), 1),
        "runs_that_started_a_job_median": med(started_counts),
        "job_seconds_per_rep_median": med(secs), "job_seconds_per_rep_min": min(secs), "job_seconds_per_rep_max": max(secs),
        "minutes_per_rep_median": med(minutes), "minutes_per_rep_min": min(minutes), "minutes_per_rep_max": max(minutes),
        "first_push_to_last_job_done_seconds_median": round(med(spans), 1) if spans else "",
        "first_push_to_last_job_done_seconds_min": round(min(spans), 1) if spans else "",
        "first_push_to_last_job_done_seconds_max": round(max(spans), 1) if spans else "",
        "patterns": " | ".join(f"{v}x [{k}]" for k, v in patterns.most_common()),
    })
with open(os.path.join(RES, "summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
for o in out:
    print(o["scenario"], "|", {k: v for k, v in o.items() if k not in ("scenario", "patterns")})
    print("    ", o["patterns"])
