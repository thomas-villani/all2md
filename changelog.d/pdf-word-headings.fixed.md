- **PDF section headings are no longer dropped from documents with few font sizes.** The
  percentile filter ranked a document's *distinct* font sizes and, with fewer than eight
  of them, kept only the largest. A Word export, with three to five sizes, came out with
  its title as the only heading. It is now off by default (`header_percentile_threshold`
  0; set 75 to restore it), and a size needs 3 lines rather than 5 to be a heading size
  (`header_min_occurrences`). On the PDF to Word lane, 38 of 52 headings are found, up
  from 12; the 12 still scored as misses are numbered titles ("Article 1 Basic Terms")
  whose number the source document keeps in list numbering.
- **A misread body size no longer turns prose into headings.** When two sizes set
  near-equal amounts of text, body detection can pick the wrong one, and the real body
  size then clears every test above "body". A size that sets more than a quarter of the
  text now counts as a heading size only for its bold lines.
- **Headings that read as prose or a bare number become paragraphs.** A finished heading
  with no letter (page numbers, table figures), ending in a comma, semicolon or hyphen,
  opening with a lowercase word (labels such as `a.` and `iv.` excepted), or ending in a
  full stop after eight or more words is emitted as a paragraph.
- On the PMC born-digital dev corpus with layout analysis off, section-heading recall rises
  from 15.7% to 23.4% and precision from 41.2% to 51.9%; block structure rises 0.0111
  with layout analysis off and 0.0022 with it on, and text, reading order and tables do
  not move.
