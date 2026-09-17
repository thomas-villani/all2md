# all2md Roadmap

> A living plan for where `all2md` goes next. Nothing here is committed until it is a
> pull request; the sequencing is by leverage per effort, and it changes when evidence
> changes it. Shipped work is summarised in one line and lives in `CHANGELOG.md`.

Legend: 🌱 natural next step · 🚀 ambitious · 🌙 moonshot · ⏸️ parked with a reason

## Where we are (2026-09-17)

**v1.15.0 shipped on 2026-09-16.** Its spine was the DOCX fidelity batch: a Word-generated
ground-truth corpus (`benchmarks/docx`, 23 cases, 66 checks) that now gates every pull
request, and the defect stream it opened is closed at **0 failing checks** — tracked
changes, display equations, style-inherited numbering, the `numFmt` whitelist, content
controls, `w:numStyleLink`, field codes, merged cells, comments, legal numbering, footnotes
and endnotes, list restarts, and bold carried by a character style. The remaining item of
the old `docx-plus` plan, effective formatting, shipped in-tree with its own style cascade,
so that dependency question is settled: not adopted.

The PDF side closed its arc the same release. On the sealed 103-article PMC holdout
(reading of 2026-08-29, corrected ground truth): all2md leads recall of attainable text
outright at **97.3%**, novel share **0.55%** against Docling's 2.05% and pymupdf4llm's
6.26%, and the table gap to Docling is **6.2 points**, of which every point is *row
grouping*: all2md holds 99.8% of every truth table's words, best of the three, and 97% of
Docling's per-table wins are the same words in a different order. The diagnosis
(`benchmarks/comparison/tablediag.py`) concluded that the residue is a model-class
difference, a learned structure model over the page image against geometry rules over
words, and **table work stops there** rather than fitting more heuristics. Section headings
are now scored across every tool and all three lose about a fifth of them to prose
(all2md 79.0%, Docling 80.3%, pymupdf4llm 79.2%).

