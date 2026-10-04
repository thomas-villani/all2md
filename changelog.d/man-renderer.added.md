- **Write man pages.** `all2md README.md --to man` (or `from_ast(doc, "man")`) renders any
  document as a man(7) page that `man`, `groff -man` and `mandoc` display. A leading
  `# LS(1)` heading or the title metadata fills `.TH`, with the date, source and manual
  taken from the metadata or the new `ManRendererOptions` (`section`, `date`, `source`,
  `manual`, `uppercase_section_headings`). The next two heading levels become `.SH` and
  `.SS`. Lists become `.IP`, definition lists `.TP`, code `.EX`/`.EE`, links `.UR`/`.UE`
  and tables tbl, with column and row spans. Text is escaped for roff: `\e`, `\-` for
  options, `\&` before a leading `.` or `'`, and `\[uXXXX]` outside ASCII, so groff needs
  no preconv. Reading a page and writing it back reproduces the same document: six real
  pages (CPython's `python.1` and man-pages' `open.2`, `ldd.1`, `ascii.7`, `printf.3`,
  `signal.7`) convert to identical Markdown either way, and the output passes
  `groff -ww` without a warning.
