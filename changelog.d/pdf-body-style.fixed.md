- **PDF → Word keeps the body text's font, size and spacing.** A converted PDF came out
  in Calibri 11 with 1.15 lines and 10pt between paragraphs whatever it was set in, so
  a 10pt Arial report ran a page longer in Word than in the PDF and a 12pt Calibri one a
  page shorter. The PDF parser now records a `body_style` metadata entry: the commonest
  font (named as Word names it, from the embedded font where it can) and size of the
  body text, its line spacing as the multiple Word would set, and the space between
  paragraphs, read only from text kept as body (not table cells, running headers and
  footers, tables of contents or OCR pages). The DOCX renderer applies them to the
  Normal style and the document's paragraph defaults; a font or size passed in
  `default_font` / `default_font_size` wins, and a reference template keeps its own.
