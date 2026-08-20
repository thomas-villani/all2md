- **PDF: wrapped table cells no longer shred into one row per printed line.** The
  word-gutter grid emitted every printed line as a table row, so a cell wrapping to
  a second line split mid-sentence — and the old repair (merge when the leftmost
  well-filled column is empty) was blind to three measured shapes: middle-aligned
  cells that fill every column on continuation lines, wraps living *in* the anchor
  column itself, and row-label columns too sparse to qualify as the anchor. Rows are
  now recovered from three guarded signals: a jump in the inter-line gaps names the
  rows geometrically (abandoned whole when it would fuse adjacent numeric rows, or
  stack three-plus separate cells into one column of a merged row); a line filling
  exactly one column tighter than the table's median gap folds up as a wrap; and the
  anchor column may be sparse (down to 20% fill) when the merge it implies survives
  the same fusion guards and introduces no content in columns its row start left
  empty. On the PMC dev corpus: 34 → 26 attainable table blocks below the recall
  bar (table-block recall 69.1% → 76.4%), dense single-line tables byte-identical.
