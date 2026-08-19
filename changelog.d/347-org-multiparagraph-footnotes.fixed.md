- **Org footnote definitions keep their paragraphs across a round trip.**
  Org continues a footnote definition across a single blank line and ends it at
  two, but neither side spoke that dialect
  ([#347](https://github.com/thomas-villani/all2md/issues/347)): the renderer
  joined a definition's paragraphs with a bare newline (one continuation line on
  re-parse) and followed a definition with a single blank line (which would
  swallow the next block), while the parser's block splitter discarded the blank
  counts entirely. The renderer now separates a definition's paragraphs with one
  blank line and follows a definition with two; the splitter counts the blank
  lines between blocks, and single-gap paragraph blocks after a `[fn:id]` join
  its definition. Also ported the boundary-break hoisting cure
  ([#391](https://github.com/thomas-villani/all2md/issues/391)) to the Org
  span delimiters (`/`, `*`, `+`, `_`): a hard break at a span's edge stranded
  the delimiter at a line start, where `* ` opens a headline and `+ ` a list
  item.
