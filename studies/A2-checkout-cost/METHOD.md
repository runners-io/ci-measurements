# A2: what a checkout costs

Measured 2026-11-17 on GitHub-hosted runners, in this public repository, so it cost nothing to run.

## What was measured

The wall-clock seconds of one `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1) step, read from two
`date +%s.%N` calls on either side of it, in the same job. Only the checkout step is timed: the harness checkout, the
`measure` step and the artifact upload are outside the two readings.

- Runner: `runs-on: ubuntu-24.04`, image `ubuntu24 20261111.x` (the exact image is in each row's `image` column), git 2.56.1.
- `persist-credentials: false` in every cell. Every cell checks out one commit, pinned by the plan job at the start of the run, so a
  push during the run cannot change the work.
- One cell is one job: a fresh machine, so nothing is cached from the cell before.
- **Control cell:** the checkout step is skipped; it measures what two clock readings and a step boundary cost (0.01 to 0.03 s).

## Cells

`kind=history` (workflow input), one workflow run per repository (the list is in `scripts/plan.py`):

| cell | inputs |
|---|---|
| default | `fetch-depth: 1` (the action's default) |
| depth0 | `fetch-depth: 0` |
| depth0-blobnone | `fetch-depth: 0`, `filter: blob:none` |
| depth0-tree0 | `fetch-depth: 0`, `filter: tree:0` |
| sparse | `sparse-checkout:` the first top-level directory whose name does not start with a dot, in path order (cone mode) |
| control | the checkout step is skipped |

`kind=submodules`: `no-submodules` (default), `submodules: true`, `submodules: recursive`, and the control.

Repetitions: **10 per cell**, in a random order (seeded with the run ID, so the order is reproducible from the run) and at most 20 jobs at
once. With 10 runs, **p95 is the slowest run**: read it as "the worst we saw", not as an estimate of the tail.

## Repositories, and why these

History study, chosen by a rule and not by hand. For each of Python, Go and TypeScript: the 30 most-starred public repositories
from GitHub's search API (`language:X stars:>1000 sort:stars`), kept if the licence field is not empty or `NOASSERTION`, not archived, and pushed in
the last 90 days; sorted by the `size` the API reports; the **median** and the **90th-percentile** repository are taken.

| repository | language | role | `size` (MB, API) | licence | sparse directory | commit |
|---|---|---|---|---|---|---|
| Graphify-Labs/graphify | Python | median | 36 MB | Apache-2.0 | `docs` | 480b61ed91cb |
| langchain-ai/langchain | Python | p90 | 623 MB | MIT | `libs` | 92c7defb0ac5 |
| syncthing/syncthing | Go | median | 125 MB | MPL-2.0 | `assets` | b0df1033fe2a |
| golang/go | Go | p90 | 460 MB | BSD-3-Clause | `api` | 37939dec89a7 |
| immich-app/immich | TypeScript | median | 319 MB | AGPL-3.0 | `deployment` | 8a11e96e28b6 |
| stablyai/orca | TypeScript | p90 | 2,937 MB | MIT | `Casks` | 9fe58fd7729c |

The sparse directory is a rule and not a good choice: the first by name is often small (`api`, `docs`) and in `langchain` it is `libs`, which holds most of
the repository, so its sparse cell is a bad case on purpose. A real job picks the directory it builds.

Submodule study, chosen because they declare submodules (counted from `.gitmodules` through the API): `grpc/grpc` (20 declared, Apache-2.0) and
`pytorch/pytorch` (34 declared; GitHub's licence field says `NOASSERTION`).

## What each row records

`checkout_s`; the size of `.git` and of the working tree in KB (`du -sk`, on disk, not bytes transferred); files on disk; commits and tags in the
clone; and, run after the checkout and each stopped at 60 seconds (return code 124): `git describe --tags --abbrev=0`, `git diff --shortstat HEAD~1 HEAD`
and `git blame -L 1,40` of the first README-like file. Their return codes say what the checkout left usable: `128` is git's "fatal".
The time of the post-checkout commands is **not** in `checkout_s`: a partial clone fetches blobs on demand, and that time shows up there.

## Not measured

A runner-side cache, a cold or warm network path, Windows or macOS, LFS, a repository behind a proxy, or a second run's effect: every cell is a fresh machine's first fetch. GitHub's
network speed varies by the hour; one day and one image only. A first smoke run (`44063524997`, 1 repetition, a different cell list) is not in the results.

## Files

- `results/history.csv`, `results/submodules.csv`: every row, with `date` and `run_id`.
- Workflow `.github/workflows/A2-checkout-cost.yml`; `scripts/plan.py`, `scripts/measure.py`, `scripts/collect.py`.
- Runs: history 44065090637 (graphify), 44065101805 (langchain), 44065114221 (syncthing), 44065125637 (golang/go), 44065137607 (immich), 44065148856 (orca);
  submodules 44065159780 (grpc), 44065170247 (pytorch).
