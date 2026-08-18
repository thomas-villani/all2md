- **The AsciiDoc renderer/parser pair stops rejecting, corrupting, or leaking its own
  output.** Four defects, one format. A bold or italic span wrapping only a hard break
  stranded its delimiters at a line start, where `* ` is a level-1 list marker and
  `** ` a level-2 one -- the first silently turned emphasis into a list item, the
  second crashed the parser outright, the round-trip matrix's only open crash
  ([#353](https://github.com/thomas-villani/all2md/issues/353)); boundary breaks now
  hoist outside the delimiters, the same cure as markdown's #391. A definition-list
  description on the line directly below its `term::` -- the standard placement, and
  what this renderer itself emits -- parsed to nothing: the term came back empty, the
  text as a sibling paragraph, and the list split at every term
  ([#351](https://github.com/thomas-villani/all2md/issues/351)); unindented lines
  adjacent to the term now bind to it as one wrapped paragraph. The renderer also
  fused a description's paragraphs into one token (`only`+`extra` -> `onlyextra`,
  #352's class); blocks now join as continuation lines. And the parser did not
  recognise the named inline footnote form `footnote:a1[text]` -- valid Asciidoctor
  and the renderer's own spelling -- so the raw markup leaked into the prose as
  literal text ([#346](https://github.com/thomas-villani/all2md/issues/346)); it now
  parses, a hard break inside the macro's brackets degrades to a space instead of an
  unparseable embedded newline, and an id referenced but never defined gets an empty
  definition rather than an unbalanced round trip.
