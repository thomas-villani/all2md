- **DOCX: a list numbered by a Word *list style* is no longer demoted to bullets.** Word
  writes a numbering style as a **pair** of `w:abstractNum` elements: one holds the nine
  levels and carries `w:styleLink` naming the style, and a second holds *no levels at all*
  and carries `w:numStyleLink` pointing back at the same style. The paragraphs' `w:numId`
  points at the empty one, so reading the levels off it found nothing, the format could not
  be named, and the fallback text sniff defaulted to bullet — the list survived, the item
  text survived, and the numbering quietly did not.

  The two are now paired by the style they name. ECMA-376 routes the indirection through
  `styles.xml` — `w:numStyleLink` names a style whose own `w:numPr` names the real
  `w:numId` — and that lands on the abstract declaring `w:styleLink` for the same style,
  so the pairing needs no second part to be read.

  This is the shape Word writes whenever numbering is applied from a list style rather
  than typed onto the paragraphs, which is what a template gallery does, and the corpus
  now carries a Word-generated case for it.
