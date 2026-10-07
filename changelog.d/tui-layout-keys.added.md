- **The groundwork for the terminal viewer (`all2md.tui`).** `DocumentLayout` lays a
  document out at whatever width the terminal has and keeps the last few widths. It
  answers what the viewer needs: the outline, which section a line is in, the next
  and previous heading, the links on screen, where a `#fragment` link or footnote
  reference jumps to, and where to scroll after a resize. Fragments match
  GitHub-style heading anchors and explicit heading ids. `all2md.tui.keys` holds the
  key presets as data: a default preset, and a `vim` one that adds the keys of less
  and vim. Neither needs Wijjit, which the viewer itself will. The terminal
  renderer's `HeadingPosition` gains an `anchor` field with the heading's explicit
  id.
