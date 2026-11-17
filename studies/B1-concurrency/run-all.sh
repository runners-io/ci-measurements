#!/usr/bin/env bash
# Runs the B1 scenarios in turn: push, wait, collect. Needs B1_EMAIL set to the committer address.
#   run-all.sh <reps> [scenario ...]      (default: every scenario)
# After a push, `collect` sleeps B1_WAIT_SECONDS (the longest the scenario takes: 60 for most, 360 for queue-max) before
# it reads anything, so it makes about one REST call a minute while it waits.
set -euo pipefail
cd "$(dirname "$0")"
reps="${1:-10}"
shift || true
scenarios=("$@")
if [ ${#scenarios[@]} -eq 0 ]; then
  scenarios=(none default-group cancel queue-max head-ref matrix-shared matrix-keyed queue-max-cancel)
fi
for scenario in "${scenarios[@]}"; do
  python3 drive.py push "$scenario" "$reps"
  case "$scenario" in queue-max|queue-max-cancel) wait=360 ;; *) wait=90 ;; esac
  B1_WAIT_SECONDS=$wait python3 drive.py collect "$scenario"
done
