- **PDF tables: a stray gap no longer defines what counts as a row** (#438). Row grouping
  separates wrapped lines from row boundaries by the jump in inter-line gaps, but a
  vertically centred multi-line cell prints *three* gap populations, not two: lines from
  different columns interlace and go negative, a tall cell's own successive lines merely
  abut, and real rows are separated by padding. Worse, the jump candidates are *distinct*
  gap values, so a single stray gap could sit below the whole population and take the
  threshold with it — on the held-out corpus's largest table one −7.95pt gap below a
  cluster of 52 at −3.21pt turned 97 printed lines into 89 rows with nothing merged at
  all. Jumps are now tried in order and the first whose grouping is not mostly half-empty
  rows wins: the grouping is judged by what it produces rather than by the gap statistics
  that proposed it.
