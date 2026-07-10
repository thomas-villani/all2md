# all2md Roadmap

> A living, intentionally-wide brainstorm of where `all2md` could go. Nothing here is
> committed — it's a menu of directions, sequenced roughly by leverage and effort.

Legend: 🌱 natural next step · 🚀 ambitious · 🌙 moonshot · ✅ foundation already exists
· 🚢 **shipped**

> **Status note (updated 2026-07-09).** Since this roadmap was first written we've
> shipped the headline Theme 1 item — `all2md chunk` (provenance-aware chunking, 11
> strategies, `all2md.chunk()` Python API, `[chunk]` extra) — plus mermaid/syntax-
> highlighting in `view`/`serve` and one-click `uv` install scripts. The **Fidelity &
> Trust** batch has since landed the conversion cache, the confidence report
> (`all2md report`), DOCX character-style round-tripping, and round-trip fidelity scoring
> (`all2md roundtrip`), leaving the conversion optimizer unblocked as its capstone.
> Shipped items are marked 🚢 inline below; the license question that gated chunking is
> resolved (chunkers vendored, optional extra). Tactical near-term work lives in `todo.md`,
> which is developer-local (git-ignored) — anything that needs to outlive a working tree is
> cross-referenced into the themes below or filed as an issue.

---

## Vision

`all2md` is already a universal document↔Markdown engine with an AST core, transform
pipeline, 50+ parsers/renderers, search, diff, lint, and an MCP server. The next chapter
is about turning that foundation into **the default substrate for getting documents into
and out of LLM workflows** — with best-in-class fidelity, measurable quality, and the
scale to handle real corpora.

Three bets stand out as highest-leverage for us specifically:

1. **RAG-native output** (chunking + provenance) — we have the AST and search; nobody
   does provenance-preserving chunking well, and we have a sister library to draw from.
2. **A public fidelity benchmark** — cheap to build on our existing diff engine, doubles
   as marketing and a regression guard.
3. **Async + scale** — unblocks the server/MCP story we've already started.

---

## Theme 1 — RAG-native output (chunking & provenance)

We have an AST with line mapping and source spans; `localvectordb` (sister lib) has 8
composable, position-tracking chunkers and a clean `ChunkerFactory` API. The synergy is
obvious.

- 🚢 **First-class `all2md chunk`** — *shipped (v1.8.0).* Eleven strategies (`semantic`
  default, `heading`, `section`, `auto`, `token`, `sentence`, `paragraph`, `word`, `line`,
  `char`, `code`), JSONL/JSON/pretty output, `--max-tokens`/`--overlap`/`--min-tokens`,
  tiktoken-backed real BPE counting via the `[chunk]` extra, atomic table/code chunks,
  data-URI elision, and a one-call `all2md.chunk()` Python API. Fine-grained chunkers are
  vendored from `localvectordb`.
- 🚀 **Provenance-preserving conversion** — *partially shipped.* `all2md chunk` records
  provenance now include section heading/level and (where the parser tracks it, e.g. PDF)
  the source page span. The remaining ambition is end-to-end node-level provenance
  (page, bbox, char offset) on *every* output node so an LLM answer can cite exactly where
  it came from — the RAG-trust differentiator. Bbox/char-offset spans are the gap.
- 🌱 **Token-budget conversion** — `llm-minify` (🚢 v1.3.0) and `--slice X/Y` paging
  (🚢 v1.7.1) exist; the open piece is "fit this 400-page PDF into 100k tokens" with
  section-aware elision/summarization rather than uniform minification.
- 🚀 **Structured extraction** — *not started* (distinct from the shipped `--extract`
  selector, which pulls sections/tables/figures as Markdown). The ambition here is
  `all2md extract doc.pdf --schema invoice.json` → typed, schema-validated JSON
  (tables → records, key/value fields). Document → data, not prose.
