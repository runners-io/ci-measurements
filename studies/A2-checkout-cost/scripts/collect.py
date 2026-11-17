#!/usr/bin/env python3
"""Gather the rows of one A2 run into one CSV.

usage: collect.py RUN_ID OUT_CSV

Downloads every `row-*` artifact of the run with `gh run download`, and joins the rows in cell order.
"""
import csv, glob, pathlib, subprocess, sys, tempfile

run_id, out = sys.argv[1], sys.argv[2]
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["gh", "run", "download", run_id, "-R", "runners-io/ci-measurements", "-D", tmp, "-p", "row-*"], check=True)
    rows = []
    for p in glob.glob(f"{tmp}/row-*/row.csv"):
        with open(p, newline="") as f:
            rows.extend(csv.DictReader(f))
rows.sort(key=lambda r: int(r["order"]))
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} rows -> {out}")
