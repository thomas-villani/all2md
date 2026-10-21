<p align="center">
  <img src="https://raw.githubusercontent.com/thomas-villani/all2md/main/docs/source/_static/logo.svg" alt="all2md logo" width="120" />
</p>

# all2md

**Read, convert, search, and chunk PDFs, Office files, e-books, emails, and 40+ other formats, as Markdown and back again. From Python, from your terminal, or from your AI assistant.**

[![PyPI version](https://img.shields.io/pypi/v/all2md.svg)](https://pypi.org/project/all2md/)
[![Python Versions](https://img.shields.io/pypi/pyversions/all2md.svg)](https://pypi.org/project/all2md/)
[![CI](https://github.com/thomas-villani/all2md/actions/workflows/ci.yml/badge.svg)](https://github.com/thomas-villani/all2md/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/thomas-villani/all2md/graph/badge.svg)](https://codecov.io/gh/thomas-villani/all2md)
[![Documentation](https://readthedocs.org/projects/all2md/badge/?version=latest)](https://all2md.readthedocs.io/)
[![License](https://img.shields.io/pypi/l/all2md.svg)](https://opensource.org/licenses/MIT)
<br>
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Downloads](https://static.pepy.tech/badge/all2md/month)](https://pepy.tech/project/all2md)
[![MCP server](https://img.shields.io/badge/MCP-server-6E56CF)](https://all2md.readthedocs.io/en/latest/mcp.html)
[![GitHub Action](https://img.shields.io/badge/GitHub_Action-quality_gate-2088FF?logo=githubactions&logoColor=white)](https://all2md.readthedocs.io/en/latest/github_action.html)

<p align="center">
  <img src="https://raw.githubusercontent.com/thomas-villani/all2md/main/docs/source/_static/read-demo.gif" alt="all2md read showing a Word document in the terminal, with an outline, a table, code and a list of links" width="900" />
</p>

<p align="center"><i>A Word document, read in the terminal with <code>all2md read</code>.</i></p>

## Try it in ten seconds

With [uv](https://docs.astral.sh/uv/) there is nothing to install first:

```bash
uvx --from "all2md[all]" rcat report.pdf          # read any document in the terminal
uvx --from "all2md[all]" all2md report.docx       # print it as Markdown
```

Keep it around as a tool, with `all2md`, `rcat` and the `all2md-mcp` server on your `PATH`:

```bash
uv tool install "all2md[all]"
```

Or use it as a library:

```bash
uv add "all2md[pdf,docx]"      # or: pip install "all2md[pdf,docx]"
```

```python
from all2md import to_markdown

markdown = to_markdown("report.pdf")
```

## Pick your path

| I want to… | Start with | Read |
| --- | --- | --- |
| Read documents without leaving the terminal | `rcat report.docx`, `all2md read docs/` | [Read in the terminal](#read-documents-in-your-terminal) |
| Convert files, one or a thousand, in either direction | `all2md ./inbox -r --output-dir ./md` | [Convert](#convert-documents-from-the-command-line) |
| Parse documents in my Python code | `to_markdown("report.pdf")` | [Python API](#python-api) |
| Find text inside PDFs, Word files and slide decks | `all2md grep "deadline" contracts/ -r` | [Search](#search-inside-any-document) |
| Feed documents to a RAG pipeline | `all2md chunk handbook.pdf` | [RAG and chunking](#rag-and-chunking) |
| Let Claude or another assistant work with my files | the one-click Claude Desktop extension | [AI assistants (MCP)](#give-your-ai-assistant-your-documents) |
| Know how far to trust the output | `all2md report scan.pdf` | [Measured fidelity](#measured-fidelity) |

## Read documents in your terminal

`rcat` is `cat` for documents. It renders PDFs, Word and PowerPoint files (the 97-2003 `.doc` and `.ppt` too), spreadsheets, e-books, emails, notebooks, man pages and every other format all2md reads, with headings, tables, syntax-highlighted code, links with their targets, footnotes, math and admonitions. No browser, no office suite, and it works over SSH. If you reach for [glow](https://github.com/charmbracelet/glow) to read Markdown or [doxx](https://github.com/bgreenwell/doxx) to read Word files, `rcat` is the same idea for every format.

```bash
rcat report.docx                              # read a Word document
rcat deck.pptx --outline                      # just the slide titles
rcat handbook.pdf --extract "Installation"    # one section, by heading
rcat contract.pdf --pager                     # page through it
curl -sL https://example.com/spec.pdf | rcat -
```

For anything longer, `all2md read` (or `rcat -i`) opens the interactive viewer shown above: an outline beside the text, jumps between headings, the links on screen, and, given a folder, a tree of the documents in it.

```bash
all2md read handbook.pdf
all2md read docs/            # choose from the documents in a folder
```

When you would rather have a browser, `all2md view report.docx` opens a styled HTML preview, `all2md serve ./docs -r` serves a whole folder with on-demand conversion, and `all2md edit notes.md` opens a browser editor that saves back to the file.

Styling needs the `cli_extras` extra and the viewer needs `tui`; `all2md[all]` includes both. More in the [viewer documentation](https://all2md.readthedocs.io/en/latest/viewer.html).

## Convert documents from the command line

Any supported format to Markdown, and Markdown back to DOCX, PDF, PPTX, HTML, EPUB and more:

```bash
all2md report.pdf > report.md                     # to Markdown on stdout
all2md answer.md --out answer.docx                # Markdown (an LLM's output, say) to Word
all2md ./inbox -r --output-dir ./markdown -p 4    # a whole tree, four at a time
all2md ./inbox -r --output-dir ./markdown --watch # keep converting as files arrive
all2md scan.pdf --pdf-ocr-enabled                 # scanned pages, through OCR
```

Every option of every converter is a CLI flag (`all2md --help`) or a key in a config file (`all2md config generate`). Every file command reads stdin and writes stdout with `-`, so all2md slots into pipelines. Word documents come out as Word shows them: tracked changes resolved by policy, comments with their anchors, footnotes, field results, merged cells, and the list numbers Word actually prints.

See the [CLI reference](https://all2md.readthedocs.io/en/latest/cli.html) and the [cheat sheet](https://all2md.readthedocs.io/en/latest/cheatsheet.html).

## Python API

`to_markdown()` handles the common case; `convert()` goes between any two formats; `to_ast()` gives you the parsed document to work with.

```python
from all2md import to_markdown, convert, to_ast, from_ast

markdown = to_markdown("report.pdf", pages="1-3", flavor="gfm")
convert("notes.md", "notes.docx", target_format="docx")

doc = to_ast("report.docx")          # a typed document tree
html = from_ast(doc, target_format="html")
```

The core has no dependencies; each format's extra pulls in only what that format needs. Options are typed dataclasses (`PdfOptions`, `DocxOptions`, …) or plain keyword arguments, and AST transforms (`remove-images`, `heading-offset`, your own) slot in between parsing and rendering. New formats and transforms plug in through entry points.

If you are an LLM with a coding environment, `all2md llm-help` prints usage guidance written for you, and `all2md install-skills` installs it as a skill for Claude Code, Cursor and others.

See the [Python API guide](https://all2md.readthedocs.io/en/latest/python_api.html), the [AST guide](https://all2md.readthedocs.io/en/latest/ast_guide.html), and [examples/python](https://github.com/thomas-villani/all2md/tree/main/examples/python).

## Search inside any document

`grep` doesn't look inside a PDF or a `.docx`. `all2md grep` does, across any mix of formats, with the usual flags:

```bash
all2md grep -i "termination" contracts/ -r            # every format in the tree
all2md grep -C 2 "deadline" contracts/ -r --rich      # with context, highlighted
all2md search "renewal terms" ./contracts --keyword   # ranked BM25 search
all2md search "who approved the budget" ./minutes --hybrid
all2md diff draft-v1.docx draft-v2.pdf                # a colored diff, across formats
```

Vector and hybrid search need the `search` extra. Add `--cache` (or `ALL2MD_CACHE=1`) to reuse parsed documents across repeated runs.

## RAG and chunking

`all2md chunk` converts and splits in one step. Each chunk carries its section heading and source page span, so answers can cite where they came from.

```bash
all2md chunk handbook.pdf --strategy semantic --max-tokens 512 --overlap 64 > chunks.jsonl
```

```python
import all2md

for c in all2md.chunk("handbook.pdf", strategy="semantic", max_tokens=512, overlap=64):
    print(c.chunk_id, c.section_heading, c.page, c.token_count)
```

There are 11 strategies (semantic, heading, section, token, sentence, paragraph, code, …). Tables and code blocks are kept whole, and the output is JSONL ready for any vector store. Real token counts use `tiktoken` from the `chunk` extra. See the [chunk command](https://all2md.readthedocs.io/en/latest/cli.html#chunk-command).

## Give your AI assistant your documents

all2md ships a [Model Context Protocol](https://modelcontextprotocol.io/) server, so an assistant like Claude can read your PDFs and Office files, write Word documents, edit them in place, search a folder, and compare two versions. You don't need to write any code.

**In Claude Desktop** (no Python or terminal needed):

1. Download `all2md.mcpb` from the [latest release](https://github.com/thomas-villani/all2md/releases/latest).
2. Open **Claude Desktop → Settings → Extensions** and drag the file onto the page.
3. Choose the folder all2md may work in, and whether it may write files.
4. Ask Claude about the documents in that folder.

<details>
<summary><b>Other MCP clients, and the developer configuration</b></summary>

The server is in the [MCP Registry](https://registry.modelcontextprotocol.io/) as `io.github.thomas-villani/all2md`. To run it yourself, use `uvx` (nothing to install):

```json
{
  "mcpServers": {
    "all2md": {
      "command": "uvx",
      "args": ["--from", "all2md[all]", "all2md-mcp", "--temp", "--enable-from-md"]
    }
  }
}
```

or install it with `uv tool install "all2md[mcp]"` and use `"command": "all2md-mcp"`. The `[mcp]` extra covers PDF, Word, PowerPoint, Excel, HTML, EPUB, ODF and reStructuredText; use `[all]` for everything.

**Tools:** `read_document_as_markdown`, `save_document_from_markdown`, `edit_document`, plus the read-only `search_documents`, `diff_documents` and `get_document_outline`.

See the [MCP documentation](https://all2md.readthedocs.io/en/latest/mcp.html) for the options and the security model.

</details>

<!-- mcp-name: io.github.thomas-villani/all2md -->

## Measured fidelity

all2md's conversion quality is measured against independent ground truth, not asserted. Each benchmark lane is published with a control that shows what the measurement looks like when it *should* fail:

- **Born-digital PDFs:** publisher PDFs from PubMed Central, scored against the JATS XML deposited beside them.
- **Scanned pages:** 981 OmniDocBench pages against human annotation, for the OCR path.
- **Round trips:** Markdown → format → Markdown must hold fidelity 100 for this repository's own docs, on every pull request.

Against other converters, on a sealed holdout of 103 PubMed Central articles scored with the same instruments (reading of 2026-08-29):

| | all2md | pymupdf4llm 1.28.2 | Docling 2.120.3 |
| --- | ---: | ---: | ---: |
| Recall of attainable text | **97.3%** | 97.1% | 96.2% |
| Invented text (lower is better) | **0.55%** | 6.26% | 2.05% |
| Table text preserved | 73.1% | 60.7% | **79.3%** |

Docling's learned table model still leads on tables. The [comparison lane](https://github.com/thomas-villani/all2md/tree/main/benchmarks/comparison) has the full results, the ground rules, and the caveats that bound them. [Conversion Fidelity](https://all2md.readthedocs.io/en/latest/benchmarks.html) has the rest.

You can measure your own documents the same way:

```bash
all2md report scan.pdf                        # a reference-free "quality card"
all2md roundtrip notes.md --via docx          # convert, parse back, score what survived
all2md optimize hard.pdf --sample-pages 5     # auto-tune the settings for a difficult file
```

### CI quality gate

The same scores run as a GitHub Action, which fails the build when your documents stop converting cleanly:

```yaml
- uses: thomas-villani/all2md@v1.17.0
  with:
    paths: docs/**/*.md
    roundtrip-fail-under: 97
```

It fails rather than passing quietly when no files match, no threshold is set, or a document cannot be converted at all, and it warns when a threshold sits so far below your real floor that it could never fire. See the [action's documentation](https://all2md.readthedocs.io/en/latest/github_action.html).

## Supported formats

- **Documents:** PDF, DOCX, DOC, PPTX, PPT, ODT, ODP, RTF, EPUB, FB2, CHM
- **Web & markup:** HTML, MHTML, Markdown, reStructuredText, AsciiDoc, Org-Mode, LaTeX, MediaWiki, Textile, DokuWiki, BBCode, man pages
- **Data & spreadsheets:** XLSX, ODS, CSV/TSV, JSON, YAML, TOML, INI, OpenAPI/Swagger
- **Email:** EML, MBOX, Outlook (MSG/PST/OST), Evernote (ENEX)
- **Notebooks & code:** Jupyter, plus nearly 200 source-code and config file types
- **Archives:** ZIP, TAR, 7Z, RAR and more; `.gz`, `.bz2` and `.xz` convert as the file they hold
- **Custom output:** any text format through Jinja2 templates

<details>
<summary><b>Full format matrix (input / output / required extra)</b></summary>

| Format                        | File Extensions                               | Input (Parse) | Output (Render) | Dependencies Extra |
| ----------------------------- | --------------------------------------------- | :-----------: | :-------------: | ------------------ |
| **PDF**                       | `.pdf`                                        |       ✅       |        ✅      | `pdf`, `pdf_render`|
| **Word Document**             | `.docx`                                       |       ✅       |        ✅      | `docx`             |
| **Word 97-2003 Document**     | `.doc`, `.dot`                                |       ✅       |       (N/A)    | (built-in)         |
| **PowerPoint Presentation**   | `.pptx`                                       |       ✅       |        ✅      | `pptx`             |
| **PowerPoint 97-2003**        | `.ppt`, `.pps`, `.pot`                        |       ✅       |       (N/A)    | (built-in)         |
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
| **Man Page (man(7))**         | `.1` to `.9`, `.man`                          |       ✅       |        ✅      | (built-in)         |
| **Evernote Export**           | `.enex`                                       |       ✅       |       (N/A)    | `enex`             |
| **Safari Web Archive**        | `.webarchive`                                 |       ✅       |       (N/A)    | `html`             |
| **JSON**                      | `.json`                                       |       ✅       |        ✅      | (built-in)         |
| **YAML**                      | `.yaml`, `.yml`                               |       ✅       |        ✅      | (built-in)         |
| **TOML**                      | `.toml`                                       |       ✅       |        ✅      | (built-in)         |
| **INI / Config**              | `.ini`, `.cfg`, `.conf`                       |       ✅       |        ✅      | (built-in)         |
| **OpenAPI/Swagger**           | `.yaml`, `.yml`, `.json`                      |       ✅       |       (N/A)    | `openapi`          |
| **Plain Text**                | `.txt`, `.text`                               |       ✅       |        ✅      | (built-in)         |
| **Source Code**               | nearly 200 extensions (`.py`, `.js`, etc.)    |       ✅       |       (N/A)    | (built-in)         |
| **Archive Formats**           | `.tar`, `.tgz`, `.7z`, `.rar`, etc.           |       ✅       |       (N/A)    | (built-in)         |
| **Single Compressed File**    | `.gz`, `.bz2`, `.xz` (e.g. `ls.1.gz`)         |       ✅       |       (N/A)    | (built-in)         |
| **ZIP Archive**               | `.zip`                                        |       ✅       |       (N/A)    | (built-in)         |
| **Jinja2 Templates (Custom)** | User-defined (`.jinja2`, `.j2`)               |       ❌       |        ✅      | `jinja2`           |

Run `all2md list-formats` to see what your install supports, or browse the [formats documentation](https://all2md.readthedocs.io/en/latest/formats.html).

</details>

## Installation

| You are… | Install |
| --- | --- |
| Using the CLI and viewer | `uv tool install "all2md[all]"` |
| Trying it once | `uvx --from "all2md[all]" rcat FILE` |
| Building with the library | `uv add "all2md[pdf,docx,html]"` or `pip install "all2md[pdf,docx,html]"` |
| Running the MCP server | the Claude Desktop extension above, or `uv tool install "all2md[mcp]"` |

`all2md check-deps` shows which formats your install can handle.

<details>
<summary><b>One-click install scripts, OCR, layout analysis and other extras</b></summary>

**Install scripts.** These set up [uv](https://docs.astral.sh/uv/) (installing it if needed) and install the CLI globally with the `all` extra.

```bash
# macOS / Linux
curl -LsSf https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.sh | sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.ps1 | iex"
```

To slim it down, download the script and pass the extras you want: `sh install.sh pdf,docx,html` or `.\install.ps1 -Extras pdf,docx,html`.

**Extras for specific needs:**

```bash
uv add "all2md[cli_extras]"     # terminal styling for --rich / rcat, progress bars, watch mode
uv add "all2md[tui]"            # the interactive viewer, all2md read
uv add "all2md[pdf,ocr]"        # OCR for scanned PDFs (Tesseract; needs the system binary)
uv add "all2md[pdf,ocr-easyocr]" # ...or binary-free EasyOCR (downloads models on first use)
uv add "all2md[pdf_layout]"     # ML layout analysis for difficult PDFs
uv add "all2md[search]"         # vector and hybrid search
uv add "all2md[chunk]"          # real token counts for chunking
uv add "all2md[outlook]"        # Outlook MSG (PST/OST also need: pip install libpff-python)
```

See the [installation guide](https://all2md.readthedocs.io/en/latest/installation.html) for the full list.

</details>

## FAQ

**How is all2md different from Pandoc?**
all2md is Python-native and built for programmatic use, LLM pipelines and reading documents in the terminal. Pandoc has more publishing breadth and scholarly features such as citations. They complement each other well.

**Does it work with scanned PDFs?**
Yes. Install `all2md[pdf,ocr]` (or `ocr-easyocr` for no system binary) and pass `--pdf-ocr-enabled`. `all2md report` tells you when a PDF has no text layer.

**Can I output something other than Markdown?**
Yes: DOCX, PDF, PPTX, HTML, EPUB, ODT, RST, LaTeX and more, or any text format through [Jinja2 templates](https://all2md.readthedocs.io/en/latest/templates.html).

**How do I add a format?**
Write a parser, describe it with `ConverterMetadata`, and register it under the `all2md.converters` entry point. See [examples/plugins](https://github.com/thomas-villani/all2md/tree/main/examples/plugins).

## Contributing

Bug reports, feature requests, docs and code are all welcome. See [CONTRIBUTING.md](https://github.com/thomas-villani/all2md/blob/main/CONTRIBUTING.md) for the development setup. Parser changes are judged against the [benchmark lanes](https://github.com/thomas-villani/all2md/tree/main/benchmarks); see [Conversion Fidelity](https://all2md.readthedocs.io/en/latest/benchmarks.html).

Questions and bugs go to [GitHub Issues](https://github.com/thomas-villani/all2md/issues). Full documentation is on [Read the Docs](https://all2md.readthedocs.io/).

## License

MIT. See [LICENSE](https://github.com/thomas-villani/all2md/blob/main/LICENSE).
