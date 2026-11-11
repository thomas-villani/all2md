- **Shaded PDF table cells no longer add empty columns.** Word shades a cell twice, once
  over the whole cell and once inset by its padding, and table detection took the edges
  of both as column boundaries: a vendor form's 4x4 grid of shaded labels arrived as 4x8
  and was then rejected as mostly empty, and an annual report's 6x4 table with a shaded
  header and banded rows came out 6x12. The padding strips (empty columns of one shared
  width, at most 10pt) are now folded back into the columns they belong to, and the text
  of an unshaded row, drawn as one cell across the strips, lands in its own column. A
  grid is left as it was when its strips differ in width (a page laid out in boxes),
  when a row's cells overlap, or when the page has words inside the table that no cell
  holds.
- On the PDF-to-Word lane, table cells in the right place rise from 99 to 151 of 451;
  both shaded tables now match exactly. On the PMC born-digital dev corpus, text, reading
  order, block structure and table content do not move in either layout mode. Across a
  990-PDF fuzz pool, 42 documents change: columns that held nothing are dropped and
  tables the empty-cell guard had flattened into one line of text come back as grids,
  with no word lost beyond hyphenated words rejoined.
