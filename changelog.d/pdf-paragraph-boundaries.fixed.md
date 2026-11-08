- **PDF paragraphs and numbered clauses keep their boundaries.** A paragraph no longer
  breaks after an ordinary line because the leading below it happened to be 5.1pt rather
  than 4.9pt: the gap between two lines is now the white space between them, not the
  distance between their bottoms. Numbered clauses set on a hanging indent, such as Word's
  `1.1`, `1.2` and `(a)` with the number at the margin and the text at a tab stop, now come
  out one per paragraph instead of running together. A long figure caption is no longer
  cut short with its remainder left in the body: the paragraph that holds the whole
  caption completes it, and a soft hyphen no longer stops a caption's body copy being
  recognized. On the PDF to Word lane, paragraphs left whole go from 109 to 128 of 128 and
  list items in their own paragraph from 32 to 47 of 47. On the PMC born-digital dev
  corpus, block structure rises 0.0013 with layout analysis on and off, and text content
  0.0029 with it off.
