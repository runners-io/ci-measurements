#!/usr/bin/env python3
"""B2: print the counts and times of results/queue-<config>-*.csv. Usage: summarise.py <file> ..."""
import csv, collections, statistics, datetime, sys
P = lambda t: datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S") if t else None
for path in sys.argv[1:]:
    rows = list(csv.DictReader(open(path)))
    prs = [r for r in rows if r["kind"] == "pr"]
    runs = [r for r in rows if r["kind"] == "run"]
    print("==", path, "| pull requests", len(prs), "| runs", len(runs))
    print(" states:", dict(collections.Counter((r["pr_state"], r["removed_reason"]) for r in prs)))
    for ev in ("pull_request", "merge_group"):
        rr = [r for r in runs if r["event"] == ev]
        print(" ", ev, "runs", len(rr), "job-minutes", sum(int(r["job_billed_minutes"] or 0) for r in rr), "conclusions", dict(collections.Counter(r["run_conclusion"] for r in rr)))
    per = collections.Counter((r["rep"], r["n"]) for r in runs if r["event"] == "merge_group")
    print(" merge_group runs per pull request:", dict(collections.Counter(per.get((p["rep"], p["n"]), 0) for p in prs)))
    reps = sorted({p["rep"] for p in prs})
    spans = []
    for rep in reps:
        ps = [p for p in prs if p["rep"] == rep and p["added_to_queue"]]
        ms = [P(p["merged_at"]) for p in ps if p["merged_at"]]
        if ps and ms:
            spans.append(int((max(ms) - min(P(p["added_to_queue"]) for p in ps)).total_seconds()))
    print(" seconds, first added to last merged, per rep:", spans)
    for n in sorted({int(p["n"]) for p in prs}):
        ts = [int(p["seconds_enqueue_to_merge"]) for p in prs if int(p["n"]) == n and p["seconds_enqueue_to_merge"]]
        print("  n", n, "merged", len(ts), "of", len([p for p in prs if int(p["n"]) == n]), "median s", statistics.median(ts) if ts else "", "range", (min(ts), max(ts)) if ts else "")
