#!/usr/bin/env python3
"""Measure one finished checkout and write one CSV row.

usage: measure.py REPO_DIR OUT_CSV

Everything else comes from the environment (set by the workflow): CONFIG, REP, ORDER, REPO, SHA, KIND, T0, T1
(the two clock readings around the checkout step, seconds since the epoch), and GITHUB_RUN_ID, GITHUB_JOB,
ImageVersion, ImageOS. The post-checkout commands are the ones a build commonly runs; each is timed, and the
return code says whether it worked on what the checkout left.
"""
import csv, datetime, os, pathlib, re, subprocess, sys, time

repo_dir, out = pathlib.Path(sys.argv[1]), sys.argv[2]
E = os.environ


def run(cmd, cwd=repo_dir, timeout=180):
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        rc, out_ = p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        rc, out_ = 124, ""
    return rc, out_.strip(), round(time.perf_counter() - t, 3)


def du_kb(path, exclude=None):
    args = ["du", "-sk"] + ([f"--exclude={exclude}"] if exclude else []) + [str(path)]
    return int(subprocess.run(args, capture_output=True, text=True).stdout.split()[0])


row = {
    "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    "run_id": E["GITHUB_RUN_ID"],
    "job": E.get("JOB_NAME", ""),
    "kind": E["KIND"],
    "repo": E["REPO"],
    "sha": E["SHA"],
    "config": E["CONFIG"],
    "rep": E["REP"],
    "order": E["ORDER"],
    "image": f'{E.get("ImageOS", "")} {E.get("ImageVersion", "")}'.strip(),
    "checkout_s": round(float(E["T1"]) - float(E["T0"]), 3),
}

if E["CONFIG"] == "control" or not repo_dir.exists():
    # The control cell skips the checkout: its time is what two clock readings and a step boundary cost alone.
    for k in ("git_kb", "tree_kb", "files", "submodules_declared", "submodules_filled", "commits", "tags", "describe_rc", "describe_s", "diff_rc", "diff_s",
              "blame_rc", "blame_s", "git_version"):
        row[k] = ""
else:
    row["git_kb"] = du_kb(repo_dir / ".git")
    row["tree_kb"] = du_kb(repo_dir, exclude=".git")
    # Files on disk, not in the index: a sparse checkout lists every path in the index and keeps only some of them.
    _, files, _ = run(["bash", "-c", "find . -path ./.git -prune -o -type f -print | wc -l"])
    row["files"] = files
    # Submodules: how many the repository declares and how many the checkout filled in (git marks an empty one with "-").
    _, declared, _ = run(["bash", "-c", "git submodule status | wc -l"])
    _, filled, _ = run(["bash", "-c", "git submodule status | grep -vc '^-' || true"])
    row["submodules_declared"], row["submodules_filled"] = declared, filled
    _, commits, _ = run(["git", "rev-list", "--count", "HEAD"])
    row["commits"] = commits
    _, tags, _ = run(["bash", "-c", "git tag | wc -l"])
    row["tags"] = tags
    # What a build that reads history does next. A shallow clone has no parent and no tags; a partial clone has
    # them but fetches blobs on demand, which is network time the checkout step did not spend.
    row["describe_rc"], _, row["describe_s"] = run(["git", "describe", "--tags", "--abbrev=0"])
    row["diff_rc"], _, row["diff_s"] = run(["git", "diff", "--shortstat", "HEAD~1", "HEAD"])
    _, tracked, _ = run(["bash", "-c", "git ls-files | grep -m1 -i -E '(^|/)readme[^/]*$' || git ls-files | head -1"])
    row["blame_rc"], _, row["blame_s"] = run(["git", "blame", "-L", "1,40", "--", tracked]) if tracked else ("", "", "")
    _, v, _ = run(["git", "--version"])
    row["git_version"] = v.replace("git version ", "")

cols = ["date", "run_id", "job", "kind", "repo", "sha", "config", "rep", "order", "image", "git_version", "checkout_s",
        "git_kb", "tree_kb", "files", "submodules_declared", "submodules_filled", "commits", "tags", "describe_rc", "describe_s", "diff_rc", "diff_s", "blame_rc",
        "blame_s"]
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerow({c: row.get(c, "") for c in cols})
print(",".join(str(row.get(c, "")) for c in cols))
