#!/usr/bin/env python3
"""B2: put N pull requests into a merge queue at once and record what the queue did.

  drive.py run <config> <reps> [prs]    # config is c1, c2, c3 or c4; reps run in parallel, one base branch each
  drive.py collect <config> <stamp>     # read the pull requests and runs back (run does this itself)

The study branches b2-mq-<config>-r<rep> and the rulesets that put a merge queue on them are in rulesets/.
Needs git, the gh CLI (write access to this repository) and python3. Every PR changes one file of its own, so none
conflicts. In config c4 the third PR carries a file whose name contains "fail": its merge-group check fails and its
pull-request check passes ("green alone, red once combined").
"""
import csv, datetime, json, math, os, subprocess, sys, tempfile, threading, time

REPO = "runners-io/ci-measurements"
OWNER, NAME = REPO.split("/")
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
CHECK = "B2 merge queue check"
FAIL_AT = {"c4": 3}


def now_ms():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def sh(*args, cwd=None, check=True, retries=4):
    """Run a command, retrying a few times (GitHub's secondary rate limits answer a burst of pushes and pull requests with a refusal)."""
    for attempt in range(retries + 1):
        got = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        if got.returncode == 0 or not check:
            return got.stdout.strip()
        if attempt == retries:
            raise SystemExit(f"{' '.join(args)} failed {retries + 1} times: {got.stderr.strip()[:400]}")
        time.sleep(5 * (attempt + 1) + (hash((args, threading.get_ident())) % 5))


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
        got = json.loads(subprocess.run(["gh", "api", "rate_limit"], capture_output=True, text=True).stdout)["resources"]["core"]
        if got["remaining"] < 1000:
            raise SystemExit(f"stopping: only {got['remaining']} REST calls left in the shared quota (below 1,000)")


def gh_api(path, *extra):
    quota_guard()
    got = subprocess.run(["gh", "api", path, *extra], capture_output=True, text=True)
    if got.returncode != 0:
        raise SystemExit(f"gh api {path} failed (not retried; a retry loop is how the quota was spent): {got.stderr.strip()[:300]}")
    return json.loads(got.stdout)


def graphql(query, **vars_):
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in vars_.items():
        if isinstance(v, list):
            for item in v:
                args += ["-f", f"{k}[]={item}"]
        else:
            args += ["-F", f"{k}={v}"]
    return json.loads(sh(*args))


