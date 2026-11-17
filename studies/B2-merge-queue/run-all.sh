#!/usr/bin/env bash
# The configurations of 2026-11-17, in the order they were run (the first, c1, was started by an earlier version of this
# driver and collected afterwards with `drive.py collect c1 <stamp>`). Needs B2_EMAIL set to the committer address.
# The shared REST quota is small, so the driver makes about 20 REST calls a minute and stops below 1,000 left.
set -euo pipefail
cd "$(dirname "$0")"
python3 drive.py run c1 5 8   # build concurrency 1, groups of 1: 5 queues of 8
python3 drive.py run c2 3 6   # build concurrency 5, groups of up to 5: 3 queues of 6
python3 drive.py run c4 3 6   # as c2, the third pull request fails once combined
python3 drive.py run c0 3 1   # a workflow with no merge_group trigger (run 17:10 UTC, after the billing lock; METHOD.md)
python3 drive.py run c5 3 3   # the pull-request run skips the job (run 17:18 UTC, after the billing lock; METHOD.md)
