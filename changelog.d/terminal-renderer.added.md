- **`rcat` and `--rich` draw the document itself, not Markdown text.** A new `terminal`
  renderer builds rich output straight from the parsed document. The old path rendered
  Markdown and let `rich.markdown` parse it again, so footnotes, math, task lists,
  definition lists, admonitions and GitHub alerts printed as raw syntax, underline
  vanished, and display math lost the backslash in `\,`. Now footnotes are numbered and
  collected at the end, math is verbatim (display math in a box), task items show ☑/☐,
  definitions are indented under their term, admonitions are titled panels colored by
  kind, and sub/superscripts use Unicode where they can. The `--rich-*` flags and the
  `[rich]` style table keep working, with new names for the new elements (`math`,
  `footnote`, `admonition.warning`, ...). It is also an output format: `--to terminal`
  writes ANSI text, and `--terminal-renderer-color-system none` writes plain text.
  With `--line-numbers` the numbered Markdown source is printed unstyled, since the
  numbers count its lines. In the `[rich]` table, a dotted element name such as
  `"item.bullet"` now gets the `markdown.` prefix, as the configuration docs always said
  it did.
