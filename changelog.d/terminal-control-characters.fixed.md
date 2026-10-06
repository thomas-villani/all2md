- **Document output shown in a terminal no longer carries the document's control
  characters.** The terminal renderer (`--to terminal`, `--rich`, `rcat`) cleans text,
  headings, alt text and link targets of the C0 controls other than tab and line feed,
  DEL and the C1 controls before drawing, with the same tree-wide pass the DOCX and
  EPUB renderers use for characters XML cannot carry. Unstyled text output removes the
  same characters when it goes to a terminal or the pager; output to a file or a pipe is
  left exactly as converted.
