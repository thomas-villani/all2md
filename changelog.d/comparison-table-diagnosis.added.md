- **benchmarks/comparison: the table gap to the strongest baseline is diagnosed, and it is
  entirely order — none of it is content.** `benchmarks/comparison/tablediag.py` scores every
  attainable truth table twice against the same output: the published n-gram measure, and an
  order-free multiset token containment. The audit that preceded it established why the pair
  is needed — the median table cell is two words and 69–83% of a truth table's 5-grams cross
  a cell boundary, so the published figure is overwhelmingly cell adjacency and reading
  order, and quoted alone it reads as content recovery, which it is not.

  On 146 attainable tables of the sealed holdout, **all2md holds 99.8% of every truth table's
  words** — the best of the three tools and effectively at ceiling — against an n-gram figure
  of 0.838. There is no content deficit left to close, and a tool can only be charged for
  losing order once it is shown to have the words.

  What separates the tools is how many rows each cuts a table into: all2md's row count
  matches the truth's 54% of the time against Docling's 81%. The per-table disagreement is
  also far more symmetric than the mean suggests — Docling wins 35 tables by more than ten
  points, all2md wins 29 — and **97% of Docling's wins are the same words in a different
  order**. The reading publishes pymupdf4llm's row column as its own guard: it gets more row
  counts right than all2md and still scores worst of the three, so row grouping is what
  separates these two tools on this corpus rather than a general ranking.

  Two negatives ship with it rather than being left as folklore. The win direction clusters
  by *article* (64.1% within-article agreement against a 31.6% permutation null, p = 0.004),
  but every document-level variable probed came back flat: ruling density, rules drawn as
  rectangles rather than line items, journal identity, two-column layout, landscape pages,
  and table shape. And the one mechanism that looked decisive priced out at nothing — half of
  all recorded grids arrive with no vertical gap between any two lines, because a ruled
  table's row boxes share edges, and merge recall there collapses from 79.5% to 29.2%. Those
  grids are already correctly rowed, which is *why* they tile, so the collapse is worth
  +0.017 to +0.032 of containment against +0.054 to +0.101 for grids with real geometry. A
  merge-recall number can look catastrophic and be worthless; a grouping lead has to be
  priced in containment before it is chased.

  The conclusion recorded with the reading is that the residue is a model-class difference —
  a learned table-structure model over the page image against geometry rules over extracted
  words — and not a rule all2md is missing. Table work stops there rather than continuing to
  fit heuristics to a corpus.
