- **`serve`'s upload form and `/api/convert` endpoint are removed**, with
  `--enable-upload`, `--enable-api` and `--max-upload-size`. They were marked
  development-only; `serve` now refuses those flags with an explanation. Convert from a
  program with the Python API or `all2md mcp`.
