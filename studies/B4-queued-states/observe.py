#!/usr/bin/env python3
"""B4: dispatch .github/workflows/B4-queued-states.yml twice per rep, read the statuses back, cancel the runs.

  observe.py <reps>

For each rep, one run is dispatched per kind of wait (two, a second apart, for `limited`). The status of each run and
of its job is read at fixed times, so the table shows which status word each kind of wait has.
Runs that are still waiting are cancelled at the end: the `no-runner` job would otherwise wait for 24 hours.
"""
import csv, datetime, json, os, subprocess, sys, threading, time

REPO = "runners-io/ci-measurements"
HERE = os.path.dirname(os.path.abspath(__file__))
READ_AT = [15, 45, 75]  # seconds after the (first) dispatch; the `limited` job of the first run works for 90 seconds


def sh(*a):
    return subprocess.run(a, check=True, capture_output=True, text=True).stdout.strip()


def api(path):
    for i in range(6):
        try:
            return json.loads(sh("gh", "api", path))
        except subprocess.CalledProcessError:
            time.sleep(2 * (i + 1))
    raise SystemExit(path)


def dispatch(kind, label):
    sh("gh", "workflow", "run", "B4-queued-states.yml", "-R", REPO, "-f", f"label={label}", "-f", f"kind={kind}")


def one(rep, kind, stamp, rows, lock):
    label = f"{stamp}-r{rep}"
    title = f"B4 queued states {kind} {label}"
    n_dispatch = 2 if kind == "limited" else 1  # `limited` needs a second run of the same group
    dispatch(kind, label)
    if n_dispatch == 2:
        time.sleep(1)
        dispatch(kind, label)
    t0 = time.time()
    runs = []
    while len(runs) < n_dispatch and time.time() - t0 < 60:
        found = [r for r in api(f"repos/{REPO}/actions/runs?event=workflow_dispatch&per_page=50")["workflow_runs"] if r["display_title"] == title]
        runs = sorted(found, key=lambda r: r["created_at"])
        time.sleep(2)
    for k in READ_AT:
        time.sleep(max(0, t0 + k - time.time()))
        for n, r in enumerate(runs, 1):
            run = api(f"repos/{REPO}/actions/runs/{r['id']}")
            jobs = api(f"repos/{REPO}/actions/runs/{r['id']}/jobs?per_page=20")["jobs"]
            for j in jobs:
                if j["conclusion"] == "skipped":
                    continue
                with lock:
                    rows.append({"label": label, "rep": rep, "kind": kind, "dispatch": n, "run_id": r["id"], "seconds_after_dispatch": k, "run_status": run["status"],
                                 "job": j["name"], "job_status": j["status"], "job_conclusion": j["conclusion"] or "", "runner_name": j["runner_name"] or "", "job_labels": ";".join(j["labels"])})
    for r in runs:
        subprocess.run(["gh", "run", "cancel", str(r["id"]), "-R", REPO], capture_output=True)


if __name__ == "__main__":
    reps = int(sys.argv[1])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%m%d%H%M")
    rows, lock = [], threading.Lock()
    ts = [threading.Thread(target=one, args=(r, k, stamp, rows, lock)) for r in range(1, reps + 1) for k in ("no-runner", "gated", "limited")]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", f"states-{stamp}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in sorted(rows, key=lambda r: (r["kind"], r["rep"], r["dispatch"], r["seconds_after_dispatch"])):
            w.writerow(row)
    print(f"wrote {len(rows)} rows to {path}")
