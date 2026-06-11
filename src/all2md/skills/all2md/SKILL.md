---
name: all2md
description: "Convert, read, generate, search, and compare documents with the all2md CLI and Python library. Use whenever a task involves reading or extracting text/tables from a document (PDF, Word, PowerPoint, Excel, HTML, email, EPUB, Jupyter, images, or 100+ source-code and text file types); converting between formats (PDF→Markdown, Markdown→DOCX/PDF/PPTX/HTML/EPUB, any-to-any); generating documents or static sites from Markdown; grepping for patterns inside non-plaintext files; ranked keyword or semantic search across a document collection; or diffing two documents. Triggers include 'read this PDF', 'extract text/tables', 'convert to Word/PDF', 'make slides', 'export to EPUB', 'search these documents', 'grep this docx', or 'what changed between these files'."
metadata:
  author: all2md
  version: "2.0"
---

# all2md

`all2md` converts between 40+ document formats and Markdown, from both the command line and a Python API. It reads PDF, DOCX, PPTX, XLSX, HTML, EML, EPUB, ODT/ODP/ODS, RTF, Jupyter notebooks, images, and 100+ source-code and config file types; renders Markdown back out to DOCX, PDF, PPTX, HTML, EPUB, LaTeX, RST, and more; and ships task commands for search, grep, diff, and static-site generation.

This file is the overview and index. Pick the task below and read the matching reference file for full CLI flags, Python API, and examples.

## Choose a reference

| You want to… | Read | Command family |
|---|---|---|
| Read / extract text or tables from a document | [references/read.md](references/read.md) | `all2md <file>` |
| Convert a file from one format to another | [references/convert.md](references/convert.md) | `all2md <file> --output-format <fmt>` |
| Generate a document or static site from Markdown | [references/generate.md](references/generate.md) | `all2md <md> --output-format <fmt>`, `generate-site`, `arxiv` |
| Find a pattern inside documents (like grep) | [references/grep.md](references/grep.md) | `all2md grep` |
| Ranked keyword/semantic search across a collection | [references/search.md](references/search.md) | `all2md search` |
| Compare two documents / see what changed | [references/diff.md](references/diff.md) | `all2md diff` |

## Core model

- **Read**: `to_markdown(path)` / `to_ast(path)` auto-detect the input format and route to the right parser.
- **Write**: `from_markdown(...)` / `from_ast(doc, fmt)` render an AST to a target format.
- **CLI**: `all2md <input> [--output-format FMT] [-o OUT]`. Default output is Markdown to stdout. Use `-` for stdin.
- **Format-specific flags** follow the pattern `--<format>-<option>` for parsers (e.g. `--pdf-pages`) and `--<format>-renderer-<option>` for renderers (e.g. `--html-renderer-no-standalone`).

## Quick start

```bash
# Read any document to Markdown (stdout)
all2md report.pdf

# Save to a file
all2md report.pdf -o report.md

# Convert between formats
all2md report.md --output-format docx -o report.docx
all2md page.html --output-format pdf -o page.pdf

# Read from stdin
cat report.pdf | all2md -

# Search, grep, diff
all2md grep "revenue" *.pdf
all2md search "machine learning" ./papers --vector
all2md diff v1.docx v2.docx
```

```python
from all2md import to_markdown, from_markdown, to_ast, from_ast

markdown = to_markdown("report.pdf")          # read
from_markdown("report.md", "docx", output="report.docx")   # generate
doc = to_ast("report.pdf")                    # AST for programmatic access
from_ast(doc, "html", output="report.html")   # render
```

## Tips

- `all2md list-formats` shows every input/output format with dependency status.
- `all2md check-deps` verifies optional dependencies (PyMuPDF for PDF, etc.).
- Beyond the task families above, the CLI also has: `all2md view <file>` (preview in a browser), `all2md serve` (local HTTP API), `all2md edit <file>` (web editor), `all2md lint <file>` (Markdown linter with `--fix`), and `all2md config generate|show` (configuration files). Run `all2md <command> --help` for flags.
- `all2md --help full` prints the complete flag reference, including all format-specific options.
- `all2md llm-help [topic]` prints these references to stdout (topics: read, convert, generate, grep, search, diff) — handy when driving the CLI without installing the skill.
- Every CLI option also reads an environment variable: `ALL2MD_<OPTION>` (e.g. `ALL2MD_PDF_OCR_ENABLED=true`).