- 🚀 **Loader adapters (two tiers).** Every framework wants the same payload —
  *text + metadata records* — which our AST + chunker already produces. Split the work:
  - **RAG-framework adapters** (🌱, easy, high-visibility) — one thin module each:
    - *LangChain* — `BaseLoader` subclass with `.load() → list[Document]`
      (`Document = {page_content, metadata}`); add `.lazy_load()` generator for streaming.
    - *LlamaIndex* — `BaseReader` with `.load_data() → list[Document]`; list on LlamaHub.
    - *Haystack* — `@component` class whose `run()` returns `{"documents": [...]}`.
    - **Differentiator:** pass our provenance metadata (page/bbox/source-span) into each
      framework's `metadata` dict — most loaders ship no usable provenance.
  - **Training-corpus preprocessor** (🚀, higher value for the ML crowd) — offline batch
    conversion → chunked, tokenized, **sharded records** (Parquet / WebDataset / TFRecord).
    Training pipelines overwhelmingly preprocess offline, so this beats a live loader.
    - *PyTorch* — `Dataset` / `IterableDataset` wrappers. Note: PyMuPDF/OCR are CPU-heavy
      and GIL-bound under `DataLoader(num_workers>0)`, so the **async / ProcessPoolExecutor
      work in Theme 3 directly enables clean multi-worker loading** — a concrete async payoff.
    - *TensorFlow* — `tf.data.from_generator` for live use, but the real story is
      pre-sharded TFRecords from the batch engine.

**Reuse note (resolved):** `localvectordb` is PolyForm Noncommercial-licensed. We took the
recommended path — the fine-grained chunking primitives were **vendored** into `all2md`
(self-contained, `tiktoken`-based) rather than added as a hard dependency, and BPE counting
lives behind the optional `[chunk]` extra. License posture settled; no runtime dependency
on the noncommercial package.

---

## Theme 2 — Conversion fidelity (deepen the core moat)

People star us because "it just converted my gnarly PDF perfectly." Protect and extend that.

- 🚢 **Round-trip fidelity scoring** — *shipped (unreleased; lands in v1.9.0).* `all2md
  roundtrip doc.docx` renders to an intermediate format, parses it straight back, and scores
  the structure that survived — `0-100` plus per-dimension metrics and itemized
  `StructuralDelta`s. Built on the **AST**, not on `all2md.diff` as originally planned: that
  engine is a text `difflib` and cannot see a demoted heading. A clean document round-trips
  through Markdown at exactly `100`, so the metric is a real regression guard rather than
  noise. *Still open:* wiring it into the `benchmarks/corpus/` harness (🚢 v1.1.1) for a
  corpus-wide fidelity report — the remaining half of the "marketable metric" story.
- 🚢 **DOCX round-trip: character styles** — *shipped (unreleased).* Run-level named
  character styles ("Quote Char", "Intense Reference") now ride on the inline node's
  `metadata['source_style']` and are re-applied when rendering to DOCX with a template,
  matching the paragraph-level behaviour (🚢 v1.1.1).
