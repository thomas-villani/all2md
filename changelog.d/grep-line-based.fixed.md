- **`all2md grep` works line by line, as grep does.** Each section used to be searched as
  one flattened line, so `-A`/`-B`/`-C` added nothing, `-n` always printed 1, and a table
  came out as one run of words. Now each paragraph, list item, table row, heading and line
  of code is a line (a soft break in a Markdown or text source starts one), `-n` counts
  lines through the document, context lines are marked `N-`, and `--` separates runs.
  Headings, inline code and code blocks are searched; they were skipped. `-M 0` no longer
  truncates long lines. And the exit status follows grep: 1 when nothing matched (with
  nothing printed, where it used to print "No results found." and exit 0), 3 for an
  invalid regular expression.
