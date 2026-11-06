- **Breaking: an RST file can no longer read other files or fetch URLs into its output
  (GHSA-q9p2-g3hh-xx9c).** `.. include::`, and the `:file:` and `:url:` options of
  `raw` and `csv-table`, used to copy any local file (or a URL's response) into the
  Markdown, even under `--safe-mode`, so an RST file you did not write could leak your
  secrets or reach internal addresses. They are now refused by default, the rest of
  the document converts as before, and each skipped directive logs a warning. To
  convert a document you trust that relies on includes, add `--rst-parse-includes`
  (`RstParserOptions(parse_includes=True)`). Thanks to santhreal for the report.
