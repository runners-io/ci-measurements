# B1: what five pushes do under each concurrency setting

Run on 2026-11-17 for [RUN-3056](https://www.runners.io/blog/github-actions-concurrency). Everything here ran on
GitHub-hosted `ubuntu-24.04` runners, in this public repository, where standard runners are free.

## What was measured

For each setting, a branch was pushed to five times, back to back (each push is a separate `git push` of a separate
commit), and the push-event runs it started were read back through the REST API. The question is which of the five runs
ran, which were cancelled, in what order, and how many job-minutes that would cost in a private repository.

| scenario | workflow | the setting |
|---|---|---|
| `none` | `B1-concurrency-none.yml` | no `concurrency:` key |
| `default-group` | `B1-concurrency-default-group.yml` | `group: b1-default-group-${{ github.ref }}` and nothing else |
| `cancel` | `B1-concurrency-cancel.yml` | the same group with `cancel-in-progress: true` |
| `queue-max` | `B1-concurrency-queue-max.yml` | the same group with `queue: max` |
| `head-ref` | `B1-concurrency-head-ref.yml` | `group: ${{ github.head_ref \|\| github.run_id }}` with `cancel-in-progress: true` (the fallback GitHub's documentation gives) |
| `matrix-shared` | `B1-concurrency-matrix-shared.yml` | a three-leg matrix, a job-level group that does not name the leg, `cancel-in-progress: true` |
| `matrix-keyed` | `B1-concurrency-matrix-keyed.yml` | the same matrix, a job-level group that names the leg |
| `queue-max-cancel` | `B1-concurrency-queue-max-cancel.yml` | `queue: max` with `cancel-in-progress: true`, which GitHub's documentation says is a validation error |

Every job runs `sleep 40` on `ubuntu-24.04`. The workflows are triggered by pushes to `b1-<scenario>/**` branches and
only those, so no other push in the repository starts them.

## How

- `drive.py push <scenario> 10` clones the repository ten times in parallel, one branch per repetition, makes five
  commits on each, then pushes them one after another. It records the start and end time of every push.
- Ten repetitions of one scenario therefore run at once, on ten different branches. A concurrency group here is keyed on
  `github.ref`, so repetitions never share a group. The pushes of one repetition were about 8 to 9 seconds apart (the
  `pushes_span_seconds_median` column of `results/summary.csv`: the first push to the last, about 43 seconds); doing ten
  repetitions in parallel from one laptop slowed each push. A single repetition run alone took about 19 seconds.
- `drive.py collect <scenario>` waits until no run is queued, pending or in progress, then writes `results/runs-<scenario>.csv`
  with one row per job (or one row for a run with no job): run id, status, conclusion, created, started and updated
  times, each job's start, completion and seconds.
- `summarise.py` labels each push `ok`, `cut` (cancelled while a job was running), `dropped` (cancelled before any job
  started) or `invalid`, and writes `results/summary.csv`.

## How the figures are summarised

- 10 repetitions for `none`, `default-group`, `cancel` and `queue-max`; 5 for `head-ref`, `matrix-shared`, `matrix-keyed` and
  `queue-max-cancel` (the shared REST quota did not allow more). All repetitions of a scenario gave the same pattern, so the
  table prints the pattern, not a median of it. Times are medians with the minimum and maximum beside them.
- **Minutes are computed, not billed.** This repository is public, so nothing was charged. A job's seconds are rounded up
  to a whole minute, which is the rule on GitHub's runner pricing reference ("GitHub rounds the minutes and partial
  minutes each job uses up to the nearest whole minute"). A run cancelled before its job started has no job and so no minutes.
- Times are absolute and include GitHub's queueing. They are not a comparison with anything.

## Limits of this study

- One runner image (`ubuntu-24.04`), one day, a job of 40 seconds. A longer job, or pushes further apart, changes which
  runs are cancelled while they run and which before: the pattern for `cancel` depends on how long a job takes to start
  against how far apart the pushes are. The pattern for `default-group` does not.
- Pushes, not pull requests. Event type does not change how a concurrency group counts, but `github.head_ref` is empty on
  a push, which is the whole of the `head-ref` result.

## Findings that are not in the post's table

- `queue-max-cancel`: GitHub refuses the workflow. Every push produced a completed run with the conclusion `failure`, no job, and
  the workflow file's path in place of its `name`. The same workflow also fails on every push to ANY branch of the repository, not
  only `b1-queue-max-cancel/**`, because a workflow that cannot be read has no trigger filter. It produced about 100 failed runs
  from other studies' pushes before we disabled it (`gh workflow disable`). Rows in `runs-queue-max-cancel.csv` are matched on
  the head SHA of our own pushes, so they count 25 and not 100.
- In `matrix-shared` and `matrix-keyed` one repetition each took about 385 seconds from the first push to the last job finishing,
  against about 100 for the others. We did not investigate.
- Summary of the matrix scenarios: a "cut" job is one that started and was cancelled; the label of a push in the pattern is `cut`
  when any job of it was cut, `ok` when all succeeded. See `results/runs-*.csv` for the job-level rows.
