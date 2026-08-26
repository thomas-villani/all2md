- **PDF: a footer printed close to the body no longer vetoes the column split** (#440). The
  trim that stopped page furniture erasing a tight-gutter column channel banded the page at
  24pt of clear space. Ten held-out pages set their footer 8.6–11.5pt below the last line of
  text — tighter than the gap above many a table row — so the trim could not see them and the
  page was read line-by-line in y, interleaving both columns. No measure of clear space can
  separate the two cases; height can. Furniture prints a line or two, the body prints the
  page, so a trim is now admitted by the share of the page's printed text it discards, and
  it must cut at a band boundary rather than between arbitrary blocks. Measured against JATS
  ground truth on the 110-article held-out corpus: 10 pages split that did not, 14 lost
  blocks come back (13 of them reference titles), no block's share falls, and 36 of the 43
  re-converted articles project byte-identically.
