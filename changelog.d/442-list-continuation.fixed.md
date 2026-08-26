- **PDF: a list item keeps the lines it wraps onto** (#442). Paragraph assembly refused any
  merge touching a list item. That is right for two *items*, but it also stranded every line
  a long item wraps onto — and a numbered bibliography is a list of long items, so a
  reference's title and journal arrived as separate blocks from its authors, and the
  hyphenation repair that runs at a merged seam never got the chance to run. Measured over
  8,183 merge decisions on twelve dev-corpus articles, 151 of the 325 blocks that end
  mid-sentence are stranded this way, and 98% of them sit 0.5–3.8pt below the item — the
  same geometry as the wraps already merged (median 1.98pt, 95th percentile 3.67pt). A
  continuation now joins its item on that geometry; a new list item never merges, and
  neither does a block starting *above* its predecessor, which under a list item is a page
  or column break rather than a wrap. Across those twelve articles: blocks 1,262 → 1,066,
  blocks ending mid-sentence 412 → 257 (32.6% → 24.1%), median words per block 15 → 23.
