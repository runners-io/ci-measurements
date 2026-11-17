#!/usr/bin/env python3
"""B1: push five commits to a branch, back to back, and record what the runs did.

  drive.py push   <scenario> <reps>   # push, in parallel, one branch per rep
  drive.py collect <scenario>         # read the runs back and append to results/

Needs git, the gh CLI (logged in with write access to this repository) and python3.
Every push is made as a real `git push` of a real commit, so the runs are push-event runs.
"""
import csv, datetime, json, math, os, subprocess, sys, tempfile, threading, time

REPO = "runners-io/ci-measurements"
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
PUSHES = 5


def now_ms():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def one_rep(scenario, rep, day, out, lock):
    branch = f"b1-{scenario}/{day}-r{rep:02d}"
    with tempfile.TemporaryDirectory() as d:
        sh("git", "clone", "-q", "--depth", "1", f"https://github.com/{REPO}.git", d)
        sh("git", "config", "user.name", "Grant Unwin", cwd=d)
        sh("git", "config", "user.email", os.environ["B1_EMAIL"], cwd=d)
        sh("git", "checkout", "-q", "-b", branch, cwd=d)
        shas = []
        for n in range(1, PUSHES + 1):
            with open(os.path.join(d, "studies", "B1-concurrency", "push.txt"), "w") as f:
                f.write(f"{scenario} rep {rep} push {n}\n")
            sh("git", "add", "-A", cwd=d)
            sh("git", "commit", "-q", "-m", f"b1 {scenario} r{rep:02d} push {n}", cwd=d)
            shas.append(sh("git", "rev-parse", "HEAD", cwd=d))
        # All five commits exist before the first push, so the pushes are back to back; each is a separate `git push`.
        for n, sha in enumerate(shas, 1):
            t0 = now_ms()
            sh("git", "push", "-q", "origin", f"{sha}:refs/heads/{branch}", cwd=d)
            t1 = now_ms()
            with lock:
                out.append({"scenario": scenario, "rep": rep, "branch": branch, "push_n": n, "sha": sha, "push_started": t0, "push_finished": t1})


def cmd_push(scenario, reps):
    os.makedirs(RESULTS, exist_ok=True)
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M")
    out, lock = [], threading.Lock()
    threads = [threading.Thread(target=one_rep, args=(scenario, r, day, out, lock)) for r in range(1, reps + 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    path = os.path.join(RESULTS, f"pushes-{scenario}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "rep", "branch", "push_n", "sha", "push_started", "push_finished"])
        w.writeheader()
        for row in sorted(out, key=lambda r: (r["rep"], r["push_n"])):
            w.writerow(row)
    print(f"pushed {len(out)} commits for {scenario}; wrote {path}")


def parse(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) if ts else None


_calls = 0


def quota_guard():
    """Called before every REST call: at most one call every 3 seconds (about 20 a minute), and a check of the shared quota every 20 calls.

    The quota (5,000 an hour) is shared with other people's jobs and with the merge waiters. Below 1,000 left, sleep until
    the reset rather than spend the rest (RUN-4125: the first version of this driver ran the account dry).
    """
    global _calls
    _calls += 1
    time.sleep(3.0)
    if _calls % 20 == 1:
        got = json.loads(sh("gh", "api", "rate_limit"))["resources"]["core"]  # this endpoint is not counted against the quota
        if got["remaining"] < 1000:
            raise SystemExit(f"stopping: only {got['remaining']} REST calls left in the shared quota (below 1,000)")


def gh_api(path):
    quota_guard()
    return json.loads(sh("gh", "api", path))


def push_runs(scenario, shas):
    """The push-event runs of these commits, by head sha: one listing of the scenario's own workflow (50 runs fit in a page)."""
    found = {}
    runs = gh_api(f"repos/{REPO}/actions/workflows/B1-concurrency-{scenario}.yml/runs?event=push&per_page=100")["workflow_runs"]
    for r in runs:
        if r["head_sha"] in shas:
            found.setdefault(r["head_sha"], []).append(r)
    return found


def wait_until_idle(pushes, scenario, expect_seconds):
    """Sleep for the longest the scenario could take, then read ONE listing of its workflow's runs, once a minute, until none is busy."""
    shas = {p["sha"] for p in pushes}
    time.sleep(expect_seconds)
    deadline = time.time() + 1800
    while time.time() < deadline:
        found = push_runs(scenario, shas)
        busy = sum(1 for rs in found.values() for r in rs if r["status"] != "completed")
        if busy == 0 and len(found) == len(shas):
            return
        time.sleep(60)
    raise SystemExit("runs were still busy after 30 minutes")


def cmd_collect(scenario):
    pushes = list(csv.DictReader(open(os.path.join(RESULTS, f"pushes-{scenario}.csv"))))
    wait_until_idle(pushes, scenario, int(os.environ.get('B1_WAIT_SECONDS', '0')))
    by_sha = push_runs(scenario, {p["sha"] for p in pushes})
    rows = []
    for p in pushes:
        path_name = f".github/workflows/B1-concurrency-{scenario}.yml"  # a workflow GitHub refuses as invalid is named by its path
        runs = [r for r in by_sha.get(p["sha"], []) if r["name"] in (f"B1 {scenario}", path_name)]
        if not runs:
            rows.append({**p, "run_id": "", "note": "no run was created"})
            continue
        for r in runs:
            if r["name"] == path_name:
                jobs = []  # an invalid workflow has no jobs: one fewer call
            else:
                jobs = gh_api(f"repos/{REPO}/actions/runs/{r['id']}/jobs?per_page=50")["jobs"]
            if not jobs:
                rows.append({**p, "run_id": r["id"], "run_status": r["status"], "run_conclusion": r["conclusion"], "run_created": r["created_at"], "run_started": r["run_started_at"], "run_updated": r["updated_at"], "job": "", "note": "no job"})
            for j in jobs:
                s, c = parse(j["started_at"]), parse(j["completed_at"])
                secs = (c - s).total_seconds() if s and c else 0
                rows.append({**p, "run_id": r["id"], "run_status": r["status"], "run_conclusion": r["conclusion"], "run_created": r["created_at"], "run_started": r["run_started_at"], "run_updated": r["updated_at"],
                             "job": j["name"], "job_conclusion": j["conclusion"], "job_started": j["started_at"], "job_completed": j["completed_at"],
                             "job_seconds": int(secs), "job_billed_minutes": math.ceil(secs / 60) if secs > 0 else 0})
    fields = ["scenario", "rep", "branch", "push_n", "sha", "push_started", "push_finished", "run_id", "run_status", "run_conclusion", "run_created", "run_started", "run_updated", "job", "job_conclusion", "job_started", "job_completed", "job_seconds", "job_billed_minutes", "note"]
    path = os.path.join(RESULTS, f"runs-{scenario}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    if sys.argv[1] == "push":
        cmd_push(sys.argv[2], int(sys.argv[3]))
    elif sys.argv[1] == "collect":
        cmd_collect(sys.argv[2])
    else:
        raise SystemExit(__doc__)
