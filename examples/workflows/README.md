# CI workflows -- conversion quality in GitHub Actions

Copy-paste workflows for the [`all2md` conversion-quality
gate](https://all2md.readthedocs.io/en/latest/github_action.html). Drop one into
`.github/workflows/` in your own repository and adjust the paths.

```
examples/workflows/
  calibrate-thresholds.yml   Start here -- measure your real floor before gating
  docs-portability.yml       PR gate: your documents changed
  dependency-canary.yml      Scheduled: your dependencies changed
```

## Start with calibration

The threshold is the whole gate, and guessing it is the one mistake that
produces a workflow which passes forever and looks like evidence of quality.
Documents that convert well score 99-100, so a threshold of `80` -- which
*sounds* strict -- has twenty points of dead headroom: conversion can degrade
badly and the build stays green the entire way down.

`calibrate-thresholds.yml` is a manual (`workflow_dispatch`) run that scores your
documents and reports the floor **without gating on anything**. Run it once, read
the number off the job summary, then paste that number into one of the gating
workflows.

Measure on CI, not locally. Scores are deterministic for a given interpreter and
dependency set but not guaranteed across them, so a document can score
differently on your laptop than on a runner from identical bytes.

## Two workflows, opposite pinning strategies

This is the part worth understanding before you copy anything. The two gating
workflows answer different questions and are deliberately pinned in opposite
directions.

| | `docs-portability.yml` | `dependency-canary.yml` |
| --- | --- | --- |
| Trigger | pull request | schedule + dependency PRs |
| `all2md-version` | **pinned exactly** | **`latest`** |
| Turns red when | *your documents* regress | *upstream* regresses |
| Blocks a merge | yes | no |

**The PR gate is pinned** so the only variable is your documents. A pinned action
tag gives a deterministic score, which is what makes a red build actionable:
someone changed a document.

**The canary floats to `latest`** on purpose, and runs on a schedule rather than
on your PRs. This is where the gate earns its keep, because the failure it
catches is otherwise invisible: a parser dependency ships a new version,
extraction quietly degrades on two-column PDFs or nested tables, and nothing
anywhere goes red. Your RAG index gets worse and someone notices in six weeks.

Put differently: **this gate's value peaks when your dependencies change, not
when your documents change.** A canary that fails tells you not to adopt the new
version yet -- and because it never runs on a PR, it can never block a merge on
something that isn't your fault.

Running both is the point. Neither substitutes for the other.

## Which check to use

The two thresholds fail in different directions:

- **`roundtrip-fail-under`** scores what survives a parse -> render -> parse
  cycle. Sharp about structure, but blind to a construct dropped *consistently*:
  if a feature vanishes on the way out and stays vanished on the way back in,
  both sides agree and the score stays high.
- **`report-fail-under`** scores confidence in the parse itself -- scanned pages,
  OCR fallbacks, structural guesses. It catches "this document was never really
  read", which round-tripping cannot see, at the cost of being a heuristic.

Gate on both when the documents matter.

If your documents are **already Markdown**, `roundtrip` is really a *portability*
check: it tells you which constructs survive being processed by tooling. That is
genuinely useful if you publish to several destinations, but it is not a
statement about whether your documentation is good.

## Treat the number as a ratchet

When a document legitimately gets harder to convert, re-run calibration and
re-record the floor deliberately. Do not nudge the threshold down to clear a red
build -- that converts a working instrument into a decoration.

## Without the Action

Every one of these runs the same CLI you can run anywhere, including locally and
on CI systems that aren't GitHub:

```bash
all2md roundtrip docs/*.md --fail-under 97
all2md report inbox/*.pdf --fail-under 80
```

The Action adds a per-document summary table, step outputs, and scoring each
document in its own process so it reports *every* failing file rather than
stopping at the first.

## See also

- [Action documentation](https://all2md.readthedocs.io/en/latest/github_action.html)
- `examples/cli/diff-in-ci.sh` -- semantic cross-format diffing as a CI gate
- `examples/cli/vcs-converter/` -- keeping binary documents git-friendly
