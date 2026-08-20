- **PDF: `find_tables()` grids no longer trust `Table.extract()`'s text assembly
  blindly.** Two damage classes measured on the PMC dev corpus, both inside grids
  whose geometry the ruling lines corroborate: cell text clipped mid-character
  ("Contro", "0.7" for 0.75 — much of it numeric, which the letters-only split-word
  guard ignores by design), and wrapped cells shredded into one row per printed
  line. Extracted grids are now checked both ways — for tokens the page does not
  contain (the existing fragment test, run on every strategy) and for page words
  the grid lost (a new digit-aware containment test) — and on failure the cell
  text is rebuilt from the page's own word boxes, which cannot be cut by
  construction; a rebuild that comes back lighter than the extract is discarded
  (rotated pages put cell rects and word boxes in different coordinate frames).
  Logical rows are then recovered with the same guarded continuation merge the
  word-gutter path uses, with two find_tables-specific guards: overlapping row
  bboxes (row spans) disable the merge outright, and — because find_tables row
  boxes tile, leaving gap geometry inert — a line only folds upward when its
  filled columns are a subset of those its row already fills, keeping two-tier
  headers apart. On the PMC dev corpus: 26 → 25 attainable table blocks below the
  recall bar (table-block recall 76.4% → 77.3%), mean per-table text survival
  0.837 → 0.853, no table regressing across the bar.
