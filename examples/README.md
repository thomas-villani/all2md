# all2md examples

Practical, runnable examples for `all2md` -- the document conversion engine for
turning PDF, Word, PowerPoint, HTML, email, Excel, images, and 200+ text formats
to and from Markdown. The examples span everyday document processing and
LLM/RAG workflows, from one-liners to production-ready tools.

Every example here has been run against the current library. Most accept a
document path and fall back to printing usage when run with no arguments.

## Layout

Examples are grouped by theme:

```
examples/
  cli/        Shell pipelines & batch jobs (bash + PowerShell), plus git automation
  python/     Core Python API: conversion, AST, transforms, batch, analysis
  llm/        LLM / RAG workflows (Anthropic Claude), with a no-key mock provider
  web/        Web app serving Markdown (Flask)
  templates/  Custom output via Jinja2 templates
  plugins/    Writing your own parser/renderer/transform plugins
```

## Start here

New to `all2md`? In rough order of complexity:

1. `python/progress_callback_demo.py` -- track conversion progress with a callback.
2. `python/transforms_by_name.py` -- clean up a document with built-in transforms.
3. `cli/convert-and-pipe.sh` / `.ps1` -- the everyday CLI moves.
4. `python/ast_json_roundtrip.py` -- the AST and its JSON interchange form.
5. `llm/search_to_llm_rag.py` -- retrieval-augmented generation over a corpus.

---

## Examples by theme

### `cli/` -- shell pipelines (bash + PowerShell)

The CLI is a first-class surface. Each concept ships as a `.sh` and a `.ps1`.
See `cli/README.md` for the full table. Highlights:

- **convert-and-pipe** -- convert to stdout, `--to` any format, stdin with `-`, attachment modes.
- **batch-convert** -- whole-folder conversion, `--collate`, parallel fan-out.
- **extract-and-navigate** -- `--outline`, `--line-numbers`, `--extract` by section or line range.
- **grep-binary-docs** -- `all2md grep` inside PDF/DOCX that plain grep can't read.
- **search-corpus** -- ranked `all2md search --json` with provenance, post-processed by `jq` / `ConvertFrom-Json`.
- **diff-in-ci** -- semantic, cross-format `all2md diff` as a CI gate.
- **llm-minify-pipe** -- shrink a document to token-lean text before an LLM call.
- **rag-ingest** -- assemble a grounded, cited LLM prompt from retrieved chunks.

### `python/` -- core Python API

| Script | What it shows | Complexity |
| ------ | ------------- | ---------- |
| `progress_callback_demo.py` | Progress callbacks (`progress_callback=`) and `ProgressEvent` | Beginner |
| `transforms_by_name.py` | Built-in transforms by name, a custom `NodeTransformer`, and hooks | Beginner |
| `ast_json_roundtrip.py` | `to_ast` -> `ast_to_json` -> `json_to_ast` -> `from_ast` interchange | Beginner |
| `api_doc_extractor.py` | Extract runnable code blocks from docs | Intermediate |
| `link_checker.py` | Extract & validate links/anchors (HTTP checks via `httpx`) | Intermediate |
| `document_sanitizer.py` | Redact PII / strip metadata with AST transforms, then re-render | Intermediate |
| `batch_converter.py` | Parallel bulk conversion with checkpoint/resume | Advanced |

### `llm/` -- LLM & RAG workflows

These use Anthropic's Claude through a shared `_llm_client.py` helper. Every
script also supports `--llm mock`, a deterministic offline provider, so you can
run them end-to-end with **no API key**.

| Script | What it shows |
| ------ | ------------- |
| `search_to_llm_rag.py` | **RAG**: index a corpus, retrieve chunks with provenance, answer with citations |
| `llm_translation_demo.py` | Translate any document format, preserving structure, via an AST transform |
| `study_guide_generator.py` | Build study guides; optional LLM-generated quizzes/problems |
| `code_example_generator.py` | Generate & validate code examples, insert them back into docs |
| `_llm_client.py` | Shared Claude client + mock provider (one place to keep SDK wiring current) |

Real Claude calls need `pip install anthropic` and an `ANTHROPIC_API_KEY`.

### `web/` -- web applications

- `flask_markdown_site.py` -- a Flask blog/site that serves Markdown with YAML
  frontmatter as HTML. Sample content in `web/flask-site-content/`.

### `templates/` -- custom output formats

