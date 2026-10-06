- **No more "Keyword arguments were ignored" from the CLI's own modes.** `--outline`,
  `--extract`, `--slice`, `--head`/`--tail`/`--lines`, `--collate`, `--split-by` and
  `--merge-from-list` parse to an AST and render it in two steps, and they passed every
  option to both. Each step warned about the other's options, so
  `all2md guide.md --to man --man-renderer-section 8 --head 3` warned about `section`.
  Parser options now go to the parser and renderer options to the renderer.
