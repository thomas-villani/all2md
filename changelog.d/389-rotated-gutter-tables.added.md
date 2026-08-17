- **The PDF parser recovers rotated (landscape) tables in their own frame.** The
  word-gutter pass declined any region whose words were predominantly taller than
  wide, because gridding a rotated table in page coordinates scrambles its reading
  order — measured, a 28x4 truth table came back 8x12 with its containment destroyed.
  Declining was the right call and the wrong ending: on the PMC born-digital corpus,
  3 of the 13 still-missing tables were genuine landscape tables behind exactly this
  guard ([#389](https://github.com/thomas-villani/all2md/issues/389)). Such regions
  now go through the same gutter sweep with their boxes transposed into the table's
  own frame. Transposing is a reflection, so one axis always runs backwards for one
  of the two rotation directions — undecidable from the boxes alone, so both axes are
  checked against PyMuPDF's own stream order, which holds the words as they read, and
  mirrored where they disagree; getting that wrong would not mis-shape the grid but
  reverse its rows or columns, putting every cell in the wrong place. Dispatch demands
  stronger evidence than the old decline did: a word counts as rotated only when its
  box is taller than wide by a measured margin (real rotated table words sit at median
  aspect 2.5–2.7, a mixed-orientation region that must not be transposed at 1.05),
  because transposing upright text manufactures perfect fake "gutters" out of its line
  spacing. Ambiguous regions are still declined to the prose path, exactly as before —
  including the fourth rotated table in the deficit, whose orientation evidence is
  genuinely mixed.
