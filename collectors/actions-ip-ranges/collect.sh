#!/usr/bin/env bash
# Reads the `actions` ranges from https://api.github.com/meta and records them.
#
# One CSV row per read (the time it was read, not the time the cron was due:
# scheduled runs here arrive hours late), and the full list as a dated file.
# Needs bash, curl, jq, sha256sum (or shasum) and comm. Run from the repo root.
set -euo pipefail

dir="collectors/actions-ip-ranges"
csv="$dir/ranges.csv"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
day="$(date -u +%Y-%m-%d)"
run_id="${GITHUB_RUN_ID:-manual}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Retry: a failed read must fail the run, never write a row.
curl -fsS --retry 5 --retry-delay 5 --retry-all-errors \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  https://api.github.com/meta -o "$tmp/meta.json"

jq -r '.actions[]' "$tmp/meta.json" | LC_ALL=C sort -u >"$tmp/list.txt"
count="$(wc -l <"$tmp/list.txt" | tr -d ' ')"
# Anti-vacuity: an empty or tiny list means the read went wrong, not that
# GitHub has no ranges. Refuse to record it.
if [ "$count" -lt 100 ]; then
  echo "refusing to record: only $count actions ranges read" >&2
  exit 1
fi
v6="$(grep -c ':' "$tmp/list.txt" || true)"
v4=$((count - v6))
if command -v sha256sum >/dev/null 2>&1; then
  hash="$(sha256sum "$tmp/list.txt" | cut -d' ' -f1)"
else
  hash="$(shasum -a 256 "$tmp/list.txt" | cut -d' ' -f1)"
fi

# Previous list = the newest dated file already stored, other than today's.
prev="$(ls "$dir"/lists/*.txt 2>/dev/null | grep -v "/$day.txt$" | sort | tail -1 || true)"
if [ -n "$prev" ]; then
  added="$(LC_ALL=C comm -13 "$prev" "$tmp/list.txt" | wc -l | tr -d ' ')"
  removed="$(LC_ALL=C comm -23 "$prev" "$tmp/list.txt" | wc -l | tr -d ' ')"
else
  added=""
  removed=""
fi

mkdir -p "$dir/lists"
cp "$tmp/list.txt" "$dir/lists/$day.txt"

if [ ! -f "$csv" ]; then
  echo "read_at_utc,run_id,actions_ranges,ipv4_ranges,ipv6_ranges,sha256,added_vs_previous_list,removed_vs_previous_list,list_file" >"$csv"
fi
echo "$now,$run_id,$count,$v4,$v6,$hash,$added,$removed,lists/$day.txt" >>"$csv"
echo "recorded $count ranges at $now (sha256 $hash)"
