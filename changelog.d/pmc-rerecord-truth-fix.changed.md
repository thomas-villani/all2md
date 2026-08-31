- **benchmarks/pmc: the born-digital lane is re-recorded against the corrected ground
  truth.** `reference.json` now holds the CI reading taken on `main` at `2925f5c`, the
  first since the JATS projection stopped printing a space the page does not print. Almost
  all of the movement is that correction rather than a parser change, and the published
  page says so: raw recall 62.3% → **63.8%**, table attainable-recall 82.7% → **84.9%**,
  `table_content_similarity` 0.611 → **0.629**, `table_structure_similarity` 0.622 →
  **0.636**, `text_content_similarity` 0.683 → **0.690**, caption recall 94.4% →
  **97.7%**, supported share 95.5% → **95.6%**. **Recall of what is attainable is
  unchanged at 98.9%** — the correction puts more of the ground truth inside the ceiling
  and recovers it in the same proportion, which is what a published ceiling is for. Ground
  truth coverage of the page falls 0.965 → **0.932** for the same reason, and its maximum
  falls 1.197 → **1.122**: the projection was claiming more words than the page shows,
  which is precisely the direction a spurious space produces.

- **docs: one published table-surplus figure was stale, and the figures gate could not see
  it.** The census reports the surplus split by source; the page prints both halves, but
  only the first is a snippet the gate renders from the artifact. `outside_jats` fell from
  42 to 40 at the previous re-record and the derived "the other 22" was never updated. It
  now reads **20**. The gate covers declared snippets, not the prose around them, which is
  the second time that gap has produced a stale published number.
