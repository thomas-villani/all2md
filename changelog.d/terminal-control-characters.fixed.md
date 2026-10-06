- **The terminal renderer draws a document's control characters as nothing, not as
  terminal input.** Text, headings, alt text and link targets are cleaned of the C0
  controls other than tab and line feed, DEL and the C1 controls before drawing, with
  the same tree-wide pass the DOCX and EPUB renderers use for characters XML cannot
  carry.