- `jinja_template_demo.py` -- render the AST through Jinja2 templates (DocBook
  XML, YAML metadata, ANSI terminal, custom outlines). Templates in
  `templates/jinja-templates/`.

### `plugins/` -- extend all2md

- `simpledoc-plugin/` -- a complete bidirectional format plugin (parser +
  renderer + options + tests). The template for adding a new format.
- `watermark-plugin/` -- a transform plugin that watermarks document images.

---

## Requirements

```bash
pip install all2md          # core
pip install all2md[all]     # all optional format support (PDF, DOCX, ...)
```

Per-example extras:

```bash
pip install anthropic       # llm/ examples (real Claude calls)
pip install flask           # web/ example
pip install httpx           # python/link_checker.py URL checks
```

The `cli/` bash scripts that parse JSON (`search`, `diff`, `rag`) use `jq`; the
PowerShell versions parse JSON natively. On Windows, run `.sh` files under Git
Bash or WSL and `.ps1` files in PowerShell 7+.

---

## Key concepts (correct, current API)

### Parse to an AST, transform, render

```python
from all2md import to_ast, from_ast

doc = to_ast("input.pdf")           # -> Document
# ... inspect or transform doc ...
markdown = from_ast(doc, "markdown")        # text formats -> str
from_ast(doc, "docx", output="out.docx")    # binary formats -> file/bytes
```

### Custom transforms (NodeTransformer)

`NodeTransformer` lives in `all2md.ast.transforms`. Visitor methods are
**snake_case** by node type (`visit_link`, `visit_image`, `visit_text`, ...):

```python
from all2md.ast.transforms import NodeTransformer

class StripTrackingParams(NodeTransformer):
    def visit_link(self, node):              # note: snake_case
        node.url = node.url.split("?")[0]
        return node

from all2md import to_markdown
markdown = to_markdown("page.html", transforms=[StripTrackingParams()])
```

### Built-in transforms by name

The same names the CLI exposes via `--transform` (see `all2md list-transforms`):

```python
markdown = to_markdown(
    "report.docx",
    transforms=["remove-images", "heading-offset", "remove-boilerplate"],
)
```

### Hooks (per-node-type callbacks during rendering)

```python
def note_image(node, context):
    print("image:", node.url)
    return node                              # return the (maybe modified) node

to_markdown("doc.pdf", hooks={"image": [note_image]})
```

### Progress callbacks

The callback takes a single `ProgressEvent` (canonical types: `started`,
`item_done`, `detected`, `finished`, `error`):

```python
from all2md import to_markdown
from all2md.progress import ProgressEvent

def on_progress(event: ProgressEvent):
    print(event.event_type, event.message, f"{event.current}/{event.total}")

to_markdown("big.pdf", progress_callback=on_progress)
```

### AST <-> JSON (LLM-friendly interchange)

```python
from all2md import to_ast, from_ast
from all2md.ast.serialization import ast_to_json, json_to_ast

doc = to_ast("input.docx")
blob = ast_to_json(doc, indent=2)    # stable, inspectable JSON of the structure
doc2 = json_to_ast(blob)             # round-trips back to a Document
html = from_ast(doc2, "html")
```

### Search a corpus (retrieval for RAG)

```python
from all2md.search import search_documents
from all2md.search.service import SearchDocumentInput

docs = [SearchDocumentInput(source=p) for p in ["a.pdf", "b.docx"]]
hits = search_documents(docs, "billing policy", mode="keyword", top_k=5)
for h in hits:
    print(h.score, h.chunk.metadata.get("document_path"), h.chunk.metadata.get("section_heading"))
```

---

## Running the examples

```bash
# Python scripts (use uv, or any environment with all2md installed)
python python/transforms_by_name.py path/to/document.docx
python llm/search_to_llm_rag.py "your question" ./docs --llm mock

# Shell scripts
bash cli/convert-and-pipe.sh report.pdf            # bash / Git Bash / WSL
pwsh cli/convert-and-pipe.ps1 report.pdf           # PowerShell 7+
```

Run any script with no arguments (or `--help`) to see its usage.

## Contributing an example

Good examples solve a real problem, use the current public API, run out of the
box (or with a clearly stated extra), and include a short docstring with usage.
Drop new files into the matching theme folder and add a row to the tables above.

See the main project docs for the full API reference and the cookbook
(`docs/source/recipes.rst`).
