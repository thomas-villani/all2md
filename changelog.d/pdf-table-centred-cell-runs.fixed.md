- **A PDF table that centres its cells vertically no longer has its row grouping thrown
  away.** A guard refuses a grouping when one of a group's columns is filled in three or
  more separate runs, reasoning that a cell fills contiguous lines so a column inside one
  logical row is a single run. The reasoning holds for the cell but not for the grid of
  printed lines it is read out of: where the cells of one logical row are set at different
  heights, the extractor emits a line per distinct baseline, so a wrapped cell's lines
  alternate with its taller neighbours' and that one cell shows up as several runs. A
  gene/locus table printing "SH2B3" and "[64]" on either side of a line holding only the
  middle columns was condemned on exactly that count, and kept 0.15 of its text where its
  own printed lines allow all of it. A run is now counted only where the line starting it
  fills most of the grid's columns, which is what separates a row from a fragment; the
  bar sits at four fifths because a real row does leave a column empty where a value
  repeats, and the table this guard exists to protect elides a name on every row after
  the first of a group.

  This came out of an audit for heuristics fitted to the corpus they were developed
  against, and it is the clearest case the audit found. The guard predates the corpus
  drawn afterwards and fires on both -- 30 groupings across 10 articles -- but on the
  corpus it was measured against it never changes an outcome, while on the corpus drawn
  afterwards it costs 0.0289 mean n-gram containment against JATS ground truth across
  eight tables, three of which the fix takes to the best score their printed lines
  permit. Measured over the 225 truth tables of both development corpora the change moves
  n-gram containment 0.778 to 0.807 on the newer corpus with eight tables better and none
  worse, leaves the older one byte-identical, and takes tables recovered whole from 53 to
  54. Every fill share from 0.7 to 1.0 scores identically, so the bar is a plateau rather
  than a fitted peak. The sealed holdout was not consulted.
