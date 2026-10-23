- **Alerts and horizontal rules in DOCX output look the part.** A GitHub alert
  (`> [!NOTE]`) or an admonition from reST, MkDocs or AsciiDoc was written as a plain
  quote, its kind lost. It now opens with its label in bold ("Note", "Warning", or the
  admonition's own title) and has a bar down its left side, both in the GitHub color
  for its kind; other admonition kinds take the nearest one (`danger` is red like
  `caution`). The DOCX parser reads the five GitHub labels back, so an alert round
  trips. A thematic break (`---`) was a line of 75 gray box-drawing characters, which
  read back as text; it is now the bottom-bordered empty paragraph Word draws itself,
  and reads back as `---`.
