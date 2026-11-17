# F1: the GitHub Actions matrix, every pattern run

Read by the post "GitHub Actions matrix strategy" on runners.io (slug `github-actions-matrix-strategy`).

## What was measured

Whether GitHub starts the jobs a matrix's YAML says it should, and what it does at the edges its documentation leaves open. One
workflow per pattern, `.github/workflows/F1-*.yml`, each `workflow_dispatch`, each run on 2026-11-17.

| workflow | question | result |
|---|---|---|
| F1-01 | OS by version | 6 jobs, named `job (os, version)` |
| F1-02 | `include` that fits, and one that does not | 5 jobs; the fifth is named with every value |
| F1-03 | `include` with no axes | 3 jobs |
| F1-04 | `exclude` | 3 jobs |
| F1-05 | partial `exclude`, then `include` | 3 jobs; `include` is processed after `exclude` |
| F1-06 | matrix from changed paths, `fromJSON` | 2 jobs; `[]` skipped by an `if` |
| F1-06b | the same with an empty array and no `if` | workflow refused: "Matrix vector 'dir' does not contain any values" |
| F1-07 | `max-parallel: 2`, `fail-fast` true and false | true cancels the rest; false runs all, two at a time |
| F1-08 | outputs from matrix jobs | one output per leg; a shared name keeps one leg's value |
| F1-09 | matrix calling a reusable workflow | 3 jobs named `call (v) / test` |
| F1-10 | `background`, `wait`, `parallel` steps | background steps overlap; outputs read after `wait` |
| F1-11 | 256 and 257 legs | 256 ran; 257 refused: "produced 257 configurations which exceeds the maximum of 256" |
| F1-12 | unquoted `3.10` | job named `3.1` |
| F1-13 | how `include` compares values | `"22"` fits `22`; case is ignored; `"true"` does not fit `true` |
| F1-14 | two matrices of 130 legs in one run | all 260 ran: the limit is per matrix in practice |

F1-13 is observed behaviour that GitHub's documentation does not state, on one day.

## How

- Image: `ubuntu-24.04`, except the legs of F1-01 to F1-05 that name `ubuntu-22.04` or `windows-2025`.
- Actions are pinned by commit: checkout v7.0.1, 3d3c42e5aac5ba805825da76410c181273ba90b1.
- These are behaviour checks, not timings. F1-07 and F1-10 read start and finish times from the jobs API, to the second, and say so.
- Two dispatches were rejected by GitHub with HTTP 422 before they ran: F1-08 (an output name built from `matrix.version`, "Unrecognized named-value: 'matrix'") and F1-10 (a `parallel` group written without `background`, first attempt, which GitHub rejected as "Unexpected value 'parallel'"). Both were fixed and re-run; the failing first runs of F1-08 and F1-10 are in the run history and are not in the CSV.
- A first dispatch of F1-06b was rejected as not found on the default branch; it was re-dispatched after the push.

## Summary

`results/jobs-started.csv`: every job GitHub started, one row per job, with workflow, run id, job name as GitHub printed it,
conclusion and UTC start and completion. `collect.py` regenerates it from the jobs API.
The same job names are the test fixtures of the expander on runners.io (`lib/matrix-expander/expand.test.ts`).

## Read from the run pages and the jobs API, not in the CSV

Error text GitHub printed (read from the run page on 2026-11-17):

- Run 44064193197 (F1-06b): "Error when evaluating 'strategy' for job 'test'." and "Matrix vector 'dir' does not contain any values". Only the `plan` job ran.
- Run 44064615210 (F1-11, 257 legs): "Strategy for job 'leg' produced 257 configurations which exceeds the maximum of 256 configurations". The `plan` job ran and succeeded; no `leg` job started.

Step times of run 44063610716 (F1-10), from the jobs API, UTC:

| step | start | end |
|---|---|---|
| two sleeps of 10 s in a row | 10:20:41 | 10:21:03 |
| background a, background b, wait for both | 10:21:03 | 10:21:13 |
| `parallel` group of p1 and p2 (10 s each) | 10:21:13 | 10:21:23 |

Output of the `report` job of run 44063605573 (F1-08), from the job log: `{"shared": "leg-2", "output_1": "built-1", "output_3": "built-3", "output_2": "built-2"}`; the `shared` output was written by all three legs and one value came back.

F1-06's workflow comment was reworded after the runs ("fails when the matrix is evaluated"); no line of YAML changed.
