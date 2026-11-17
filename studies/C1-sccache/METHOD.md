# C1: sccache on GitHub Actions, measured on a Rust workspace

**Question.** On one mid-size public Rust workspace, how long does a build take cold and warm with (a) nothing cached, (b) `actions/cache` on `target/`, (c) sccache with its GitHub Actions cache backend, and (d) sccache with a local directory saved and restored by `actions/cache`?

**Workspace.** [helix-editor/helix](https://github.com/helix-editor/helix) at tag 25.07.1, commit `ac94841019910ff405f31a8668389a06a169e0e5`: 14 workspace members, 321 locked packages, MPL-2.0. `rust-toolchain.toml` is deleted after checkout so every arm uses the runner's own Rust (the version is in every row, `rustc`). `HELIX_DISABLE_AUTO_GRAMMAR_BUILD=1`, because `helix-term`'s build script otherwise fetches and compiles 245 tree-sitter grammars from git, which measures the network and not the compiler. `CARGO_INCREMENTAL=0` in every arm (sccache cannot cache incrementally compiled crates).

**Builds.** `cargo build --workspace --locked` (profile `dev`) and `cargo build --workspace --release --locked` (profile `release`; helix's release profile has `lto = "thin"`).

**Where.** This public repository, GitHub-hosted `ubuntu-24.04`, the standard runner for public repositories (4 vCPU, 16 GB RAM, 14 GB SSD). The image version of every job is in its row (`image`). Each cell is its own job on its own fresh runner.

**Arms** (`arm` in the rows):

| arm | what is cached | cold run | warm run |
|---|---|---|---|
| `none` | nothing | build | not run |
| `target-cache` | `src/target`, by `actions/cache/restore` and `actions/cache/save` | restore (miss), build, save | restore (hit), build |
| `sccache-gha` | sccache's GitHub Actions backend (`SCCACHE_GHA_ENABLED=true`), `mozilla-actions/sccache-action@v0.0.11` | build (writes as it goes) | build (reads) |
| `sccache-local` | `~/.cache/sccache`, by `actions/cache/restore` and `actions/cache/save` | restore (miss), build, stop server, save | restore (hit), build |

**Phases.** For each (profile, repetition), all cold cells run first, then all warm cells (`needs`), so a warm run always follows a cold run of the same repetition. Every cache key, and `SCCACHE_GHA_VERSION` (which namespaces sccache's GHA entries), contains the run ID, the profile and the repetition, so no repetition ever reads another's cache and a cold run is truly cold. A warm run is the same commit on a new runner, with the files' modification times new (a fresh checkout), as in a real second run.

**What is timed.** `cargo fetch --locked` is run first in every arm and timed on its own (`fetch_s`), so the crate download is not in any build time. `build_s` is the wall-clock time of the cargo build step, from `date` before and after. `restore_s` and `save_s` are wall-clock seconds around the `actions/cache` restore and save steps, measured with `date` in the neighbouring steps, so they include about a second of step start-up. Checkout, toolchain and runner start-up are not timed. sccache's own statistics (`sccache --show-stats --stats-format json`) are kept per job.

**Repetitions and summary.** 5 repetitions per cell. The post reports the median and the range (min to max) of each figure. No ratio is reported against anything.

**Cleanup.** Each pair deletes its own cache entries when it ends; one last job deletes the `sccache/` entries of the GHA backend (their keys do not carry the run ID, so they are told apart by the cache version only).

**Results.** `results/builds-<run id>.csv`: one row per job, with the date and run ID. `results/sccache-stats-<run id>/` holds sccache's JSON statistics for the sccache arms.

## Runs

- **44069031081** (2026-11-17, `C-all.yml`, stage 5): the first complete run. The ten (profile, repetition) pairs ran three at a time, in the same repository as other studies, so up to three builds shared the repository's cache upload rate. `results/builds-44069031081-pairs-3-at-a-time.csv`. In it, the dev warm restores of the `target-cache` arm missed their entry in 5 of 5 pairs and those of `sccache-local` in 2 of 5, and the GHA backend's cold runs recorded a median of 176 failed cache writes (67 to 182) and a median of 80 warm hits out of 256 (74 to 189).
- **44078371515** (2026-11-17, `C1-sccache.yml` with `max-parallel: 1`): the pairs one at a time. `results/builds-44078371515-one-pair-at-a-time.csv`. All 5 dev repetitions completed. For release, repetitions 1 and 2 completed; at 12:30 UTC GitHub refused to start any further job in this organisation ("The job was not started because your account is locked due to a billing issue"), so release repetitions 3 to 5 did not run. Release figures from this run rest on 2 repetitions and are not the basis of any published claim.

In the one-at-a-time run, one dev repetition (`sccache-local`, repetition 1) found no cache entry on its warm restore (`restore_hit` empty, 0 of 256 hits). This repository's cache is shared with other studies written the same day, so an eviction by another study cannot be ruled out; the cause was not established. The published medians include that repetition.
