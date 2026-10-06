- **Document output shown in a terminal no longer carries the document's control
  characters.** `--rich` output (Markdown and other targets) and unstyled output written
  to a terminal or the pager now remove the C0 controls other than tab and line feed,
  DEL and the C1 controls from the document text first. Output to a file or a pipe is
  left exactly as converted.
