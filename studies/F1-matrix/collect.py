#!/usr/bin/env python3
"""Record every job each F1 workflow run started, from the jobs API, as CSV on stdout.

usage: collect.py > results/jobs-started.csv
One row per job: date, workflow file, run id, job name as GitHub printed it, conclusion, started and completed (UTC).
The workflows are .github/workflows/F1-*.yml. Runs whose workflow was rejected at dispatch (HTTP 422) never existed
and are not here; METHOD.md lists the two that were.
"""
import csv, json, subprocess, sys

REPO = "runners-io/ci-measurements"
gh = lambda *a: subprocess.run(["gh", *a], check=True, capture_output=True, text=True).stdout
workflows = [w for w in json.loads(gh("api", f"repos/{REPO}/actions/workflows", "--paginate", "-q", "[.workflows[]|{id,path}]"))] if False else None
listing = json.loads(gh("api", "--paginate", "--slurp", f"repos/{REPO}/actions/workflows?per_page=100"))
workflows = [w for page in listing for w in page["workflows"] if w["path"].startswith(".github/workflows/F1-")]
w = csv.writer(sys.stdout)
w.writerow(["date", "workflow", "run_id", "run_conclusion", "job", "job_conclusion", "started_at", "completed_at"])
for wf in sorted(workflows, key=lambda x: x["path"]):
    runs = json.loads(gh("api", f"repos/{REPO}/actions/workflows/{wf['id']}/runs?per_page=30&event=workflow_dispatch"))["workflow_runs"]
    for run in sorted(runs, key=lambda r: r["id"]):
        if run["status"] != "completed":
            continue
        pages = json.loads(gh("api", "--paginate", "--slurp", f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100"))
        for j in (j for p in pages for j in p["jobs"]):
            w.writerow([run["created_at"][:10], wf["path"].split("/")[-1], run["id"], run["conclusion"], j["name"], j["conclusion"], j["started_at"], j["completed_at"]])
