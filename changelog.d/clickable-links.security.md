- **Links in `rcat`, `--rich` and `all2md read` are no longer clickable by default, and
  always show where they go.** A terminal hands a clicked link (OSC 8) to whatever program
  the operating system registers for its scheme, and every link was clickable, so one
  Ctrl+click on a link in an untrusted document could open a `file:` path or start an
  application's handler (`ms-msdt:`, `vscode:`, ...); the text could also name a different
  site than the target. Now no link is clickable unless `--clickable-links` says so:
  `web` for `http` and `https`, `all` for every scheme (only for documents you trust). Set
  it with `ALL2MD_CLICKABLE_LINKS`, or in the `[read]` config section; `--to terminal`
  takes `--terminal-renderer-clickable-links`. Whatever the setting, an external link's
  target follows its text, shortened in the middle of its path but never in its host,
  unless the text already is the target. **This changes the default:** to click web links
  as before, pass `--clickable-links web`.
