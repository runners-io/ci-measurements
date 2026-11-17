# G1: what a timeout does, and the p95 script

Run 2026-11-17 (run 44065010453) on GitHub-hosted `ubuntu-24.04`, in this public repository. Used by the post
"timeout-minutes in GitHub Actions: the default, job against step, what a timeout does".

## What was run

Nine variants, **five repetitions each** (45 jobs), `fail-fast: false`. Each runs `scripts/victim.sh`, a step that never finishes: it prints a
heartbeat once a second with its own clock, and prints a line when it receives SIGINT or SIGTERM. The variants differ in:

- where the limit is: `timeout-minutes: 1` on the job, or on the step (the job then has 10);
- how the script is launched: as a child of the step's shell (`run: studies/.../victim.sh`) or as the step's own process (`run: exec studies/.../victim.sh`);
- whether it exits on a signal (polite) or ignores SIGINT and SIGTERM (stubborn);
- plus one variant with `continue-on-error: true` on the step.

Five steps follow the victim, each with a different condition: none, `success()`, `failure()`, `cancelled()`, `always()`, and each echoes that it ran.
`scripts/collect.py` reads, for every job, the conclusions from the jobs API, the check-run annotations, and the timestamps in the job log.

## Summary of what it found

See `results/timeout-behaviour.csv`. Five repetitions is enough to show the pattern, not to give a tail. Times are in seconds.

## Not run

Self-hosted runners, Windows, macOS, a job queued behind a concurrency group, `timeout-minutes` above 1, an expression for `timeout-minutes`, a reusable workflow.
One runner image on one day; the runner software can change these timings.

## The p95 script

`timeout-p95.sh OWNER/REPO [RUNS]` needs `gh` (logged in), `jq`, `awk`, makes 1 + RUNS API calls, and prints median, nearest-rank p95 and max for every job in the last RUNS successful runs, plus
`2 x p95`, rounded up to whole minutes and never below 5. `results/p95-example-vitejs-vite.txt` is its output for `vitejs/vite`, 100 runs, 2026-11-17.
