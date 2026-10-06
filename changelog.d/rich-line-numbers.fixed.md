- **`--line-numbers` with `--rich` keeps one numbered line per line.** Rich's
  Markdown reader reflowed the numbered source (and the numbered `--outline`) into a
  single paragraph; the numbered Markdown is now printed as it is. `--to terminal --rich`
  no longer passes the already-styled output through a syntax highlighter, which broke its
  layout.
