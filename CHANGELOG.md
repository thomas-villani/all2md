# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.6] - 2026-04-10

### Added
- Per-subdirectory index pages with breadcrumb navigation when serving directories recursively (`all2md serve --recursive`)
- Batch conversion examples added to CLI help output for discoverability

### Fixed
- PDF conversion crash when PyMuPDF detects empty tables (tables with no cells)
- `view --no-wait` deleting the temp file before the browser could load it

### Changed
- Default document author is now set to "all2md" when not otherwise specified by the source document
- Auto-release CI workflow: tag pushes now run CI checks then publish to PyPI automatically
- Bumped `codecov/codecov-action` from 5 to 6 and `actions/setup-python` from 5 to 6

## [1.0.5] - 2026-04-08

### Added
- `--no-wait` flag for the `view` command for non-interactive use

### Fixed
- Create missing list styles when rendering DOCX with custom templates

## [1.0.4] - 2026-03-25

### Added
- ArXiv submission package generator (`all2md arxiv`) — converts any supported document format into a complete ArXiv-ready LaTeX submission archive (`.tar.gz` or directory) with extracted figures and optional `.bib` bibliography
- Pre-built [Agent Skills](https://agentskills.io) — 6 focused skill files (`all2md-read`, `all2md-convert`, `all2md-generate`, `all2md-grep`, `all2md-search`, `all2md-diff`) that teach AI coding assistants (Claude Code, Cursor, Windsurf) how to use all2md. Install with `all2md install-skills`
- Optional `pymupdf-layout` integration for GNN-based PDF layout analysis — classifies text blocks by semantic role (title, section-header, caption, footnote, etc.) for improved reading order and structure detection. Install with `pip install "all2md[pdf_layout]"`

### Fixed
- CLI renderer options (e.g. `--docx-renderer-template-path`) were silently dropped during format filtering, causing renderer-specific flags to have no effect

## [1.0.3] - 2026-03-16

### Added
- Flow layout engine for Markdown-to-PPTX rendering with template placeholder reuse and inherited built-in styles
- H1-to-Title promotion for Markdown-to-DOCX rendering

### Fixed
- HTML renderer anchor links now use GitHub-style heading IDs (`id="introduction"` instead of `id="introduction-1"`), so `#ref` links resolve correctly
- PPTX flow layout no longer overlaps template placeholders; HTML comments route to speaker notes
- `--collate --out` now writes the target format (e.g. DOCX) instead of raw Markdown
- Sphinx documentation build warning from malformed `.. deprecated::` directive
- Stale mypy `type: ignore` comments across pptx renderer, title promotion transform, and archive parser
- Flaky `test_detect_latin1` marked as `xfail` (chardet Latin-1 detection unreliable across platforms)

### Changed
- Upgraded to Black 26.x and pinned version (`~=26.1`) to prevent CI/local formatting drift
- Pre-commit format-sync hooks now use `uv run` for Windows compatibility
- `options=` accepted as deprecated alias for `parser_options` in `to_markdown()`; unmatched kwargs now warn

## [1.0.2] - 2026-02-27

### Fixed
- PPTX flow layout overlapping template placeholders
- HTML comments in PPTX now route to speaker notes

## [1.0.1] - 2025-12-18

### Added
- Softbreak parsing and DOCX CodeBlock styling support
- Dependency-aware file filtering for shell completions

### Fixed
- Diff CLI args renamed to original/modified for clarity
- CLI processor refactoring and PDF parsing internals split out
- Broken test from CLI help text change
- mypy type issue from merging lost branch

### Changed
- Refactored CLI processors and split PDF parsing internals

## [1.0.0] - 2025-10-29

#### Core Features
- Universal document conversion library supporting bidirectional transformation between various formats and Markdown
- AST-based (Abstract Syntax Tree) pipeline for consistent document manipulation across all formats
- Smart dependency management with format-specific optional dependencies
- Security-conscious design with SSRF protection and archive validation

#### Supported Input Formats (Parse to AST/Markdown)
- **Office Documents**: PDF, DOCX, PPTX, RTF, ODT, ODP, ODS, XLSX
- **Web & Markup**: HTML, MHTML, Markdown, reStructuredText, AsciiDoc, Org-Mode, MediaWiki, Textile, BBCode, DokuWiki
- **Email**: EML, MBOX, MSG (Outlook), PST/OST (Outlook archives)
- **E-books**: EPUB, FB2, CHM
- **Data & Code**: CSV/TSV, Jupyter Notebooks (.ipynb), OpenAPI/Swagger, 200+ source code languages
- **Archives**: ZIP, TAR, 7Z, RAR and other archive formats
- **Other**: LaTeX, plain text

#### Supported Output Formats (Render from AST/Markdown)
- **Markdown**: Multiple flavors (GFM, CommonMark, etc.)
- **Office**: DOCX, PPTX, PDF, ODT, ODP
- **Web**: HTML, RTF
- **Markup**: reStructuredText, AsciiDoc, Org-Mode, MediaWiki, Textile, DokuWiki, LaTeX
- **Data**: CSV, Jupyter Notebooks (.ipynb), AST JSON
- **Templates**: Custom Jinja2 templates for any text-based format
- **Plain text**

#### MCP Server Integration
- Built-in Model Context Protocol (MCP) server for AI assistant integration
- Smart auto-detection of input sources (file paths, data URIs, base64, plain text)
- Section extraction by heading name for targeted reading
- Security features including file allowlists and network controls
- Support for vision-enabled models with base64 image embedding

#### PDF Features
- Advanced table detection and extraction
- Multi-column layout analysis
- Intelligent header/footer removal
- OCR support for scanned documents (via Tesseract)
- Page range selection
- Configurable text extraction powered by PyMuPDF

#### Transform System
- Built-in transforms:
  - `remove-images`: Strip images from documents
  - `remove-nodes`: Remove specific node types
  - `heading-offset`: Adjust heading levels
  - `link-rewriter`: Rewrite URLs with patterns
  - `text-replacer`: Find and replace text content
  - `add-heading-ids`: Generate heading IDs for anchors
  - `remove-boilerplate`: Strip common boilerplate content
  - `add-timestamp`: Add conversion timestamp metadata
  - `word-count`: Add word count metadata
  - `add-attachment-footnotes`: Add footnotes for attachments
- Extensible plugin system for custom transforms via entry points

#### CLI Features
- Multi-file and directory processing with recursive mode
- Parallel execution for batch conversions
- Directory watching for automatic conversion
- stdin/stdout piping support
- Format-specific options exposed as CLI flags
- Progress bars and rich terminal output
- Preset configurations for common workflows
- Transform application from command line

#### Python API
- Simple `to_markdown()` function for quick conversions
- `convert()` function for format-to-format conversion
- `to_ast()` and `from_ast()` for AST manipulation
- Type-safe configuration with dataclass-based options
- Programmatic transform pipeline application
- Direct AST node manipulation for advanced use cases

#### Template System
- Jinja2 template renderer for custom output formats
- Example templates included:
  - DocBook XML
  - YAML metadata
  - ANSI terminal output
  - Custom outlines

#### Developer Features
- Comprehensive test suite with pytest markers (unit, integration, e2e, format-specific)
- Property-based testing with Hypothesis
- Golden/snapshot testing with Syrupy
- Type checking with mypy and custom type stubs
- Code quality enforcement with Ruff
- Pre-commit hooks
- Extensive documentation with Sphinx
- Entry point system for third-party plugins

#### Documentation
- Comprehensive README with examples
- API documentation with Sphinx
- Format-specific guides
- Security and threat model documentation
- Plugin development guide
- MCP server configuration guide
- Transform system documentation
- Contributing guidelines

### Security
- SSRF protection for remote resource fetching
- ZIP bomb detection and prevention
- Path traversal protection in archives
- Network security controls with allowlists/blocklists
- HTML sanitization with configurable policies
- URL validation and sanitization

### Technical Details
- Python 3.10+ required
- Hatchling build backend
- MIT License
- Comprehensive type hints throughout codebase
- NumPy-style docstrings
- Modular architecture with clear separation of concerns

[1.0.6]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.6
[1.0.5]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.5
[1.0.4]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.4
[1.0.3]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.3
[1.0.2]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.2
[1.0.1]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.1
[1.0.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.0
