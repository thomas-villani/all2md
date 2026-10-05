- **Markdown piped to stdin is read as Markdown.** Detection by content had no test for
  Markdown, so `cat notes.md | rcat` (or `| all2md -`) read it as plain text and printed
  `\# Heading`. Nameless text that every content detector declined is now read as Markdown
  when it carries two kinds of Markdown mark (ATX headings set off by blank lines, lists,
  links, strong emphasis, tables, fenced code, block quotes, inline code) and nothing of
  another language's syntax (program statements, reST directives and roles, Org keywords,
  minified JavaScript); fenced code is set aside first, so a README full of shell examples
  still counts. Markdown that opens with YAML (`---`) or TOML (`+++`) front matter is
  recognized before the YAML detector, which used to claim it, and a Markdown note that is
  only a heading and a bullet list is no longer read as a YAML list. Over the repository's
  own files the test says yes to 84 of 104 `.md` files (the rest are short snippets with one
  kind of mark, which stay plain text) and to 2 of 1,390 other text files. Without the
  Markdown parser installed (mistune), nameless text stays plain text as before; a named
  file is unaffected.
