- **benchmarks/pmc: the ground truth no longer discards half of a table the publisher split
  for the page.** A wide table is often typeset as two `<table>` elements under one
  `<table-wrap>` — the same rows, the left columns and then the right — and the projection
  read only the first, so the remaining columns were absent from the truth entirely. That is
  not a rounding error: it is **5.3% of the development corpus's table text**, sitting in
  halves no converter was ever asked to match, and every tool that *did* extract them was
  charged for emitting text with nothing behind it. Each `<table>` a wrap carries is now its
  own truth table, which needs no guess about whether the parts are stacked or side by side —
  merging them would have had to pick one and the structure figures would have inherited it.
  The caption stays on the first part, because the page prints it once.

  Found by auditing the table scoring path end to end, after three separate instrument
  defects surfaced in a single day. Two other checks in the same audit came back clean and
  are now pinned by tests rather than by memory: `colspan` text is not duplicated (a spanning
  cell is printed once and counted once), and table footnotes belong to the caption stream
  rather than to cell text. A third found a second latent bug — a table nested inside a cell
  had its rows counted as the outer table's *and* its text counted twice — which had zero
  incidence on either development corpus but is fixed here rather than left waiting for the
  article that has one.

  The lane's `SCHEMA_VERSION` moves to 7 with it. No payload key changes shape; the ground
  truth underneath every figure does, and the schema pin is what stops a projection edit from
  landing while the recorded artifact quietly describes an older one — a gap worth naming,
  because none of the three existing guards could see a truth change: the corpus pin hashes
  the manifest, the schema pin covered payload shape, and the published-figures test compares
  the page against the recorded file rather than against a fresh run.
