# all2md Roadmap

> A living plan for where `all2md` goes next. Nothing here is committed until it is a
> pull request; the sequencing is by leverage per effort, and it changes when evidence
> changes it. Shipped work is summarised in one line and lives in `CHANGELOG.md`.

Legend: 🌱 natural next step · 🚀 ambitious · 🌙 moonshot · ⏸️ parked with a reason

## Where we are (2026-10-01)

**v1.15.1 shipped on 2026-09-18**, the cleanup patch: PDF numbered lists (#503), and
adjacent same-kind lists that RST and AsciiDoc read back as one (#496, #497). Since then
`main` has carried two DOCX streams, both manual instruments with a committed ledger
rather than a CI gate:

- **PDF → DOCX, renderer side.** `python -m benchmarks.pmc docx` re-reads the PMC corpus's
  articles through our own DOCX output (#521). Its first reading was a six-item defect
  ledger, now worked: characters XML cannot carry crashed 18 of 66 documents (#523);
  captions were never written as captions (#524); nested lists flattened and adjacent
  numbered lists ran together (#527); an image whose picture could not be embedded lost
  its alt text (#526). Two of the six were the instrument's own artifacts, not losses
  (#525 links, #528 heading spaces), which is why every ledger item is now checked
  against the direct AST before it is called a defect. Its follow-ups shipped too:
  Markdown link destinations and emphasis delimiters that read back (#540, #541, the
  latter closing #529), a year at a line start read as a list number (#542), one link per
  text span (#543), and TeX math fonts embedded without a Unicode map (#544). Kept by
  decision: the "image" placeholder alt text for an undescribed picture, in every parser,
  because it records that a picture existed. Left by design: fonts re-encoded per
  document and glyph-number subsets, which no published table can read.
- **DOCX reader, against other people's files.** LibreOffice's Writer regression corpus,
  1,526 files, scored word for word against what Word shows (`benchmarks/libreoffice`,
  #539). Five reader gaps closed (#531–#538, below); export words missed 3,908 → 657,
  267 of them math written as LaTeX, and no file Word opens fails any more.

The PDF side's numbers stand as of v1.15.0 (sealed 103-article holdout, reading of
2026-08-29): attainable recall **97.3%**, novel share **0.55%** against Docling's 2.05%
and pymupdf4llm's 6.26%, and a **6.2-point** table gap that is all row grouping, where
table work stopped on evidence. What remains open on PDF (#442, #456 step 3, #440's
remainder) is Theme 8 Stage 4 layout reconstruction and is carried there.

**Open issues at this date:** #517 (the RST renderer writes a nested list that reads back
as a definition list), and three parked by design (#256, #186, #183).

## Next

### Before the next release

- **#517** — the RST renderer writes a nested list that reparses as a definition list,
  and the parent item's text goes with it.
- **Gate the PMC lane on fidelity when its exit criterion is met.** The criterion, written
  2026-08-13, is two consecutive *scheduled* runs that open no new defect issue. The count
  restarted after #509; two articles' JATS changed upstream and were re-pinned (#522)
  ahead of the 2026-10-15 run, which is the first that can count.

### The next batch: PDF → DOCX fidelity (Theme 2)

"Make this PDF an editable Word document" is the most-requested conversion in the wild, a
path `all2md` technically supports, and nothing measures it. Its fidelity is the product
of the PDF parse, just improved through the comparison arc, and a DOCX-renderer half with
no instrument at all. `benchmarks/roundtrip --via docx` scores `md → docx → md` on
synthetic documents, not whether a two-column paper with figures and tables becomes a
usable Word document. The DOCX batch was the prerequisite: an instrument that re-reads
our own DOCX output through our own parser blames the renderer for every parser defect,
and the parser has now been through a defect stream. The two large reader gaps still open,
text boxes and nested tables (see the next section), are moot here because the PDF parser
emits neither.

Instruments, cheapest first. Each is a step; the first two are the batch's spine.

1. ✅ **Re-parse scoring** (#521). Convert the PMC corpus's PDFs to DOCX, parse the DOCX
   back with our parser, run the existing JATS oracle on that AST. The delta against the
   direct PDF → AST reading isolates renderer loss with zero new ground truth. Manual, by
   decision: no CI step. Its first reading's ledger is worked (see "Where we are"), and a
   second full reading of the development corpus (2026-10-01) confirmed the fixes together.
2. ✅ **Word as the write-side oracle** (`benchmarks.pmc word`). A hidden Word reads the
   converted document back through its own object model: do headings reach the navigation
   pane, do lists number, do tables survive as tables. This is the check the re-parse
   cannot do, because our parser and renderer can agree on a reading Word rejects. Each
   loss is split by who lost it: Word only, our parser only, or both. Windows-only and by
   hand; readings are dated in `benchmarks/pmc/README.md`. The first reading (2026-10-03)
   found four renderer defects our parser hides. Adjacent tables join into one. Every
   bullet list in a document is one list to Word. Every document opens in Compatibility
   Mode. Captions carry no `SEQ` field. Headings, list numbering, links and pictures are
   clean.
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
- Figures: the PDF parser emits `Figure` nodes with bound captions since v1.13.0.
  Instrument 2's answer: every picture arrives and every caption carries Word's Caption
  style (#524), but none has a `SEQ Figure` field, so Word does not number them.
- Tables: the renderer already lays out colspan and rowspan (`_layout_table_grid`). The
  PDF side's row-grouping residue will show up here as the same 6.2 points and must not
  be re-chased under a new name.

Decided: the re-parse lane stays a manual ledger, as the DOCX lane did. Still open: whether
Word's import is worth publishing as a comparison column at all, given that it is a
different product with a different goal.

### Alongside: DOCX reader gaps from the LibreOffice corpus

The DOCX lane's 23 cases are documents we made in Word, so they assert what we believed
the format means. LibreOffice's own Writer regression files
(`sw/qa/extras/ooxml{export,import}/data`, 1,526 `.docx`, MPL-2.0) are documents other
people made, many of them bug reports. A first sweep on 2026-09-29 compared the words
our parser reads against the words Word itself shows for each file (main story, notes and
text-box stories, read over COM):

| Set | Files compared | Identical | Word's words | We missed | We added |
|---|---|---|---|---|---|
| export | 1,311 | 1,021 | 122,096 | 3,908 (3.2%) | 1,895 |
| import | 153 | 128 | 6,235 | 82 | 21 |

Of the missed main-story words, 264 are math glyphs: Word shows Unicode and we write
LaTeX, which is a difference of form, not a loss. What remains, in order:

1. ✅ **Crash on an XML comment in `document.xml`** (#531). lxml gives a comment node a
   function where a tag name should be; comments and processing instructions are now
   skipped wherever they sit. The three files Word opens and we failed on now read.
2. ✅ **Text boxes** (#532). Each `w:txbxContent` is read as ordinary blocks right after
   the paragraph that anchors it (the mammoth convention), and a modern box's VML
   fallback is skipped when its DrawingML original is there. Text-box words missed:
   2,359 → 316, most of the rest in table cells (item 3).
3. ✅ **Nested tables and text boxes in cells.** A cell used to read only its own
   paragraphs, so a table inside it vanished with all its text (28 files; one lost 311
   words, one lost everything). A nested table's cells, and a box anchored in a cell,
   are now read in place as lines of the outer cell. The AST's table cell is inline-only
   in all sixteen renderers, so the parser flattens the nesting rather than making every
   renderer learn it, as the HTML parser already did. **Depth is capped at 30**, about
   where Word gives out: deeper tables are read as a flat run of their paragraphs with
   no recursion, so every word is still read, work stays linear, and no file is rejected.
   lxml refuses XML nested past 256 elements (about 60 table levels) before we see it.
   Export words missed: 1,786 → 781, with no file changing status; the five new extra
   words are list labels Word's text omits and one box the COM reading cannot see.
4. ✅ **Transparent run wrappers.** `w:dir`/`w:bdo` (direction), `w:smartTag` and
   `w:customXml` are unwrapped on the element tree before reading, beside content
   controls. The Arabic file (tdf119143) lost all 71 words; export words missed
   781 → 653, and only the 14 files carrying a wrapper changed.
5. ✅ **Missing optional parts and Strict OOXML.** Missing parts (#536): when an open
   fails, the package is rebuilt in memory without relationships to parts the archive
   lacks and read again (16 files now read, 15 of them ones Word opens). Strict OOXML:
   the same retry renames Strict's `purl.oclc.org` namespaces and relationship types to
   the Transitional ones, which is all the 7 Strict files Word opens needed; all 7 read
   and match Word's words (the equation in `strict.docx` is LaTeX). Every file still
   failing is one Word refuses too: encrypted, malformed XML, or missing content types.

Each fix takes its trigger file into the tests. ✅ The sweep is `benchmarks/libreoffice`, a
manual instrument like the PDF → DOCX ledger: no CI step, the Word reading committed and
dated because it needs Word, and a paired comparison against the base for judging a
change. After items 1–5: export words missed 3,908 → 657 (267 of them math glyphs), and
no file Word opens fails.

### Alongside: inbound formats (Theme 4)

Three format families, chosen 2026-10-01 for value per effort: man pages, the formats
PyMuPDF already opens, and legacy binary Office. Each is a run of small PRs that touches
none of the PDF → DOCX work, so they interleave with it. Decided 2026-10-03: everything
stays pure Python on the standard library where it can. There is no LibreOffice backend,
no `olefile` dependency and no new install extra.

1. ✅ **OLE routing** (#548). One shared detector reads the compound file's root stream
   names (`WordDocument`, `PowerPoint Document`, `Workbook`, `__substg1.0_*`) and routes
   each to its parser, or to a clear unsupported-format error, instead of the Outlook
   parser claiming the OLE signature outright. Real `.msg` files, which had all been
   failing on `message_id`, read again (#549).
2. ✅ **Man pages, both directions.** The man(7) parser (#550) and renderer (#553), and
   `--via man` in `benchmarks/roundtrip` (#554): 36 cases pass, and the 3 expected
   failures are what man cannot express (footnotes, raw HTML). Review fixes:
   #555, #557–#560. Gzipped pages read through the archive fix (#551). Still to do:
   **mdoc(7)**, the BSD macro set, and later a corpus lane with `mandoc -T markdown` as
   the independent oracle.
3. **XPS and OXPS through the PDF pipeline.** The parser hardcodes `filetype="pdf"` on
   stream input; parameterizing it makes each format a thin subclass with no new
   dependency. **MOBI** (decided): we unpack it ourselves, PalmDB records and PalmDOC
   LZ77 decompression, and hand the HTML inside to the HTML parser. PyMuPDF lays
   reflowable text into pages and loses the headings.
4. **Legacy `.doc` and `.ppt`, native, in fidelity tiers.** The bar for shipping `.doc`
   (decided) is all the extractable text, not DOCX-level fidelity.
   - ✅ **CFB stream reader** (#565): `utils/cfb.py` reads every stream, regular and
     mini, v3 and v4. Every chain and size is checked against hostile files, and every
     stream of Word, PowerPoint and Outlook files reads byte for byte as `olefile` reads
     it.
   - ✅ **`.doc` tier 1** (#566, in review): all the text through the piece table, with:
     - footnotes and endnotes, and comments with their author;
     - text boxes, and optionally headers and footers;
     - field results, with `HYPERLINK` as links;
     - tracked deletions hidden;
     - summary-information metadata.

     On 191 LibreOffice corpus files saved as `.doc` by Word, the words read match
     the `.docx` parse except 99 of 9,906, every one explained (equations, generated
     list labels, unreferenced footnotes).
   - **`.ppt` tier 1** next: slide text atoms through `Current User` → `UserEditAtom`
     → persist directory, with the same oracle against `.pptx` twins.
   - ⏸️ **`.doc` tier 2, parked for later:** headings (paragraph styles through the
     STSH, built-in style ids being language-independent), real tables (`fInTable`/
     `fTtp` from the paragraph properties, since a cell end and a row end are the same
     `\x07` without them), lists and their numbers, and bold/italic. The character-run
     reader tier 1 uses for deletions is the start of it. Until then, a table's cells
     read as one paragraph each, and no text is lost. Tier 3 is images.

   The oracle comes free: the scratchpad check saves corpus `.docx`/`.pptx` files as
   `.doc`/`.ppt` with Word and scores each parse against its twin's. It is worth turning
   into a `benchmarks/` lane when tier 2 starts.

### Alongside: reading documents in the terminal (Theme 5)

The README now leads with `rcat`, and a class of tools exists only to do this (doxx for
`.docx`, glow and mdcat for Markdown). Our path renders the AST to Markdown text and lets
`rich.markdown` parse it again in a smaller dialect, so footnotes, math, task lists,
definition lists and admonitions print as raw syntax, and display math loses its `\,`.
Decided 2026-10-05, in this order, design in `docs/plans/terminal-viewer.md`:

1. ✅ **A terminal renderer from the AST.** rich renderables built from the nodes
   themselves, no Markdown string between; `--rich` switches to it (#580 for a whole
   document; `--extract`, `--outline`, `--slice` and the line windows after), and
   `--to terminal` writes it. Needs no new dependency. Preceded by #578 and #579, which
   gave admonitions a single metadata key and read GitHub alerts.
2. 🌱 **An interactive viewer on Wijjit**: a `ContentView` body, a `Tree` outline that
   jumps to headings, a status bar, default/vim/less keys, as `all2md read` (or
   `rcat -i`). A `tui` extra, Python 3.11+ only, since Wijjit needs it; testable headless
   in CI. Starts with a few fixes in Wijjit itself (see the plan).
3. **Search** in the viewer, best done upstream in Wijjit's `ContentView`.
4. **Images** through the Kitty, iTerm2 and Sixel protocols, with Wijjit's half-block
   `ImageView` as the fallback.

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
- ✅ **DOCX reader: text boxes and nested tables** — the two largest losses the
  LibreOffice-corpus sweep found (see **Next**), both read now; nested tables are capped
  at 30 levels against hand-crafted files.
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

- 🌱 **Man pages, XPS/OXPS, legacy `.doc`/`.ppt`, mdoc, MOBI** — in progress (man pages and
  `.doc` tier 1 done); see **Next**.
- 🌱 **More inbound formats**, roughly cheapest first: `.xls` (`xlrd` 2.x still reads it,
  and it slots into the OLE routing table), SRT/VTT subtitles, chat exports (Slack,
  Discord, Telegram, WhatsApp, whose timestamps follow the phone's locale), Notion and
  Confluence exports, draw.io and Visio → Mermaid, Numbers then Pages (from
  `numbers-parser`'s reverse-engineered IWA schemas, which drift between iWork
  versions), and OneNote (Graph API first; a local `.one` reader only on demand, the
  format being intricate and Python having no structural parser for it).
- 🌱 **Cloud input sources** — `all2md s3://bucket/key.pdf`, `gdrive:<id>`, Azure Blob,
  reusing the remote-input plumbing HTTP(S) already has. Each backend an optional extra;
  Google Docs via the export API so format detection stays honest.
- 🌱 **Scientific-document lint profile** — the profile mechanism exists (`accessibility`,
  `prose`); the net-new rules are figure and table numbering, caption presence,
  cross-reference integrity, IMRaD ordering, acronym defined on first use. The PMC and
  arXiv corpora are the documents these rules are for.
- 🚀 **Audio and video → markdown** — transcript, chapters, speaker diarization.
  `faster-whisper` (CTranslate2, no torch; PyAV bundles FFmpeg) behind a `transcribe`
  extra modeled on the OCR engines; subtitle tracks already in the container are read
  before anything is transcribed. The costs are a model download on first use,
  non-deterministic output for tests, and CPU speed; diarization needs torch and stays
  a separate engine.
- 🚀 **Spreadsheet semantics** — formulas, named ranges and cross-sheet references, not
  only rendered values.
- 🌙 **Diagram intelligence** — Mermaid renders in `view`/`serve` since v1.8.0; parsing and
  round-tripping Graphviz, draw.io and PlantUML is the gap.

---

## Theme 5 — Ecosystem and distribution

Shipped: one-click `uv` install scripts (v1.8.0), the GitHub Action as a conversion-quality
gate (v1.10.1), `all2md view`/`serve` with mermaid and syntax highlighting.

- 🌱 **The outward push** — see **Next**.
- 🌱 **Reading documents in the terminal** — an AST-native terminal renderer, then an
  interactive viewer on Wijjit; see **Next** and `docs/plans/terminal-viewer.md`.
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

- **v1.15.1** (2026-09-18) — PDF numbered lists, and adjacent same-kind lists kept apart
  in RST and AsciiDoc.
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
