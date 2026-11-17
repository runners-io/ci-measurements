#!/usr/bin/env python3
"""Writes a directory of FILES files totalling about SIZE_MB megabytes, for the cache-grid study.

Content is pseudo-random words from a fixed 3,000-word vocabulary, so it compresses roughly like source code and
installed packages do (a few to one), not like random bytes (1 to 1) and not like zeros (1000 to 1). The seed is fixed,
so every run of a cell writes the same bytes.

Usage: make-tree.py DIR SIZE_MB FILES
"""
import os
import random
import sys

root, size_mb, files = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rnd = random.Random(20261117)
vocab = ["".join(rnd.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rnd.randint(2, 11))) for _ in range(3000)]
# One 4 MB pool of text; each file takes a slice from a different offset.
pool = (" ".join(rnd.choice(vocab) for _ in range(700_000))).encode()
total = size_mb * 1024 * 1024
per_file, extra = divmod(total, files)
per_dir = 200
made = 0
for i in range(files):
    d = os.path.join(root, f"d{i // per_dir:05d}")
    if i % per_dir == 0:
        os.makedirs(d, exist_ok=True)
    n = per_file + (1 if i < extra else 0)
    off = rnd.randrange(0, max(1, len(pool) - n)) if n < len(pool) else 0
    chunk = pool[off:off + n] if n <= len(pool) else (pool * (n // len(pool) + 1))[:n]
    with open(os.path.join(d, f"f{i:06d}.txt"), "wb") as fh:
        fh.write(chunk)
    made += len(chunk)
print(f"wrote {files} files, {made / 1024 / 1024:.1f} MB under {root}")
