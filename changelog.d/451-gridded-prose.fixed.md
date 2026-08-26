- **PDF: a figure or a keywords box is no longer detected as a table that swallows the
  prose beside it** (#451). A journal first page prints its keywords next to its abstract,
  a peer-review page prints a reviewer's comments next to an author's response, and a
  magazine prints a figure between two columns of body text. The whitespace separating
  them is a real gutter, so the grid the detector builds is sound and only its *content*
  says the region is not a table — the abstract arrived as a table cell, and where the
  region spanned two columns they interleaved line by line inside that cell. Three signals
  must now agree before a grid is condemned: one cell of 60+ words carrying three or more
  sentence terminators, that cell holding 60% or more of the grid's text, and a median
  filled cell of 5+ words. No two of them suffice. Censused over the 411 tables emitted
  across the dev and held-out corpora, twelve grids hold a long prose cell, and *dominance
  orders two of them backwards*: a real 6×5 data grid that absorbed a figure caption
  dominates more (70%) than an abstract printed beside its author affiliations (69%). The
  median cell length divides that pair — values are one word, an affiliation list is
  forty-nine — and dominance divides both from a real clinical table whose three parallel
  case descriptions leave no cell dominant. Together they take all ten defective regions
  and none of the other 401 grids, and the verdict does not move across any of the 81
  threshold combinations tried. Rejected regions are demoted to paragraphs, never dropped:
  text inside a table's bbox is removed from the ordinary text blocks before the table is
  validated, so a guard that returned nothing would delete the region rather than fall
  back to prose. The guard runs on both the ``find_tables()`` and word-gutter paths, which
  is where the two shapes respectively arrive.
