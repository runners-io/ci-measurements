#!/usr/bin/env bash
# timeout-p95.sh OWNER/REPO [RUNS]
#
# For every job in the last RUNS successful workflow runs of a repository (default 100), print how many runs it
# has, its median, its 95th percentile (nearest rank) and its longest duration, and a suggested timeout-minutes:
# twice the p95, rounded up to whole minutes, and never under 5.
#
# Needs: gh (logged in), jq, awk. It reads the jobs API only, so it works on a private repository you can read.
# It makes one API call for the run list and one for each run, so RUNS=100 is 101 calls of the 5,000 an hour a
# user token gets. A job's duration is completed_at minus started_at: the time it ran, not the time it queued.
set -euo pipefail

repo=${1:?usage: timeout-p95.sh OWNER/REPO [RUNS]}
runs=${2:-100}

durations=$(mktemp)
trap 'rm -f "$durations"' EXIT

run_list=$(gh run list -R "$repo" --status success --limit "$runs" --json databaseId,workflowName \
  --jq '.[] | [.databaseId, .workflowName] | @tsv')

while IFS=$'\t' read -r id workflow; do
  jobs=$(gh api "repos/$repo/actions/runs/$id/jobs?per_page=100") || {
    echo "timeout-p95: could not read the jobs of run $id; stopping, so a partial table is not mistaken for a full one" >&2
    exit 1
  }
  printf '%s\n' "$jobs" | jq -r --arg wf "$workflow" '.jobs[]
    | select(.conclusion == "success" and .started_at != null and .completed_at != null)
    | [$wf, .name, ((.completed_at | fromdate) - (.started_at | fromdate))] | @tsv' >> "$durations"
done <<< "$run_list"

sort -t$'\t' -k1,1 -k2,2 -k3,3n "$durations" |
  awk -F'\t' '
    function flush(   rank, p95, med, sug) {
      if (n == 0) return
      rank = int(0.95 * n); if (rank < 0.95 * n) rank++      # nearest rank: ceil(0.95 * n)
      p95 = d[rank]; med = (n % 2) ? d[(n + 1) / 2] : (d[n / 2] + d[n / 2 + 1]) / 2
      sug = int((2 * p95 + 59) / 60); if (sug < 5) sug = 5
      printf "%-28.28s %-40.40s %4d %7.1f %7.1f %7.1f %6d%s\n", wf, name, n, med / 60, p95 / 60, d[n] / 60, sug, (n < 20 ? "  (under 20 runs: treat the p95 as a guess)" : "")
    }
    BEGIN { printf "%-28s %-40s %4s %7s %7s %7s %6s\n", "workflow", "job", "runs", "median", "p95", "max", "timeout"; printf "%-28s %-40s %4s %7s %7s %7s %6s\n", "", "", "", "(min)", "(min)", "(min)", "(min)" }
    { if ($1 != wf || $2 != name) { flush(); wf = $1; name = $2; n = 0 } d[++n] = $3 }
    END { flush() }'
