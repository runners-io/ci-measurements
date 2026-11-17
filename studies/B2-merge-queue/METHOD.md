# B2: what a merge queue runs and what it costs in Actions minutes

Run on 2026-11-17 for the post "GitHub merge queue: how to set it up, what merge_group runs, and what it adds to your Actions
bill" on runners.io. Everything ran on GitHub-hosted `ubuntu-24.04` runners in this public repository (owned by an
organisation, which is what GitHub's documentation requires for a merge queue on a public repository). Standard runners are free
in public repositories, so nothing was charged; the minutes below are computed.

## What was measured

Pull requests were put into a merge queue and the queue's runs were counted. The one workflow, `B2-merge-queue-check.yml`, has a
single job `check` that works for 30 seconds. It triggers on `pull_request` into `b2-mq-*` branches and on `merge_group`.
A file whose name contains `fail`, in `studies/B2-merge-queue/prs/`, makes the merge-group run fail and the pull-request run pass:
"green alone, red once combined".

Every configuration has its own set of base branches (`b2-mq-<config>-r<rep>`), each with a branch ruleset that requires the
`check` job and a merge queue (`rulesets/<config>.json`). One repetition is one base branch.

| config | build concurrency | merge group min / max | other |
|---|---|---|---|
| `c1` | 1 | 1 / 1 | 5 queues of 8 pull requests (40) |
| `c2` | 5 | 1 / 5 | 3 queues of 6 (18) |
| `c4` | 5 | 1 / 5 | 3 queues of 6 (18); the third pull request carries the failing file |
| `c5` | 5 | 1 / 5 | 3 queues of 3 (9); the pull-request run skips the job (`if: github.event_name == 'merge_group'`); only the merge group does the work |
| `c0` | 5 | 1 / 5 | 3 queues of 1 (3); the workflow on that branch has no `merge_group` trigger; check timeout 5 minutes |

## How

`drive.py run <config> <reps> <prs>` opens the pull requests on each base branch (each changes one file of its own, so none
conflicts), waits until every pull request's own check has passed, then queues them in order with the `enqueuePullRequest`
GraphQL mutation, back to back. `drive.py collect` waits until every pull request has merged or been removed, then reads the
queue events (GraphQL timeline) and the runs and jobs (REST), and writes `results/queue-<config>-<stamp>.csv`: one row per
pull request and one per run, with the job's start and finish and the minutes rounded up per job, which is GitHub's
rounding rule.

## How the figures are summarised

Counts of runs are exact. Times are medians with the range. Minutes are the job seconds rounded up to a whole minute, per job.

## Limits

A 30-second check, five or fewer base branches per configuration, one day, one image. The number of runs does not depend on the
length of the check; the minutes do. Pull requests were created by a script and never touched the same file, so none conflicted.
We did not run the queue's "jump to the top" option.

The study was cut to these sizes after the first version of the driver used too much of the account's shared API quota; a
third configuration with a minimum group size of 5 (`c3`) was dropped and not run.
