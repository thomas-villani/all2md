- **PDF tables: a wrapped cell stays one cell** (#438). Row grouping separates wrapped lines
  from row boundaries by the jump in inter-line gaps, but a vertically centred multi-line
  cell prints *three* gap populations, not two: lines from different columns interlace and
  go negative, a tall cell's own successive lines merely abut, and real rows are separated
  by padding. Taking the first jump on faith put a cell's own wrap lines on the
  row-boundary side, so the top and bottom lines of a tall header cell stood as rows of
  their own and displaced the header labels down into the first body row. Worse, the jump
  candidates are *distinct* gap values, so a single stray gap could sit below the whole
  population and take the threshold with it — on the held-out corpus's largest table one
  −7.95pt gap below a cluster of 52 at −3.21pt turned 97 printed lines into 89 rows with
  nothing merged at all. Jumps are now tried in order and the first whose grouping is not
  mostly half-empty rows wins, and a fragment that adds no columns of its own folds into
  whichever neighbour it abuts — including *downward*, which is how a table's first printed
  line can now join the header it belongs to. Measured over every table on the 110-article
  held-out corpus: 14 tables improve, 154 spurious rows and 166 half-empty rows disappear,
  and **no table gets worse**. The worst table on the corpus goes from 96 rows to 49.
