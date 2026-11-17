# ci-measurements

Measurements of GitHub Actions on GitHub-hosted runners, run in the open so anyone can check them.

Each study has its own directory with:

- the workflow that produced the numbers (under `.github/workflows/`);
- `METHOD.md`: what was measured, on which runner image, how many runs, and how the figures were summarised;
- `results/`: the raw timings as CSV, with the date and run ID of every run.

The numbers are absolute times on GitHub's own runners. They are not a comparison with any other provider.

Published by [runners.io](https://www.runners.io/blog). Corrections are welcome as issues or pull requests.

## Collectors

Two scheduled workflows record data that only exists going forward:

- `collectors/actions-ip-ranges/`: the `actions` ranges from `https://api.github.com/meta`, once a day.
- `collectors/runner-images/`: the image version, tool versions and free disk of `ubuntu-latest`, once a day.

GitHub's schedules can run hours late. Each record carries the time it was actually read.

## Licence

Code: MIT. Data: CC BY 4.0.
