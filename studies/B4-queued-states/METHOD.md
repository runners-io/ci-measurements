# B4: the status word of each wait

Run on 2026-11-17 for the post "GitHub Actions run not starting: queued, pending or waiting?" on runners.io. Everything ran
on GitHub-hosted `ubuntu-24.04` runners in this public repository, where standard runners are free.

## What was measured

When a run is held back, the Actions API gives it a status. We made each kind of wait happen on purpose and read the status
back, so the post can say which word means which wait, instead of repeating what forum threads say.

| kind | how it was made | workflow |
|---|---|---|
| `no-runner` | a job whose `runs-on` is a label that no runner has (`b4-no-such-runner`) | `B4-queued-states.yml`, input `kind=no-runner` |
| `gated` | a job in the environment `b4-gated`, which has one required reviewer | the same, `kind=gated` |
| `limited` | two runs of the same job-level concurrency group, a second apart; the first sleeps 90 seconds | the same, `kind=limited` |
| required check that never ran | a pull request into the branch `b4-required`, which requires a check named `build`, changing a file outside the `paths:` filter of the workflow that produces it | `B4-path-filtered.yml` |

## How

- `observe.py <reps>` dispatches one run per kind per repetition (two, a second apart, for `limited`), reads the run and its
  job through the REST API 15, 45 and 75 seconds after the dispatch, and cancels the runs. It records the run status, the
  job status, the conclusion and the runner name, if one was assigned.
- `observe-required.py <reps>` opens a pull request into `b4-required` that changes a file outside the filter, reads what the
  pull request reports (merge state, checks listed, workflow runs for its branch) at 20 and 90 seconds, and closes it.
  The branch's ruleset is `rulesets-b4-required.json`.

## How the figures are summarised

Every repetition of a kind gave the same status at every read, so the post reports the word and the count ("5 of 5"), not a
median. The reads are at fixed offsets after the dispatch; the first read of the first run of a `limited` pair can still be
starting, which `results/states-*.csv` shows as `queued` before `in_progress`.

## Limits

Five repetitions show what word a wait has. They say nothing about how often a wait happens, or how long it lasts in the wild.
One runner image, one day. The status words are GitHub's and may change; the file records the day they were read.
