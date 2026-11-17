#!/usr/bin/env python3
"""Plan one A2 run: the pinned commit, the sparse directory, and the shuffled matrix.

usage: plan.py KIND REPO REPS     (KIND is history or submodules)

Reads GITHUB_RUN_ID (the shuffle seed, so the order is reproducible from the run) and GH_TOKEN. Writes
`matrix=` and `sha=` lines for $GITHUB_OUTPUT on stdout, and a human line on stderr.
"""
import json, os, random, subprocess, sys

kind, repo, reps = sys.argv[1], sys.argv[2], int(sys.argv[3])


def gh(*args):
    return subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True).stdout.strip()


# One commit for every cell, so a push to the repository during the run cannot change what is checked out.
sha = gh(f"repos/{repo}/commits/HEAD", "-q", ".sha")

# The sparse directory is a rule, not a choice: the first top-level directory in path order whose name does not
# begin with a dot. The cone-mode checkout then holds that directory plus the files in the repository root.
tree = json.loads(gh(f"repos/{repo}/git/trees/{sha}"))["tree"]
dirs = sorted(e["path"] for e in tree if e["type"] == "tree" and not e["path"].startswith("."))
sparse = dirs[0] if dirs else ""

if kind == "history":
    configs = [
        # name, fetch-depth, filter, sparse-checkout, submodules
        ("control", "1", "", "", "false"),  # the checkout step is skipped: what the two clock readings cost alone
        ("default", "1", "", "", "false"),
        ("depth2", "2", "", "", "false"),
        ("depth0", "0", "", "", "false"),
        ("depth0-blobnone", "0", "blob:none", "", "false"),
        ("depth0-tree0", "0", "tree:0", "", "false"),
        ("sparse", "1", "", sparse, "false"),
    ]
else:
    configs = [
        ("control", "1", "", "", "false"),
        ("no-submodules", "1", "", "", "false"),
        ("submodules-true", "1", "", "", "true"),
        ("submodules-recursive", "1", "", "", "recursive"),
    ]

include = [
    {"config": c, "depth": d, "filter": f, "sparse": s, "submodules": m, "rep": rep}
    for rep in range(1, reps + 1)
    for (c, d, f, s, m) in configs
]
random.Random(int(os.environ["GITHUB_RUN_ID"])).shuffle(include)
for i, cell in enumerate(include, 1):
    cell["order"] = i

print("matrix=" + json.dumps({"include": include}, separators=(",", ":")))
print(f"sha={sha}")
print(f"sparse={sparse}")
print(f"{repo} {sha} sparse={sparse!r} cells={len(include)}", file=sys.stderr)
