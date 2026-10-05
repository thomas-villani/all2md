- **reStructuredText: nested lists read back as nested lists** (#517). The renderer wrote a
  nested list on the line after its parent item, six columns in, and docutils read the
  parent's text and the list as a definition list, so the item lost both its paragraph and
  its list. A nested list now sits a blank line below the item's text at the item's text
  column (three columns for `1.`, four for `10.`). The other blocks of a list item keep the
  blank lines between them, so a code block or a second paragraph inside an item no longer
  fuses with the text above it either.
