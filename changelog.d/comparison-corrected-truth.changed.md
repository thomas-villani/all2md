- **benchmarks/comparison: the sealed holdout is re-read, and the table gap to Docling is 6.2
  points rather than the 16.7 published.** Two corrections landed between the readings. The
  ground truth stopped printing a space the page does not print, and all2md's outputs were
  regenerated at `2925f5c`, which carries the row-grouping fixes the previous reading's
  outputs predate. Of the 10.5 points closed, **7.1 are the truth correction and 4.1 are the
  parser**. The baselines were deliberately not re-run — their markdown is byte-identical to
  the previous reading, re-scored — so the movement is attributable to the two things that
  changed. `results-2026-08-29.json` records it; the superseded figures in the 2026-08-28
  section are labeled rather than edited.

- **The obvious reading of that correction is wrong, and the artifact says so.** It is not
  that the broken truth flattered Docling: on the 132 tables attainable under *both* truths,
  no tool's recovery changed at all — all2md 92, Docling 114, pymupdf4llm 83, before and
  after. The whole movement is **13 tables that became attainable**, of which all2md recovers
  8, pymupdf4llm 5 and Docling 1. They are the tables dense in glued inline markup — `X1`,
  `RRHF`, `0.552a`, `NSCLCb`, `Willis43` — which the old truth spelled with spaces, putting
  them outside the ceiling for every tool. Inside a table cell Docling prints `X 1 (W)` where
  all2md prints `X1 (W)`; both get it right in prose, so it is Docling's table pipeline rather
  than its text extraction. all2md also now leads recall of attainable outright at 97.3%, and
  novel share is unmoved at 0.55% — it has survived a corpus reseal *and* a ground-truth
  correction without shifting.
