# Contributing to the VCS Document Converter

This directory is an **example** shipped with [all2md](https://github.com/thomas-villani/all2md).
It shows how to make binary documents (DOCX, PPTX, PDF) git-friendly by keeping
parallel Markdown versions under version control. Improvements are welcome.

## Development setup

```bash
# From an all2md checkout
pip install -e .            # install all2md itself
pip install all2md[all]     # optional: all format support (PDF, DOCX, PPTX, ...)

# Run the example directly from this directory
python vcs_converter.py scan
python vcs_converter.py to-md path/to/document.docx
python vcs_converter.py to-binary .vcs-docs/document.vcs.md
```

The script has no third-party dependencies of its own beyond `all2md`; it uses
only the public API (`all2md.to_ast`, `all2md.from_ast`, `all2md.from_markdown`)
plus the standard library.

## How it is organized

- `vcs_converter.py` — the converter and its CLI (`to-md`, `to-binary`, `batch`, `scan`, `clean`).
- `pre-commit-hook.sh` / `install_hook.py` — git pre-commit integration.
- `vcs-converter.config.json` — example configuration (`markdown_dir`, `track_metadata`, `store_ast`, `exclude_patterns`).
- `README.md` / `QUICKSTART.md` / `COMMANDS.md` / `OVERVIEW.md` / `INDEX.md` — documentation.
- `demo.py` — a self-contained demonstration.

## Enhancement ideas

These are deliberately left out of the example to keep it small, and make good
starting points for contributions:

- **PPTX round-trip** — `to-binary` currently raises `NotImplementedError` for
  `.pptx`/`.ppt`. Wire up `from_markdown(..., "pptx", ...)` once slide layout
  fidelity is acceptable.
- **Image preservation** — extract attachments with `--attachment-mode save`
  and store them alongside the Markdown so round-trips keep images.
- **Configurable rendering** — expose `MarkdownRendererOptions` (line wrapping,
  emphasis symbols, etc.) through the config file.
- **Git LFS / large files** — guidance and helpers for very large binaries.

## Guidelines

1. Keep the example dependency-light and use only all2md's **public** API.
2. Match the existing code style (run `ruff format` / `ruff check`).
3. If you add a config key, make sure the code actually reads it and document it
   in `README.md` — an advertised-but-ignored option is worse than no option.
4. Verify a full round-trip (`to-md` then `to-binary`) before submitting.

File issues and pull requests in the main
[all2md repository](https://github.com/thomas-villani/all2md).
