- **PDF: side-by-side columns no longer interleave line-by-line** (#405). Journal
  reference pages print two columns with a 15–18pt gutter — under the 20pt threshold —
  so the split never fired and the y-sort shredded every entry into the other column.
  Three fixes, each behind structural evidence: a *channel* detector admits a
  sub-threshold gutter only when an x-interval untouched by any block separates enough
  y-overlapping content on both sides; blocks PyMuPDF fused *across* the gutter are
  resegmented line-band by line-band (an undetected table cannot split — its bands are
  many and narrow); and a word hyphenated at a block seam ("transcrip- tion") is joined
  when the paragraphs merge. On the PMC dev corpus: 254 → 97 missing attainable
  blocks (titles 171 → 28), zero blocks newly missing, table blocks untouched.
