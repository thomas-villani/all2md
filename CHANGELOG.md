# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `all2md grep` command improvements:
  - `-i/--ignore-case` flag for case-insensitive matching (default: case-sensitive)
  - `-n/--line-number` flag to show line numbers for matching lines
  - `-M/--max-columns` option to control maximum display width for long lines (default: 150)
  - Intelligent line truncation that shows context around first match when lines are too long
  - Clean plain text output with highlighting markers removed (only shown in `--rich` mode)

### Changed
- Reduced grep line truncation context from 80 to 40 characters for more concise output
- Updated `all2md search` command to support `-i/--ignore-case` flag in grep mode

### Fixed

## [1.0.0] - 2025-10-29

### Added

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
- Python 3.12+ required
- Hatchling build backend
- MIT License
- Comprehensive type hints throughout codebase
- NumPy-style docstrings
- Modular architecture with clear separation of concerns

[1.0.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.0
