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


def sh(*args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


def gh_api(path, *extra):
    for attempt in range(6):
        try:
            return json.loads(sh("gh", "api", path, *extra))
        except subprocess.CalledProcessError:
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"gh api {path} failed")


def graphql(query, **vars_):
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in vars_.items():
        args += ["-F", f"{k}={v}"]
    for attempt in range(6):
        try:
            return json.loads(sh(*args))
        except subprocess.CalledProcessError:
            time.sleep(2 * (attempt + 1))
    raise SystemExit("graphql failed")


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
            head = sh("git", "rev-parse", "HEAD", cwd=d)
            prs.append({"config": cfg, "rep": rep, "base": base, "n": n, "branch": branch, "pr": number, "head_sha": head, "marked_fail": int(fail)})
    # Wait until every pull request's own check has passed, then enqueue them in order, back to back.
    deadline = time.time() + 900
    pending = {p["pr"]: p for p in prs}
    while pending and time.time() < deadline:
        for number, p in list(pending.items()):
            runs = gh_api(f"repos/{REPO}/commits/{p['head_sha']}/check-runs?check_name=check")["check_runs"]
            if any(r["conclusion"] == "success" for r in runs):
                del pending[number]
        time.sleep(5)
    if pending:
        raise SystemExit(f"{cfg} r{rep}: checks never passed on {sorted(pending)}")
    for p in prs:
        p["enqueue_issued"] = now_ms()
        enqueue(p["pr"])
        p["enqueue_returned"] = now_ms()
    with lock:
        out.extend(prs)


ENQUEUE = "mutation($id:ID!){enqueuePullRequest(input:{pullRequestId:$id}){mergeQueueEntry{position state}}}"


def enqueue(number):
    """Add a pull request to its base branch's merge queue. `gh pr merge` would try auto-merge, which this repository leaves off."""
    node_id = sh("gh", "pr", "view", str(number), "--repo", REPO, "--json", "id", "-q", ".id")
    for attempt in range(5):
        try:
            sh("gh", "api", "graphql", "-f", f"query={ENQUEUE}", "-F", f"id={node_id}")
            return
        except subprocess.CalledProcessError:
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"could not enqueue PR {number}")


def cmd_run(cfg, reps, n_prs):
    os.makedirs(RESULTS, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%m%d%H%M")
    out, lock = [], threading.Lock()
    threads = [threading.Thread(target=one_rep, args=(cfg, r, n_prs, stamp, out, lock)) for r in range(1, reps + 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    path = os.path.join(RESULTS, f"prs-{cfg}-{stamp}.csv")
    fields = ["config", "rep", "base", "n", "branch", "pr", "head_sha", "marked_fail", "enqueue_issued", "enqueue_returned"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in sorted(out, key=lambda r: (r["rep"], r["n"])):
            w.writerow(row)
    print(f"enqueued {len(out)} pull requests; wrote {path}")
    cmd_collect(cfg, stamp)


TIMELINE = """query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){
 state createdAt mergedAt closedAt
 timelineItems(first:60,itemTypes:[ADDED_TO_MERGE_QUEUE_EVENT,REMOVED_FROM_MERGE_QUEUE_EVENT,MERGED_EVENT]){nodes{__typename
  ... on AddedToMergeQueueEvent{createdAt}
  ... on RemovedFromMergeQueueEvent{createdAt reason}
  ... on MergedEvent{createdAt}}}}}}"""


def pr_state(number):
    return graphql(TIMELINE, o=OWNER, r=NAME, n=number)["data"]["repository"]["pullRequest"]


def terminal(number):
    pr = pr_state(number)
    if pr["state"] != "OPEN":
        return pr
    events = [e["__typename"] for e in pr["timelineItems"]["nodes"]]
    if events and events[-1] == "RemovedFromMergeQueueEvent":
        return pr
    return None


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
    # 1. wait until every pull request has merged or been removed from the queue (up to 45 minutes)
    deadline, done = time.time() + 2700, {}
    while time.time() < deadline and len(done) < len(prs):
        for p in prs:
            if p["pr"] not in done:
                got = terminal(p["pr"])
                if got:
                    done[p["pr"]] = got
        if len(done) < len(prs):
            time.sleep(10)
    # 2. wait until no merge-group run is still going
    while time.time() < deadline:
        busy = 0
        for base in sorted({p["base"] for p in prs}):
            runs = gh_api(f"repos/{REPO}/actions/runs?event=merge_group&per_page=100")["workflow_runs"]
            busy += sum(1 for r in runs if r["head_branch"].startswith(f"gh-readonly-queue/{base}/") and r["status"] != "completed")
            break
        if busy == 0:
            break
        time.sleep(10)
    rows = []
    pr_by_number = {p["pr"]: p for p in prs}
    for p in prs:
        s = pr_state(p["pr"])
        ev = s["timelineItems"]["nodes"]
        added = [e["createdAt"] for e in ev if e["__typename"] == "AddedToMergeQueueEvent"]
        removed = [(e["createdAt"], e.get("reason")) for e in ev if e["__typename"] == "RemovedFromMergeQueueEvent"]
        merged = s["mergedAt"]
        rows.append({"kind": "pr", **{k: p[k] for k in ("config", "rep", "base", "n", "pr", "marked_fail")},
                     "pr_state": s["state"], "pr_created": s["createdAt"], "enqueue_issued": p["enqueue_issued"],
                     "added_to_queue": added[0] if added else "", "times_added": len(added),
                     "merged_at": merged or "", "removed_at": removed[0][0] if removed else "", "removed_reason": removed[0][1] if removed else "",
                     "seconds_enqueue_to_merge": int((parse(merged) - parse(added[0])).total_seconds()) if merged and added else ""})
        # the pull request's own check run
        for r in gh_api(f"repos/{REPO}/actions/runs?event=pull_request&branch={p['branch']}&per_page=20")["workflow_runs"]:
            if r["name"] != CHECK:
                continue
            for j in job_rows(r["id"]):
                rows.append({"kind": "run", "config": p["config"], "rep": p["rep"], "base": p["base"], "n": p["n"], "pr": p["pr"], "event": "pull_request",
                             "run_id": r["id"], "run_conclusion": r["conclusion"], "run_created": r["created_at"], **j})
    # the merge-group runs for each base branch
    seen = set()
    for base in sorted({p["base"] for p in prs}):
        page = 1
        while True:
            runs = gh_api(f"repos/{REPO}/actions/runs?event=merge_group&per_page=100&page={page}")["workflow_runs"]
            if not runs:
                break
            for r in runs:
                hb = r["head_branch"]
                if r["name"] != CHECK or not hb.startswith(f"gh-readonly-queue/{base}/") or r["id"] in seen:
                    continue
                pr_no = int(hb.rsplit("/", 1)[1].split("-")[1])
                if str(pr_no) not in pr_by_number:
                    continue  # an earlier pilot's entry on the same base branch
                seen.add(r["id"])
                p = pr_by_number[str(pr_no)]
                for j in job_rows(r["id"]):
                    rows.append({"kind": "run", "config": p["config"], "rep": p["rep"], "base": base, "n": p["n"], "pr": pr_no, "event": "merge_group",
                                 "run_id": r["id"], "run_conclusion": r["conclusion"], "run_created": r["created_at"], **j})
            page += 1
            if page > 6:
                break
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
