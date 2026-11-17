# D1: docker/build-push-action and setup-buildx-action, tested

This directory holds the workflows behind the post "docker/build-push-action and setup-buildx-action: inputs, cache types,
versions" on runners.io. It is a test that the YAML works, not a timing study, so there are no timings here.

## What was tested

Nine workflows, each run once by hand (`workflow_dispatch`) on `ubuntu-24.04` GitHub-hosted runners on 2026-11-17, in this
public repository:

| workflow | what it proves |
|---|---|
| `D1-cache-minimal` | `docker/login-action` to GHCR with the `GITHUB_TOKEN`, `setup-buildx-action`, then `build-push-action` with `push: true`; the pushed image runs |
| `D1-cache-gha`, `-registry`, `-inline`, `-local` | the four cache types that work on a hosted runner's own builder |
| `D1-cache-s3`, `-azblob` | `type=s3` against Adobe S3Mock and `type=azblob` against Azurite, both started in the job |
| `D1-cache-multiplatform` | `platforms: linux/amd64,linux/arm64` with `setup-qemu-action`; the pushed tag lists both |
| `D1-cache-multiplatformbare` | the same without `setup-qemu-action` |

The file names say `cache` for the first batch; the minimal and two-platform workflows share the prefix.

## How a cache type is proved

`Dockerfile` here has one `RUN date +%s%N > /stamp`. Each cache workflow builds it twice in one job:

1. build with the printed `cache-from` and `cache-to`, push, and read `/stamp` from the pushed image;
2. remove the builder and everything it held (`docker buildx rm`, `docker system prune --all`), as a new runner would;
3. set up a new builder, build again with the same lines, push, read `/stamp` again.

The two stamps are equal only if the second build took the `RUN` layer from the cache. A miss runs `date` again and prints a
new number, so a cache that does nothing fails the job. For `gha`, `registry` and `inline` the job first fails if the
cache already exists, so a pass cannot come from an earlier run.

## What the post prints and what ran

`generate.py` writes both the workflows and `snippets/*.yml` from one table. The snippets are the workflows as the post
prints them: actions by tag (`@v7`), `on: push`, `tags: ...:latest`. The workflows in `.github/workflows/` differ in
three ways only: each action is pinned to a commit; the trigger is `workflow_dispatch`; and the tag is `...:d1-<name>` so
that nine runs at once do not push to one tag. The post also writes `context: .` where the workflow builds this folder.
The proof steps (the second build and the comparison) are added around the printed steps.

The `s3` and `azblob` tests ran against test servers on `127.0.0.1`, with the servers' own test credentials in the job's
`env`. We have not run either type against AWS S3 or Azure Blob Storage.

## Versions

`docker/setup-buildx-action` v4.4.1, `docker/build-push-action` v7.4.0, `docker/login-action` v4.8.0 (the `v4` tag),
`docker/setup-qemu-action` v4.4.0, `actions/checkout` v7.0.1, `actions/cache` v6.1.0. Runner image `ubuntu-24.04`, version
recorded in each run's log under "Set up job".

## Results

`results/runs.csv`: one row per workflow, with the run ID, the date and the conclusion.
