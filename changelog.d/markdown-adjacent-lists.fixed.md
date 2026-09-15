- **Markdown: two lists written back to back stay two lists.** A blank line does not end a
  Markdown list, so two ordered lists rendered one after the other read back as a single
  list -- the second list's own numbering merged into the first, and a list restarted at 1
  simply continued. The renderer now marks the boundary: in CommonMark, GFM and
  MarkdownPlus output the second list switches marker (`1)` after `1.`, `-` after `*`), and
  a third switches back; in the other flavors, which do not start a new list on a changed
  marker, an empty `<!-- -->` sits between them. The same holds inside block quotes and
  inside a list item holding two sublists.

  Two new round-trip invariants cover the shape in every text format. They also measured
  the same merge in the RST renderer (two bullet lists) and the AsciiDoc renderer (two
  ordered and two bullet lists), now recorded as known gaps.
