- **`all2md view` browses a folder.** Given a folder or a quoted glob pattern
  (`all2md view ./docs -r`, `all2md view "reports/*.pdf"`), `view` starts a local server
  and opens a listing of every document it can convert, each converted when opened; the
  listing follows the folder as files change. The listing is generated even when the
  folder has a README, which rarely lists everything (`--index-page` shows the README or
  `index.md` instead). Images a document names by path now show, in `view` and `serve`
  alike, when they are inside the folder being viewed. `--recursive`, `--include-hidden`,
  `--port`, `--host`, `--poll-interval`, `--window` and `--cache` all work here.
