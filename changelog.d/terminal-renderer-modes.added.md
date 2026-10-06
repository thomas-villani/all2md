- **`--extract`, `--outline`, `--slice` and the line windows draw with the terminal
  renderer under `--rich` too.** An extracted section, a slice, or a `--head`/`--tail`/
  `--lines`/`--extract line:` window now shows footnotes, task lists, math and admonitions
  as `rcat` does for a whole document. The outline is a nested list of the headings with
  their formatting, and a slice's "next slice" hint is a dimmed last line instead of an
  HTML comment. Line windows are still chosen from the Markdown rendering, so their numbers
  agree with `--outline --line-numbers`.
