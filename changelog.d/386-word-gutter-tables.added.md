- **The PDF parser recovers borderless tables from word-box gutters.** Layout-predicted
  table regions that PyMuPDF's strategies could not grid — 56 of the 63 tables missing
  from the born-digital corpus, every one shredded by the text strategy and then
  correctly refused by the split-word guard — now get a third pass that builds the grid
  from the page's own word boxes: columns from vertical bands no word crosses, whole
  words assigned to the column holding their center, wrapped cell lines folded into
  their logical row with hyphenation repair across the join
  ([#386](https://github.com/thomas-villani/all2md/issues/386)). Cut and space-joined
  words are impossible by construction. Three measured guards keep prose out: a grid
  needs three-plus columns (one gutter is what any two-column layout has), a
  sequential-integer column beside sentence-length cells reads as a numbered
  bibliography and demotes to prose (gridding one scrambles every citation), and a
  region of predominantly rotated words is declined in favor of the rotation-aware
  prose path. Measured on the 12-article PMC sample: tables emitted rose 12 → 30 of 32
  expected, `table_content_similarity` median 0.000 → 0.88, `table_structure_similarity`
  median 0.000 → 0.73, with whole-article attainable recall at 0.941 (baseline 0.951 —
  a table's cell stream breaks a few truth blocks' n-grams that its prose form kept)
  and both wrong-article controls at zero.
