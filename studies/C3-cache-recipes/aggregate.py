#!/usr/bin/env python3
"""Joins the per-job artifacts of one orchestrator run into one CSV per study. Usage: aggregate.py ARTIFACT_DIR OUT_DIR RUN_ID

Each job uploaded an artifact named <prefix>-... holding row.csv. Prefixes: c1 (sccache builds), c2g (cache grid),
c2i (real installs), c3 (cache recipes), c3f (recipes with exclusion patterns). Also copies sccache's JSON statistics
and the key-drift listings, which are evidence for the rows.
"""
import csv, glob, os, shutil, sys
src, out, run = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
groups = {"c1": "builds", "c2g": "grid", "c2i": "installs", "c3": "recipes", "c3f": "recipes-fixed"}
for prefix, name in groups.items():
    rows = []
    for d in sorted(glob.glob(os.path.join(src, prefix + "-*"))):
        for f in glob.glob(os.path.join(d, "row.csv")):
            rows += list(csv.DictReader(open(f)))
    if rows:
        with open(os.path.join(out, f"{name}-{run}.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(name, len(rows), "rows")
for kind, pat in (("sccache-stats", "c1-*/sccache-stats-*.json"), ("keydrift", "c3*-*/keydrift.txt")):
    d = os.path.join(out, f"{kind}-{run}"); os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(src, pat)):
        shutil.copy(f, os.path.join(d, os.path.basename(os.path.dirname(f)) + "-" + os.path.basename(f)))
