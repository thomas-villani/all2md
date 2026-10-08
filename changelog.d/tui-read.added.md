- **`all2md read` (and `rcat -i`): an interactive viewer in the terminal.** The document
  scrolls in one pane beside an outline, with a status bar showing the section and the
  position; `[`/`]` move between headings, `l` lists the links on screen, `?` shows the
  keys, and `--keys vim` adds the keys of less and vim. Links to a heading or a footnote
  move the viewer (Left or Backspace goes back); any other link is shown, and `y` copies
  it, but it is never opened. The view keeps its place when the terminal is resized, and
  `all2md read -` reads the document from stdin. Needs the new `tui` extra
  (`pip install 'all2md[tui]'`, Wijjit, Python 3.11 or later); `rcat` without `-i`
  works as before.
