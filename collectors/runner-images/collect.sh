#!/usr/bin/env bash
# Records what a GitHub-hosted `ubuntu-latest` runner looks like today: the
# image name and version, the free space on /, and the version of the tools
# people ask about. One CSV row per read. Run from the repo root on the runner.
set -euo pipefail

dir="collectors/runner-images"
csv="$dir/images.csv"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
run_id="${GITHUB_RUN_ID:-manual}"

# A tool that is missing is recorded as "missing", never as an empty cell that
# could be mistaken for "not read".
ver() { "$@" 2>/dev/null | head -1 | tr -d '\r,' || true; }
or_missing() { if [ -n "$1" ]; then echo "$1"; else echo "missing"; fi; }

image_os="${ImageOS:-}"
image_version="${ImageVersion:-}"
if [ -z "$image_os" ] || [ -z "$image_version" ]; then
  echo "refusing to record: ImageOS or ImageVersion is not set (is this a GitHub-hosted runner?)" >&2
  exit 1
fi

# df -h / is the figure people quote; the byte count is the one you can diff.
df_h_avail="$(df -h / | awk 'NR==2 {print $4}')"
df_h_size="$(df -h / | awk 'NR==2 {print $2}')"
df_avail_bytes="$(df -B1 --output=avail / | tail -1 | tr -d ' ')"

node_v="$(or_missing "$(ver node --version)")"
python_v="$(or_missing "$(ver python3 --version | sed 's/^Python //')")"
go_v="$(or_missing "$(ver go version | awk '{print $3}' | sed 's/^go//')")"
docker_v="$(or_missing "$(ver docker version --format '{{.Client.Version}}')")"
git_v="$(or_missing "$(ver git --version | sed 's/^git version //')")"
os_v="$(. /etc/os-release && echo "$VERSION_ID")"
kernel="$(uname -r)"
cpus="$(nproc)"
mem_kib="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"

if [ ! -f "$csv" ]; then
  echo "read_at_utc,run_id,image_os,image_version,os_version_id,kernel,cpus,mem_kib,root_size,root_avail,root_avail_bytes,node,python,go,docker,git" >"$csv"
fi
echo "$now,$run_id,$image_os,$image_version,$os_v,$kernel,$cpus,$mem_kib,$df_h_size,$df_h_avail,$df_avail_bytes,$node_v,$python_v,$go_v,$docker_v,$git_v" >>"$csv"
tail -1 "$csv"
