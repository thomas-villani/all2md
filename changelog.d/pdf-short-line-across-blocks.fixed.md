- **A short PDF paragraph in a block of its own no longer runs into the next one.** PyMuPDF
  often gives each short paragraph (an agenda item, a clause) a block of its own, where the
  short-line test could not see it, and the merge joined them. The merge now asks the same
  test across the block boundary, against the width of the paragraph's column on the page.
