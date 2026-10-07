- **The terminal renderer reports where things land.** `TerminalRenderer.layout()`
  lays a document out once and returns the text together with the line of every
  heading and footnote definition and the line and columns of every link and
  footnote reference, groundwork for the interactive viewer. `heading_positions()`
  now comes from the same pass and includes nested headings (in quotes, lists and
  footnotes).
