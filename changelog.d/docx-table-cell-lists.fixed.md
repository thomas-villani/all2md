- **DOCX: a numbered list inside a table cell keeps its numbers.** A contract schedule or
  an obligations table often puts "The Supplier shall:" and its numbered clauses in one
  cell. Every paragraph of a cell was appended to the next with nothing between them, so
  the cell read as one run-on string — `The Supplier shall:deliver the goodsinvoice
  monthly` — with the numbering gone. A cell's paragraphs are now separate lines (`<br>` in
  a Markdown table), and a numbered or bulleted paragraph keeps a `1.` or `•` marker, counted
  per level within the cell. With `preserve_tables` off, the same paragraphs now form a
  real list that ends with its cell.

  A list that runs straight up to a table is also written before the table again; it was
  only closed by the next paragraph after the table, so it landed below it.
