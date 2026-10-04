- **Man page tables with `T{` text blocks are read as tables.** Any tbl table holding a
  `T{` ... `T}` text block, as nearly every man-pages ATTRIBUTES table does, became a
  code block of raw roff. Text blocks are now read as cells, through a nested parse,
  so requests inside them (`.BR`, `.UR`/`.UE`, `.br`, even lists) work. Fields after
  `T}` continue the row, and `.T&` format changes are skipped. `syscalls(2)`, with 133
  text blocks, now converts to a Markdown table. In the other direction, the man
  renderer writes a cell that holds a link or a hard line break as a text block, so a
  link in a table survives a man round trip. A cell of just `_` or `=` is protected so
  tbl does not draw a rule, and table cells carry their column's alignment.
