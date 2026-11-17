#!/usr/bin/env python3
"""Print the test files (or pytest-split arguments) for one shard.

usage: split.py STRATEGY SHARDS INDEX TESTS_DIR DURATIONS_JSON

STRATEGY
  count   consecutive chunks of equal file count, files in path order
  greedy  largest recorded file time first, each file onto the least-loaded shard
"""
import json, math, pathlib, sys

strategy, shards, index = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
root, durations_path = pathlib.Path(sys.argv[4]), sys.argv[5]

files = sorted(p.relative_to(root).as_posix() for p in root.rglob("test_*.py"))
per_test = json.load(open(durations_path))  # pytest-split format: "path::test" -> seconds
seen = {}
for test_id, seconds in per_test.items():
    f = test_id.split("::")[0]
    seen[f] = seen.get(f, 0.0) + seconds
mean = sum(seen.values()) / max(len(seen), 1)
weight = {f: seen.get(f, mean) for f in files}  # a file with no record counts as the mean

if strategy == "count":
    size = math.ceil(len(files) / shards)
    mine = files[index * size : (index + 1) * size]
elif strategy == "greedy":
    load = [0.0] * shards
    buckets = [[] for _ in range(shards)]
    for f in sorted(files, key=lambda f: (-weight[f], f)):
        k = min(range(shards), key=lambda k: (load[k], k))
        buckets[k].append(f)
        load[k] += weight[f]
    mine = sorted(buckets[index])
else:
    sys.exit(f"unknown strategy {strategy}")

print("\n".join(mine))
