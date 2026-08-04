# all2md Roadmap

> A living, intentionally-wide brainstorm of where `all2md` could go. Nothing here is
> committed — it's a menu of directions, sequenced roughly by leverage and effort.

Legend: 🌱 natural next step · 🚀 ambitious · 🌙 moonshot · ✅ foundation already exists
· 🚢 **shipped**

**Status (2026-08-01).** The **External ground truth** batch is complete and cuts as **v1.11.0**.
The OmniDocBench lane is live with a recorded baseline, and the fuzzer backlog it shipped
alongside is closed: all seven crash classes and eleven of the twelve invariant gaps are fixed,
leaving `KNOWN_INVARIANT_GAPS` at a single entry. Two lessons carried out of it. First, the
same defect appeared twice in one metric — *segmentation measured and called order* — and
both times the run **passed**; only reading the distribution caught it, which is why the
review step is now written into the lane's README. Second, the corpus turned out to be
981 page images, so the headline number grades our OCR pipeline rather than our PDF engine.
That is the right instrument for Theme 8 and the wrong one for Theme 2's general claim, and
knowing which is which is worth more than the number.

**Status (2026-07-30).** The headline Theme 1 item — `all2md chunk` — is shipped, along with
mermaid/syntax highlighting in `view`/`serve` and one-click `uv` install scripts. The
**Fidelity & Trust** batch landed in **v1.9.0**: the conversion cache, the confidence report
(`all2md report`), DOCX character-style round-tripping, round-trip fidelity scoring
(`all2md roundtrip`), and its capstone the conversion optimizer (`all2md optimize`). Shipped
items are marked 🚢 inline below.

The **Quality & Speed Ratchets** batch landed in **v1.10.1**. Bet 1 below is now done: all
three harnesses are wired to CI as blocking gates against committed baselines, cold start
dropped ~28%, and the gate is pointed outward as a reusable GitHub Action. The lesson worth
carrying forward is that **every one of those instruments already contained a vacuous pass**
— a green produced by not measuring rather than by measuring well — and that finding them
required demonstrating each gate red against deliberately-broken code before trusting it.
Wiring the gates up is also what surfaced a silent data-loss bug in the Markdown parser.

