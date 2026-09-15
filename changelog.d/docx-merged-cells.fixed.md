- **DOCX: a merged table cell is written once, not once per column or row it covers.**
  `python-docx`'s `Row.cells` returns one cell per grid position and repeats a merged
  cell at every position it spans, so a cell merged across two columns printed its text
  twice, and a cell merged down two rows printed it again in the row below. The parser now
  walks the row's real `w:tc` elements: `w:gridSpan` becomes the cell's colspan, and a
  `w:vMerge` continuation extends the cell that restarted the merge instead of becoming a
  cell of its own. Word shows only that cell's content, and so does the output. The
  flattened (`preserve_tables=False`) path reads the same cells, so it no longer repeats
  merged text as extra paragraphs.

  A row that starts past the first grid columns (`w:gridBefore`, common in tables
  converted from older formats) now gets an empty cell for the skipped columns, so its
  cells stay in their own columns instead of sliding left.
