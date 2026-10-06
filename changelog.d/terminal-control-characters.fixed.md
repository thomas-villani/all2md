- **The terminal renderer draws a document's control characters as nothing.** The
  renderer behind `--to terminal`, `--rich` and `rcat` removes the C0 controls other than
  tab and line feed, DEL and the C1 controls from text, headings, alt text and link
  targets before drawing, with the same tree-wide pass the DOCX and EPUB renderers use for
  characters XML cannot carry. (Unstyled output to a terminal shipped in 1.16.1.)