def parse(ts):
    return datetime.datetime.strptime(ts[:19] + "Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) if ts else None


def one_rep(cfg, rep, n_prs, stamp, out, lock):
    base = f"b2-mq-{cfg}-r{rep}"
    with tempfile.TemporaryDirectory() as d:
        sh("git", "clone", "-q", "--depth", "1", "--branch", base, f"https://github.com/{REPO}.git", d)
        sh("git", "config", "user.name", "Grant Unwin", cwd=d)
        sh("git", "config", "user.email", os.environ["B2_EMAIL"], cwd=d)
        prs = []
        for n in range(1, n_prs + 1):
            branch = f"b2p-{cfg}-r{rep}-n{n}-{stamp}"
            sh("git", "checkout", "-q", "-B", branch, f"origin/{base}", cwd=d)
            fail = FAIL_AT.get(cfg) == n
            name = f"{cfg}-r{rep}-n{n:02d}-{stamp}{'-fail' if fail else ''}.txt"
            with open(os.path.join(d, "studies", "B2-merge-queue", "prs", name), "w") as f:
                f.write(f"{cfg} rep {rep} pull request {n}\n")
            sh("git", "add", "-A", cwd=d)
            sh("git", "commit", "-q", "-m", f"b2 {cfg} r{rep} n{n}", cwd=d)
            sh("git", "push", "-q", "origin", f"HEAD:refs/heads/{branch}", cwd=d)
            url = sh("gh", "pr", "create", "--repo", REPO, "--base", base, "--head", branch, "--title", f"b2 {cfg} r{rep} n{n} {stamp}", "--body", "A pull request of the merge-queue study (studies/B2-merge-queue). Safe to ignore.")
            number = int(url.rsplit("/", 1)[1])
            node_id = sh("gh", "pr", "view", str(number), "--repo", REPO, "--json", "id", "-q", ".id")
            head = sh("git", "rev-parse", "HEAD", cwd=d)
            prs.append({"config": cfg, "rep": rep, "base": base, "n": n, "branch": branch, "pr": number, "node_id": node_id, "head_sha": head, "marked_fail": int(fail)})
    # Wait until every pull request's own check has passed: one GraphQL call per poll (the REST quota is shared and small).
    deadline = time.time() + 900
    while time.time() < deadline:
        states = rollup_states([p["node_id"] for p in prs])
        if all(st == "SUCCESS" for st in states.values()):
            break
        time.sleep(60)
    else:
        raise SystemExit(f"{cfg} r{rep}: checks never passed: {states}")
    for p in prs:
        p["enqueue_issued"] = now_ms()
        enqueue(p["node_id"])
        p["enqueue_returned"] = now_ms()
    with lock:
        out.extend(prs)


ROLLUP = """query($ids:[ID!]!){nodes(ids:$ids){... on PullRequest{id commits(last:1){nodes{commit{statusCheckRollup{state}}}}}}}"""


def rollup_states(ids):
    got = graphql(ROLLUP, ids=ids)
    out = {}
    for n in got["data"]["nodes"]:
        c = n["commits"]["nodes"][0]["commit"]["statusCheckRollup"]
        out[n["id"]] = c["state"] if c else "NONE"
    return out


ENQUEUE = "mutation($id:ID!){enqueuePullRequest(input:{pullRequestId:$id}){mergeQueueEntry{position state}}}"


def enqueue(node_id):
    """Add a pull request to its base branch's merge queue. `gh pr merge` would try auto-merge, which this repository leaves off."""
    sh("gh", "api", "graphql", "-f", f"query={ENQUEUE}", "-F", f"id={node_id}")


def cmd_run(cfg, reps, n_prs):
    os.makedirs(RESULTS, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%m%d%H%M")
    out, lock = [], threading.Lock()
    threads = [threading.Thread(target=one_rep, args=(cfg, r, n_prs, stamp, out, lock)) for r in range(1, reps + 1)]
    for t in threads:
        t.start()
        time.sleep(3)  # stagger the reps: five at once trips GitHub's secondary rate limit on pushes and pull requests
    for t in threads:
        t.join()
    path = os.path.join(RESULTS, f"prs-{cfg}-{stamp}.csv")
    fields = ["config", "rep", "base", "n", "branch", "pr", "node_id", "head_sha", "marked_fail", "enqueue_issued", "enqueue_returned"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in sorted(out, key=lambda r: (r["rep"], r["n"])):
            w.writerow(row)
    print(f"enqueued {len(out)} pull requests; wrote {path}")
    cmd_collect(cfg, stamp)


TIMELINE = """query($ids:[ID!]!){nodes(ids:$ids){... on PullRequest{id number state createdAt mergedAt closedAt
 timelineItems(first:60,itemTypes:[ADDED_TO_MERGE_QUEUE_EVENT,REMOVED_FROM_MERGE_QUEUE_EVENT,MERGED_EVENT]){nodes{__typename
  ... on AddedToMergeQueueEvent{createdAt}
  ... on RemovedFromMergeQueueEvent{createdAt reason}
  ... on MergedEvent{createdAt}}}}}}"""


def pr_states(ids):
    """Every pull request's state and queue events, one GraphQL call for all of them, keyed by node id."""
    return {n["id"]: n for n in graphql(TIMELINE, ids=ids)["data"]["nodes"]}


def is_terminal(pr):
    if pr["state"] != "OPEN":
        return True
    events = [e["__typename"] for e in pr["timelineItems"]["nodes"]]
    return bool(events) and events[-1] == "RemovedFromMergeQueueEvent"


def job_rows(run_id):
    jobs = gh_api(f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=20")["jobs"]
    rows = []
    for j in jobs:
        s, c = parse(j["started_at"]), parse(j["completed_at"])
        secs = int((c - s).total_seconds()) if s and c else 0
        rows.append({"job_conclusion": j["conclusion"], "job_started": j["started_at"], "job_completed": j["completed_at"], "job_seconds": secs, "job_billed_minutes": math.ceil(secs / 60) if secs > 0 else 0})
    return rows or [{"job_conclusion": "", "job_started": "", "job_completed": "", "job_seconds": 0, "job_billed_minutes": 0}]


def cmd_collect(cfg, stamp):
    prs = list(csv.DictReader(open(os.path.join(RESULTS, f"prs-{cfg}-{stamp}.csv"))))
    ids = [p["node_id"] for p in prs]
    # 1. wait until every pull request has merged or been removed from the queue (up to 45 minutes)
    deadline = time.time() + 2700
    while True:
        states = pr_states(ids)
        if all(is_terminal(st) for st in states.values()) or time.time() > deadline:
            break
        time.sleep(60)
    # 2. one listing of the workflow's merge-group runs and one of its pull-request runs (a page of 100 each; a second page only if
    #    the first is full), repeated once a minute only while a merge-group run is still going.
    wf = f"repos/{REPO}/actions/workflows/B2-merge-queue-check.yml/runs"

    def listing(event):
        out, page = [], 1
        while page <= 4:
            got = gh_api(f"{wf}?event={event}&per_page=100&page={page}")["workflow_runs"]
            out += got
            if len(got) < 100:
                break
            page += 1
        return out

    bases = sorted({p["base"] for p in prs})
    mine = lambda r: any(r["head_branch"].startswith(f"gh-readonly-queue/{b}/") for b in bases)
    while True:
        mg_runs = [r for r in listing("merge_group") if mine(r)]
        if not any(r["status"] != "completed" for r in mg_runs) or time.time() > deadline:
            break
        time.sleep(60)
    pr_runs = {r["head_branch"]: r for r in listing("pull_request")}
    rows = []
    pr_by_number = {p["pr"]: p for p in prs}
    for p in prs:
        s = states[p["node_id"]]
        ev = s["timelineItems"]["nodes"]
        added = [e["createdAt"] for e in ev if e["__typename"] == "AddedToMergeQueueEvent"]
        removed = [(e["createdAt"], e.get("reason")) for e in ev if e["__typename"] == "RemovedFromMergeQueueEvent"]
        merged = s["mergedAt"]
        rows.append({"kind": "pr", **{k: p[k] for k in ("config", "rep", "base", "n", "pr", "marked_fail")},
                     "pr_state": s["state"], "pr_created": s["createdAt"], "enqueue_issued": p["enqueue_issued"],
                     "added_to_queue": added[0] if added else "", "times_added": len(added),
                     "merged_at": merged or "", "removed_at": removed[0][0] if removed else "", "removed_reason": removed[0][1] if removed else "",
                     "seconds_enqueue_to_merge": int((parse(merged) - parse(added[0])).total_seconds()) if merged and added else ""})
        r = pr_runs.get(p["branch"])
        if r:  # the pull request's own check run; its jobs are read once, now that the run has completed
            for j in job_rows(r["id"]):
                rows.append({"kind": "run", "config": p["config"], "rep": p["rep"], "base": p["base"], "n": p["n"], "pr": p["pr"], "event": "pull_request",
                             "run_id": r["id"], "run_conclusion": r["conclusion"], "run_created": r["created_at"], **j})
    for r in mg_runs:
        pr_no = r["head_branch"].rsplit("/", 1)[1].split("-")[1]
        if pr_no not in pr_by_number:
            continue  # an earlier pilot's entry on the same base branch
        p = pr_by_number[pr_no]
        for j in job_rows(r["id"]):
            rows.append({"kind": "run", "config": p["config"], "rep": p["rep"], "base": p["base"], "n": p["n"], "pr": int(pr_no), "event": "merge_group",
                         "run_id": r["id"], "run_conclusion": r["conclusion"], "run_created": r["created_at"], **j})
    fields = ["kind", "config", "rep", "base", "n", "pr", "marked_fail", "pr_state", "pr_created", "enqueue_issued", "added_to_queue", "times_added", "merged_at", "removed_at", "removed_reason", "seconds_enqueue_to_merge",
              "event", "run_id", "run_conclusion", "run_created", "job_conclusion", "job_started", "job_completed", "job_seconds", "job_billed_minutes"]
    path = os.path.join(RESULTS, f"queue-{cfg}-{stamp}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        cmd_run(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 8)
    elif sys.argv[1] == "collect":
        cmd_collect(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
