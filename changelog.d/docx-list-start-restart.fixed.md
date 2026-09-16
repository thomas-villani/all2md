- **DOCX: lists keep the numbers Word prints.** A list interrupted by a paragraph carries
  on counting instead of starting again at 1, a level's start value (`w:start`) is
  honoured, and Word's "Restart Numbering" splits two lists written back to back instead
  of fusing them into one. The count runs through numbered headings and table cells in
  document order, and a list whose first items sit deeper than the items after it no
  longer loses them.
