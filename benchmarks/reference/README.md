# Reference benchmark reports

This directory holds **committed** snapshots of corpus benchmark runs from
meaningful points in the project's history. They serve as long-lived data
points that the documentation can link to — unlike ad-hoc local runs under
`benchmarks/corpus/results/`, which are gitignored and ephemeral.

## What's here

Each snapshot is a pair of files named `<sha>-<label>.{md,json}`:

| File                        | What it captures                                                                |
| --------------------------- | ------------------------------------------------------------------------------- |
| `b0e4224-baseline.md/json`  | Pre-optimization baseline. State of the codebase after the heading-detection rework (`b0e4224`) but **before** the table guards, image alt-text fix, and `find_tables()` gate landed. Captured 2026-05-06 7:21 PM local time. |
| `3516bc9-optimized.md/json` | Post-optimization state, after the v1.1.1 perf work: table guards (`cbd5de7`), alt-text image skip (`10227a6`), and the `find_tables()` pre-flight gate plus benchmark layout-model toggle (`3516bc9`). Captured 2026-05-15 3:35 PM local time. |

The `<sha>` is the commit the code-under-test corresponds to (which may differ
from `run.machine.git_commit` in the JSON when the report captured uncommitted
working-tree changes — see "SHA vs report header" below).

## How to read these

`docs/source/optimizations.rst` references both files when discussing the v1.1.1
perf work and quotes specific numbers from them. The aggregate numbers and the
per-doc tables are the load-bearing data points.

For a more rigorous comparison, diff the two `.json` files at the per-doc level
— they record `duration_seconds` for every document, so you can spot which
specific files moved and by how much.

## Reproducibility caveats

These were captured on a single Windows 11 / Python 3.13 development machine
with normal background load. Wall-clock numbers will not be identical on other
hardware, and even on the same machine they drift by ±20–30% depending on what
else is running. The README inside `benchmarks/corpus/` calls this out as a
general property of the harness.

**Use these as illustrative, not authoritative.** The ratios between the two
runs are far more meaningful than the absolute numbers: any reader running the
harness against the same SHAs on their own hardware should see comparable
*proportions* of speedup even if the wall-clock seconds differ.

To reproduce a clean comparison on a stable runner, dispatch the corpus
benchmark GitHub Action:

```
gh workflow run benchmark.yml          # against current main
gh workflow run benchmark.yml --ref <sha>   # against a specific commit
```

The workflow uploads the same `.md` + `.json` pair as a 90-day artifact.

## SHA vs report header

The `<sha>` in each filename reflects the commit the code under test should be
attributed to. The SHA recorded inside the report header (`run.machine.git_commit`
in the JSON, or the version line in the rendered markdown) is whatever
`git rev-parse HEAD` returned at run time — these can differ when the run was
fired against uncommitted working-tree changes:

- `b0e4224-baseline.{md,json}` — both filename and header agree on `b0e422479436`.
- `3516bc9-optimized.{md,json}` — header reads `3f6fce6d7ebc` (the workflow
  commit); the actual code under test was the find-tables-gate code that
  subsequently landed as `3516bc9`. The filename uses the post-commit SHA so
  the file is correctly attributed when read in isolation.

Future snapshots should be captured *after* the relevant change is committed
to avoid this skew.

## Adding a new snapshot

Take new snapshots at release boundaries or when landing a perf change worth
documenting. To add one:

1. Run the benchmark locally (or via the GHA workflow) against committed code:
   `.venv/Scripts/python.exe -m benchmarks.corpus.run`
2. Copy the resulting `results_<timestamp>.{md,json}` from
   `benchmarks/corpus/results/` into this directory, renaming to `<sha>-<label>.{md,json}`.
3. Update this README's "What's here" table.
4. Reference the new file from `docs/source/optimizations.rst` if it represents
   a doc-worthy data point.
