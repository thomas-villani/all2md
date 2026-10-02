- **Man pages: a parser for the man(7) macros.** `all2md ls.1` reads Unix manual pages
  directly, with no roff installation: `.TH` becomes the title, date and section
  metadata (and an `LS(1)` heading, which `--man-no-title-heading` turns off), `.SH`
  and `.SS` become headings, `.TP` and tagged `.IP` paragraphs become definition lists,
  `.IP` bullets and numbers become lists, `.RS`/`.RE` nests them, `.nf` and `.EX`
  regions become code blocks, `.UR`/`.MT` become links and simple `tbl` tables become
  tables. The font escapes and macros map to bold, italic and code. Extensions `.1` to
  `.9` and `.man` are confirmed by content (the first macro must be `.TH`), so a rotated
  `app.log.1` still reads as plain text, and a page with any other extension, such as
  Perl's `.3pm`, is found by content alone. The preamble pod2man writes before `.TH`
  (conditionals, string and macro definitions) is read rather than printed. Not yet:
  mdoc(7) pages (`.Dd`/`.Sh`), `.so` includes (reported, not followed) and gzipped pages.
