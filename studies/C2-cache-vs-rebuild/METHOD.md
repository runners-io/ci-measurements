# C2: when does a cache cost more than it saves?

Two parts, both on GitHub-hosted `ubuntu-24.04`, the standard runner for public repositories (4 vCPU, 16 GB RAM, 14 GB SSD), in this public repository. The image version of every job is in its row.

## Part A: the cost of saving and restoring a directory (`C2-grid.yml`)

**Question.** How many seconds do `actions/cache/save` and `actions/cache/restore` take for a directory of a given size and file count?

**Cells.** Total size in MB x number of files: 50 x {100; 10,000; 100,000}, 500 x {100; 10,000; 100,000; 500,000}, 2,000 x {100; 100,000}. Each cell is a job; 5 repetitions per cell.

**The tree.** `make-tree.py` writes the files under `~/tree`: pseudo-random words from a fixed 3,000-word vocabulary with a fixed seed, so the content compresses a few to one, as source code and installed packages do, and is the same bytes every time. 200 files a directory.

**Steps.** make the tree (not timed); `sync`; save (timed); read the size of the stored entry with `gh cache list`; delete the tree, `sync` and drop the page cache (`echo 3 > /proc/sys/vm/drop_caches`); restore (timed, `fail-on-cache-miss: true`); check that every file came back; delete the entry. The save and the restore run in the same job, on the same runner, with the page cache emptied between them; the entry travels through the cache service as it would to another runner.

**Timing.** `save_s` and `restore_s` are the wall-clock seconds around the step, measured with `date` in the neighbouring steps, so they include about a second of step start-up, which is what a workflow's step shows too.

## Part B: real projects (`C2-installs.yml`)

**Question.** For a real dependency set, how long does each of three things take: a fresh install with nothing cached; saving and restoring the package manager's own cache directory and installing from it; saving and restoring the installed tree and using it as it is?

**Projects.** The C3 fixtures `npm`, `pnpm`, `pip`, `cargo`, `go` (small real projects with real lockfiles) and `npm-large`, a 760-package front-end dependency set (`fixtures/npm-large/`, committed lockfile). The "install" of `cargo` is `cargo build --locked` (it compiles), of `go` is `go build ./...`.

**Steps, in one job on one runner, for each project and repetition (5 repetitions).** fresh install, timed (`fresh_s`); measure the cache directory and the installed tree (MB and files); save the cache directory (`save_dir_s`); save the installed tree (`save_tree_s`); wipe everything and drop the page cache; restore the cache directory (`restore_dir_s`), install from it (`install_from_dir_s`); wipe and drop again; restore the installed tree (`restore_tree_s`) and run a check that uses it (`verify_s`: a `require` of the main packages, an import, or a build that finds nothing to do). Entries are deleted at the end.

**Summary.** Median and range of 5 repetitions. The post derives, from the medians, the hit rate above which caching wins: `h = (save + 0.4) / (gain + save + 0.4)`, where `gain = fresh - restore - what is left to do`.

**Results.** `results/grid-<run id>.csv` and `results/installs-<run id>.csv`, one row per job, with the date and run ID.

**Runs.** `C-all.yml` run 44069031081 (2026-11-17), stages 2 and 3: `results/grid-44069031081.csv` (45 jobs) and `results/installs-44069031081.csv` (30 jobs). `C2-snippet.yml` (run 44079310177) runs the timing snippet printed in the post, as printed. The post's break-even hit rate is `(save + 0.4) / (gain + save + 0.4)` with `gain = fresh - restore - what is left to do`, from the medians in the installs file; 0.4 s is the time of a restore that finds nothing, which the C3 runs measured at 0.25 to 0.51 s.