- 🌱 **DOCX/HTML round-trip asymmetries** — *found by `all2md roundtrip`, unfixed.* Each is a
  renderer/parser pair that does not invert:
  - [#70](https://github.com/thomas-villani/all2md/issues/70) — rendering to DOCX applies
    `TitlePromotionTransform` (leading H1 → Word "Title", every later heading shifted up
    one), but the DOCX parser maps "Title" → `Paragraph`. So `md → docx → md` demotes the
    title *and* shifts H2→H1.
  - [#71](https://github.com/thomas-villani/all2md/issues/71) — the DOCX round trip drops
    inline `Code`, and writes a `BlockQuote` as an indented `Normal` paragraph that the
    parser reads back as a bullet list.
  - [#72](https://github.com/thomas-villani/all2md/issues/72) — the HTML parser wraps `<li>`
    content in a `Paragraph` unconditionally, so `<li><p>x</p></li>` parses to
    `ListItem > Paragraph > Paragraph > Text`.

  Reproduce any of them with `all2md roundtrip <file> --via docx` (or `--via html`).
- 🚀 **Layout-aware PDF reconstruction** — correct reading order across columns,
  footnote/endnote linking, running header/footer stripping, caption↔figure association.
  The eternal PDF pain points; we already have `_pdf_layout.py` to build on.
- 🚀 **Math everywhere** — emit LaTeX from DOCX (OMML→LaTeX), PDF equation regions,
  HTML MathML, and (optionally) images of equations via OCR. Huge for academic/technical
  users and a natural pairing with the existing arxiv packager.
- 🚀 **Public fidelity benchmark** — a golden corpus + scores vs markitdown / pandoc /
  docling. Marketing + regression guard in one. *Groundwork exists:* `benchmarks/corpus/`
  already pulls deterministic samples from arxiv, PubMed Central, govdocs1, Apache POI, and
  Enron and emits a stratified report (🚢 v1.1.1); a manual-dispatch CI workflow runs it on a
  clean VM. **A self-referential quality score now exists too** (`roundtrip_report`, 🚢), so
  what remains is (a) running it corpus-wide, (b) scoring against an external *ground truth*
  where one exists, and (c) the head-to-head against other tools. Corpora, split by job:
  - **Structure ground-truth (headline metric):** [**OmniDocBench**](https://github.com/opendatalab/OmniDocBench)
    (CVPR 2025) — 981 pages, 9 doc types, with table (Markdown/HTML/LaTeX), formula, and
    reading-order metrics that map directly onto our output. Anchor the public score here.
    Supplement with [**DocLayNet**](https://github.com/DS4SD/DocLayNet) (80k diverse
    annotated pages, good for reading order) and **M6Doc** (scanned + CJK coverage).
    *Avoid relying on PubLayNet/DocBank alone — academic-only, low layout variability.*
  - **Robustness / "doesn't crash" tier:** [**GovDocs1**](https://digitalcorpora.org/corpora/file-corpora/)
    (~239k real .gov files), the **SafeDocs Stressful PDF Corpus** + **CC-MAIN SAFEDOCS**
    (~8M modern Common Crawl PDFs, malformed edge cases). Indexed via the
    [PDF Association corpora list](https://github.com/pdf-association/pdf-corpora).
  - **Format gaps we must fill ourselves:** no good public benchmark exists for Office /
    email / HTML fidelity — hand-build a ~100-doc golden set. Sources: EDGAR filings
    (financial DOCX/HTML/XBRL), the Enron corpus (mbox/eml threading torture-test),
    Wikipedia HTML dumps, and **arXiv source↔PDF pairs** (free round-trip *math* ground
    truth — pairs with the math-support work).
- 🚢 **Conversion confidence report** — *shipped (unreleased).* `all2md report <file>` and
  `Document.metadata['confidence']` surface the sanity signals the PDF/DOCX parsers already
  computed as guards (table cell-fill density, dot-leader ratio, ghost-image counts,
  near-empty-page ratio) as a structured "quality card" instead of log noise. Reference-free,
  so it works on documents with no ground truth.
- 🚀 **Conversion optimizer (`all2md optimize`)** — auto-tune converter settings for a
  difficult document (headline case: gnarly PDFs). Searches the parameter space
  (`table_detection_mode`, `detect_columns`, OCR mode/engine, `min_image_dimension`,
  header/footer filtering, dehyphenation, layout model, heading size-ratio, …) and returns
  the settings that maximize a quality score — emitted as a reusable preset / `.all2md.toml`
  snippet.
  - **Objective (the crux):** difficult PDFs rarely have a reference to diff against, so the
    optimizer needs a **reference-free** quality score — exactly the vector the *confidence
    report* produces (real-word ratio, table sanity, ghost-image count, reading-order
    coherence, near-empty-page ratio, hyphenation-merge success). **Both halves of that
    substrate now exist** (confidence 🚢, round-trip 🚢), so this is *unblocked* and is the
    next item up. Use `confidence_report(...).score` where no reference can be manufactured
    and `roundtrip_report(...).score` where one can; both respond to converter options — e.g.
    `html_passthrough_mode="pass-through"` moves `basic.md` from 98 to 100 — which is exactly
    what makes them hill-climbable.
  - **Search shape (keep it cheap):** score a handful of named presets first (interpretable,
    fast), then a 1-D refine on the highest-impact continuous knob — not a full grid. Sample
    a page subset (first N + random) rather than reconverting a 400-page doc, and **cache per
    (param-set × content-hash)**, reusing the Theme 3 conversion-cache fingerprint.
  - **Two levels:** per-document autotune, *and* a corpus-level mode that tunes over
    `benchmarks/corpus/` to improve **shipped defaults** — a concrete step toward the
    self-improving converters in Theme 7.
- 🌙 **Vision-model fallback** — when structural parsing fails (scanned tables, complex
  figures, handwriting), optionally hand the page to a vision LLM and merge its structured
  output back into the AST.

---

## Theme 3 — Async & scale

See the **Async Architecture Decision** below for the strategy. The shape:

- 🌱 **Async facade** — `ato_markdown` / `aconvert` that offload the CPU-bound sync core via
  `asyncio.to_thread`, so MCP / `serve` can await conversions without blocking the loop.
- 🌱 **Async I/O edge** — `httpx.AsyncClient` path in `utils/network_security.py`.
- 🚀 **Deferred asset resolution** — parse to AST with asset placeholders, then resolve all
  remote assets concurrently (`asyncio.gather`), then finalize. Turns N serial fetches into
  one concurrent batch — the real user-visible speedup for asset-heavy HTML.
- 🌱 **Persistent / incremental search index + shared conversion cache** — *outstanding
  (`todo.md`).* Today `--search-index-dir` (`mcp/query_tools.py`) is keyed only by directory,
  so reusing an index across a changed corpus or a different `paths` set can return **stale
  results**. Roll the MCP search index together with a general conversion cache: stash
  converted documents/ASTs keyed by content-hash + mtime, and key/invalidate the BM25 index
  off the same fingerprint. Fixes correctness *and* avoids redundant re-conversions across
  tools — a rare "fixes a bug and adds a feature" item. The same cache is reusable well
  beyond MCP: `view` and `serve` re-convert a file on every scan/request today and would
  skip unchanged files, and the **conversion optimizer** (Theme 2) reuses the fingerprint to
  avoid reconverting identical param-sets.
- 🚀 **Parallel batch engine v2** — the `ProcessPoolExecutor` path with resume, a failure
  manifest, and as-completed streaming progress.
- 🌙 **WASM build** — `all2md` in-browser (Pyodide, or a Rust core for hot paths) for
  client-side, privacy-preserving conversion. No upload required.

---

## Theme 4 — New formats & domains

- 🌱 **More inbound formats** — Apple iWork (Pages/Numbers/Keynote), Visio, OneNote,
  Google Docs export, Slack/Discord/WhatsApp exports, Confluence/Notion exports.
- 🚀 **Audio/video → markdown** — transcript + chapters + speaker diarization → structured
  notes. Meeting recordings are a massive use case.
- 🚀 **Spreadsheet semantics** — preserve formulas, named ranges, and cross-sheet refs,
  not just rendered values.
- 🌙 **Diagram intelligence** — Mermaid / Graphviz / draw.io / PlantUML round-tripping, and
  reverse-engineering diagrams from images. *Down-payment:* `view`/`serve` now **render**
  ```mermaid``` fences via mermaid.js and the HTML renderer has `render_mermaid`
  (🚢 v1.8.0) — rendering exists; parsing/round-tripping other diagram formats is the gap.

---

## Theme 5 — Ecosystem & distribution

> **Install experience — decided.** We shipped one-click **`uv`-based install scripts**
> (🚢 v1.8.0) rather than a frozen PyInstaller binary; that resolves the "build a binary so
> people can install directly?" question in `todo.md`. A browser/web-UI is still planned
> (local-only design spec). The channels below (Docker, Action, hosted API) are unstarted.

- 🌱 **Docker image** — `docker run all2md` as a one-line microservice / CI step. Also the
  building block for the GitHub Action and hosted API below — bake PyMuPDF/tesseract in once.
- 🌱 **GitHub Action** — "convert docs in this repo to markdown on commit." A direct
  adoption channel for a stars-collecting project. *How it works:* two pieces —
  (1) a **reusable action repo** (e.g. `all2md-action`) with an `action.yml` at its root;
  best as a **Docker action** (points at a Dockerfile) since we have heavy native deps, so
  they're baked in once rather than `pip install`ed per run. (2) a documented **example
  workflow** users drop into their `.github/workflows/` (`uses: thomas-villani/all2md-action@v1`).
  No registration step — GitHub auto-discovers workflow YAML; we just tag releases and
  optionally list on the **Marketplace** (a checkbox on a release; the action still runs
  from our repo).
- 🚀 **Hosted conversion API** — a freemium endpoint (could fund the project); the Docker
  image is the building block. Also the backend for the browser extension and Node SDK.
- 🚀 **Node / JS SDK** — *not a port.* The JS conversion ecosystem is fragmented and weaker
  (pdf.js, mammoth.js, turndown, SheetJS, remark/unified) with no equivalent of our layout
  analysis or unified AST — reimplementing that is a second product. Instead ship a **thin
  typed Node client over the hosted API / Docker service** (`npm i all2md`, ~200 lines of
  `fetch` wrappers). Keep WASM/Pyodide as the long-game for offline use.
- 🚀 **Browser extension** — "convert this page / PDF to clean markdown" button. Manifest V3
  (content script scrapes page HTML → our strongest parser). Extensions run JS not Python,
  so the MVP is a **thin client over the hosted API**; native-messaging (local install) or
  WASM (fully client-side) are later, more private options.
- 🚀 **pre-commit hook + docs-site generator** — point at a folder of mixed docs, get a
  built static site (builds on the existing `generate-site` work).

---

## Theme 6 — Editing, collaboration & live workflows

- 🌱 **Expand the edit API** — *groundwork shipped:* the MCP `edit_document` tool does
  atomic, in-place batch edits with format-preserving write-back (🚢 v1.6.0) and the
  `all2md edit` web editor exists (🚢 v1.1.0). Outstanding: **CLI** insert/replace/delete
  commands (`todo.md`), and beyond section ops — table-cell edits, find-and-restructure,
  programmatic AST patches with undo.
- 🌱 **Element re-routing on conversion** — *outstanding (`todo.md`).* One pass that can
  drop images/tables entirely, extract tables to separate file(s) (combined or per-table),
  or collate all images/tables to the end of the document. Overlaps the chunker's
  `--drop-elements` (🚢) but as a conversion-output restructuring, not just chunking; useful
  for both human reading and RAG prep. Also: **extract text around a table/anchor** and
  **extend `--extract` to all AST element types**.
- 🚀 **Watch-and-sync daemon** — keep a markdown mirror of a source doc continuously
  updated; optionally bidirectional.
- 🌙 **Bidirectional live editing** — edit the markdown, regenerate the DOCX *preserving the
  original corporate template/styling*. The "fix a typo without breaking the template" grail.

---

## Theme 7 — Trust, safety & observability

- 🚀 **Redaction / PII detection mode** — flag or strip emails, SSNs, secrets, keys during
  conversion. Compliance-friendly.
- 🌙 **Semantic document graph** — convert a folder into a linked knowledge graph
  (entities, cross-references, citations) you can query.
- 🌙 **Self-improving converters** — log failures, auto-generate test fixtures from them,
  and eventually suggest parser fixes.

---

## Async Architecture Decision

**Decision:** Keep the synchronous core as the source of truth; add a thin async edge.
Do **not** rewrite the base as async-native, and do **not** maintain duplicate
sync/async implementations.

**Why.** The core is CPU-bound — PyMuPDF, python-docx, python-pptx, openpyxl, OCR are
synchronous C-extensions with no awaitable API. The genuine I/O is a thin edge
(`utils/network_security.py`), hit only when a document references remote assets. Batch
already parallelizes via `ProcessPoolExecutor`.

Rejected alternatives:

- **Async-native core + sync runner that calls `asyncio.run`.** Every parser/renderer
  would become `async def` only to immediately `await asyncio.to_thread(...)` around a
  blocking C call — full function-color tax, zero throughput gain. Worse, `asyncio.run`
  in the sync wrapper can't nest inside an existing event loop, so calls from Jupyter or
  from our *own* FastMCP server would raise `RuntimeError: event loop is already running`.
- **Duplicate sync + async implementations** (the httpx/unasync model). That cost only
  pays off when the *core* is I/O. Ours is CPU; we'd maintain two copies of parsing logic
  for no throughput benefit.

**Chosen shape:**

1. Sync `to_markdown` / `convert` / parsers / renderers stay as-is.
2. Add `ato_markdown` / `aconvert` = `await asyncio.to_thread(to_markdown, ...)`.
3. Give `network_security` a real `httpx.AsyncClient` path.
4. (Phase 2) Defer remote-asset resolution out of the parse step and resolve concurrently
   via `asyncio.gather` — the actual user-visible win.
5. Batch stays `ProcessPoolExecutor`, with an optional async orchestrator on top.

Result: ~90% of files (no remote assets) never touch async; the async API exists for
servers and the asset-heavy minority where it genuinely helps — with no async tax on the
CPU core.

---

## Suggested sequencing

**Done since first draft:** ~~`all2md chunk`~~ 🚢 (was #2) — the biggest single item is
shipped, along with mermaid rendering and `uv` install scripts.

**Done in the Fidelity & Trust batch** (unreleased, lands in v1.9.0): ~~round-trip fidelity
scoring~~ 🚢, ~~conversion confidence report~~ 🚢, ~~DOCX character-style round-trip~~ 🚢,
~~search-index / conversion-cache correctness~~ 🚢. That closes the previous arc's top two
entries and unblocks the batch capstone, which leads the revised arc below.

Revised arc for the **next batch**, ordered by leverage-per-effort:

1. **Conversion optimizer (`all2md optimize`)** — the capstone, now unblocked: both quality
   scores it hill-climbs on exist and are exercised by tests. Start here.
2. **Public fidelity benchmark** — round-trip scoring exists, so productize it: wire it into
   the `benchmarks/corpus/` harness for a corpus-wide report, then a head-to-head vs.
   markitdown / pandoc / docling.
3. **DOCX/HTML round-trip asymmetries** — the concrete defects `all2md roundtrip` surfaced
   on its first run (Theme 2). Small, well-specified, and each one raises the benchmark
   number above.
4. **Async facade + async I/O edge** — unblocks the server/MCP story (see the Async
   Architecture Decision); the deferred-asset-resolution phase is the user-visible win.
5. **GitHub Action + Docker image** — adoption channels for a project gaining stars; Docker
   is the shared building block for the Action and a future hosted API.
6. **Math support** + **layout-aware PDF** — deepen the fidelity moat (larger efforts).

Everything below 🚀/🌙 is opportunistic — pull forward whatever a real user asks for. The
small `todo.md` bug-fixes (filename-hint detection, leading blank line in DOCX, smarter
capitalization-aware dehyphenation, rich `--help` by default) are independent quick wins.
