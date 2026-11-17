#!/usr/bin/env bash
# Runs every B1 scenario in turn: push, wait, collect. Needs B1_EMAIL set to the committer address.
set -euo pipefail
cd "$(dirname "$0")"
reps="${1:-10}"
for scenario in none default-group cancel queue-max head-ref matrix-shared matrix-keyed queue-max-cancel; do
  python3 drive.py push "$scenario" "$reps"
  python3 drive.py collect "$scenario"
done
