# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `all2md serve` now auto-renders an `index.html`, `index.htm`, `index.md`, or `README.md` (case-insensitive, priority order) from the served directory through the active theme instead of the generated file listing. Applies to every directory the server can reach, including subdirectories in `--recursive` mode. New `--force-auto-index` flag opts back into the generated listing.
- `all2md serve` directory mode now picks up newly added, removed, and modified files automatically via a background polling thread. New `--poll-interval SECONDS` flag (default `2.0`, set `0` to disable) controls the rescan cadence; on detected change the cached index page is invalidated and stale file-cache entries for vanished files are dropped.

### Changed
- `all2md serve` now handles requests on per-connection threads (`ThreadingHTTPServer`), so a slow conversion no longer blocks other visitors.

### Fixed
- `all2md serve` Ctrl+C shutdown was previously delayed until the next inbound request arrived to unblock `select()` on Windows. The server now runs `serve_forever()` in a background daemon thread and the main thread reacts to SIGINT immediately, calling `httpd.shutdown()` for a prompt clean exit.

## [1.1.1] - 2026-05-15

### Added
- New PDF parsing options for handling brittle real-world layouts: `min_image_dimension` (filter decorative artifacts under a pixel threshold), `filter_header_footer_images` (drop images sitting inside detected page-header/footer bands), `collapse_excess_whitespace` (collapse long whitespace runs that PDF spans use as layout padding), `dedup_running_headings` (merge split numbering-prefix headings like `"I."` + `"Background"` into `"I. Background"`), and `annotate_rotated_text` (opt-in `*[rotated 90° counter-clockwise]*` marker; default off).
- DOCX round-trip formatting preservation. `to_ast`/`from_ast`/`from_markdown`/`convert` accept a new `preserve_formatting` kwarg, and `all2md edit` gains a `--preserve-formatting` flag (on by default for `.docx` → `.docx`; pass `--no-preserve-formatting` to opt out). Round-tripping a `.docx` through Markdown now keeps page setup, theme, headers/footers, and named paragraph styles instead of collapsing them to defaults. The parser stashes `paragraph.style.name` on AST nodes via `metadata['source_style']`, and the renderer re-applies it when the template defines the style — so custom paragraph styles like "Chapter Title" survive instead of degrading to "Heading 1". `to_ast` auto-stashes `Document.metadata['source_path']` for file-path inputs so the original document can be reused as a rendering template. Out of scope: run-level character styles still collapse on round-trip (tracked separately).
- `DocxRendererOptions.clear_template_body` (default `False`) — gates whether a loaded `template_path` keeps its body content (letterhead use case) or has it stripped before the AST is rendered (round-trip use case). Section properties, headers/footers, and style definitions are always preserved.
- Corpus benchmark harness under `benchmarks/corpus/` — pulls deterministic samples from arxiv, PubMed Central, govdocs1, Apache POI, and Enron, times conversion, and emits a stratified Markdown report. Companion `inspect` command saves converted Markdown next to the source for manual quality review on the slowest, largest, and random subsets. See `benchmarks/corpus/README.md` and the new "Corpus Benchmark Harness" section in `docs/source/performance.rst`.
- Manual-dispatch GitHub Actions workflow (`.github/workflows/benchmark.yml`) that runs the corpus harness on a clean `ubuntu-latest` VM, caches the ~1 GB corpus between runs, and uploads results as a 90-day workflow artifact. Use for reproducible perf numbers when the local dev box is too noisy.
- Benchmark CLI ergonomics: `purge` subcommand to delete the ~1 GB corpus cache, `--purge-after` flag for post-run cleanup (CI / ephemeral disks), and `--use-layout-model` to opt back into the optional `pymupdf-layout` ONNX classifier — off by default in the benchmark for reproducibility across machines.
- Reference benchmark snapshots under `benchmarks/reference/` — committed before/after `.md` + `.json` reports (`b0e4224-baseline`, `3516bc9-optimized`) that anchor the performance numbers cited in the docs.
- New documentation page `docs/source/optimizations.rst` walking through the v1.1.1 PDF performance work: methodology (corpus benchmark + cProfile + inspect), headline numbers, the 000887.pdf case study (5.6 min → 11.65 s), per-commit attribution, and a "what's still slow" section.

