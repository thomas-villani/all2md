- **`all2md check-deps` reports features as well as formats.** A "Features" section
  says whether `all2md read` (the `tui` extra, Python 3.11+), `all2md mcp`, `--watch`,
  exact token counts in `all2md chunk` and `all2md search` can run, and names the extra
  that installs each one (`pip install "all2md[tui]"`). `all2md check-deps read` checks
  one feature, and `--json` output gains a `features` object.
