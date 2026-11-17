#!/usr/bin/env python3
"""B4: what a pull request says when its required check never ran.

  observe-required.py <reps>

The branch b4-required has a ruleset that requires a check named "build" (rulesets/b4-required.json). The workflow
.github/workflows/B4-path-filtered.yml makes that check, but only for changes under studies/B4-queued-states/trigger/.
Each rep opens a pull request that changes a file elsewhere, reads what the pull request reports at 20, 60 and 120
seconds, and closes it. The third read is the point: the check never arrives, so the wait never ends by itself.
"""
import csv, datetime, json, os, subprocess, sys, tempfile, threading, time

REPO = "runners-io/ci-measurements"
HERE = os.path.dirname(os.path.abspath(__file__))
READ_AT = [20, 90]


def sh(*a, cwd=None):
    return subprocess.run(a, check=True, capture_output=True, text=True, cwd=cwd).stdout.strip()


def one(rep, stamp, rows, lock):
    branch = f"b4p-required-{stamp}-r{rep}"
    with tempfile.TemporaryDirectory() as d:
        sh("git", "clone", "-q", "--depth", "1", "--branch", "b4-required", f"https://github.com/{REPO}.git", d)
        sh("git", "config", "user.name", "Grant Unwin", cwd=d)
        sh("git", "config", "user.email", os.environ["B4_EMAIL"], cwd=d)
        sh("git", "checkout", "-q", "-b", branch, cwd=d)
        with open(os.path.join(d, "studies", "B4-queued-states", f"elsewhere-{stamp}-r{rep}.txt"), "w") as f:
            f.write("a change outside the path filter\n")
        sh("git", "add", "-A", cwd=d)
        sh("git", "commit", "-q", "-m", f"b4 required r{rep}", cwd=d)
        sh("git", "push", "-q", "origin", f"HEAD:refs/heads/{branch}", cwd=d)
    url = sh("gh", "pr", "create", "--repo", REPO, "--base", "b4-required", "--head", branch, "--title", f"b4 required {stamp} r{rep}", "--body", "A pull request of the queued-states study. Safe to ignore.")
    number = url.rsplit("/", 1)[1]
    t0 = time.time()
    for k in READ_AT:
        time.sleep(max(0, t0 + k - time.time()))
        pr = json.loads(sh("gh", "pr", "view", number, "--repo", REPO, "--json", "mergeStateStatus,mergeable,statusCheckRollup,state"))
        time.sleep(3)
        runs = json.loads(sh("gh", "api", f"repos/{REPO}/actions/runs?event=pull_request&branch={branch}"))["workflow_runs"]
        with lock:
            rows.append({"rep": rep, "pr": number, "seconds_after_open": k, "merge_state_status": pr["mergeStateStatus"], "mergeable": pr["mergeable"],
                         "checks_listed": len(pr["statusCheckRollup"] or []), "workflow_runs_for_the_branch": len(runs)})
    sh("gh", "pr", "close", number, "--repo", REPO, "--delete-branch")


if __name__ == "__main__":
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%m%d%H%M")
    rows, lock = [], threading.Lock()
    ts = [threading.Thread(target=one, args=(r, stamp, rows, lock)) for r in range(1, int(sys.argv[1]) + 1)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    path = os.path.join(HERE, "results", f"required-{stamp}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in sorted(rows, key=lambda r: (r["rep"], r["seconds_after_open"])):
            w.writerow(row)
    print(f"wrote {len(rows)} rows to {path}")
