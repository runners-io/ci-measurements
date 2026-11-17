# F2: splitting a test suite across jobs, measured

Read by the post "Splitting tests across GitHub Actions jobs by timing" on runners.io (slug `split-tests-github-actions`).

## What was measured

One real test suite, split three ways at 2, 4, 8 and 16 shards, against the same suite run as one job. For each: the wall time
(the slowest job), the **billed minutes** (each job's seconds rounded up to a whole minute, summed, which is how GitHub
bills), and how unevenly the work fell.

## The suite

[networkx](https://github.com/networkx/networkx) at tag `networkx-3.7`, commit `49ca2290b80c1389eb4d8d8e49dcba73f8fec016`:
263 test files, 10,117 recorded test items (9,320 passed, 60 skipped, 741 xfailed in a run), Python 3.13, installed with
`pip install -e '.[default,test]' pytest-split`. It runs with plain `pytest networkx` (no `-n`, so one process).

## The three ways

| strategy | how it splits |
|---|---|
| `count` | the files in path order, in consecutive chunks of equal file count |
| `greedy` | `scripts/split.py`: files sorted by recorded time, largest first, each onto the least-loaded shard |
| `pytest-split` | `pytest-split --splitting-algorithm least_duration`, from the same recorded timings |

The recorded timings are `durations.json`: per-test seconds from rep 1 of the baseline (run 44062456029), in pytest-split's
format. They were recorded once and not refreshed, so `greedy` and `pytest-split` split with timings from a different run than
the one they are measured in, as a real repository does.

## How many runs

- Baseline (whole suite, one job): 10 runs, one dispatch, `mode: baseline`.
- Split: 5 dispatches of `mode: split`, each running all 12 configurations (3 strategies x 4 shard counts): 5 runs of each
  configuration, 450 jobs. Runs 44063095287, 44063110146, 44063125845, 44063140793, 44063154505.
- Medians and ranges are over those runs. Wall time of a configuration in one run is its slowest job.

## What is in a job's time

Every job is on `ubuntu-24.04` (image version 20261111.127.1, read from the baseline run's job log; GitHub rolls images, so the split runs may have started on a newer one) and does: checkout of this repository, checkout of networkx at the pinned commit, setup-python,
`pip install`, select tests, run pytest. `job_seconds` is the jobs API's start to completion for the whole job; `pytest_s` is
the pytest step; `pytest_reported_s` is the figure pytest printed. "Fixed" in the post is `job_seconds - pytest_s`.

## Files

- `results/baseline.csv`, `results/split.csv`: one row per job with date, run id, strategy, shards, shard, rep, files, step
  seconds, billed minutes (`ceil(job_seconds / 60)`) and pytest's pass counts.
- Every configuration ran all 9,320 passing tests in total, with 0 failures (checked in `collect.py`'s `passed` and `failed` columns).
- `scripts/collect.py` rebuilds the CSVs from the jobs API and the run artifacts; `scripts/split.py` is the greedy splitter.
- `.github/workflows/F2-test-splitting.yml` is the workflow; `F2-collection-cost.yml` times pytest's collection alone (run 44069739581, 5 reps, `results/collection.csv`: whole suite median 9.9 s, 9.3 to 10.1; the one file `test_common.py` alone 0.65 s); `F2-recipe.yml` is the workflow the post prints.

## Limits

- One suite. A suite with a slower install, or slower tests, moves where the cost knee falls; the calculator in the post takes
  those as inputs.
- The 5 split runs are 5 samples. Ranges are in the CSV and in the post.
- Runner start time is inside `job_seconds`; queueing before a job starts is not.
