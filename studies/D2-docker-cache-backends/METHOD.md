# D2: Docker cache backends on three Dockerfiles

How long a `docker/build-push-action` build takes on a GitHub-hosted runner under each cache backend, for three Dockerfiles
and three cases. Absolute seconds only; nothing here is compared with any other provider.

## The question

A CI job starts on a machine that has never seen the image. Which `cache-from` and `cache-to` make the build fast, for a
build with nothing changed and for the build after a one-line source change?

## The three Dockerfiles (`apps/`)

All use public base images from Docker Hub and public packages.

| image | what it is | base | stages |
|---|---|---|---|
| `node` | an Express app in TypeScript: 668 packages in the lockfile (Next.js, React, Jest, Webpack, Vite and others) | `node:24-bookworm-slim` | three: build (`npm ci`, `tsc`), prod-deps (`npm ci --omit=dev`), runtime |
| `go` | a service that imports gin, grpc, pgx, prometheus and zap, built with `CGO_ENABLED=0` | `golang:1.26-bookworm`, then `debian:bookworm-slim` | two: build (`go mod download`, `go build`), runtime |
| `python` | numpy, pandas, scipy, scikit-learn, matplotlib and pyarrow, pinned | `python:3.13-slim-bookworm` | one |

No Dockerfile uses a BuildKit cache mount, because a cache mount is not exported by any of these backends.

## The seven backends

| label | `cache-from` | `cache-to` |
|---|---|---|
| `none` | none | none |
| `gha-min`, `gha-max` | `type=gha,scope=S` | `type=gha,scope=S,mode=min` or `max` |
| `registry-min`, `registry-max` | `type=registry,ref=ghcr.io/runners-io/ci-measurements:d2cache-...` | the same ref, `mode=min` or `max` |
| `inline` | `type=registry,ref=` the pushed image | `type=inline` |
| `local` | `type=local,src=DIR` | `type=local,dest=DIR-new,mode=max`, and the directory is carried between phases with `actions/cache/save` and `restore` |

`S` and every `ref` and tag contain the workflow run ID, so a repetition never reads an earlier repetition's cache. The
registry is GHCR, written with the repository's `GITHUB_TOKEN` (`packages: write`). Every build pushes its image, because
that is what a job that builds an image does, and `inline` needs the push.

## The three cases (phases)

One job per (image, backend) runs three phases in a row. Before each phase it removes every builder and everything the
builder held, and prunes the Docker daemon, so each phase starts the way a new runner does: only the backend knows what an
earlier phase built. Each phase sets up a new builder with `docker/setup-buildx-action` and builds with
`docker/build-push-action`, using the same `cache-from` and `cache-to` lines in all three.

1. `cold`: nothing is cached anywhere. The build exports its cache.
2. `warm`: the same source. Everything should come from the cache.
3. `change`: one line of source changed (a build number in the main source file, `0` to `1`). The dependency layers should
   still come from the cache, and the new cache is exported.

`change` is what an ordinary push pays: a cache to read, a little to rebuild, a cache to write.

## What is timed

`total_s` is the sum of four timed steps, read with `date +%s.%N`:

- `setup_s`: `docker/setup-buildx-action` (creates the builder; pulls the BuildKit image);
- `restore_s`: for `local` only, `actions/cache/restore`;
- `build_s`: `docker/build-push-action`, which includes the base image pulls, the cache import, the build, the cache export
  and the push;
- `save_s`: for `local` only, rotating the directory and `actions/cache/save`.

Checkout, the registry login and the job's own set-up are not timed. The build summary and the build-record upload are on,
as they are by default.

## Repetitions and summary

One workflow dispatch is one repetition (`rep` in the CSV). Repetitions ran one after another, never together, because the
`gha` backend shares the repository's single Actions cache with every other study and two repetitions would evict each other.
After each repetition the workflow deletes the cache entries BuildKit and `local` wrote.

The summary is the **median** of the repetitions and the **range** (lowest to highest), per image, backend and phase. `none`
has no cache, so its three phases are the same build, and its row pools all of them. There were **6 repetitions** (`rep` 1 to 6), so a cell has 6 values (18 for `none`). `rep` 0 is a smoke run of the
Node image on five backends, kept in `results/runs/44063275157.csv` and left out of every figure. `results/summary.csv`
holds the medians and ranges.

## Cache sizes

`registry-*`: the sum of the layer sizes in the cache manifest after the `cold` phase. `local`: `du -sb` of the directory.
`inline`: not sized, because the cache is inside the image. `gha`: `D2-gha-sizes.yml` builds each Dockerfile once with
`type=gha` in a quiet repository and adds up BuildKit's own cache entries (the keys beginning `index-` and `buildkit-blob-`),
then deletes them. Bytes are as stored (gzip), not as unpacked.

The `gha` sizes were taken once per image and mode (not per repetition) in a quiet repository, so they are single readings. The
first run of that workflow (run 44073547046) lost five of its six rows because each job rebased a stale copy of the CSV; the
numbers it logged matched the second run to within 0.01 MB for Go and Python and 0.002 MB for Node, and the second run
(44076225571, with the step fixed to pull before it appends) is what `results/gha-sizes.csv` holds.

## What this does and does not show

- GitHub-hosted runners vary from job to job, and so does the network to Docker Hub, GHCR and GitHub's cache service. The
  range column is that variation. Do not read a difference smaller than the range as a difference.
- The images are small next to a large monorepo's. A cache is only as good as the work it saves: where an install takes ten
  seconds, a cache that takes ten seconds to read is not worth having, and the data shows that for one Dockerfile.
- The `gha` backend's blobs are keyed by digest, so layers shared between cells (the base images) can already be there; that is
  how the backend behaves in a real repository too.
- The registry here is GHCR on the same network as the runner. A registry elsewhere will not behave the same.

## Files

- `apps/`: the three Dockerfiles and their sources.
- `../../.github/workflows/D2-docker-cache-backends.yml` and `../../.github/actions/d2-phase/action.yml`: the workflow.
- `../../.github/workflows/D2-gha-sizes.yml`: the size of the `gha` cache.
- `results/runs/<run id>.csv`: every timing, one row per phase, with the date, the run ID and the runner image version.
- `results/summary.csv`: the medians and ranges the post prints.
- `results/gha-sizes.csv`: the size of the `gha` cache.