### Changed
- PDF table detection in the default mode now skips PyMuPDF's `find_tables()` on pages with no ruling-line drawings or large closed rectangles. Avoids ~1s/page of wasted work on prose-only pages where `find_tables()` would either return nothing useful or fire on decorative frames that downstream guards already reject. Net impact on the 149-doc corpus benchmark: 21.4 min → 6.7 min total (3.2x faster); PDF p50 8.5s → 728ms (12x); the slowest single file 5.6 min → 11.65 s (28x). The new `page_has_table_signals()` helper is conservative on error (returns True / runs `find_tables`) so PyMuPDF quirks can't silently lose real tables. `table_detection_mode="pymupdf"` is unchanged — explicit opt-in to always-run behavior. See `docs/source/optimizations.rst` for the full writeup.
- `image_placement_markers` no longer applies when `attachment_mode="alt_text"` (the default). Markers had no URL to target in that mode, so `![Image from page N]()` placeholders were just noise. The option now only takes effect in `save` and `base64` modes. As a side effect, image-heavy PDFs in the default mode also skip pixmap decoding entirely (≈160 decodes avoided on a typical 32-page workshop PDF).
- DOCX rendering re-applies parser-stashed `source_style` paragraph styles when the template defines them, rather than always falling back to built-in heading mapping.
- `DocxRendererOptions` field order: `network` moved to the end so the auto-generated options docs read in a more natural order. All fields remain keyword-friendly with defaults.

### Fixed
- PDF heading detection misclassified the body=11pt / header=12pt convention as body text (the 1.2 size-ratio default produced an empty `header_id`), silently ignored bold-only header styles, and classified mixed-style lines by `spans[0]` only. Spans are now aggregated per line and style requirements are enforced.
- PDF rotated text flooded output with one `*[rotated 90° counter-clockwise]*` marker per line (~280 markers on the "Attention Is All You Need" figure-axis labels). Consecutive rotated spans are now grouped within blocks and merged across blocks via metadata, and the annotation is opt-in via the new `annotate_rotated_text` option.
- PDF table detection fired on TOC dot-leader regions, decorative frames, and oversized empty grids in both PyMuPDF's `find_tables()` and the ruling-line fallback. Shared size, sparsity, uniformity, and dot-leader-ratio guards now reject pathological detections in both paths rather than emitting them as garbage tables.
- PDF `attachment_mode="alt_text"` emitted 100+ empty `![Image from page N]()` placeholders on image-heavy documents. `extract_page_images()` now returns early in `alt_text` mode (suppresses the placeholders and avoids decoding every pixmap only to throw the bytes away).
- Tiny decorative PDF images (logo strokes, signature artifacts) and images sitting inside detected page-header/footer regions are no longer emitted as ghost markers — see the new `min_image_dimension` and `filter_header_footer_images` options.

## [1.1.0] - 2026-05-01

### Added
- `all2md edit FILE` command — launches a local web-based editor (Toast UI Editor v3.2.2 with Markdown and WYSIWYG modes) pre-loaded with any supported document converted to Markdown. Saves back to disk in any installed target format, with automatic `.bak` creation when overwriting. For `.md` sources the default save target is the original file (overwrite enabled); for any other format the default target is a sibling `.md` file (overwrite disabled). Toast UI assets are vendored under `themes/assets/` and served from `/assets/` with a strict allow-list.
- Linter v2: 27 new rules across three new categories and four expanded ones, bringing the total to 47 built-in rules. New categories: **LST** (lists), **TBL** (tables), **IMG** (images). Expanded categories: STR (`short-section`, `empty-document`, `excessive-nesting`), HDG (`heading-as-sentence`, `heading-url`), LNK (`insecure-link`, `link-text-is-url`), TYP (`ellipsis-character`, `space-before-punctuation`, `consecutive-punctuation`).
- Auto-fix framework: `all2md lint --fix` applies safe auto-fixes in place. Seven rules ship with safe fixes attached: TYP001 (trailing-spaces), TYP002 (multiple-spaces), TYP003 (straight-quotes), TYP004 (double-hyphens), TYP006 (ellipsis-character), TYP007 (space-before-punctuation), and STR004 (empty-heading).
- `--dry-run` flag for `lint --fix`: report what would be changed without writing the file.
- Public API: `all2md.linter.lint_and_fix_document()`, `lint_and_fix_file()`, `LintFixResult`, `LintFix`, `FixSafety`, `FixContext`, `apply_fixes`.
- Reporters now surface auto-fix results: the text reporter prints per-file `applied N fix(es)` plus deferred-conflict counts; the JSON reporter adds `applied_fixes`, `skipped_fixes`, `pre_fix_violations`, and `rewritten` keys per result entry.

### Changed
- `Violation.fixable` is now a derived `@property` (`fix is not None`) rather than a stored field. Code that constructs `Violation(..., fixable=True)` will need to pass a `LintFix` instead.
- `LintRule.build_violation()` accepts an optional `fix=` keyword to attach a `LintFix` to a violation.

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
