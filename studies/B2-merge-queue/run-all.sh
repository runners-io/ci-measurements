#!/usr/bin/env bash
# Runs the four merge-queue configurations in turn, five base branches in parallel for each, eight pull requests per branch.
# Needs B2_EMAIL set to the committer address. Each `drive.py run` waits for its queue to drain and writes results/.
set -euo pipefail
cd "$(dirname "$0")"
for cfg in c1 c2 c3 c4; do
  python3 drive.py run "$cfg" 5 8
done
