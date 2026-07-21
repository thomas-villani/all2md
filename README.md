<p align="center">
  <img src="https://raw.githubusercontent.com/thomas-villani/all2md/main/docs/source/_static/logo.svg" alt="all2md logo" width="120" />
</p>

# all2md

**Convert PDFs, Office files, HTML, emails, spreadsheets, and 40+ other formats into clean, LLM-ready Markdown — and back again.**

[![PyPI version](https://img.shields.io/pypi/v/all2md.svg)](https://pypi.org/project/all2md/)
[![CI](https://github.com/thomas-villani/all2md/actions/workflows/ci.yml/badge.svg)](https://github.com/thomas-villani/all2md/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/thomas-villani/all2md/graph/badge.svg)](https://codecov.io/gh/thomas-villani/all2md)
[![Documentation](https://img.shields.io/badge/docs-readthedocs-blue.svg)](https://all2md.readthedocs.io/)
[![License](https://img.shields.io/pypi/l/all2md.svg)](https://opensource.org/licenses/MIT)
[![Python Versions](https://img.shields.io/pypi/pyversions/all2md.svg)](https://pypi.org/project/all2md/)

`all2md` is a Python library **and** command-line tool for turning many document formats into structured, LLM-friendly Markdown — and converting Markdown back into rich formats like DOCX, PDF, and HTML. Built on an AST-based pipeline, it's designed for RAG ingestion, LLM preprocessing, batch automation, and embedding document conversion directly into Python applications.

📦 **[PyPI](https://pypi.org/project/all2md/)** · 📖 **[Documentation](https://all2md.readthedocs.io/)** · 💡 **[Examples](examples/)**

## Quick start

```bash
# Install with PDF support (add more extras as you need them)
pip install "all2md[pdf]"

# Convert any document to Markdown (prints to stdout)
all2md report.pdf > report.md

# Go the other way — Markdown back to a rich format
all2md notes.md --out notes.docx
```

In Python:

```python
from all2md import to_markdown

markdown = to_markdown("report.pdf")
```

That's it. For more formats, install only the extras you need — `all2md[docx,html,xlsx]` — or `all2md[all]` for everything.

## Common use cases

```bash
# Convert a PDF to Markdown for RAG / LLM ingestion
all2md paper.pdf > paper.md

# Batch-convert a directory (recursively) into a folder of Markdown
all2md ./docs --recursive --output-dir ./markdown

# Grep across mixed document types like they were plain text
all2md grep "revenue" reports/*.pdf

# Chunk a document for a RAG pipeline (JSONL with section + page provenance)
all2md chunk handbook.pdf --strategy semantic --max-tokens 512 --overlap 64

# Preview any document in your browser
all2md view proposal.docx

# Turn Markdown (e.g. an LLM's output) back into DOCX, PDF, or PPTX
all2md answer.md --out answer.docx
```

Every file command supports stdin/stdout via `-`, so you can pipe and chain:

```bash
curl -s https://example.com/doc.pdf | all2md - | grep "important"
```

## Why all2md?

- **Clean, LLM-friendly Markdown** for RAG, search, and preprocessing pipelines.
- **Bidirectional** — convert *to* Markdown and *back* to rich formats (DOCX, PDF, PPTX, HTML, EPUB, …).
- **Python-native API** designed for embedding in apps and pipelines, not just CLI usage.
- **A genuinely powerful CLI** — batch conversion, preview, grep, semantic search, diff, and chunking.
- **Lightweight by default** — the core has no dependencies; install only the extras you need.
- **Extensible** — add custom formats and AST transforms via a simple entry-point plugin system.

> Reach for **all2md** when you want a Python-first, automation-friendly document workflow with first-class LLM integration. Reach for **[Pandoc](https://pandoc.org/)** when you need maximum publishing breadth or advanced scholarly output (citations, bibliographies). They complement each other well.

## Who is this for?

- **LLM / RAG builders** — convert source documents into chunkable Markdown with section and page provenance, ready for retrieval.
- **CLI / automation users** — batch-process mixed document collections, watch directories, and pipe conversions into any workflow.
- **Python developers** — embed document parsing and conversion directly into applications with a clean, typed API.
- **Knowledge & documentation workflows** — move content between formats and into portable Markdown, or generate static sites.

## Example output

A PDF research paper in, structured Markdown out — headings, prose, and tables preserved:

```md
# Efficient Retrieval Methods

## Abstract
We study retrieval-augmented generation across a range of...

## 1  Introduction
Retrieval-augmented generation (RAG) combines a retriever with...

| Model | Accuracy | Latency |
|-------|---------:|--------:|
| A     |   91.2%  |   40 ms |
| B     |   93.8%  |   65 ms |
```

Tables, multi-column layouts, and scanned pages (via OCR) are handled by the [advanced PDF parser](#advanced-features). See [`all2md report`](#advanced-features) to score how much to trust any given conversion.

## Supported formats

`all2md` uses a modular system — dependencies are only required for the formats you actually process.

- **Documents:** PDF, DOCX, PPTX, ODT, ODP, RTF, EPUB, FB2, CHM
- **Web & markup:** HTML, MHTML, Markdown, reStructuredText, AsciiDoc, Org-Mode, LaTeX, MediaWiki, Textile, DokuWiki, BBCode
- **Data & spreadsheets:** XLSX, ODS, CSV/TSV, JSON, YAML, TOML, INI, OpenAPI/Swagger
- **Email:** EML, MBOX, Outlook (MSG/PST/OST), Evernote (ENEX)
- **Notebooks & code:** Jupyter (IPYNB), plus 100+ source-code and config file types
- **Archives:** ZIP, TAR, TGZ, 7Z, RAR, and more
- **Custom output:** any text format via Jinja2 templates (DocBook XML, YAML, ANSI, …)

Run `all2md list-formats` to see everything on your install, or browse the [full formats matrix](https://all2md.readthedocs.io/en/latest/formats.html).

<details>
<summary><b>Full format matrix (input / output / required extra)</b></summary>

| Format                        | File Extensions                               | Input (Parse) | Output (Render) | Dependencies Extra |
| ----------------------------- | --------------------------------------------- | :-----------: | :-------------: | ------------------ |
| **PDF**                       | `.pdf`                                        |       ✅       |        ✅      | `pdf`, `pdf_render`|
| **Word Document**             | `.docx`                                       |       ✅       |        ✅      | `docx`             |
| **PowerPoint Presentation**   | `.pptx`                                       |       ✅       |        ✅      | `pptx`             |
| **HTML**                      | `.html`, `.htm`                               |       ✅       |        ✅      | `html`             |
| **MHTML Web Archive**         | `.mhtml`, `.mht`                              |       ✅       |       (N/A)    | `html`             |
| **Email Message**             | `.eml`                                        |       ✅       |       (N/A)    | (built-in)         |
| **MBOX Mailbox Archive**      | `.mbox`, `.mbx`                               |       ✅       |       (N/A)    | (built-in)         |
| **Outlook Message/Archive**   | `.msg`, `.pst`, `.ost`                        |       ✅       |       (N/A)    | `outlook`          |
| **Jupyter Notebook**          | `.ipynb`                                      |       ✅       |        ✅      | (built-in)         |
| **EPUB E-book**               | `.epub`                                       |       ✅       |        ✅      | `epub`             |
| **FictionBook 2.0 (FB2)**     | `.fb2`                                        |       ✅       |       (N/A)    | `fb2`              |
| **CHM (Compiled HTML Help)** | `.chm`                                        |       ✅       |       (N/A)    | `chm`              |
| **OpenDocument Text**         | `.odt`                                        |       ✅       |        ✅      | `odf`              |
| **OpenDocument Presentation** | `.odp`                                        |       ✅       |        ✅      | `odf`              |
| **OpenDocument Spreadsheet**  | `.ods`                                        |       ✅       |       (N/A)    | `odf`              |
| **Excel Spreadsheet**         | `.xlsx`                                       |       ✅       |       (N/A)    | `xlsx`             |
| **CSV / TSV**                 | `.csv`, `.tsv`                                |       ✅       |        ✅      | (built-in)         |
| **Rich Text Format**          | `.rtf`                                        |       ✅       |        ✅      | `rtf`              |
| **LaTeX**                     | `.tex`, `.latex`                              |       ✅       |        ✅      | `latex`            |
| **AsciiDoc**                  | `.adoc`, `.asciidoc`, `.asc`                  |       ✅       |        ✅      | (built-in)         |
| **reStructuredText**          | `.rst`                                        |       ✅       |        ✅      | `rst`              |
| **Org-Mode**                  | `.org`                                        |       ✅       |        ✅      | `org`              |
| **MediaWiki**                 | `.wiki`, `.mw`                                |       ✅       |        ✅      | `wiki`             |
| **Textile**                   | `.textile`                                    |       ✅       |        ✅      | (built-in)         |
| **BBCode**                    | `.bbcode`, `.bb`                              |       ✅       |       (N/A)    | (built-in)         |
| **DokuWiki**                  | `.doku`, `.dokuwiki`                          |       ✅       |        ✅      | (built-in)         |
| **Evernote Export**           | `.enex`                                       |       ✅       |       (N/A)    | `enex`             |
| **Safari Web Archive**        | `.webarchive`                                 |       ✅       |       (N/A)    | `html`             |
| **JSON**                      | `.json`                                       |       ✅       |        ✅      | (built-in)         |
| **YAML**                      | `.yaml`, `.yml`                               |       ✅       |        ✅      | (built-in)         |
| **TOML**                      | `.toml`                                       |       ✅       |        ✅      | (built-in)         |
| **INI / Config**              | `.ini`, `.cfg`, `.conf`                       |       ✅       |        ✅      | (built-in)         |
| **OpenAPI/Swagger**           | `.yaml`, `.yml`, `.json`                      |       ✅       |       (N/A)    | `openapi`          |
| **Plain Text**                | `.txt`, `.text`                               |       ✅       |        ✅      | (built-in)         |
| **Source Code**               | 100+ extensions (`.py`, `.js`, etc.)          |       ✅       |       (N/A)    | (built-in)         |
| **Archive Formats**           | `.tar`, `.tgz`, `.7z`, `.rar`, etc.           |       ✅       |       (N/A)    | (built-in)         |
| **ZIP Archive**               | `.zip`                                        |       ✅       |       (N/A)    | (built-in)         |
| **Jinja2 Templates (Custom)** | User-defined (`.jinja2`, `.j2`)               |       ❌       |        ✅      | `jinja2`           |

> **💡 Custom output formats:** render to any text-based format using Jinja2 templates, no Python required. See the [Template Guide](https://all2md.readthedocs.io/en/latest/templates.html) and [examples/templates/](examples/templates/).

</details>

## Installation

The core library has no dependencies — install support for formats as you need them.

**CLI (system-wide, no Python setup to manage):**

```bash
uv tool install "all2md[all]"
```

**Python library:**

```bash
pip install "all2md[pdf,docx,html]"
```

**Minimal (core only):**

```bash
pip install all2md
```

**Check what format support you have installed:**

```bash
all2md check-deps
```

<details>
<summary><b>Other installation options (one-click scripts, OCR, layout analysis, extras)</b></summary>

**One-click install (no Python setup required).** The scripts set up [uv](https://docs.astral.sh/uv/) (installing it first if needed) and install the `all2md` CLI globally.

macOS / Linux (bash or zsh):

```bash
curl -LsSf https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.ps1 | iex"
```

Both scripts install the `all` extra by default. To slim it down, download the script and pass a comma-separated extras list — `sh install.sh pdf,docx,html` or `.\install.ps1 -Extras pdf,docx,html` (use `none` for a base-only install). The scripts are also attached to each [GitHub release](https://github.com/thomas-villani/all2md/releases).

**Extras for specific needs:**

```bash
# Spreadsheets and ODF documents
pip install "all2md[xlsx,odf]"

# PDF with OCR for scanned documents (Tesseract engine; needs the system binary)
pip install "all2md[pdf,ocr]"

# ...or the binary-free EasyOCR engine (downloads models on first use)
pip install "all2md[pdf,ocr-easyocr]"

# PDF with GNN-based semantic layout analysis
pip install "all2md[pdf_layout]"

# Outlook MSG files
pip install "all2md[outlook]"
# Note: PST/OST support requires an extra manual step: pip install libpff-python

# Everything
pip install "all2md[all]"
```

</details>

## Command-line usage

The essentials:

```bash
all2md document.pdf                       # convert to Markdown on stdout
all2md report.docx --out report.md        # write to a file
all2md notes.md --out notes.docx          # Markdown → rich format (bidirectional)
all2md ./docs -r --output-dir ./out       # recursively batch-convert a directory
all2md document.pdf --rich                # render in the terminal (fancy `cat`)
all2md view document.pdf --theme docs     # HTML preview in the browser
all2md grep "search term" documents/*.pdf # grep through any document format
```

<details>
<summary><b>The full command set (search, chunk, diff, quality scoring, static sites, transforms, config…)</b></summary>

```bash
# View & edit
all2md doc.pdf --rich                 # rich terminal rendering (rcat = shorthand)
all2md view document.pdf              # instant HTML preview in the browser
all2md serve ./docs --recursive       # serve a directory over HTTP with live preview
all2md edit notes.md                  # browser-based Markdown/WYSIWYG editor, saves back

# Extract sections by heading
all2md doc.pdf --extract "Introduction"
all2md view report.docx --extract "Q3 Results"

# Grep and search
all2md grep -i "case insensitive" report.docx
all2md search "machine learning" ./research_papers/
all2md search "project timeline" --semantic ./docs/

# Chunk documents for RAG/LLM pipelines (JSONL with section + page provenance)
all2md chunk report.pdf --strategy semantic --max-tokens 512 --overlap 64

# Conversion quality: score, round-trip, and auto-tune
all2md report scan.pdf                        # reference-free quality "card"
all2md report inbox/*.docx --fail-under 80    # CI gate
all2md roundtrip notes.md --via docx          # convert → parse back → score fidelity
all2md optimize scanned.pdf --sample-pages 5  # auto-tune settings for a hard document

# Diff any two documents (any format), like Unix diff
echo "<p>Version 1</p>" | all2md diff - version2.html

# Package a paper for ArXiv submission
all2md arxiv paper.md -o submission.tar.gz --bib references.bib

# Multi-file, parallel, and watch mode
all2md ./large_docs -r --output-dir ./output -p 4
all2md ./watched_folder -r --output-dir ./output --watch

# Apply AST transforms from the CLI
all2md report.docx -t remove-images
all2md chapter.docx -t "heading-offset --offset 1"
all2md list-transforms

# Static site generation (Hugo, Jekyll, MkDocs, Zola, Eleventy)
all2md generate-site ./content --output-dir ./site --generator hugo --scaffold

# Format-specific options — every option is a CLI flag; run --help to see them
all2md report.pdf --pdf-pages "1-3,5"
all2md scanned.pdf --pdf-ocr-enabled --pdf-ocr-mode auto --pdf-ocr-languages eng
all2md document.docx --attachment-mode save --attachment-output-dir ./images

# Discovery & config
all2md list-formats
all2md config generate > all2md.toml
all2md config validate all2md.toml
```

Speed up repeat runs with the opt-in on-disk cache (`--cache`, or `export ALL2MD_CACHE=1`), which reuses parsed documents across `grep`, `search`, `chunk`, `view`, `report`, `roundtrip`, and `optimize`.

</details>

## Python API

The `to_markdown()` function is the easiest way to get started; `convert()` handles conversions between any two formats.

```python
from all2md import to_markdown, convert

# Convert a file to Markdown
markdown = to_markdown("document.pdf")

# Fine-tune with typed options or plain keyword arguments
markdown = to_markdown("report.pdf", pages="1-3,5", flavor="gfm")

# Bidirectional conversion between any two supported formats
convert("input.md", "output.docx", target_format="docx")
convert("page.html", "page.pdf", target_format="pdf")
```

**Chunking for RAG** — convert and split in one call, keeping provenance most chunkers throw away:

```python
import all2md

chunks = all2md.chunk("report.pdf", strategy="semantic", max_tokens=512, overlap=64)
for c in chunks:
    print(c.chunk_id, c.section_heading, c.page, c.token_count)
    record = c.to_dict()  # flat dict — the same object emitted as JSONL by the CLI
```

<details>
<summary><b>Options objects, working with the AST, and transform pipelines</b></summary>

**Typed options objects** give you type safety and clarity:

```python
from all2md import to_markdown, PdfOptions, MarkdownRendererOptions

pdf_opts = PdfOptions(pages="1-3,5", attachment_mode="base64")
md_opts = MarkdownRendererOptions(flavor="gfm", emphasis_symbol="_")
markdown = to_markdown("report.pdf", parser_options=pdf_opts, renderer_options=md_opts)

# Scanned PDF with OCR (engine="tesseract" default, or "easyocr" for binary-free)
from all2md.options.common import OCROptions
ocr_opts = OCROptions(enabled=True, mode="auto", engine="tesseract", languages="eng", dpi=300)
markdown = to_markdown("scanned.pdf", parser_options=PdfOptions(ocr=ocr_opts))
```

**Working with the AST** for advanced processing:

```python
from all2md import to_ast, from_ast
from all2md.ast import Heading, Text

doc = to_ast("document.pdf")                                   # parse to AST
doc.children.insert(0, Heading(level=1, content=[Text(content="New Title")]))
markdown = from_ast(doc, target_format="markdown")             # render back out
```

**Transform pipelines** for systematic modification:

```python
from all2md import to_ast
from all2md.transforms import render, HeadingOffsetTransform, RemoveImagesTransform

doc = to_ast("report.docx")
markdown = render(doc, transforms=[
    RemoveImagesTransform(),          # an instance
    "add-heading-ids",                # a registered name
    HeadingOffsetTransform(offset=1), # an instance with parameters
])
```

Real BPE token counting for chunking uses `tiktoken` (`pip install all2md[chunk]`); count-only strategies fall back to a whitespace approximation. See the [API documentation](https://all2md.readthedocs.io/) for the full reference and more examples under [examples/python/](examples/python/).

</details>

## AI integrations

all2md is built to sit inside LLM and agent workflows.

- **RAG-native chunking** — `all2md chunk` (and `all2md.chunk()`) split any document into retrieval-ready chunks, each carrying its **section heading/level** and **source page span** so answers can cite where they came from. 11 strategies (semantic/heading/section/token/sentence/paragraph/word/line/char/code/auto); keep tables and code blocks whole; strip noisy elements.
- **MCP server** — a built-in [Model Context Protocol](https://modelcontextprotocol.io/) server lets AI assistants like Claude read, convert, search, diff, and outline documents directly. No wrapper scripts needed.
- **Agent skills** — pre-built skill files that teach AI coding assistants (Claude Code, Cursor, Windsurf, …) how to use all2md. Install with `all2md install-skills`, or get the same guidance without installing anything via `all2md llm-help [topic]`.

<details>
<summary><b>MCP server setup (Claude Desktop one-click + manual config)</b></summary>

```bash
pip install "all2md[mcp]"
all2md-mcp --temp --enable-from-md
```

**Tools:** `read_document_as_markdown`, `save_document_from_markdown`, `edit_document`, plus three read-only query tools enabled by default — `search_documents` (grep + keyword/BM25 across a corpus), `diff_documents`, and `get_document_outline`.

**One-click install (Claude Desktop).** Install the prebuilt MCPB bundle — no manual config or separate Python install required (the bundle pulls in all2md via `uv` on first run):

1. Download `all2md.mcpb` from the [latest release](https://github.com/thomas-villani/all2md/releases/latest).
2. Open **Claude Desktop → Settings → Extensions**.
3. **Drag `all2md.mcpb` onto the Extensions pane** (or use **Install Extension** to browse for it).
4. In the install dialog, choose a **workspace folder** all2md may read from and write to, and adjust the toggles for writing/rendering, in-place editing, and network access.
5. The all2md tools then appear under the **"+" → Connectors** panel in a chat.

> Requires a Claude Desktop build with MCPB extension support (late-2025 or newer). To rebuild the bundle yourself, see [`mcpb/README.md`](mcpb/README.md).

**Manual configuration (developers / other MCP clients)** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "all2md": {
      "command": "all2md-mcp",
      "args": ["--temp", "--enable-from-md"]
    }
  }
}
```

See the [MCP documentation](https://all2md.readthedocs.io/en/latest/mcp.html) and [Agent Skills documentation](https://all2md.readthedocs.io/en/latest/agent_skills.html) for full details.

</details>

## Advanced features

Built on an **AST-based pipeline** (parse → transform → render), all2md offers capabilities that direct format-to-format converters can't:

- **Advanced PDF parsing** — intelligent table detection, multi-column layout analysis, optional GNN-based semantic layout classification (`pdf_layout` extra), header/footer removal, and OCR for scanned documents (Tesseract or binary-free EasyOCR), powered by PyMuPDF.
- **Conversion quality tooling** — `all2md report` gives a reference-free confidence "quality card" for any document (usable as a CI gate); `all2md roundtrip` scores how much structure survives a `convert → parse-back` round trip; `all2md optimize` auto-tunes converter settings for a difficult document.
- **Document diff** — a `diff` command that works like Unix `diff` but across any document formats, with text-based symmetric comparison.
- **Custom output via templates** — render the AST to any text format (DocBook XML, YAML, ANSI, custom markup) using Jinja2 templates, no Python required.
- **Static site generation** — turn document collections into ready-to-deploy Hugo, Jekyll, MkDocs, Zola, or Eleventy sites.
- **Extensible plugin system** — add custom converters (`all2md.converters` entry point) and transforms (`all2md.transforms` entry point). See [examples/plugins/](examples/plugins/).
- **Security-conscious** — SSRF protection when fetching remote resources, archive validation (ZIP bombs, path traversal), and sandboxed HTML rendering.

## Frequently asked questions

**How is all2md different from Pandoc?**
all2md is Python-native, with a focus on programmatic use, LLM integration, and extensibility. Pandoc is more comprehensive for scholarly documents but is Haskell-based and CLI-focused. Use all2md for Python projects and AI workflows; use Pandoc for academic publishing — they complement each other well.

**Can I convert back from Markdown to Word/PDF?**
Yes — all2md is bidirectional. Use `convert("input.md", "output.docx", target_format="docx")`, or the CLI: `all2md input.md --out output.pdf`.

**What's the best format for feeding documents to LLMs?**
Markdown with the `gfm` (GitHub Flavored Markdown) flavor — structured, consistent, and well-understood by LLMs. Use `to_markdown(file, flavor="gfm")`.

**Does all2md work with scanned PDFs?**
Yes. Install OCR support (`pip install "all2md[pdf,ocr]"`) and use `--pdf-ocr-enabled` (or `OCROptions(enabled=True)`). The default Tesseract engine needs the Tesseract binary; the binary-free EasyOCR engine is available via `all2md[pdf,ocr-easyocr]` and `--pdf-ocr-engine easyocr`.

**Can I customize the output beyond Markdown?**
Yes — use Jinja2 templates to render any text-based format. See [examples/templates/](examples/templates/) for DocBook XML, YAML, ANSI terminal output, and more.

**How do I add support for a new file format?**
Create a parser class, define a `ConverterMetadata` object, and register it via the `all2md.converters` entry point in your `pyproject.toml`. See [examples/plugins/](examples/plugins/) for a complete example.

**How do I handle large document batches efficiently?**
Use parallel processing: `all2md ./docs -r --output-dir ./output -p 8`, or `--watch` for incremental processing as files arrive.

## Getting help

- **Documentation:** [Read the full docs on ReadTheDocs](https://all2md.readthedocs.io/)
- **Examples:** Browse the [examples/](examples/) directory, organized by use case
- **Issues:** Report bugs or request features on [GitHub Issues](https://github.com/thomas-villani/all2md/issues)

## Contributing

Contributions are welcome — bug reports, feature requests, documentation improvements, and code. Ways to help: report bugs, improve docs, add support for new formats via the plugin system, create new AST transforms, or fix bugs in existing converters.

For contributors evaluating parser changes, all2md ships benchmark harnesses in [`benchmarks/corpus/`](benchmarks/corpus/) (times conversion across public document corpora) and [`benchmarks/roundtrip/`](benchmarks/roundtrip/) (checks `Markdown → AST → Markdown` fidelity). See the [Performance Tuning docs](https://all2md.readthedocs.io/en/latest/performance.html) for details.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

This project is licensed under the MIT License. See the [`LICENSE`](LICENSE) file for details.
