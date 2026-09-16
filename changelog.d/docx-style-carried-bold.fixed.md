- **DOCX: bold, italic and strikethrough carried by a character style are emitted.** A run
  whose only character property is `w:rStyle` renders bold in Word when the style it names
  is defined bold, but `python-docx` answers `run.bold` from the run's own `w:rPr` alone,
  so it reported "no opinion" and the word printed as plain text. Legal and corporate
  templates put defined-term and party-name emphasis in exactly that place.

  The weight is now resolved through the cascade Word itself walks: `w:docDefaults`, the
  paragraph style chain, the character style chain, then direct run formatting. Bold,
  italic and strike are ECMA-376 17.7.3 **toggles**, so they do not resolve by override —
  the base is flipped once per *style level* that differs from it, which means a bold
  paragraph style and a bold character style cancel, while a child style restating its
  parent's `<w:b/>` does not (a `w:basedOn` chain is one level, flattened by override).
  Direct formatting stays absolute. These are Word's measured rules rather than a reading
  of the spec, borrowed from `docx-plus`, and all2md keeps its own small resolver rather
  than taking a dependency for them.

  **Inherited weight is judged relatively, which is what keeps headings intact.** `**`
  marks a span as heavier than the text around it, so a run that merely matches its
  paragraph has nothing to be marked against. `Heading 1` carries its own `<w:b/>`;
  marking every effectively-bold run would have wrapped every heading's text in `**`
  inside the `#`. Weight a run *inherits* is therefore compared against its paragraph's
  baseline — the same cascade without the character style or the run's direct formatting
  — and marked only where it rises above it. Weight a run states **directly** is marked
  as stated, whatever surrounds it: that is an explicit authorial act and is what all2md
  always emitted, so a directly bold run inside a bold heading keeps its `**`.

  One visible consequence beyond the defect: a run wearing a style that Word's own
  template defines with weight — `Intense Emphasis` is bold *and* italic — now arrives
  emphasised rather than as plain text. Two parser tests asserted the old, wrong shape
  and have been updated to the rendered one.

  Two layers are deliberately still unread: a **table style**'s weight, which needs the
  cell's position and its table's `w:tblLook` to reach, and the paragraph *mark*'s
  `w:rPr`, which formats the pilcrow rather than the paragraph's text. A `w:basedOn` cycle
  or an over-deep chain stops the walk and keeps what it resolved instead of raising.
