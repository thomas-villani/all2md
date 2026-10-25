- **`all2md serve` is deprecated; use `all2md view`**, which browses a folder or a glob
  the same way. `serve` still works in this release and prints a note; it will be removed
  in the next. Moving over: `view` opens the browser itself (drop `-B`), lists every
  document by default (pass `--index-page` where `serve` showed a README, and drop
  `--force-auto-index`), takes `--host`/`--port` in place of `--address`, and reads
  `[view]` in place of `[serve]`. The Windows folder context-menu entry now runs `view`;
  install it again to update one installed earlier.
