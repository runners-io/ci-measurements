#!/usr/bin/env bash
# A step that never finishes, and says what happens to it.
#   victim.sh polite     exits when it is signalled
#   victim.sh stubborn   ignores SIGINT and SIGTERM, so only SIGKILL stops it
# Every line carries the seconds since the script started, and a heartbeat prints once a second, so the last
# heartbeat in the log is the last second the process was alive.
mode=${1:-polite}
start=$(date +%s.%N)
stamp() { printf '%s +%.1fs\n' "$1" "$(echo "$(date +%s.%N) - $start" | bc)"; }
if [ "$mode" = polite ]; then
  trap 'stamp "got SIGINT, exiting"; exit 130' INT
  trap 'stamp "got SIGTERM, exiting"; exit 143' TERM
else
  trap 'stamp "got SIGINT, ignoring"' INT
  trap 'stamp "got SIGTERM, ignoring"' TERM
fi
stamp "started ($mode)"
i=0
while true; do
  sleep 1 &
  wait $!
  i=$((i + 1))
  stamp "heartbeat $i"
done