What that leaves open on PDF is small, named, and not reachable by the levers already
tried: prose over-segmentation around equations (#442, closed on measurement), sub- and
superscript reconstruction in display math (#456's step 3), and the precision half of
gutter-crossing interleaving (#440's remainder). All three are Theme 8 Stage 4 work,
layout reconstruction, and are carried there rather than as open fixes.

**Open issues at this date:** three small bugs filed 2026-09-15 (#503 PDF numbered lists,
#496 RST and #497 AsciiDoc adjacent lists), and three parked by design (#256, #186, #183).

## Next

### v1.15.1 — cleanup ahead of the outward push

Small, user-visible, no new instruments.

- **#503** — the PDF parser recognises bullet glyphs but not decimal `N.` markers, so an
  ordered list comes out as escaped paragraphs. Fix at the source, as #499 decided; the
  golden changes back to an unescaped list.
- **#496 / #497** — the RST and AsciiDoc renderers write two adjacent same-kind lists
  with only a blank line between them, and both formats read that back as one list. The
  Markdown renderer's boundary marker from #495 is the model; both are pinned as strict
  xfails, so the fix must also delete the allowlist entries.
- **Gate the PMC lane on fidelity when its exit criterion is met.** The criterion, written
  2026-08-13, is two consecutive *scheduled* runs that open no new defect issue. The first
  scheduled run (2026-09-15) failed on a housekeeping-timestamp bug (#509, fixed in #510),
  so the count restarts; the lane is monthly, so this lands in a later patch, not this one.

### The next batch: PDF → DOCX fidelity (Theme 2)

"Make this PDF an editable Word document" is the most-requested conversion in the wild, a
path `all2md` technically supports, and nothing measures it. Its fidelity is the product
of the PDF parse, just improved through the comparison arc, and a DOCX-renderer half with
no instrument at all. `benchmarks/roundtrip --via docx` scores `md → docx → md` on
synthetic documents, not whether a two-column paper with figures and tables becomes a
usable Word document. The DOCX batch was the prerequisite: an instrument that re-reads
our own DOCX output through our own parser blames the renderer for every parser defect,
and the parser has now been through a defect stream. The one reader gap still open, nested
tables, is moot here because the PDF parser never emits one.

Instruments, cheapest first. Each is a step; the first two are the batch's spine.

1. **Re-parse scoring.** Convert the PMC corpus's PDFs to DOCX, parse the DOCX back with
   our parser, run the existing JATS oracle on that AST. The delta against the direct
   PDF → AST reading isolates renderer loss with zero new ground truth. Runs in CI on the
   existing corpus pin. The first reading is a defect ledger for the DOCX renderer, which
   has never had one.
2. **Word as the write-side oracle.** `wordlive` reads the converted document back through
   Word's own object model: do styles resolve, do lists number, do tables survive as
   tables, do headings appear in the navigation pane. This is the check the re-parse
   cannot do, because our parser and renderer can agree on a reading Word rejects. The
   probe verified the loop end-to-end on 2026-08-23. Offline, like the DOCX corpus:
   generated readings are committed and dated, never run in CI.
3. **Visual A/B.** `wordlive export-pdf` renders the converted DOCX through Word; compare
   page images against the source PDF. Layout fidelity judged on Word's rendering.
4. **The incumbent baseline.** Word opens PDFs itself, through its reflow importer, and it
   is drivable over the same COM channel. Score Word's own import on instruments 1–3 on the
   comparison lane's terms: defaults, dated readings, prepared to lose a column.

Known gaps to state before the first reading rather than discover after it:

- The DOCX renderer's section, column and floating-figure support is unprobed. A
  two-column source rendered as one column is a legitimate default and should be
  documented as one, not scored as a loss.
- PDF has no structural footnote detection, so converted footnotes cannot become real
  Word footnotes until the parser finds them. A Theme 8 Stage 4 dependency; state it.
- Figures: the PDF parser emits `Figure` nodes with bound captions since v1.13.0. Whether
  the DOCX renderer writes them as pictures with captions Word recognises (`SEQ Figure`
  fields) is exactly what instrument 2 answers.
- Tables: the renderer already lays out colspan and rowspan (`_layout_table_grid`). The
  PDF side's row-grouping residue will show up here as the same 6.2 points and must not
  be re-chased under a new name.

Decisions this batch will need: whether the re-parse lane gets a fidelity gate on its
first reading or stays a ledger until the renderer defect stream runs dry (the DOCX lane
took the ledger route and it was right); and whether Word's import is worth publishing as
a comparison column at all, given that it is a different product with a different goal.

### Then: the outward push (Theme 5)

Mostly writing, so it interleaves with the batch above rather than occupying one. It has
been deferred by three engineering batches on the argument that measurable defect streams
had more leverage; that argument is spent. The pieces:

- MCP-registry listings, and the GitHub Marketplace decision for the quality-gate action
  (#186, a public publication step that needs a yes or a no).
- Upstream-sharing the OCR-gate calibration to pymupdf4llm, whose defaults auto-OCR
  born-digital pages, the exact misfire class the PMC lane measures and gates.
- The announcement itself, with `docs/source/benchmarks.rst` as the artifact: every figure
  beside the control that could falsify it.
- Fillers if the moment wants something new: the RAG-framework loader adapters (Theme 1,
  about a day each), the chunking tutorial, rich `--help` by default.

### Then: Theme 8 Stages 2–3, positional fidelity

The largest remaining bet, deferred three batches running on the same leverage argument.
Stage 1 is substantially shipped. Stages 2 and 3, decoupling the OCR contract and then
node-level provenance, are the RAG-trust differentiator, and structured extraction stays
queued directly behind Stage 3 because a typed field that can cite its page and bbox is
the version nobody else ships. Detail in the Theme 8 section.

---

## Vision

`all2md` is a universal document ↔ Markdown engine with an AST core, a transform pipeline,
50+ parsers and renderers, search, diff, lint, an MCP server, and three external
ground-truth lanes that score it honestly. The next chapter turns that into **the default
substrate for getting documents into and out of LLM workflows**: best-in-class fidelity,
measured, at the scale of real corpora.

Three bets: the quality ratchet (shipped v1.10.1, every harness gates CI), **positional
fidelity** (Theme 8, the single thread that makes RAG citations real), and async and
scale (Theme 3, pulled forward only when a real user needs it).

---

## Theme 1 — RAG-native output

Shipped: `all2md chunk` with eleven strategies and provenance records (v1.8.0),
`llm-minify` (v1.3.0), `--slice` paging (v1.7.1), the `--extract` selector.

- 🚀 **Node-level provenance on every output node** — page, bbox, char offset — so an
  answer can cite exactly where it came from. The geometry has to survive the parsers
  first; tracked as Theme 8 Stage 3.
- 🚀 **Structured extraction** — `all2md extract doc.pdf --schema invoice.json` → typed,
  schema-validated JSON. Document → data, not prose. The biggest unstarted user-visible
  item on the board, sequenced behind Theme 8 Stage 3 so that a field can cite its source.
- 🌱 **Token-budget conversion** — "fit this 400-page PDF into 100k tokens" with
  section-aware elision rather than uniform minification.
- 🌱 **Chunking workflow tutorial** — one `docs/source/chunking.rst` walking chunk → embed
  → retrieve, strategy by document shape, and reading provenance back. No library change.
- 🚀 **Loader adapters, two tiers.** RAG-framework adapters (LangChain `BaseLoader`,
  LlamaIndex `BaseReader`, Haystack `@component`) are thin, a day each, and commodity until
  provenance lands; `metadata` is a plain dict, so they can be enriched later without an
  API break. The training-corpus preprocessor (sharded Parquet / WebDataset / TFRecord,
  `Dataset` wrappers) is the higher-value tier for the ML crowd, and the one that makes
  Theme 3's process-pool work pay.

---

## Theme 2 — Conversion fidelity

Shipped: round-trip scoring and the conversion optimizer (v1.9.0); the CI ratchet over
`roundtrip`, `startup`, `corpus` and the generative fuzzer (v1.10.1); the OmniDocBench raster
lane (v1.11.0); the PMC born-digital lane and its first defect stream (v1.12.0); the figure
pipeline and table admissions (v1.13.0); the head-to-head comparison lane and the column,
equation and table fixes it drove (v1.14.0); the DOCX lane, its defect stream, the PMC
oracle audit, the heading measure and the table diagnosis (v1.15.0).

- 🌱 **PDF → DOCX fidelity** — the next batch; see **Next**.
- 🚀 **Math support** — coverage, not existence: OMML → LaTeX already exists in the DOCX
  parser (fractions, scripts, radicals and n-ary correct; matrices, delimiters and accents
  degrade). PDF equation regions are isolated and de-emphasised since v1.14.0 but their
  sub- and superscripts are not reconstructed. Neither external lane can grade it:
  OmniDocBench's formula pages are rasters and PMC's JATS records MathML the page never
  prints. The instrument is an **arXiv lane**: arXiv's own LaTeXML HTML as truth beside
  the arXiv PDF, probed and viable (real colspan tables, MathML, section nesting, and
  numbered headings that dissolve the heading-control problem). Never parse the `.tex`.
- 🌱 **Script coverage** — every corpus here is English, so a change that deleted all CJK,
  Cyrillic and Arabic content would score perfectly on every lane. The `numFmt` audit
  showed the blind spot already lives in a parser, not only in the corpora: 41 of the 46
  numbering formats Word writes were unrecognised and almost all were CJK, Hebrew and
  Arabic. Until a non-Latin corpus exists (M6Doc is the candidate), write cross-script
  tests rather than reading the benchmarks as coverage.
- 🌱 **Heading recovery** — all three tools lose about a fifth of section headings to
  prose. The triage on our side: 74 run-in headings at 0% recovery and 47 whose bold run
  stops short of the heading text. #296 was closed at a 1.3% class; the heading measure
  says 6.2%; reconcile the two and measure precision *first*, because every run-in gate
  tried so far invented more headings than it recovered.
- 🌱 **"Omni-flavor" viewer** — make `view` and `serve` render the union of Markdown
  dialects. Verified gaps, each currently shown as literal text: raw HTML blocks escaped
  in the viewer (the HTML renderer's default is `escape` and `view` never overrides it;
  render under `sanitize` with an allowlist, the biggest win), GFM alerts, heading
  attributes leaking into slugs, Pandoc inline footnotes and fenced divs, kramdown IAL,
  wikilinks, emoji shortcodes, abbreviations. Footnotes render but with raw labels, no
  hover preview, and no footnote/endnote distinction. Each syntax is a small mistune plugin
  under the existing `parse_*` option pattern; the viewer fixes ship first.
- 🌱 **Corpus-level optimizer mode** — `all2md optimize` tunes one document; a mode that
  tunes over `benchmarks/corpus/` to improve shipped defaults is the concrete step toward
  Theme 7's self-improving converters.
- 🌱 **Widen the fuzzer's node coverage** — the generative strategy builds 19 of 34 AST
  node types; footnotes, definition lists, math, marks and sub/superscript are unreachable
  at any example count, and `benchmarks/roundtrip` has found real bugs in exactly those.
  One node-type group per PR, footnotes first. This is not the same request as raising
  `max_examples`, which deepens only shapes already reachable.
- 🌱 **PDF footnote detection** — structural, not textual; a prerequisite for real Word
  footnotes in PDF → DOCX and for the viewer's footnote work. Theme 8 Stage 4.
- 🌱 **DOCX reader: nested tables** — the one known reader loss left after the DOCX batch.
  A cell's content is read as inline paragraphs only.
- ⏸️ **`docx-plus` adoption** — evaluated 2026-08-04, and every item it was to supply
  (tracked changes, fields, style-inherited numbering, effective formatting) has since
  shipped in-tree. Not adopted; revisit only if a new reader gap names it.
- ⏸️ **Tables against Docling** — closed on evidence (v1.15.0). The 6.2-point gap is row
  grouping, a model-class difference; a learned row-grouper was measured and cannot replace
  the hand rules (they sit outside a logistic regression's whole held-out frontier). Do not
  reopen without a mechanism, not a heuristic.

---

## Theme 3 — Async and scale

**Decision, standing:** the synchronous core stays the source of truth; async is a thin
edge. The core is CPU-bound C extensions (PyMuPDF, python-docx, openpyxl, OCR) with no
awaitable API, and the genuine I/O is a thin remote-asset edge. An async-native core would
pay the full function-colour tax for zero throughput and could not nest inside Jupyter or
our own FastMCP loop; duplicate sync and async implementations only pay off when the core
is I/O. Shape when it is needed: `ato_markdown` / `aconvert` over `asyncio.to_thread`, an
`httpx.AsyncClient` path in `network_security`, and deferred remote-asset resolution with
`asyncio.gather` as the one user-visible win. Batch stays `ProcessPoolExecutor`.

- ⏸️ **Async facade** — off the numbered list since 2026-08-13; it becomes urgent exactly
  when the server/MCP story or multi-worker training-corpus loading finds a real user.
- 🚀 **Deferred asset resolution** — parse to placeholders, resolve remote assets
  concurrently, finalise. Turns N serial fetches into one batch for asset-heavy HTML.
- 🚀 **Parallel batch engine v2** — resume, a failure manifest, as-completed progress.
- 🌱 **`serve` on the persistent conversion cache** — the one command still on its own
  in-process render cache rather than the fingerprinted on-disk one (v1.9.0).
- 🌙 **WASM build** — in-browser, privacy-preserving conversion via Pyodide or a Rust core.

---

## Theme 4 — New formats and domains

- 🌱 **More inbound formats** — iWork, Visio, OneNote, Google Docs export, chat exports
  (Slack, Discord, WhatsApp), Confluence and Notion exports.
- 🌱 **Cloud input sources** — `all2md s3://bucket/key.pdf`, `gdrive:<id>`, Azure Blob,
  reusing the remote-input plumbing HTTP(S) already has. Each backend an optional extra;
  Google Docs via the export API so format detection stays honest.
- 🌱 **Scientific-document lint profile** — the profile mechanism exists (`accessibility`,
  `prose`); the net-new rules are figure and table numbering, caption presence,
  cross-reference integrity, IMRaD ordering, acronym defined on first use. The PMC and
  arXiv corpora are the documents these rules are for.
- 🚀 **Audio and video → markdown** — transcript, chapters, speaker diarisation.
- 🚀 **Spreadsheet semantics** — formulas, named ranges and cross-sheet references, not
  only rendered values.
- 🌙 **Diagram intelligence** — Mermaid renders in `view`/`serve` since v1.8.0; parsing and
  round-tripping Graphviz, draw.io and PlantUML is the gap.

---

## Theme 5 — Ecosystem and distribution

Shipped: one-click `uv` install scripts (v1.8.0), the GitHub Action as a conversion-quality
gate (v1.10.1), `all2md view`/`serve` with mermaid and syntax highlighting.

- 🌱 **The outward push** — see **Next**.
- 🌱 **Rich `--help` by default** — `rich-argparse` plus one shared parser factory and
  `NO_COLOR` wiring, so every subcommand's help is the colour-grouped layout without `--rich`.
- 🚀 **Hosted conversion API** — a freemium endpoint; the backend for a Node client and a
  browser extension, neither of which should be a port (the JS ecosystem has no equivalent
  of our layout analysis or AST, and reimplementing it is a second product).
- 🚀 **pre-commit hook and docs-site generator** on the existing `generate-site` work.
- ⏸️ **Docker** — parked, and not to be restarted without a container-specific reason. Its
  stated purpose was a reproducible benchmark environment; the reproducibility problem was
  the corpus *manifest*, not the environment, and it cuts against the `uv` direction.

---

## Theme 6 — Editing and live workflows

Shipped: the MCP `edit_document` tool with format-preserving write-back (v1.6.0), the
`all2md edit` web editor (v1.1.0).

- 🌱 **CLI edit commands** — insert, replace, delete; then table-cell edits and
  programmatic AST patches with undo.
- 🌱 **Element re-routing on conversion** — drop, extract to separate files, or collate
  images and tables to the end, as a conversion-output restructuring rather than only the
  chunker's `--drop-elements`; extend `--extract` to every AST element type.
- 🚀 **Watch-and-sync daemon** — a continuously updated Markdown mirror of a source document.
- 🌙 **Bidirectional editing** — edit the Markdown, regenerate the DOCX preserving the
  corporate template. PDF → DOCX is this grail's one-way half, and `wordlive`'s read-back
  is the oracle it would need.

---

## Theme 7 — Trust, safety and observability

- 🚀 **Redaction and PII detection** — flag or strip emails, identifiers and secrets during
  conversion.
- 🌙 **Semantic document graph** — a folder as a queryable graph of entities,
  cross-references and citations.
- 🌙 **Self-improving converters** — log failures, generate fixtures from them, suggest
  fixes. The corpus-level optimizer mode (Theme 2) is the first step.

---

## Theme 8 — Positional fidelity (OCR geometry → provenance → layout)

**The thesis in one line:** everything that makes a document citable is geometry, and we
throw the geometry away. Four items that once sat in Themes 1, 2 and 4 are one dependency
chain: a geometry-carrying OCR result, node-level provenance, layout-aware PDF
reconstruction, and a vision-model fallback. Read separately each looks like deferrable
plumbing; together they are the RAG-trust differentiator and the largest remaining bet.

**Why the obvious scoping is wrong.** "Add an abstraction for plugging in other OCR
engines" is the cheap part and the wrong part. The socket is easy (three entry-point
registries exist to copy; the transforms registry is the model, since it registers its own
built-ins through the public table). But the adapter contract returned a flat `str`, and a
socket on that contract lets you plug in Textract, Azure Document Intelligence or surya and
discard precisely the geometry you are paying them for. The valuable change is the result
type, and that is the same change provenance and layout-aware PDF both need.

**Stages, each independently useful:**

1. 🌱 **A geometry-carrying OCR result** — *substantially shipped (v1.12.0).*
   `ocr_pixmap_layout(...) -> list[OcrParagraph] | None` sits beside the flat contract,
   Tesseract fills it from `image_to_data`, and OCR'd pages no longer collapse to one
   block; per-paragraph bboxes reach the AST through `SourceLocation.metadata['bbox']`.
   Open: granularity is the line rather than the span; Tesseract confidence is read only to
   drop negatives and then discarded; the EasyOCR adapter still flattens, which is what
   keeps `-> str` alive as a fallback. Heading classification on a scan is parked with a
   measurement: ink density is the best signal found (AUC 0.85) but the combined classifier
   scored F1 0.36 against a pre-committed 0.6 bar.
2. 🌱 **Decouple, then socket.** Move the contract to PIL/bytes plus `OCROptions`, hoist
   language detection, pass the target coordinate space in explicitly (the layout path
   reads `page.rect` for its scale factors, so hoisting language detection alone is no
   longer enough), add an `engine_options` passthrough, and *then* add an
   `all2md.ocr_engines` entry-point group. Known blockers: `OCREngine` is a closed
   `Literal` with the choices duplicated in three places; `tesseract_config` and `gpu`
   sit on shared options; OCR is attached to `PdfOptions` only, despite its docstring.
   Actively harmful before stage 1 fixed the contract, cheap after it.
3. 🚀 **Node-level provenance.** Attach (page, bbox, char offset) to output nodes and
   thread them through `all2md chunk` records. This retroactively upgrades the Theme 1
   loader adapters from commodity to "the only loader that can cite a bbox", and the DOCX
   corpus's positional truth records, informational since v1.15.0, become scoreable for free.
4. 🚀 **Layout-aware PDF reconstruction.** The PDF residue lives here: prose interleaving
   around equations (#442), sub- and superscript reconstruction (#456), the precision half
   of gutter crossings (#440), structural footnotes, running header and footer stripping.
   All geometry consumers; all easier once stages 1 and 3 exist.
5. 🌙 **Vision-model fallback.** A VLM is another engine returning structured, positioned
   output. Design stage 2 so a VLM adapter is expressible, and it is a plugin, not a rewrite.

Release shape: not invisible. Stage 2 changes a public options surface, 3 adds AST
metadata, 4 alters output. Minor version.

---

## Constraints and negative results worth keeping

These are kept because they are constraints on future work, not history. Each cost real
measurement; do not re-derive them.

- **Demonstrate every gate red before trusting it, including the release gates.** Every
  instrument here has at one point contained a vacuous pass: a green produced by not
  measuring. The Semgrep scan crash-passed for a month; the fuzzer's nightly replayed one
  fixed corpus for months; the lint gate repaired violations in the runner and exited 0.
  A gate shown red once can rot back to green when its dependencies move.
- **Pair a sharp instrument with a noisy one.** The curated round-trip oracle and the
  generative fuzzer; the scripted DOCX corpus and the tracked white papers; the PMC lane's
  gram score and its containment twin. Each is blind where the other sees.
- **Publish every figure beside the control that could falsify it.** On most text metrics
  the highest-scoring converter is one that dumps the raw text layer with no structure at
  all; a score nothing can falsify is not evidence.
- **Recall is blind to order.** Paragraph-swap interleaving read as *exactly zero* recall
  movement while the fix was real. Column work is judged on supported n-grams per page;
  table work on containment beside the gram score, because 69–83% of a truth table's
  5-grams cross a cell boundary and the gram score is mostly an ordering measure.
- **A proxy metric can be blind to its own worst outcome.** The half-empty-row rate is
  *anti*-correlated with row-merge quality, because a section-heading row is legitimately
  half-empty (#448). Price every proxy against ground truth before chasing it.
- **A corpus case names a defect; it does not size one.** One `w:sdt` case asserted one
  loss; probing the wrapper everywhere Word writes it found five, because `python-docx`
  reads direct children in five separate readers. Fix wrappers on the element tree, not at
  a seam.
- **Development corpora burn.** The 110-article PMC set was tuned against on the column
  axis and, it turned out, two table files; it is retained as a second development corpus,
  and the 103-article holdout is sealed mechanically (`test_pmc_holdout_seal.py` fails if
  any tracked file names a held-out article). Never A/B across platforms: a Windows-vs-Linux
  comparison hid ~370 novel n-grams and produced a retracted claim.
- **#442 is not reachable by merge policy.** Both directions measured and rejected; the
  defect is interleaving upstream of paragraph assembly, and 52% of the residue is one
  physics paper. Do not raise `MERGE_THRESHOLD` at it.
- **Excluding rotated text from column detection** moves 25 pages and recovers zero blocks.
- **The GitHub Action lives at this repository's root, not in a separate repo**, so that
  `@v1.15.0` installs all2md 1.15.0: the gate's verdict *is* the library's score, and a
  drifting action version would silently redefine every consumer's threshold. The
  documented pin is a `bump-my-version` target.
- **Docker is parked** (Theme 5) and the **async facade** is off the numbered list
  (Theme 3), each with the reason recorded there.
- **`design/` is gitignored.** One design document was lost that way; designs move
  in-tree (`benchmarks/*/README.md`) before any code depends on them. And never name a
  directory `build/`: ruff, black and mypy all exclude it unanchored, at any depth.
- **The OmniDocBench number grades OCR, not PDF conversion.** Every page is a full-page
  raster, so the raster lane exercises Tesseract plus our plumbing and never the native
  text and table paths. Right instrument for Theme 8; wrong one for "how well do we
  convert PDFs", and the docs must not let it be read that way.

---

## Smaller open items

None blocking.

- **#256** — `block_structure_similarity` scores 1.0 on content-free output and measures
  granularity. It cannot cause a false pass on its own, since text content scores the same
  pages; a content floor is the fix when the raster lane is next touched.
- **#183** — corpus throughput gate, blocked on a runner-variance study. Measured CI
  variance is ~7% and a CPU-class change shifts everything ~18% at once; the
  `startup` gate's raw-plus-normalised agreement rule is the model. The artifacts to
  study accumulate on every push.
- **#186** — the Marketplace listing; part of the outward push.
- **OCR the embedded image, not a 200-dpi re-render**, when a page is one full-page image:
  up to 4.3× the pixels for zero detail gain. Speed, not fidelity.
- **Two CI gaps:** `scripts/` is in no type gate, and the Windows leg runs tests but not
  `mypy`, so the `msvcrt` branch has never been type-checked in CI.

---

## Shipped

One line each; `CHANGELOG.md` has the ledger.

- **v1.15.0** (2026-09-16) — the DOCX ground-truth lane and its defect stream to 0 failing;
  the PMC oracle audit; the cross-tool heading measure; the table diagnosis that closed
  table work on evidence; the corrected ground truth that cut the Docling gap to 6.2 points.
- **v1.14.0** (2026-08-27) — the column, equation, figure-placement and table fixes the
  comparison lane drove; the sealed 103-article holdout; attainable recall 94.7% → 98.9%
  on dev and novel share 1.00% → 0.43%.
- **v1.13.0** (2026-08-19) — the PDF figure pipeline (figures get an AST node, captions bind
  to them), born-digital table admissions, the head-to-head comparison lane, and the
  interleaving fix (#405) that closed the text-survival gap to pymupdf4llm.
- **v1.12.0** (2026-08-12) — the PMC born-digital lane, its dozen PDF fixes, Theme 8 Stage 1,
  and the first *published* fidelity figures, each beside its control.
- **v1.11.0** (2026-08-04) — the OmniDocBench lane and baseline; the fuzzer's crash and
  invariant backlog closed.
- **v1.10.1** — the quality and speed ratchet: every harness gating CI, cold start −28%,
  the GitHub Action.
- **v1.9.0** — round-trip scoring, the confidence report, the conversion optimizer, the
  conversion cache, the DOCX and HTML round-trip asymmetries.
- **v1.8.0** — `all2md chunk`, mermaid and syntax highlighting in `view`/`serve`, one-click
  `uv` install.
