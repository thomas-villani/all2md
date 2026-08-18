- **The Markdown renderer no longer emits markdown its own parser misreads.** Three
  defects shared that shape. A spanned table was written one pipe cell per AST cell
  while the delimiter row was sized to the logical width, so a `colspan` header made
  the cell counts mismatch and GFM read the whole table as prose; cells are now placed
  on the resolved grid, spans padded with empty cells -- the merge is lost (pipe tables
  cannot express one), the table is not, and rows after a `rowspan` stay in their own
  columns instead of sliding left ([#385](https://github.com/thomas-villani/all2md/issues/385)).
  A hard line break was always spelled as two trailing spaces, so a break on a line
  with no visible text (one break following another) left a whitespace-only line, which
  is a paragraph boundary in every conformant parser -- consecutive breaks silently split
  their paragraph in half; such breaks now use the backslash spelling, which puts a
  visible character on the line ([#384](https://github.com/thomas-villani/all2md/issues/384)).
  And an emphasis, strong, or strikethrough span wrapping nothing visible -- or ending in
  a line break -- stranded its delimiter run alone at a line start, where `***` is a
  thematic break and `~~~~` opens a tilde code fence that swallows the rest of the
  document; nested strikethrough now renders its inner content bare (GFM strikethrough
  does not nest), spans over nothing visible emit no delimiters, and boundary breaks are
  hoisted outside the delimiters ([#391](https://github.com/thomas-villani/all2md/issues/391)).
  The round-trip fuzzer's figure-gate strategies were constrained to avoid the first two
  defects and its footnote allowlist carried the third under a wrong attribution; the
  constraints and the stale allowlist entry are removed, so the gates now guard all
  three classes.
