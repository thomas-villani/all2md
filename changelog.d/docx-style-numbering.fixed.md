- **DOCX: numbered and bulleted lists whose numbering lives on a paragraph style are
  detected again.** Word puts `w:numPr` on a paragraph or on that paragraph's *style*,
  and the parser read only the first. Corporate templates use the second almost
  exclusively — the paragraphs carry nothing but a `w:pStyle`, and the numbering is
  reachable only through `styles.xml` — so on exactly those documents an ordered list
  came out as a run of plain paragraphs, with the list structure and the numbers both
  gone. The style chain is now followed through `w:basedOn`, and `ilvl` and `numId` are
  each taken from the nearest place that sets them, which is how Word itself merges
  paragraph properties.

  Two things this newly-reachable markup made necessary. Numbering is switched on by
  `numId`, so a `w:numPr` carrying only an `ilvl` is not a list — Word's own built-in
  Subtitle style carries one, and treating it as numbering would have turned every
  subtitle into a list item; `numId="0"`, Word's explicit "no numbering", is likewise
  respected. And a level that comes from a style is shared by every paragraph using that
  style, so it cannot express nesting on its own: where `ilvl` is inherited rather than
  set on the paragraph, indentation still nests the item, which is how writers that
  cannot vary `ilvl` — `python-docx` among them, and the built-in `List Number` and
  `List Bullet` styles it leans on — have always expressed depth. An `ilvl` set on the
  paragraph is authoritative, and indentation beside it is only formatting.

  Two smaller repairs came with it. `numPr` is now read from the paragraph's own
  properties rather than from anywhere beneath it, so a numbering record inside a
  `w:pPrChange` no longer makes a paragraph a list on the strength of what it used to
  be. And the numbering definitions are parsed once per document instead of once per
  list item — the style-inherited case sends far more paragraphs through that lookup.