A **fourth instrument** arrived after the batch closed, and from outside: the generative
round-trip fuzzer contributed in [#204](https://github.com/thomas-villani/all2md/pull/204).
It is the *noisy* counterpart to `benchmarks/roundtrip`'s sharp, curated oracle — generative
and broad where that one is hand-written and deep. That is the pairing the ratchet batch
concluded with, arrived at independently by a contributor, which is decent evidence the
pattern is real rather than a story we told ourselves. It came with a defect backlog
attached: six crash classes (#206–#211), a hole in the exception contract (#212), and eleven
measured round-trip invariant gaps.

That batch — **(5) External ground truth**, with the backlog as its user-visible half — is now
shipped as **v1.11.0**. Bet 2 (positional fidelity) is the next one up and is finally
measurable, which was the point. See **Suggested sequencing**.

---

## Vision

`all2md` is already a universal document↔Markdown engine with an AST core, transform
pipeline, 50+ parsers/renderers, search, diff, lint, and an MCP server. The next chapter
is about turning that foundation into **the default substrate for getting documents into
and out of LLM workflows** — with best-in-class fidelity, measurable quality, and the
scale to handle real corpora.

Three bets stand out as highest-leverage:

1. 🚢 **A quality & speed ratchet** — *shipped (v1.10.1).* All three benchmark harnesses
   (`corpus`, `roundtrip`, `startup`) now gate CI against committed baselines, which was
   the precondition for honestly evaluating bets 2 and 3. See **Theme 2**.
2. **Positional fidelity** — OCR geometry → node-level provenance → layout-aware PDF. The
   single thread that makes RAG citations real; see **Theme 8**.
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
- 🚀 **Provenance-preserving conversion** — *partially shipped; the rest lives in **Theme 8**.*
  `all2md chunk` records provenance now include section heading/level and (where the parser
  tracks it, e.g. PDF) the source page span. The remaining ambition is end-to-end node-level
  provenance (page, bbox, char offset) on *every* output node, so an LLM answer can cite
  exactly where it came from — the RAG-trust differentiator. Bbox/char-offset spans are the
  gap, and closing it means making the geometry survive the *parsers* first. Tracked in
  Theme 8.
- 🌱 **Token-budget conversion** — `llm-minify` (🚢 v1.3.0) and `--slice X/Y` paging
  (🚢 v1.7.1) exist; the open piece is "fit this 400-page PDF into 100k tokens" with
  section-aware elision/summarization rather than uniform minification.
- 🚀 **Structured extraction** — *not started* (distinct from the shipped `--extract`
  selector, which pulls sections/tables/figures as Markdown). The ambition here is
  `all2md extract doc.pdf --schema invoice.json` → typed, schema-validated JSON
  (tables → records, key/value fields). Document → data, not prose.
- 🚀 **Loader adapters (two tiers).** Every framework wants the same payload —
  *text + metadata records* — which our AST + chunker already produces. Split the work:
  - **RAG-framework adapters** (🌱, easy, high-visibility) — one thin module each, roughly a
    day apiece. Shipped before Theme 8 these are *commodity* loaders — the same as everyone
    else's, plus better conversion. That is an argument for ordering, not for waiting:
    `metadata` is a plain dict, so a commodity loader shipped now can be enriched with
    provenance later without an API break. Good opportunistic filler, never a batch spine.
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

---

## Theme 2 — Conversion fidelity (deepen the core moat)

People star us because "it just converted my gnarly PDF perfectly." Protect and extend that.

- 🚢 **Round-trip fidelity scoring** — *shipped (v1.9.0).* `all2md roundtrip doc.docx` renders
  to an intermediate format, parses it straight back, and scores the structure that survived —
  `0-100` plus per-dimension metrics and itemized `StructuralDelta`s. It is built on the
  **AST** rather than on `all2md.diff`, which is a text `difflib` and cannot see a demoted
  heading. A clean document round-trips through Markdown at exactly `100`, so the metric is a
  real regression guard rather than noise. *Still open:* wiring it into the
  `benchmarks/corpus/` harness (🚢 v1.1.1) for a corpus-wide fidelity report — the remaining
  half of the "marketable metric" story. A separate, narrower harness now exists
  (`benchmarks/roundtrip`, 🚢 v1.9.0): it judges `markdown → AST → markdown` on a synthetic
  corpus with two independent oracles (idempotency, and HTML-equivalence via a reference
  mistune renderer). It is Markdown-only and synthetic-only by design — the CommonMark/GFM
  spec suites are its planned Phase 2 — so it complements rather than closes the corpus-wide
  item above.
- 🚢 **Markdown round-trip losses** — *found by `benchmarks/roundtrip`, fixed in v1.9.0.*
  A class of losses in our own default flavor, not just in the Office formats: footnotes,
  highlight/superscript/subscript and underline all rendered to raw HTML that the default
  `html_passthrough` policy then escaped on the next pass; inline `$$…$$` display math was
  dropped; tables nested in list items broke out of the list; and loose multi-paragraph list
  items collapsed onto one line. All now round-trip by default. Fidelity here is
  flavor-dependent — the roundtrip-safe spelling and the widely-displayable spelling are not
  always the same — so each fix landed as a flavor-aware default plus an explicit `html`
  opt-out.
- 🚢 **DOCX round-trip: character styles** — *shipped (v1.9.0).* Run-level named
  character styles ("Quote Char", "Intense Reference") now ride on the inline node's
  `metadata['source_style']` and are re-applied when rendering to DOCX with a template,
  matching the paragraph-level behaviour (🚢 v1.1.1).
- 🚢 **DOCX/HTML round-trip asymmetries** — *found by `all2md roundtrip`, fixed in v1.9.0.*
  Each was a renderer/parser pair that did not invert:
  - [#70](https://github.com/thomas-villani/all2md/issues/70) — rendering to DOCX applies
    `TitlePromotionTransform`, but the DOCX parser mapped "Title" → `Paragraph`, so
    `md → docx → md` demoted the title *and* shifted H2→H1. The parser now maps "Title" back
    to a title heading and inverts the promotion (clamped at level 6).
  - [#71](https://github.com/thomas-villani/all2md/issues/71) — the DOCX round trip dropped
    inline `Code`, and wrote a `BlockQuote` as an indented `Normal` paragraph that the
    parser read back as a bullet list. Inline code now rides on a `Verbatim Char` style and
    quotes on named quote styles.
  - [#72](https://github.com/thomas-villani/all2md/issues/72) — the HTML parser wrapped `<li>`
    content in a `Paragraph` unconditionally, so `<li><p>x</p></li>` parsed to
    `ListItem > Paragraph > Paragraph > Text`; loose items no longer double-wrap.

  The round-trip scorer that surfaced these now also scores code/math/HTML block content,
  so a regression in any of them shows up in `all2md roundtrip <file> --via docx` (or
  `--via html`).
- 🚀 **Layout-aware PDF reconstruction** — *moved to **Theme 8**.* Correct reading order
  across columns, footnote/endnote linking, running header/footer stripping, caption↔figure
  association. Every one of those is a *geometry* problem, which is why it now sits with the
  OCR and provenance work rather than alone here.
- 🚀 **Math everywhere** — emit LaTeX from DOCX (OMML→LaTeX), PDF equation regions,
  HTML MathML, and (optionally) images of equations via OCR. Huge for academic/technical
  users and a natural pairing with the existing arxiv packager.
- 🚢 **The ratchet: automate the harnesses we already built.** *Shipped (v1.10.1).* The
  diagnosis was that we did not need to *build* a benchmark — we had three good ones and
  automation on none of them. All three now gate:
  - `benchmarks/roundtrip/` — MD→AST→MD fidelity, two independent oracles (🚢 v1.9.0). Now
    a **blocking gate** on every push and PR, with an `EXPECTED_FAILURES` allowlist where an
    entry that starts passing, or goes stale, is *also* red.
  - `benchmarks/startup.py` — cold start. Now **two** gates, because the cost is milliseconds
    but the cause is an import graph: an exact module-set assertion that cannot flake, and a
    wall-clock job that requires raw and interpreter-normalized deltas to agree before going
    red (a CPU-class shift in the runner pool moves only one).
  - `benchmarks/corpus/` — now a **weekly** `Corpus Fidelity Gate` over the reproducible half
    only, comparing the failure set by name. The other half resolves against upstream state
    that moves, so gating it would report document-mix churn as a regression.

  `tests/performance` is kept but disarmed: its ceilings had 106×–1170× headroom on CI and
  its other assertions were true by construction, so it could never have failed — and never
  ran, because a bare `pytest tests/` deselects `benchmark`. It is now a `Format Benchmarks`
  job that gates on conversion rather than time, covering the dozen formats the corpus gate
  cannot reach.

  **What this actually taught us**, and the reason to distrust the next green: every one of
  these instruments already contained a *vacuous pass* — including, it turned out, the lint
  gate, where `fix = true` meant CI repaired violations in the runner and exited 0. The
  transferable rule is to pair a sharp instrument with a noisy one, because each is blind
  where the other sees, and to demonstrate every gate red against deliberately-broken code
  before trusting it.
- 🚢 **The fourth instrument: generative round-trip fuzzing** — *contributed in
  [#204](https://github.com/thomas-villani/all2md/pull/204).*
  `tests/unit/test_roundtrip_fuzzing.py` builds `Document` ASTs with Hypothesis and pushes
  them through `roundtrip_report` across all 24 round-trippable formats, behind four gates:
  every format must be classified into a group (so a 25th cannot silently skip the fuzzer),
  `ast` must score exactly 100 as the control, no format may raise outside `KNOWN_CRASHES`,
  and shapes drawn from previously-fixed defects must survive. Both allowlists are
  `xfail(strict=True)`, so they can only shrink — fixing an entry XPASSes and fails CI until
  the entry is deleted. It is the **noisy** instrument to `benchmarks/roundtrip`'s sharp one.

  **Its measured blind spot**, because the ratchet batch's lesson demands we look for one.
  Injecting deliberate renderer breaks and checking the gate goes red: a break on a shape
  present in ~20% of generated documents is caught; one at ~7% (a level-6 heading) passes
  silently. The cause is `@given(documents(), st.sampled_from(TEXT_FORMATS))` at
  `max_examples=25` — 25 examples spread over 11 formats is ~2 documents each. Parametrizing
  over the format instead gives each its own 25 examples, drops the detection floor below 7%,
  and names the offending format in the test id, for ~12s more wall clock. *Until that lands,
  do not read a green here as "no crash exists" — read it as "nothing common is broken".*

  What it produced on first contact: six crash classes (#206–#211), an exception-contract
  hole (#212), and the first **enumerated** — rather than suspected — list of round-trip gaps
  in the org and asciidoc renderers (table captions, ordered-list `start`, the `#+BEGIN_SRC`
  language, and an asciidoc trailing pipe its own parser reads as a phantom column).
- 🚢 **External ground truth** — *lane landed in `benchmarks/omnidocbench`; baseline recorded
  2026-08-01.* `roundtrip_report` (🚢) is **self-referential**: it proves we invert our own
  parsers, not that we read the document correctly. A garbled table can round-trip perfectly.
  The scheduled OmniDocBench lane downloads an immutable 981-page corpus, calls
  `all2md.to_ast` once per page, and compares supported AST facts directly with annotation
  fields for text, formulae, tables, and reading order. Its committed ratchet fails on corpus
  drift, parser-policy drift, denominator drift, vacuous metrics, regressions, and unreviewed
  improvements. Recorded at `935df18`: text content 0.5058, reading order 0.6034, block
  structure 0.1176.

  **Read that as an OCR-pipeline score, not a PDF-conversion score.** Every page in the corpus
  is a single full-page raster wrapped in a PDF — sampled across data sources, each has zero
  text characters, one image, and no vector drawings. So there is no text layer to extract, no
  ruling lines to detect, and no font or layout metadata to analyse: the numbers grade
  Tesseract 5.3.4 at 200 dpi plus our OCR plumbing, and all2md's native PDF text and table
  paths are never exercised. The zero tables follow from the corpus, not from a missing
  capability — a synthetic ruled table is detected identically under the benchmark's own
  parser policy and under library defaults. `unsupported_dimensions` used to mis-attribute
  that corpus property to a parser gap; it now states both sides and points at
  `provenance.corpus_characterization` instead of assigning a cause. This is still exactly the right
  instrument for **Theme 8**, whose subject *is* OCR geometry; it is the wrong one for
  "how well do we convert PDFs" in general, and the docs should not let it be read that way.
  Making the lane actionable is tracked as its own follow-up: stratified scoring, honest
  unsupported messages, and a content floor on block structure.
  Corpora remain split by job:
  - **Structure ground-truth (headline metric):** [**OmniDocBench**](https://github.com/opendatalab/OmniDocBench)
    (CVPR 2025), 981 pages and 9 document types with table, formula, text, and reading-order
    metrics. The scheduled external fidelity lane anchors the public score here.
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

  **Not planned: a head-to-head vs markitdown / pandoc / docling.** The regression-guard half
  of what such a benchmark would offer is the ratchet above, which needs no competitor. The
  comparison half doesn't survive the fact that these tools optimise for genuinely different
  jobs — markitdown for a fast minimal LLM payload, pandoc for typesetting round-trips,
  docling for layout ML. A single fidelity number across four tools with four goals measures
  whose goal the corpus happened to match. Our score against an external ground truth stands
  on its own. *If* a comparison ever gets built, it should be per-use-case, run each tool's
  config as its maintainers would recommend it, and be prepared to lose a column.
- 🚢 **Conversion confidence report** — *shipped (v1.9.0).* `all2md report <file>` and
  `Document.metadata['confidence']` surface the sanity signals the PDF/DOCX parsers already
  computed as guards (table cell-fill density, dot-leader ratio, ghost-image counts,
  near-empty-page ratio) as a structured "quality card" instead of log noise. Reference-free,
  so it works on documents with no ground truth. It is a **breakage detector, not a quality
  gradient** — see the optimizer entry below — and a format that emits no scored signals at
  all is banded `not_assessed` rather than a vacuous `high`.
- 🚢 **Conversion optimizer (`all2md optimize`)** — *shipped (v1.9.0).* Auto-tune converter
  settings for a difficult document (headline case: gnarly PDFs). Searches the parameter space
  (`table_detection_mode`, `detect_columns`, OCR mode/engine, `min_image_dimension`,
  header/footer filtering, dehyphenation, layout model, heading size-ratio, …) and returns
  the settings that maximize a quality score — emitted as a runnable command and a
  `.all2md.toml` snippet. Tunable formats today: `pdf`, `html`, `docx`.
  - **Objective:** neither of the two existing scores. Confidence **saturates** — it is a
    breakage detector, so on anything not visibly broken it pins to `100` regardless of
    settings (measured: 16 option combinations on a two-column PDF produced *one* distinct
    confidence score while the parsed AST produced *four* distinct outcomes). Round-trip
    **measures the wrong half** — it scores the renderer, not the parser, and a garbled table
    round-trips through Markdown perfectly. So `all2md optimize` scores the **parsed AST**
    directly. The lesson generalizes: an objective has to actually vary across the space you
    intend to search, which is worth measuring before building on it.
  - **What the objective does:** body-text retention **gates** the score rather than
    contributing to it — losing a paragraph is data loss, a leftover running header is an
    annoyance, and the two aren't interchangeable at any exchange rate — so retention
    multiplies fitness, cubed, and no amount of tidiness buys back deleted content. The
    tradeable dimensions are weighted: tables (quality-weighted *recall*, so a hallucinated
    table earns almost nothing while a missed real one still costs its cells), structure, and
    cleanliness. Fitness ranks candidates *against each other*; it is not an absolute quality
    score, and `report` / `roundtrip` remain the scores for that.
  - **Search shape:** named presets first, then **coordinate descent** — `sum(len(values))`
    conversions instead of a grid's `prod(len(values))`. Still tens of full conversions at
    ~1s per PDF page, so `--sample-pages` tunes against a slice and `--cache` makes repeat
    runs nearly free (18.5s → 0.3s warm on a 31-candidate run), reusing the Theme 3
    conversion-cache fingerprint.
  - **Two levels:** per-document autotune 🚢, *and* — still open — a corpus-level mode that
    tunes over `benchmarks/corpus/` to improve **shipped defaults**, a concrete step toward
    the self-improving converters in Theme 7.
- 🌙 **Vision-model fallback** — *moved to **Theme 8**.* When structural parsing fails
  (scanned tables, complex figures, handwriting), optionally hand the page to a vision LLM
  and merge its structured output back into the AST. "Merge back into the AST" is the same
  geometry-carrying boundary the OCR engines need, so it is the same interface question.

---

## Theme 3 — Async & scale

See the **Async Architecture Decision** below for the strategy. The shape:

- 🌱 **Async facade** — `ato_markdown` / `aconvert` that offload the CPU-bound sync core via
  `asyncio.to_thread`, so MCP / `serve` can await conversions without blocking the loop.
- 🌱 **Async I/O edge** — `httpx.AsyncClient` path in `utils/network_security.py`.
- 🚀 **Deferred asset resolution** — parse to AST with asset placeholders, then resolve all
  remote assets concurrently (`asyncio.gather`), then finalize. Turns N serial fetches into
  one concurrent batch — the real user-visible speedup for asset-heavy HTML.
- 🚢 **Persistent / incremental search index + shared conversion cache** — *shipped
  (v1.9.0).* The **correctness** half: `--search-index-dir` was keyed only by directory, so
  reusing an index across a changed corpus or a different `paths` set returned **stale
  results**; the persisted index is now invalidated when the corpus or the options change.
  The **feature** half: an opt-in on-disk conversion cache (`--cache` / `--cache-dir`, or
  `ALL2MD_CACHE=1` / `ALL2MD_CACHE_DIR`) stashes parsed ASTs keyed by a fingerprint over the
  source (path + size + mtime), the resolved format and parser options, and the all2md
  version + AST schema — so a changed file, changed options, or a version bump all miss
  cleanly rather than serving a stale AST. Wired into `grep`, `search`, `chunk`, `view`,
  `report`, `roundtrip` and `optimize`, and available programmatically as
  `all2md.conversion_cache.use_conversion_cache(...)`. *Still open:* `serve` is the one
  holdout — it has its own in-process render cache (`--no-cache`) that dies with the process,
  rather than the persistent, fingerprinted one.
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
> (🚢 v1.8.0) rather than a frozen PyInstaller binary. A browser/web UI is still planned.
> The **Action shipped** (see below). Docker and the hosted API are unstarted; Docker was
> considered and parked in the ratchet batch, and the Action no longer depends on it.

- 🌱 **Docker image** — *scheduled in the ratchet batch.* `docker run all2md` as a one-line
  microservice / CI step. Also the building block for the GitHub Action and hosted API below —
  bake PyMuPDF/tesseract in once. It earns its place in an otherwise inward-facing batch by
  doing a second job: it's the version-pinned environment that makes `benchmarks/corpus/`
  numbers comparable across runs and machines (`benchmarks/reference/README.md` already
  concedes ±20-30% drift on one dev box). It also narrows a real pain class —
  "tesseract works standalone but not through all2md" is an environment bug.
- 🚢 **GitHub Action** — *shipped in the ratchet batch, **re-scoped**.* The original pitch —
  "convert docs in this repo to markdown on commit" — solves nobody's actual problem.
  v1.9.0 shipped `report --fail-under` and `roundtrip --fail-under`, so what shipped is a
  **conversion-quality gate**: *fail the build when document fidelity degrades.* Nobody else
  ships that, because nobody else has the scores. It's the Theme 2 ratchet pointed outward —
  built for ourselves first, then shipped.

  Two deviations from the shape sketched here, both deliberate. It is a **composite**
  action, not a Docker one, because the Docker image it was to be built on was parked and
  `pip install all2md[all]` covers the deps that argued for a container. And it ships from
  **this repository's root** rather than a separate `all2md-action` repo, so `@v1.10.1`
  installs all2md 1.10.1 — the gate's verdict *is* the library's score, so a drifting action
  version would silently redefine every consumer's threshold. Marketplace listing is still
  open. See `docs/source/github_action.rst`.
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
  commands, and beyond section ops — table-cell edits, find-and-restructure, programmatic AST
  patches with undo.
- 🌱 **Element re-routing on conversion** — one pass that can drop images/tables entirely,
  extract tables to separate file(s) (combined or per-table), or collate all images/tables to
  the end of the document. Overlaps the chunker's `--drop-elements` (🚢) but as a
  conversion-output restructuring, not just chunking; useful for both human reading and RAG
  prep. Also: **extract text around a table/anchor** and **extend `--extract` to all AST
  element types**.
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

## Theme 8 — Positional fidelity (OCR geometry → provenance → layout)

> **Its own thread, deliberately.** Four items that used to sit in Themes 1, 2 and 4
> ("pluggable OCR engines", "node-level provenance", "layout-aware PDF reconstruction",
> "vision-model fallback") are one dependency chain wearing four hats. Read separately, each
> looks like deferrable plumbing. Read together they are the RAG-trust differentiator and the
> largest remaining bet on this roadmap. Sequenced after the Theme 2 ratchet, on purpose.

**The thesis in one line:** everything that makes a document citable is geometry, and we
throw the geometry away.

### Why the obvious scoping is wrong

The obvious framing — *"add an abstraction for plugging in other OCR engines"* — is the cheap
part and **the wrong part**. Building the socket is genuinely easy: dispatch today is a single
lazy `if/else` in `parsers/_ocr/` over two duck-typed adapters, and there are already three
entry-point registries to copy (`all2md.converters`, `all2md.transforms`,
`all2md.lint_rules`). The transforms registry is the cleanest precedent — it registers its own
built-ins *through the public entry-point table*, so there is no privileged first-party path
to unwind later.

But the adapter contract is:

```python
def ocr_pixmap(pix: fitz.Pixmap, page: fitz.Page, options: PdfOptions) -> str
```

It returns **`str`**, and the geometry is destroyed twice on the way out: EasyOCR already
returns bounding boxes, and our adapter uses them to reconstruct reading order and then
discards them; then the PDF parser wraps the resulting flat string in a single synthetic
PyMuPDF block spanning the whole page.

So a socket on top of this contract lets you plug in Textract, Azure Document Intelligence,
Google Document AI, surya or olmOCR — and then discard precisely the thing you are paying
them for. **The valuable change is the result type, not the plug.** That is a parser change,
and it is the same change that node-level provenance and layout-aware PDF both need. Hence:
one thread.

### Known blockers

- **The engine type is closed.** `OCREngine = Literal["tesseract", "easyocr"]` in
  `constants.py`, with the `choices` list duplicated in the options metadata — an engine name
  lives in three places. A registry-backed `str` with dynamically-populated choices is needed;
  the transforms registry resolves the same tension by validating at lookup time.
- **The "generic" OCR layer is PyMuPDF-coupled.** `fitz.Pixmap` + a live `fitz.Page` in the
  signature — the page only for language auto-detection, which both adapters call themselves.
  Any non-PDF caller would have to fabricate a `fitz.Page`. Both adapters immediately convert
  to PIL anyway, so the natural contract is image-bytes/PIL + `OCROptions`, with language
  detection hoisted out.
- **Engine-specific fields sit on shared options.** `tesseract_config` and `gpu` both live on
  `OCROptions`. This does not scale and a plugin cannot add its own — wants an
  `engine_options: dict[str, Any]` passthrough.
- **OCR is PDF-only in practice.** `OCROptions` is attached only to `PdfOptions` despite its
  own docstring claiming it "can be used by any parser." No image parser does OCR at all.

### Shape (staged, each stage independently useful)

1. 🌱 **A geometry-carrying OCR result type.** Replace `-> str` with a result object
   carrying text + per-span bboxes + confidence. Stop the EasyOCR adapter from flattening;
   stop the PDF parser from collapsing to one page-sized block. **No new engine, no plugin
   API** — this stage is pure internal correctness and is where the value is. Tesseract
   exposes boxes via `image_to_data`, so both existing engines can honour it.
2. 🌱 **Decouple + then socket.** Move to PIL/bytes + `OCROptions`, hoist language detection,
   add `engine_options` passthrough, *then* add an `all2md.ocr_engines` entry-point group
   modelled on the transforms registry. Cheap once (1) fixed the contract; actively harmful
   before it, because it would freeze the lossy signature into a public API.
3. 🚀 **Node-level provenance.** With geometry surviving the parsers, attach (page, bbox,
   char-offset) spans to output nodes and thread them through `all2md chunk` records — closing
   the Theme 1 gap. *This is the RAG-trust differentiator*, and it retroactively upgrades the
   Theme 1 loader adapters from commodity to "the only loader that can cite a bbox."
4. 🚀 **Layout-aware PDF reconstruction** (from Theme 2) — reading order across columns,
   footnote/endnote linking, header/footer stripping, caption↔figure association. All
   geometry consumers; all much easier once (1) and (3) exist.
5. 🌙 **Vision-model fallback** (from Theme 2) — a VLM is just another engine that returns
   structured, positioned output. If (1)–(2) are designed right this is a plugin, not a
   rewrite. Good forcing function for the interface: *design (1) so that a VLM adapter is
   expressible.*

**Release shape:** unlike the Theme 2 ratchet batch, this one is **not** invisible — it
changes a public options surface (2), adds AST metadata (3), and alters output (4). Minor
version, not a patch.

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

**Shipped in the Fidelity & Trust batch** (**v1.9.0**, 2026-07-15): round-trip fidelity
scoring 🚢, conversion confidence report 🚢, DOCX character-style round-trip 🚢, search-index /
conversion-cache correctness 🚢, conversion optimizer 🚢 (the batch capstone), the DOCX/HTML
round-trip asymmetries #70/#71/#72 🚢, and the Markdown round-trip losses 🚢 that the new
`benchmarks/roundtrip` harness surfaced.

**Shipped in the Quality & Speed Ratchets batch** (**v1.10.1**, 2026-07-27). Deliberately
*invisible* — no API change, no new library feature — so it cut as a patch release:

1. 🚢 **The three harnesses now gate CI against committed baselines** — `corpus`,
   `roundtrip`, `startup` (Theme 2). Regressions fail.
2. 🚢 **Startup performance** — the scaling bug was real: `all2md.options` re-exports lazily
   now, options modules 31 → 4, `import all2md` 230 → 162 ms and `--version` 246 → 178 ms on
   CI. `performance.rst` is reconciled — the hand-authored tables are gone rather than
   restated, and the startup work finally has a docs page.
3. ⏸️ **Docker image — parked**, and worth recording why so it isn't revived by accident. Its
   stated justification was to be the reproducible environment the ratchet compares in. That
   turned out to be wrong: the corpus benchmark's reproducibility problem was its *manifest*
   (arxiv queries live, POI tracks `trunk`), not the environment, so no amount of VM pinning
   would have helped. It also cuts against the one-click `uv` install direction. **Do not
   restart this without a fresh, container-specific justification.**
4. 🚢 **GitHub Action, re-scoped** — shipped as a conversion-quality gate. Two deviations,
   both forced by (3) being parked and both improvements: **composite, not Docker**
   (`pip install all2md[all]` covers the deps that argued for a container), and **`action.yml`
   at this repo's root, not a separate repo** — the gate's verdict *is* the library's score,
   so an action that could version-drift from the library would silently redefine every
   consumer's threshold. A Marketplace listing is a separate, public call and is **not** done.

**Shipped in the External ground truth batch** (**v1.11.0**). Two halves, as planned:

5. 🚢 **The OmniDocBench lane, with a recorded baseline** (Theme 2). The normalized result
   records each aggregate, denominator, and sample variance; the gate rejects zero variance,
   so a metric cannot pass merely because an evaluator path stayed constant. Two metric
   defects were found and fixed *before* the baseline was recorded, both of which the run
   reported as a pass.
6. 🚢 **The fuzzer backlog** (#204's half). Seven crash classes and eleven invariant gaps
   fixed across #206–#212 and #235–#240; `KNOWN_INVARIANT_GAPS` is down to one entry
   (#237's markdown arm, which is a deliberate open question rather than a defect).

**Remaining, ordered by leverage-per-effort.**

7. **Make the external lane actionable** (Theme 2) — the cheapest high-value item on the
   board now, and a prerequisite for trusting (8). Three parts, worth batching into one
   change because each invalidates the baseline and costs an ~80-minute re-run:
   **stratified scoring** (the annotations already carry `page_attribute`, which the corpus
   validates as required and the oracle then ignores — one aggregate over newspapers,
   handwritten notes, slides, textbooks and papers is not actionable, and the 9 data sources
   are already known); and the **`block_structure_similarity` content floor**
   ([#256](https://github.com/thomas-villani/all2md/issues/256)). Tracked as
   [#257](https://github.com/thomas-villani/all2md/issues/257). The third part —
   **honest `unsupported_dimensions` messages** — is done: the message now reports the
   input shape beside the parser's output rather than implying we cannot detect tables.
   It needed no re-run, because it changes no score.
8. **Theme 8: positional fidelity** (OCR geometry → provenance → layout). The external
   baseline makes this bet measurable, and the corpus being all-raster means the lane
   exercises precisely the path Theme 8 changes. Use score and denominator changes from the
   pinned lane to decide whether positional provenance improves real pages before expanding
   the design. Note that the recorded run bears on Stage 1's premise: the PDF parser emits
   roughly thirteen blocks per annotated region on OCR'd pages, which is not the "collapses
   to one page-sized block" failure the blocker list describes — re-check that claim against
   the current code before building on it.
9. **OCR the embedded image, not a re-render, when a PDF page is one full-page image**
   (Theme 8, small). Measured on corpus samples: rendering at a fixed 200 dpi produces up to
   **4.3x** the embedded raster's pixels. No detail is lost — the render is native or above
   on every page sampled — so this is a speed and cost item, not a fidelity one, and it
   should not be sold as the latter.
10. **Async facade + async I/O edge** — unblocks the server/MCP story (see the Async
    Architecture Decision); the deferred-asset-resolution phase is the user-visible win. Also
    a prerequisite for clean multi-worker training-corpus loading (Theme 1).
11. **Math support** (Theme 2) — deepens the fidelity moat; pairs with the arXiv source↔PDF
    ground-truth corpus. Note that OmniDocBench cannot grade this: 260 pages carry formula
    ground truth, but on an all-raster corpus recovering them is OCR-side maths recognition,
    not parsing. The arXiv source↔PDF pairs are the instrument that would actually measure it.

**Smaller open items**, none blocking: the markdown arm of
[#237](https://github.com/thomas-villani/all2md/issues/237) (keep the lossy caption demotion
and document it, or round-trip through an HTML comment — a deliberate call, not a defect);
[#140](https://github.com/thomas-villani/all2md/issues/140)/[#178](https://github.com/thomas-villani/all2md/issues/178)
(markdown HTML round trip); [#184](https://github.com/thomas-villani/all2md/issues/184)
(unreachable options classes); [#183](https://github.com/thomas-villani/all2md/issues/183)
(corpus throughput gate, parked on runner variance);
[#186](https://github.com/thomas-villani/all2md/issues/186) (Marketplace listing — a public
call, not an engineering one). Two CI gaps also remain: `scripts/` is in no gate and carries
10 mypy errors, and the Windows leg does not run mypy, so the `msvcrt` branch has never been
type-checked in CI.

Two of the fuzzer's defects were worth doing regardless of how the batch went, because they
are reachable from ordinary input rather than from a generated AST:

- 🚢 **#211 — odt/odp nested link.** Browsers accept nested `<a>` and our HTML parser preserves
  the nesting, so `all2md page.html -t odt` failed on real pages. Fixed.
- 🚢 **#212 — `from_ast` can raise bare `ValueError`/`KeyError`.** A documented contract that two
  renderers did not honour, so `except All2MdError` did not catch what the docs said it would.
  Fixed.

The batch closed as intended: the instrument that generated the backlog was made trustworthy
before we leaned on it further — twice, as it turned out.

Everything below 🚀/🌙 is opportunistic — pull forward whatever a real user asks for. The
RAG-framework loader adapters (Theme 1) remain the cheapest filler on the board (~a day each)
if a later batch needs something user-visible to announce.
