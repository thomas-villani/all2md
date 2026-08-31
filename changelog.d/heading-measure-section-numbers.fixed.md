- **benchmarks/comparison: the heading measure no longer scores a printed section number as
  a miss.** JATS keeps a section number in a `<label>` sibling of `<title>`, and the
  projection reads only the title, so the ground truth said `Discussion` where the page said
  `4 Discussion` — and every converter that printed what the page prints was charged with
  losing the heading. `headings.py` now strips a leading run of number tokens from both the
  truth and the emitted heading, which is symmetric: a heading that genuinely opens with a
  number loses it on both sides and still matches.

  It was not a rounding correction. On the development corpus numbered headings are 8.4% of
  all section headings, and of the 99 all2md was charged with losing, **97 had been emitted
  correctly, number and all** — a recovery rate of 2.0% that is really 97.0%. Both baselines
  emit numbered headings at a similar rate (13.1% and 13.5% of their emitted headings), so
  the sealed-holdout reading moves for all three and the ordering does not change: printed
  headings recovered goes **all2md 76.4% -> 79.0%, Docling 77.4% -> 80.3%, pymupdf4llm 76.6%
  -> 79.2%**. The whole-corpus control rises with it, 13.7% -> 15.6%, since stripping numbers
  makes the shared heading vocabulary collide slightly more; the rare-heading control is
  unmoved at 1.4%. The finding that every tool loses a fifth of section headings into the
  prose stream stands, one fifth smaller than first published.
