- **A PDF table whose row labels wrap no longer leaves every printed line standing as a
  row.** `merge_continuation_lines` decided continuations from a single anchor column, which
  cannot work when the column naming the rows is itself the one that wraps: a case-report
  table whose reference column prints "Suleiman", "et al.", "[8]" down three lines has that
  column filled on all of them, so no line reads as a continuation and each wrap becomes its
  own row. Row-major reading then interleaves the columns, and the table's words survive in
  the wrong order. The columns that genuinely mark rows are now found by *agreement* --
  several of them hold one short value per row and are filled on nearly the same lines --
  and a column filled on more than half a wrapping table's printed lines is refused, because
  a sparse data column mistaken for a row label is how a province column fused nine yak
  breeds into one column-major row. Four columns must agree before the pattern is believed;
  two coinciding is chance in a narrow table. They need only agree *nearly*: a multi-line
  header perturbs each marker by whichever of its lines that column's label sits on, so
  under exact equality the case-report table this was built from counted four distinct sets
  and merged nothing.

- **A table header that wraps is folded into one row.** A header cell sets at whatever
  height its own column needs, so a wrapping header's printed lines fill *disjoint* columns
  while a data row refills the columns above it; chaining while that holds ends exactly where
  the body begins. Disjointness alone is not sufficient and the difference matters: a
  two-tier header whose top tier spans column pairs leaves precisely the columns its
  sub-header fills, and folding that interleaves both tiers (measured 0.87 -> 0.79). The two
  are separated by what wrapping must leave behind -- a continued cell fills its column
  twice, a tiered header fills each of its columns once -- so the tiered header still keeps
  its rows.

- **A blank printed line inside a grid separates rows.** It was being absorbed as a
  continuation, letting a row start fold into the row above it across a gap the page had
  drawn precisely to keep them apart. It is now a boundary, and still emits no row of its own.

  Measured against JATS ground truth on both development corpora, over the 225 truth tables
  that reach a grid: n-gram containment 0.788 -> 0.808, twenty tables better and two worse,
  and 99 tables recovered whole against 89 before. Held separately the gain is 0.823 ->
  0.846 on the 66-article dev corpus with nothing worse, and 0.760 -> 0.778 on the
  110-article tuned corpus. The reachable headroom from row grouping alone is +0.059 and
  +0.098 on the two corpora, so this takes about a quarter of it; the rest of the table loss
  is column structure and words the extractor never reaches, which no row-grouping rule can
  address. The sealed holdout was not consulted.
