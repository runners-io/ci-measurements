#!/usr/bin/env bash
# observe.sh VERSION CASE DIR [COMMIT_OUTPUT REF_OUTPUT]
# Prints one CSV line describing what a checkout left in DIR. The workflow appends it to observations.csv.
# Columns: version,case,action_runtime,git_version,shallow,commits,tags,files,partial_filter,extraheader_in_git_config,
#          includeif_in_git_config,credential_files_in_runner_temp,output_commit_matches_head,output_ref
set -u
version=$1 case=$2 dir=$3 out_commit=${4:-} out_ref=${5:-}
runtime=$(grep -m1 'using:' "/home/runner/work/_actions/actions/checkout/${version}/action.yml" 2>/dev/null | awk '{print $2}')
cd "$dir" || { echo "$version,$case,$runtime,,,,,,,,,,,"; exit 0; }
shallow=$(git rev-parse --is-shallow-repository)
commits=$(git rev-list --count HEAD)
tags=$(git tag | wc -l | tr -d ' ')
files=$(git ls-files | wc -l | tr -d ' ')
work=$(find . -path ./.git -prune -o -type f -print | wc -l | tr -d ' ')
filter=$(git config --get remote.origin.partialclonefilter || true)
extra=$(git config --local --get-regexp '^http\..*\.extraheader$' | wc -l | tr -d ' ')
incl=$(git config --local --get-regexp '^includeif\.' | wc -l | tr -d ' ')
cred=$(ls "${RUNNER_TEMP:-/nonexistent}"/git-credentials-*.config 2>/dev/null | wc -l | tr -d ' ')
head=$(git rev-parse HEAD)
match=""
[ -n "$out_commit" ] && { [ "$out_commit" = "$head" ] && match=yes || match=no; }
echo "$version,$case,$runtime,$(git --version | awk '{print $3}'),$shallow,$commits,$tags,$work,${filter:-none},$extra,$incl,$cred,$match,$out_ref"
