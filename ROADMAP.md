# all2md Roadmap

> A living, intentionally-wide brainstorm of where `all2md` could go. Nothing here is
> committed — it's a menu of directions, sequenced roughly by leverage and effort.

Legend: 🌱 natural next step · 🚀 ambitious · 🌙 moonshot · ✅ foundation already exists
· 🚢 **shipped**

**Status (2026-08-27).** The born-digital arc that began with the comparison lane is
**closed, and ships as v1.14.0** — 40 commits since v1.13.0. On the development corpus,
against the reading v1.13.0 shipped with (same corpus pin, same runner): attainable recall
**94.7% → 98.9%**, tables **69.1% → 82.7%**, titles 92.5% → 98.9%, text blocks 97.2% →
99.4%, supported share 92.9% → 95.5%, novel share **1.00% → 0.43%**. The table trade that
v1.13.0 published honestly — cell extraction bought structure at the cost of text survival —
is repaid: tables are no longer the worst dimension on this lane.

The defect stream past leg 3 ran on geometry rather than tables. Column detection took three
fixes, each a different way for one block to erase a page: a footer vetoing the channel it
cannot interleave (#445), page furniture measured by *height* rather than distance from the
body (#450 — the 24pt band could not see footers printed 8.6–11.5pt below it), and a
proportional crossing tolerance (#460). Display equations took two (#457, #458): 2,716
emphasis markers removed, controls byte-identical, all 149 scored fields unchanged both
times. Plus clipped-textbox ghost text (#436 — `get_textbox()` ignores `TEXT_CLIP` and
returns text the page erases), figures emitted where they are printed (#430), fenced prose
no longer committed to a grid (#453), list items keeping the lines they wrap onto (#454),
and a Windows corpus-cache bug that read as a flake for weeks and was deterministic (#459).
Both lanes were re-recorded and the OmniDocBench oracle moved to schema 7.

**Three results worth keeping because they are negative.** #442's over-segmentation is
**not reachable by merge policy** — both directions were measured and rejected (merging
across math needs semantics and is one document; refusing math/prose merges shatters blocks
448 → 1193 and median words 19 → 3). The defect is *interleaving*, upstream of paragraph
assembly, so do not raise `MERGE_THRESHOLD` at it. #448 showed a proxy metric that could not
see its own worst outcome: the half-empty-row rate is *anti*-correlated with row-merge
quality, because a section heading row is legitimately half-empty. And excluding rotated
text from column detection moves 25 pages and recovers **zero** blocks.

**The holdout is contaminated, and that is the most important fact on this page.** The
110-article corpus this roadmap has repeatedly described as one "development never tunes
against" no longer has that property: #445, #450 and #460 were all developed directly
against its recorded geometry, its JATS ground truth and its `lost_blocks.json` to choose
rules and thresholds. The table and equation work used the development corpus and is less
affected — it is specifically the **column axis** that is compromised. Consequence: the
2026-08-23 comparison reading is both stale (it predates seven merged fixes) and biased;
quote it as a dated snapshot, never as a current held-out score.

**Done 2026-08-27: the corpus has been refreshed behind a sealed holdout.** The burned
110-article set is retained as a second development corpus (`manifest-tuned.json`) — its
exemplars are real and the tests citing them are good tests — and a fresh **103-article**
holdout was drawn at `--seed-offset 125000`, disjoint from both. The audit that motivated
it found the contamination was **wider than the column axis this page claimed**: six
tracked files named held-out articles, and two of them are table work
(`test_pdf_wrapped_cell_rows.py` transcribes a holdout table verbatim; `_pdf_tables.py`
cites another in a comment). So the table figures were in-sample too. The seal is
mechanical rather than advisory: a separate cache root, and
`tests/unit/test_pmc_holdout_seal.py`, which fails if any tracked file names a held-out
article — run against the retired corpus it catches all six historical leaks. **The fresh
holdout was then read once, on 2026-08-28** — the first genuinely held-out number since
v1.13.0. 103/103 articles for all three tools, zero failures.

**The table gap to Docling is 16.7 points, not 4.8.** On the burned corpus all2md read
77.4% table survival against Docling's 82.2%; on the sealed one it is **69.7% against
86.4%**. Both tools moved, so this is not a regression — it is the old gap having been
measured against data the table work was developed on, which hid about two-thirds of the
true distance. **This is the strongest evidence yet that tables are the right next
target, and it also means the table baseline is lower than this page has been claiming.**

What survived the seal: **novel share, 0.55%** against Docling's 2.05% and pymupdf4llm's
6.26% — barely moved from the in-sample 0.62%, which is what an honest number does when
the corpus changes underneath it. all2md also leads raw precision (93.9%) and is the
fastest of the three. Recall is a three-way tie inside 0.65 points.

**Correction to this page:** all2md is *no longer* the worst table over-emitter. It emits
226 tables against 164 expected (1.38x); pymupdf4llm emits 276 (1.68x) and Docling 206
(1.26x). The "worst over-emission of the three" claim came from the in-sample reading and
is now false.

The speed column of that reading is **not comparable** to earlier ones — all three tools
measured 1.8-2.5x slower than their own records in the same session, and a v1.13.0
worktree measured within 2% of HEAD, so it is ambient machine state rather than a
regression. Read it as an ordering only.

After that, **tables are the next quality target on evidence**, and the sealed reading
sharpens the case rather than softening it: Docling leads table-cell preservation
**86.4% against 69.7%**, a 16.7-point gap. The over-emission framing is retired — at
226/164 all2md sits between Docling (206) and pymupdf4llm (276), so the lever is cell
recovery, not emission count. The engineering
batch order is unchanged: the outward push (13), then the DOCX fidelity batch (21), then
Theme 8 Stages 2–3.

**Status (2026-08-20).** Legs 1 and 2 of the comparison's defect stream are **landed**.
Leg 1 ([#412](https://github.com/thomas-villani/all2md/pull/412)): the caption-blind oracle
is fixed with both artifacts re-recorded, [#257](https://github.com/thomas-villani/all2md/issues/257)'s
strata landed with it (the whole-corpus raster mean hid a 16× spread between handwritten
notes and academic papers), and the movement was attributed before being blessed —
byte-identical per-page scores proved the oracle change contributes zero to the raster
lane, so the baseline drift is the v1.12/v1.13 parser arc, ledgered as
[#411](https://github.com/thomas-villani/all2md/issues/411). Leg 2
([#413](https://github.com/thomas-villani/all2md/pull/413)): the
[#405](https://github.com/thomas-villani/all2md/issues/405) interleaving class is
**fixed and closed**. Measured on dev — reference-page gutters run 14.9–17.9pt against the
20pt threshold across four publishers, and 64 of 455 pages arrive with both columns fused
into one PyMuPDF block — and fixed three ways behind structural guards: channel-based
gutter admission, line-band resegmentation of fused blocks, hyphen joins at block seams.
Dev: 254 → 97 missing attainable blocks, zero newly missing. Holdout, untuned: 469 → 147
(−69%, better than dev — no overfit). Published: attainable recall **95.4% → 98.3%**
(titles 98.8%), raw recall 62.0% against a 62.4% ceiling, resequenced 6.3% → 5.1%; raster
gate flat-to-better. The gap to pymupdf4llm's raw text survival that motivated the
comparison is essentially closed. Residue (boxed regions needing y-segmentation) is
scoped as [#414](https://github.com/thomas-villani/all2md/issues/414), small on both
corpora. **Item 13's louder announcement is unblocked** — #405 was its stated gate. Leg 3,
the Docling table study (item 16), is **closed 2026-08-21** with the arc's single untuned
holdout validation: table survival 69.9% → **76.0%** on the sealed 110-article corpus
(+6.1 against dev's +8.2 — same direction, no overfit signature; the gap to Docling's
82.2% narrows from 12.3 to 6.2 points). The comparison arc is complete; the next table
lever is [#419](https://github.com/thomas-villani/all2md/issues/419).
*(Superseded — #419 landed as [#424](https://github.com/thomas-villani/all2md/pull/424) and
is closed, as is #414. The next table lever is over-emission, not extraction; see the
2026-08-27 status.)*

**Status (2026-08-19).** Batch 12 — **Figures & the born-digital queue** — is complete and
ships as **v1.13.0**: the figure pipeline ([#338](https://github.com/thomas-villani/all2md/issues/338),
[#340](https://github.com/thomas-villani/all2md/issues/340) — figures get an AST node, PDFs
emit them by default, captions bind to them), the born-digital table admissions (word-gutter
grids [#386](https://github.com/thomas-villani/all2md/issues/386), rotated tables
[#389](https://github.com/thomas-villani/all2md/issues/389), two-column regions
[#391](https://github.com/thomas-villani/all2md/issues/391), each behind a measured guard),
the wrapped-heading fix ([#400](https://github.com/thomas-villani/all2md/issues/400)), and
the round-trip defect cluster. The tables bottleneck **moved** in the process — from
under-detection (92 emitted against 121 expected) to over-emission plus a text-survival
trade (table-text recall 83.6% → 69.1% because committed tables route through cell
extraction instead of flowing out as prose) — and the fidelity page states the trade rather
than netting it.

Two new instruments landed with the batch. A **held-out 110-article corpus**
(`manifest-holdout.json`) that development never tunes against — *no longer true as of
2026-08-27, see that status block; the column work was tuned against this corpus* — its
first validation run
landed within a point of the development corpus on every text instrument, so the v1.13
numbers are not overfit. And the head-to-head comparison this roadmap once declared
**not planned** got built anyway (`benchmarks/comparison/`), on exactly the terms the
refusal demanded: defaults for every tool, one normalization path, dated pinned readings,
never in CI, and prepared to lose a column. It lost two — pymupdf4llm wins raw text
survival (98.3% vs 93.5%) and Docling wins table-cell preservation (82.2% vs 69.9%) — and
both are published, because all2md wins the column the refusal said a single number would
hide: invented text, 0.84% against 5.5% (pymupdf4llm's defaults now auto-OCR born-digital
pages) and 2.9% (Docling), at 3–9× their speed.

The comparison paid the way every lane here pays, with a defect stream: **#405**
(side-by-side regions interleave line-by-line — the largest recoverable text-loss class,
~405 of 528 lost blocks) and **#406**, which the diagnosis then **refuted as filed**. The
"66 captions absent from output" were in the output — 101 of 103 verified present in the
raw markdown. The oracle folds a bound caption into `Figure.caption`, a string attribute
`project_ast` never reads, so the better caption *binding* gets, the worse measured recall
gets. The instrument that caught everyone else's flaws had one of its own, and the
lost-block diff pointed at the parser when the parser was innocent. Correcting it is a
measurement change (schema bump + re-record); holdout recall reads 94.6% with the
blindness removed.

Decisions taken this pass: **leg 1** is the oracle caption fix and its re-record, batching
[#257](https://github.com/thomas-villani/all2md/issues/257)'s re-baseline exactly as its
2026-08-13 demotion stipulated ("batch it with the next oracle change"), plus closing #347
and re-measuring #296. **Leg 2** is #405 as the next batch spine — it is Theme 8 Stage 4
work wearing a recall number. **Leg 3** is a Docling table study feeding cell-extraction
text survival. The **outward push (item 13) is unblocked** by its own 2026-08-13
criterion; its low-effort halves (upstream-sharing the OCR-gate calibration to
pymupdf4llm, registry listings) interleave now, and the louder announcement waits until
#405 lands — "measured, honest, and just fixed its biggest known gap" beats announcing the
gap.

**Status (2026-08-13).** A planning pass, not a release. Sequencing item 11 — restore the
PMC corpus to 66 articles ([#332](https://github.com/thomas-villani/all2md/issues/332)) — is
done and sits in `[Unreleased]`, with the published figures now *checked* against the
artifacts they cite. The caption measurement that closed out that work opened a new defect
stream: the **PDF figure pipeline** ([#338](https://github.com/thomas-villani/all2md/issues/338),
[#340](https://github.com/thomas-villani/all2md/issues/340)), where default options emit zero
`Image` nodes and detected captions are discarded in every mode. Decisions taken in this
pass: the next batch is **Figures & the born-digital queue**, the outward-facing push starts
when it ships, the PMC lane's ungated status now has an exit criterion, and structured
extraction is promoted to a numbered slot. See **Suggested sequencing**.

The pass also closed a months-old CI mystery. The generative round-trip gates had been
exiled to a nightly because they took **68 minutes** on CI against ~40 seconds locally, and
six theories had been refuted against that gap — Python version, Hypothesis version, the
example database, example count, coverage instrumentation, a slow runner. The cause was one
word in `tests/conftest.py`: Hypothesis ships a built-in profile named `ci` and auto-loads
it when it detects CI, and `register_profile` *re-loads* a profile that is already active —
so our own `register_profile("ci", …, verbosity=Verbosity.verbose)` landed on the live
profile, and `dev`, registered next and what actually runs, inherited the verbosity. Verbose
pretty-prints every generated example through a printer calling `ast.parse`, ~35s on a
complex document. It could not reproduce locally because off CI nothing re-loads;
`CI=true pytest` reproduces it in one command, and that is the transferable part — an
environment-only oddity needs the environment, not a theory.

The gates are back in per-PR CI ([#342](https://github.com/thomas-villani/all2md/pull/342))
and found a real defect on their **first** run there
([#343](https://github.com/thomas-villani/all2md/issues/343)). Two things about that are
worth keeping. The allowlist entry we wrote for it blamed the wrong component — it read as a
hard-break *rendering* problem and was the AsciiDoc parser never joining a list item's
run-on lines, reachable from three lines of hand-written AsciiDoc rather than from anything
exotic. And the nightly it replaced had been **structurally incapable** of discovering
anything: it swept with `--hypothesis-seed=random`, which loses to the per-test
`derandomize=True`, so it replayed the same corpus every night. Measured by fingerprinting
the drawn documents with and without the flag — identical. That is the vacuous-pass pattern
again, in the instrument whose whole job is discovery.

**Status (2026-08-12).** The **Born-digital ground truth** batch is complete and ships as
**v1.12.0** — 55 commits in eight days. Its spine is a *second* external lane:
`benchmarks/pmc`, a pinned 66-article PMC Open Access corpus of publisher PDFs scored
against publisher JATS. The raster lane below grades our OCR pipeline, as its own entry
concedes; this one grades the native text-layer, table-detection and layout-derived
reading-order paths that most real PDF conversion actually uses. That was the
instrumentation gap that left Theme 2's general claim unmeasurable, and it is now closed.

It paid for itself on first contact, the way the fuzzer did. The batch's other half is the
defect stream the lane found: two columns starting level read right-column-first on a
five-thousandths-of-a-point difference; text rescued from a rejected table region skipping
dehyphenation, so broken words appeared **nowhere in the output at all**; symbol-font list
markers; a heading wrapping onto a second printed line becoming two headings; single math
glyphs becoming headings; and auto-OCR discarding a good text layer on 11 of 66 articles.
**Theme 8 Stage 1 also shipped here** ([#280](https://github.com/thomas-villani/all2md/pull/280)):
OCR'd pages no longer collapse to one page-sized block.

The numbers are finally *published*, too (`docs/source/benchmarks.rst`), each printed beside
the control that could falsify it — 95.3% of attainable text recovered against a 0.4%
wrong-article control — because on most text metrics the highest-scoring converter is one
that dumps the raw text layer with no structure whatsoever, and a fidelity score with
nothing to falsify it is not evidence.

**Three lessons, each sharper than the last batch's.**

First, **the vacuous pass reached the release gates themselves.** The Semgrep scan had been
crash-passing since 2026-07-01 — a pinned action against registry rules it could not parse,
with the wrapper swallowing the non-zero exit — so **v1.11.0 published through a required
check that was structurally incapable of failing.** The Action's `report-fail-under` had the
same shape: it read `score` and discarded `band`, and `report` returns a hardcoded 100 banded
`not_assessed` whenever no detector ran, which is every format but PDF — so an empty file, a
valid one and a deliberately broken one all passed `--report-fail-under 100` identically.
Both now carry a positive control that fails when the check finds nothing. The ratchet
batch's rule was to demonstrate every gate red before trusting it. The correction is that it
applies to the gates *guarding the release*, not only to the ones measuring quality, and that
a gate demonstrated red once can rot back to green when its dependencies move underneath it.

Second, **skepticism needs measuring too.** The v1.12.0 PDF defect stream (sequencing,
below) used to carry a caveat
doubting the "OCR collapses a page to one block" blocker, on the grounds that the lane
reported ~13 blocks per annotated region. [#279](https://github.com/thomas-villani/all2md/issues/279)
checked it: `block_structure_similarity` is a *symmetric* granularity ratio, so 0.077
indicates a 13:1 disparity in **either** direction, and the direction had been assumed rather
than measured. The blocker list was right and the doubt was wrong. An instrument that cannot
express a sign cannot support a claim about one — and a caveat is a claim.

Third, **every corpus here is English**, so all three lanes are blind to script. A change
that deleted all CJK, Cyrillic and Arabic content would score perfectly on every one of them.
The benchmarks page states this; it is a work item, not only a disclaimer.

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
- 🌱 **Chunking workflow tutorial** — *docs gap, added 2026-08-21.* `all2md chunk` is
  mentioned across ~10 reference pages but has no single walkthrough for the workflows
  people actually run it for: chunk → embed → retrieve, choosing a strategy by document
  shape, `--max-tokens`/`--overlap` tuning, and reading the provenance records back. One
  `docs/source/chunking.rst` page with runnable examples; no library change.
- 🚀 **Structured extraction** — *not started* (distinct from the shipped `--extract`
  selector, which pulls sections/tables/figures as Markdown). The ambition here is
  `all2md extract doc.pdf --schema invoice.json` → typed, schema-validated JSON
  (tables → records, key/value fields). Document → data, not prose. *Promoted to a numbered
  slot in **Suggested sequencing** (2026-08-13)* — it is the vision statement's "substrate
  for LLM workflows" claim made literal, and the biggest unstarted user-visible item on the
  board.
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

  **The remainder closed in v1.12.0**, and the last of it inverted a stated posture. `<del>`,
  `<s>`, `<sup>`, `<sub>` and `<mark>` now fold into the AST nodes that already existed for
  their meaning instead of self-escaping (#140), `<mark>` no longer vanishes on the HTML side
  where it was listed as inline with no handler, table captions survive through a marker
  comment (#237, the last of that issue's four formats), and block-level HTML — `<details>`,
  `<p align>` — passes through rather than degrading to a paragraph (#178). That last one
  changed the Markdown renderer's default from `escape` to `pass-through`, because escaping
  was described as a security posture and was not the one doing the work: in the direction
  where untrusted input actually arrives, the HTML *parser* drops `<script>`, `<iframe>`,
  `<form>`, `<object>`, `<embed>` and `<svg onload>` outright, so they never reach a renderer
  to be escaped. All six tracked root documents now round-trip at exactly 100, and the CI
  fidelity gate is re-recorded from 97 to 100 — which means **zero headroom**, so a
  regression there shows up immediately and an edit must be controlled against `main` before
  it is blamed.
- 🌱 **"Omni-flavor" viewer** — *added 2026-08-21; probed, not started.* Make `all2md view`
  and `all2md serve` maximally forgiving of whatever Markdown they are handed: accept and
  *render* the union of flavor features, so the viewer is useful on any file regardless of
  which dialect wrote it. The parser is already most of the way there — every mistune
  plugin (tables, footnotes, math, task lists, definition lists, strikethrough, marks,
  admonitions) is on by default regardless of `flavor` — so the work is the syntaxes
  mistune has no plugin for, plus the viewer's own render policy. Verified gaps, each
  currently rendered as literal text:
  - **Raw HTML blocks are escaped in the viewer** — `<details>`/`<summary>` shows as
    `&lt;details&gt;`. The Markdown renderer passes block HTML through (#178, above), but
    the *HTML* renderer's default is `DEFAULT_HTML_PASSTHROUGH_MODE = "escape"` and
    `view`/`serve` never override it. First fix and the biggest win: the viewer should
    render under `sanitize` (allowlist `details/summary/kbd/sub/sup/abbr/...`) — the
    security posture belongs at the parser, as the #178 note argues.
  - GFM alerts `> [!NOTE]` come out as a plain blockquote with the marker left in.
  - Heading attributes `# Title {#id}` are worse than ignored: the braces leak into the
    heading text *and* the generated slug (`id="title-custom-id"`).
  - Pandoc inline footnotes `^[...]`, fenced divs `::: warning`, grid tables; kramdown
    IAL `{: .class}`; wikilinks `[[Page]]`; emoji shortcodes; abbreviations `*[HTML]: ...`;
    MultiMarkdown table captions `[caption]` after a table.
  - **Footnotes / endnotes** work structurally (a `#footnotes` section, `fnref`/`fn`
    anchors, backlinks, themed CSS in all five themes) but are bare: the label is the raw
    identifier (`[^a]` renders as `[A]`) rather than an ordinal; no hover preview; and no
    footnote-vs-endnote distinction even though the DOCX parser emits both (PDF has no
    structural footnote detection at all).

  Shape: each missing syntax is a small mistune plugin in `parsers/markdown.py` landing
  under the existing `parse_*` option pattern (and `benchmarks/roundtrip` catches any
  spelling that doesn't invert); the viewer fixes are renderer/theme work and can ship
  first. Distinct from the flavor-*output* work above, which is about what we emit.
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
- 🌱 **`docx-plus` integration** — *evaluated 2026-08-04, re-scoped 2026-08-21, no code
  written yet.* The original writeup was never committed (the gitignored
  `design/docx-plus-evaluation.md` it cited is not on disk or in any ref), so this entry is
  now the record of the evaluation; keep it self-sufficient. Verdict: adopt
  selectively, parser read-side first, behind an optional extra pinned
  `docx-plus>=0.6,<0.7`. It composes with `python-docx` rather than replacing it and needs
  only `python-docx>=1.0.0` + `lxml>=4.9` — both already required, so adoption adds no
  transitive dependency weight. Measured against a probe DOCX plus the two real DOCX files
  already tracked in the repo (v2/v3 white papers), not read off the README.
  - **Tier 1 — take these.** Tracked changes: `w:ins`/`w:del` currently vanish silently
    (neither accepted nor rejected, so any default is an improvement) behind a
    `tracked_changes: accept|reject|mark` option — biggest win, smallest diff, proposed as
    the first spike. Effective formatting: replaces the `run.bold or False` read in
    `_get_run_formatting_key` (`src/all2md/parsers/docx.py:1219`), which affects every
    corporate-template document where weight lives on styles rather than runs — **benchmark
    before committing**, it is the one change here with a plausible corpus-gate regression
    path. Fields: one integration fixes both dropped hyperlink URLs and the `Figure :`
    caption bug.
  - **Tier 1b — style-inherited numbering (added 2026-08-21; the descent and the `numFmt`
    whitelist both DONE 2026-09-01).**
    Documents built on custom templates "lost" their list numbering because
    `_detect_list_from_numbering_props` (`src/all2md/parsers/docx.py:1942`) read only the
    paragraph's *own* `w:numPr`; when the template puts the `numPr` on the style (the normal
    corporate-template shape), we fell through to `_detect_list_from_style_name`, which
    regex-matches the literal built-in names `List Bullet`/`List Number`/`List Paragraph` and
    otherwise guesses from left indent plus a `^\d+[.)]` text pattern. The `basedOn` descent
    has now landed on its own, ahead of the effective-formatting spike, because the DOCX lane
    could not measure anything else on this path until it did. The `numFmt` whitelist went
    with it: `_map_numbering_format` used to drop any value outside its five-name whitelist,
    which **demoted the list to bullets** rather than losing it (measured 2026-09-01,
    correcting the claim this entry used to make), and the test is now for the two
    ST_NumberFormat values that are not counters instead of for a list of knowns — 5 of 50
    schemes rendered ordered before, 48 of 50 after. `w:numStyleLink` followed on
    **2026-09-01** and is no longer a hole: the corpus can generate one after all, and
    the route wordlive#104 blocks was not the only one. Word writes a numbering style as
    a *pair* of abstracts — one with the levels and a `w:styleLink`, one with **none** and
    a `w:numStyleLink` — and the paragraphs point at the empty one, so the list demoted to
    bullets exactly as an unrecognised `numFmt` used to. The two are now paired by the
    style they name, which is where ECMA-376's route through `styles.xml` lands anyway, so
    no second part has to be read. Getting the *corpus case* was the harder half: of three
    COM routes, only applying the list style's **template** to the range makes Word write
    the indirection at all — setting `Range.Style` to the list style points the paragraphs
    straight at the nine-level abstract, and a case built that way would have passed while
    proving nothing. What remains on this path is `w:lvlOverride` start values, still
    ignored. (docx-plus#31 records the same gap upstream, in both its reader and its
    cascade.)
    `docx-plus` resolves `num_id`/`num_level` through the `basedOn` chain (each half
    independently, so a level-only override keeps its style's list) and
    `read_list_definitions` gives per-level `fmt`, `%1.%2` text pattern, `start` and
    `start_overrides`. This rides the **same** `iter_resolved_paragraphs` pass as the
    effective-formatting item above, so the two are one spike, and it carries the same
    corpus-gate warning. The `numFmt` whitelist gap is a ~5-line fix we can land today
    without the dependency.
  - **Fields and bookmarks are not "partially handled" — the parser never looks.** A grep for
    `fldChar|fldSimple|instrText|bookmark` in `parsers/docx.py` returns nothing. Observed
    losses: `HYPERLINK` *fields* (older Word, mail-merge, Outlook pastes) keep their text
    and drop the URL because we only handle `w:hyperlink` elements; `REF`/`PAGEREF`
    cross-references keep the cached text and lose the target; `SEQ Figure` is the `Figure :`
    caption bug; `w:bookmarkStart` is unknown XML, so `w:hyperlink w:anchor=` links have
    nothing to land on. `read_fields` returns `FieldInfo(keyword, arguments, instruction,
    result, paragraph_index, begin_element)` and `read_bookmarks` returns
    `BookmarkInfo(name, anchored_text, paragraph_index)`; both index by paragraph, which maps
    onto `_iter_block_items`, and `begin_element` lets us splice a `Link`/`Text` at the right
    inline position rather than string-matching after the fact. Two limits to design around:
    `read_fields` scans the body only (headers, footers and notes are separate parts — fine
    for us), and nested fields fold into the outer one. Purely additive: nothing we emit
    today changes.
  - **Tier 2 — real, narrower.** Table merges close the colspan/rowspan round-trip
    asymmetry the renderer already half-supports (`_layout_table_grid`). Footnote/endnote
    reads could delete ~150 lines of hand-rolled XML (`_process_notes` and friends) — pure
    simplification, no behaviour change.
  - **Tier 3 — renderer, more speculative.** Real footnotes on render (today's
    `visit_footnote_reference` writes a literal `[1]`, so DOCX→MD→DOCX degrades genuine
    footnotes into fake ones); `add_toc`/`mark_fields_dirty` for the existing generate-toc
    transform; redlined DOCX output via `mark_insertion`/`mark_deletion` — a real product
    feature, scope creep unless deliberately chosen rather than a bug fix.
  - **What it will not fix, and was our own job regardless — DONE 2026-09-01:** block-level
    rich-text SDTs (`w:sdt`) are structural containers, not typed form fields, so
    `read_controls` correctly has nothing to return for them. Where they appear on real
    documents they were not marginal: one white paper dropped 95 of 1,645 paragraphs (a
    stale TOC gallery, arguably fine to lose), the other dropped the author's name, twice.
    The plan here was to descend in `_iter_block_items` and skip anything with
    `w:sdtPr/w:showingPlcHdr` set. **Both halves of that plan were wrong**, and probing
    the wrapper before writing the fix is what showed it. Descending at one seam would
    have fixed one of *five* measured losses — a block control, an inline control
    mid-sentence, a control around a table, one around a table row, and one around a
    paragraph in a cell — because every `python-docx` reader looks at direct children and
    each one has its own seam. So the wrapper is removed on the element tree instead,
    exactly as tracked changes are, and no reader learns about `w:sdt` at all. And
    placeholder text is **kept**, not skipped: it is what the page prints, and a
    template's empty fields are much of what makes the template worth reading — skipping
    them would have traded one silent loss for another.
  - **Correction surfaced during evaluation:** `read_controls` throws `DuplicateTagError` on
    real Word output, because Word writes empty/absent `w:tag` on most controls and the
    library keys its result dict by tag. Filed upstream; does not change the Tier 1 call —
    revisions, styles, and fields all worked cleanly on the same real file.
  - **Risk:** pre-1.0 (seven releases in ~2.5 months to 0.6.0, then none through
    2026-08-21 — the pace has cooled, which makes the `<0.7` pin comfortable), so pin the
    version range and keep the parser degrading to today's behaviour when the extra is
    absent. Tier 1 changes shift default parser output, so golden snapshots move — scope
    each item's snapshot/integration updates separately rather than batching.
  - **Sequencing (agreed 2026-08-21), three PRs:**
    1. Tracked changes alone — smallest diff, no benchmark risk; its fidelity-score delta
       tells us whether the rest earns the dependency.
    2. Fields + bookmarks — additive, fixes the dropped-URL and `Figure :` defects, no
       existing output changes.
    3. Effective formatting **and** style-inherited numbering as one spike, corpus-gated —
       this is the one that fixes the custom-template documents. The numbering half landed
       separately on 2026-09-01; what remains here is effective formatting.
    Independent of all three: the `w:sdt` fix and the `numFmt` whitelist gap, **both DONE
    (2026-09-01)**.
- 🌱 **DOCX ground truth via `wordlive`** — *added 2026-08-23, not started.* The "no good
  public benchmark exists for Office" gap below has an instrument now: **`wordlive`**
  (sister project, on PyPI) drives a live Word instance over COM, so a DOCX corpus can be
  *scripted* — the script is the ground truth, exact and free, and **Word's own serializer
  produces the .docx**, which is the PMC lane's design principle (ground truth produced by
  the ecosystem being measured, not by us) applied to Office. The payoff is that the
  authentic XML shapes the `docx-plus` batch targets — numbering on styles rather than
  paragraphs, `w:ins`/`w:del` from real revisions, `HYPERLINK`/`REF`/`SEQ` fields from
  Word's field machinery, SDT content controls, weight on styles — are exactly the shapes
  hand-authored `python-docx` fixtures cannot fake. Design constraints, decided up front:
  - **Generation is offline; CI replays, never regenerates.** Windows + licensed Word
    cannot run in CI, so the corpus is generated locally and pinned by digest,
    PMC-manifest style. This also freezes the Word-version variable that would otherwise
    make readings incomparable across regenerations. **Replay is wired as of 2026-09-01**
    — and as a per-PR *test* rather than the scheduled workflow this entry originally
    imagined, because the corpus being committed bytes means scoring costs seconds and
    has nothing external to be hostage to. The lane went six fixes deep with its gate
    living only on a developer's machine; `tests/unit/test_docx_benchmark.py` now holds
    it (no crash, no control failure, and scoring that cannot silently score nothing),
    with `docx-ledger.yml` publishing the counts weekly as a report.
  - **A scripted corpus is a sharp instrument, not a noisy one** — it measures what we
    thought to script, like `benchmarks/roundtrip` is synthetic-by-design. Pair it with
    the real-document counterpart (the two tracked white papers, a handful of EDGAR
    filings) where truth is coarser but the shapes are unplanned.
  - **Word is a second oracle, both directions.** `wordlive` reads back through Word's
    object model — Word's own interpretation as an independent check on the script's
    expectation (the `benchmarks/roundtrip` two-oracle shape). Pointed at our *renderer's*
    output, "does Word open it and resolve styles/lists as intended" is an oracle for the
    DOCX write side that nothing else here provides — the instrument the Theme 6
    bidirectional-editing grail would eventually need anyway.
  - The family generalizes: `pptlive`/`excellive` are the same trick for PPTX/XLSX
    corpora when those formats get their fidelity turn.
- 🚀 **PDF → DOCX fidelity** — *added 2026-08-23; raised alongside the wordlive lane,
  not started, not probed.* The most-requested conversion in the wild ("make this PDF an
  editable Word document") is a path we technically support and nothing measures:
  `benchmarks/roundtrip --via docx` scores `md→docx→md` on synthetic documents, not
  whether a parsed two-column paper with figures and tables becomes a *usable* Word
  document. Its fidelity is the product of the PDF parse (just improved through the
  comparison arc) and a DOCX-renderer half with no instrument. The instruments now
  exist or are scheduled, cheapest first:
  1. **Re-parse scoring** — convert PMC's PDFs to DOCX, parse the DOCX back with our own
     parser, run the existing JATS oracle on that AST; the delta against the direct
     PDF→AST reading isolates renderer loss with zero new ground truth. *Blocked on the
     wordlive lane's parser fixes*: today the DOCX read side drops nested tables,
     duplicates merged cells and skips SDTs, so the re-parse instrument would blame the
     renderer for the parser's sins. Sequencing therefore falls out for free — this item
     slots naturally after the DOCX fidelity batch (item 21).
  2. **Word as the write-side oracle** — `wordlive` reads back the converted document
     through Word's own object model: do styles resolve, do lists number, do tables
     survive as tables. The probe verified this loop end-to-end.
  3. **Visual A/B** — `wordlive export-pdf`/`snapshot` renders the converted DOCX
     through Word; compare page images against the source PDF. Layout fidelity judged on
     Word's actual rendering, not our own claims.
  4. **The incumbent baseline** — Word itself opens PDFs (its built-in reflow importer),
     drivable over the same COM channel. Scoring Word's own PDF import on instruments
     1–3 gives the honest competitor column, on the comparison lane's terms: defaults,
     dated readings, prepared to lose.
  Known gaps to state up front rather than discover: the DOCX renderer's
  section/column/floating-figure support is unprobed; and PDF has no structural footnote
  detection (per the omni-flavor entry), so converted footnotes cannot be real Word
  footnotes until the parser learns to find them — a Theme 8 Stage 4 dependency. Pairs
  with the Theme 6 bidirectional grail: this is its one-way half.
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

  **Its blind spots, each measured**, because the ratchet batch's lesson demands we look for
  them. The first is closed: injecting deliberate renderer breaks showed that a shape in ~20%
  of documents was caught while one at ~7% (a level-6 heading) passed silently, because
  `@given(documents(), st.sampled_from(TEXT_FORMATS))` at `max_examples=25` gave each format
  ~2 documents. The format is now a `parametrize` argument, so each gets its own 25 and the
  test id names the offender.

  The second is open and much larger: **the strategy can only build 19 of the 34 AST node
  types.** `Comment`, `DefinitionList`/`Term`/`Description`, `FootnoteDefinition`,
  `FootnoteReference`, `HTMLBlock`, `HTMLInline`, `Mark`, `MathBlock`, `MathInline`,
  `Subscript`, `Superscript` and `Underline` are unreachable at any example count, and
  format metacharacters are excluded from the text alphabet by design. This is the
  distinction that matters when someone asks to "expand the fuzzer": raising `max_examples`
  deepens coverage only of shapes already reachable, so **more coverage, not more examples**.
  A footnote round-trip bug is invisible here however long it runs — and `benchmarks/roundtrip`
  has already found real self-escaping-HTML bugs in exactly footnotes and marks, so this is a
  demonstrated gap rather than a theoretical one. Widening it should go one node-type group
  per PR, since each group will bring its own allowlist churn and a batch would make the reds
  unattributable. The cheap companion item is extending the invariant matrix from 6 formats
  to include textile/mediawiki/dokuwiki, which is deterministic and near-free and is exactly
  where the original empty-list-item defects (#160, #159, #119) shipped.

  What it produced on first contact: six crash classes (#206–#211), an exception-contract
  hole (#212), and the first **enumerated** — rather than suspected — list of round-trip gaps
  in the org and asciidoc renderers (table captions, ordered-list `start`, the `#+BEGIN_SRC`
  language, and an asciidoc trailing pipe its own parser reads as a phantom column). What it
  produced on its first *per-PR* run, months later, was #343 — three lines of ordinary
  AsciiDoc that crashed the parser, sitting in a format we had already fuzzed, because the
  nightly it had been exiled to was replaying one fixed corpus rather than drawing new ones.
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
    email / HTML fidelity — hand-build a ~100-doc golden set. *For DOCX this now has an
    instrument: the `wordlive` scripted-corpus entry above (added 2026-08-23).* Sources:
    EDGAR filings
    (financial DOCX/HTML/XBRL), the Enron corpus (mbox/eml threading torture-test),
    Wikipedia HTML dumps, and **arXiv source↔PDF pairs** (free round-trip *math* ground
    truth — pairs with the math-support work).

  **The head-to-head this entry refused got built anyway — on the refusal's own terms**
  (🚢 `benchmarks/comparison/`, 2026-08-19). The original objection stands and shaped the
  design: no single fidelity number across tools with different goals. What shipped is
  deliberately narrow — article-level text survival and invented text, the two instruments
  with published false-positive controls that third-party output can enter — scored on the
  held-out corpus, every tool at its defaults, every tool's markdown re-parsed through one
  normalization path, pinned versions, dated readings, never in CI. And it was prepared to
  lose a column, which it did, twice: pymupdf4llm wins raw survival, Docling wins
  table-cell preservation, all2md wins invented text by 3.5–6.5× and speed. The lane's real
  product is the **lost-block diff** (`lost_blocks.py`) — the truth blocks a baseline keeps
  that we lose — which generated #405 and #406 on its first run. The page instruments
  (reading order, table structure, heading fidelity) remain ours alone; competitors'
  output cannot enter them, and the docs say so rather than letting text survival stand in
  for quality.
- 🚢 **Born-digital ground truth** — *lane landed in `benchmarks/pmc` (v1.12.0).* The raster
  lane above grades OCR; nothing external covered text-layer extraction, vector table
  detection or layout-derived reading order, which is most real-world PDF conversion. This
  one does. Articles come from the `pmc-oa-opendata` bucket, where each versioned prefix
  holds the publisher PDF beside its JATS XML — publisher-produced ground truth with real
  sections, paragraphs and table cell markup. The bucket has no corpus-wide revision, so a
  committed manifest of SHA-256 digests takes that role: loading never lists the bucket and
  revalidates every byte.

  Three design choices are what make it evidence rather than a number. **The corpus is
  characterized independently of the filter that selected it** — 750 pages, 100% with a text
  layer, 81.1% with vector drawings, 0% with the single-full-page-image scan shape, and that
  zero was checked against a known scan first to confirm the test can fire at all. **Ground
  truth is projected onto pages by content only**, never using extracted reading order, so it
  cannot grade the reading-order metric against itself; 95.7% of JATS blocks place, against a
  0.8% false-placement rate when scored against a *different* article. And **every figure
  ships with its control**: wrong-article, reversed, scrambled and halved output, plus OCR
  left in auto mode so "no page needed OCR" stays a measurement that could fail.

  Two dimensions are reported and explicitly refused as gates, with the measurement that
  disqualified them — `block_structure_similarity` separates own-page from wrong-page output
  by ~0.06 and *rises* when half the content is deleted. Whole-article recall ships with an
  attainable ceiling, because only 61.1% of JATS blocks are recoverable from the text layer
  by any parser: structured citations and bylines record words in an order the page never
  prints, so raw recall reads as parser loss that is not there.

  **The lane is ungated on fidelity by design** — it exists to find bugs right now, and
  baselines wait until the defect stream it opened runs dry. It is scheduled monthly and does
  gate on crashing. *Dry* now has a definition rather than a mood (2026-08-13): **two
  consecutive scheduled runs that open no new defect issue → record the fidelity baseline
  and gate**, on the same ratchet shape as the raster lane. Without a written exit
  criterion, ungated-by-design decays into ungated-by-inertia, and from outside the two are
  indistinguishable.
- 🌱 **The PDF figure pipeline** — *opened by the born-digital lane's caption measurement*
  ([#340](https://github.com/thomas-villani/all2md/issues/340),
  [#338](https://github.com/thomas-villani/all2md/issues/338)). Three losses, each verified
  by direct call rather than inferred (#340): **default options emit zero `Image` nodes** for
  a PDF's figures, `include_image_captions` is inert in every attachment mode, and
  vector-drawn figures yield nothing under any settings — raster count ≠ figure count, so
  the caption metric was measuring association against a population that mostly isn't
  there. The fix direction (#338) is to bind captions to figures and **give figures a home
  in the AST** — which is the missing prerequisite for Theme 8 Stage 4's caption↔figure
  association (a caption cannot be bound to a figure the output does not contain), and the
  node where Stage 3's provenance metadata will ride. Headline of the next batch — see
  **Suggested sequencing**.
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
- 🌱 **Scientific-document lint profile** — *added 2026-08-21; deferred when the linter
  shipped.* The profile mechanism exists (`accessibility`, `prose`) and is waiting for
  the net-new rules that would let a credible `--profile scientific` exist: figure/table
  numbering, caption presence and cross-reference integrity ("Figure 3" must exist and
  be referenced), abstract/references presence, IMRaD section ordering, acronym defined
  on first use. Pairs naturally with the PMC/arXiv corpus work in Theme 2 — the same
  documents that stress the PDF parser are the ones these rules are for.
- 🌱 **Cloud input sources** — *added 2026-08-21.* Read documents directly from Google
  Drive/Docs, S3 and Azure Blob (`all2md s3://bucket/key.pdf`, `gdrive:<id>`), reusing
  the remote-input plumbing that HTTP(S) fetching already has. Not the Theme 1 loader
  adapters — those are *output* adapters for RAG frameworks; this is *where the bytes come
  from*. Each backend is an optional extra; Google Docs should export via the API rather
  than the download-as-DOCX path so the format detection stays honest.

---

## Theme 5 — Ecosystem & distribution

> **Install experience — decided.** We shipped one-click **`uv`-based install scripts**
> (🚢 v1.8.0) rather than a frozen PyInstaller binary. A browser/web UI is still planned.
> The **Action shipped** (see below). Docker and the hosted API are unstarted; Docker was
> considered and parked in the ratchet batch, and the Action no longer depends on it.

- 🌱 **Rich `--help` by default** — *added 2026-08-21; deferred from the Fidelity & Trust
  quick-wins track as bigger than a quick win.* The main command has a bespoke rich
  renderer gated behind `--rich`; the ~25 subcommand parsers are plain argparse with only
  two `formatter_class` overrides and no shared factory. The full version is
  `rich-argparse` + one shared parser factory + `NO_COLOR`/non-TTY wiring, so every
  `all2md <cmd> --help` is the same colour-grouped layout without a flag. Small, visible,
  and a natural filler for a distribution-themed batch.
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
def ocr_pixmap(pix: pymupdf.Pixmap, page: pymupdf.Page, options: PdfOptions) -> str
```

It returns **`str`**, and the geometry is destroyed twice on the way out: EasyOCR already
returns bounding boxes, and our adapter uses them to reconstruct reading order and then
discards them; then the PDF parser wraps the resulting flat string in a single synthetic
PyMuPDF block spanning the whole page.

**The second of those two losses is now fixed** (🚢 v1.12.0). A geometry-carrying contract
sits beside the flat one — `ocr_pixmap_layout(...) -> list[OcrParagraph] | None` — which
Tesseract implements through `image_to_data`, and the PDF parser emits one block per
returned paragraph. On the sampled OmniDocBench pages that took a page from a single box
covering the whole rectangle to 54 distinct ones. The first loss stands: EasyOCR still
returns flat text and still discards its own boxes, so `ocr_pixmap_layout` returns `None`
for it and `-> str` remains a live fallback rather than a replaced one.

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
- **The "generic" OCR layer is PyMuPDF-coupled.** `pymupdf.Pixmap` + a live `pymupdf.Page` in
  the signature. Any non-PDF caller would have to fabricate a `pymupdf.Page`. Both adapters
  immediately convert to PIL anyway, so the natural contract is image-bytes/PIL +
  `OCROptions`, with language detection hoisted out. **This got harder, not easier:** the page
  used to be needed only for language auto-detection, but `ocr_pixmap_layout` also reads
  `page.rect` for the scale factors that map results back into PDF points. Hoisting language
  detection is therefore no longer sufficient on its own — the target coordinate space has to
  be passed in as well.
- **Engine-specific fields sit on shared options.** `tesseract_config` and `gpu` both live on
  `OCROptions`. This does not scale and a plugin cannot add its own — wants an
  `engine_options: dict[str, Any]` passthrough.
- **OCR is PDF-only in practice.** `OCROptions` is attached only to `PdfOptions` despite its
  own docstring claiming it "can be used by any parser." No image parser does OCR at all.

### Shape (staged, each stage independently useful)

1. 🌱 **A geometry-carrying OCR result type** — *substantially shipped (v1.12.0).*
   `OcrParagraph`/`OcrLine` exist, Tesseract fills them from `image_to_data`, and the PDF
   parser no longer collapses a page to one block; per-paragraph bboxes reach the AST
   through `SourceLocation.metadata['bbox']`. Reading order comes from the OCR engine, which
   already emits blocks across columns correctly, rather than being rebuilt from `y` —
   re-sorting by vertical position assumes a column is one top-to-bottom run.
   **Three pieces are still open:** granularity is the line rather than the span; confidence
   is *read* from Tesseract only to drop `conf < 0` rows and then discarded, so nothing
   downstream can weigh a low-confidence region; and the EasyOCR adapter still flattens,
   which is what keeps `-> str` alive as a fallback instead of replacing it. A fourth piece
   is **parked with a measurement**: heading *classification* on a scan needs a signal other
   than font size, since `_pdf_headers.py` reads its histogram from an empty text layer. Ink
   density is the best candidate found (AUC 0.85) but the combined classifier scored F1 0.36
   against a pre-committed 0.6 bar; before/after spacing asymmetry and centredness were
   refuted outright. **No new engine, no plugin API** — this stage is pure internal
   correctness and is where the value is.
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

**Shipped, items 1–10.** Five batches, each ledgered in `CHANGELOG.md` at more detail
than belongs in a planning document: **v1.9.0** Fidelity & Trust (round-trip scoring,
confidence report, conversion optimizer, the DOCX/HTML round-trip asymmetries) · **v1.10.1**
Quality & Speed Ratchets (the three harnesses gating CI against committed baselines; startup
230 → 162 ms) · **v1.11.0** External ground truth (the OmniDocBench lane and its baseline;
the fuzzer backlog, `KNOWN_INVARIANT_GAPS` down to one) · **v1.12.0** Born-digital ground
truth (the `benchmarks/pmc` lane, the ~dozen PDF fixes it found, Theme 8 Stage 1, and the
published figures) · **v1.13.0** Figures & the born-digital queue (see item 12).

Two decisions from those batches are kept here because they are *constraints*, not history:

- ⏸️ **Docker — parked, and do not restart without a fresh, container-specific
  justification.** Its stated purpose was to be the reproducible environment the ratchet
  compares in. That was wrong: the corpus benchmark's reproducibility problem was its
  *manifest* (arxiv queries live, POI tracks `trunk`), not the environment, so no amount of
  VM pinning would have helped. It also cuts against the one-click `uv` install direction.
- 🚢 **The GitHub Action is composite and lives at this repo's root, not in a separate
  repo** — deliberately, because the gate's verdict *is* the library's score, so an action
  that could version-drift from the library would silently redefine every consumer's
  threshold. The documented pin is a `bump-my-version` target as of v1.14.0 for exactly that
  reason. A Marketplace listing is a separate, public call and is **not** done — it is in
  item 13's scope.

**Remaining, ordered by leverage-per-effort.**

11. 🚢 **Restore the PMC corpus to 66 articles** ([#332](https://github.com/thomas-villani/all2md/issues/332),
    Theme 2) — *done post-v1.12.0; shipped in v1.13.0.* The replacement was drawn by
    re-walking the one seed through the committed stride and filter rather than hand-picked,
    the reference and the published figures moved **in the same change**, and the published
    page is now *checked* against the artifacts it cites — a stale figure there used to read
    exactly like a measured one. The headline readings held to the published precision
    (95.3% attainable-text recall), which is what a representative corpus should do when one
    article of 66 swaps.
12. 🚢 **Figures & the born-digital queue** (Theme 2 → Theme 8) — *shipped as **v1.13.0**;
    see the 2026-08-19 status block for the ledger.* Of the queue as planned below: the
    figure pipeline shipped in full, tables moved from a detection deficit to an
    over-emission + text-survival trade (the bottleneck the plan names is stale), the
    #343 intermittent render crash never recurred, and run-in headings (#296) stayed
    parked pending the post-#401 re-measure now owed. The original plan, kept as the
    record: the spine is the **PDF figure pipeline**
    ([#340](https://github.com/thomas-villani/all2md/issues/340),
    [#338](https://github.com/thomas-villani/all2md/issues/338)) — see the new Theme 2
    entry. It is user-visible in a way benchmark plumbing is not ("your PDF's figures now
    appear at all"), and giving figures an AST home is groundwork Theme 8 Stages 3–4 sit on,
    so the batch advances the big bet rather than deferring it. Around the spine, the rest
    of the lane's queue: **tables remain the worst area** (92 emitted against 121 expected
    on the restored corpus, with *detection* rather than extraction as the bottleneck, even
    after the v1.12.0 text-alignment fallback), the remainder of the **list gap** (the
    marker-rule half is fixed — the item-end rule #299 and symbol-font bullets #300 are both
    closed — leaving markerless lists, which no marker rule can recover, and a re-measure of
    the 0.059 recall now that the fixes are in). The fuzzer's newest find
    ([#343](https://github.com/thomas-villani/all2md/issues/343)) is already fixed; an
    intermittent PDF render crash from the same sweep is **uncharacterised** — it appeared in
    2 of 4 runs and then not in the next 4, so it is open on a small sample rather than
    cleared. Run-in headings
    ([#296](https://github.com/thomas-villani/all2md/issues/296)) stay **parked with a
    measurement**: every gate tried invents more headings than it recovers, and the
    body-length rule that looked clean on 12 articles collapsed on 66.
13. **The outward-facing push** (Theme 5) — **unblocked 2026-08-19** by its own criterion:
    batch 12 shipped. Split decision rather than a start: the low-effort halves interleave
    now — upstream-sharing the OCR-gate calibration to pymupdf/pymupdf4llm (their defaults
    now auto-OCR born-digital pages, the exact misfire class the PMC lane measured and
    gated; goodwill *and* the strongest possible credibility artifact for the comparison),
    MCP-registry listings, the Marketplace call
    ([#186](https://github.com/thomas-villani/all2md/issues/186)) — while the louder
    announcement waits for item 15 (#405), the largest known text-loss class, to land
    first. The original decision, kept as the record: (decided 2026-08-13: starts when
    batch 12 ships).
    The public-channels work was deferred until the born-digital benchmark landed — it
    landed, and `docs/source/benchmarks.rst` with a control beside every figure is exactly
    the artifact that makes a listing credible rather than promotional. Scope: MCP-registry
    listings, the Marketplace call
    ([#186](https://github.com/thomas-villani/all2md/issues/186)), and — if the moment wants
    something new to announce — the Theme 1 loader adapters as filler. Sequenced *after* the
    figure batch on purpose: fix "figures don't appear" before inviting eyes. The push is
    mostly writing rather than engineering, so it can interleave with early Theme 8 work
    instead of occupying a batch alone.
    **(2026-08-23) Promoted from interleave to the next batch outright.** Its own gating
    criterion (#405) has been satisfied since 2026-08-20 and the comparison arc is closed,
    so the announcement moment — "measured, honest, and just fixed its biggest known gap" —
    is *now*, and it is perishable: the comparison readings are dated snapshots against
    pinned competitor versions, and pymupdf4llm/Docling keep moving. Waiting further is the
    ungated-by-inertia pattern this roadmap diagnosed for the PMC lane, in item form. The
    Theme 1 loader adapters, the chunking tutorial and rich `--help` are the natural
    interleave, since the push itself is mostly writing.
14. 🚢 **Leg 1: make the oracle read what the AST carries** (Theme 2, small) — **landed
    2026-08-20 as [#412](https://github.com/thomas-villani/all2md/pull/412)**; #406 and
    #257 closed, #347 closed, #296 re-measured and re-parked, drift ledgered as #411.
    The original scope, kept as the record:
    `project_ast` yields caption text from the `caption` attributes on Figure/Table/Image
    instead of being blind to them — the #406 fix. It is a measurement change, so it takes
    the full re-record workflow: `SCHEMA_VERSION` bump, CI re-record of
    `benchmarks/pmc/reference.json`, fidelity-page update, and — batched in, as its
    demotion stipulated — [#257](https://github.com/thomas-villani/all2md/issues/257)'s
    OmniDocBench re-baseline, since both lanes share the oracle. Riders: close #347 (only
    the inexpressible dokuwiki entry remains) and re-measure #296 post-#401. The correction
    is flattering (holdout attainable recall 93.5% → 94.6%; tables and titles unchanged, so
    the published trade narrative survives), which is exactly why it must land through the
    verbatim-gated re-record rather than quietly.
15. 🚢 **Leg 2: #405 — side-by-side regions interleave line-by-line** (Theme 2 → Theme 8
    Stage 4) — **landed 2026-08-20 as
    [#413](https://github.com/thomas-villani/all2md/pull/413)**; #405 closed, residue
    scoped as [#414](https://github.com/thomas-villani/all2md/issues/414). The discipline
    held exactly as written below: tuned on dev (254 → 97 missing attainable blocks, zero
    newly missing), validated on the holdout untuned (469 → 147, −69% — better than dev),
    attainable recall 95.4% → 98.3% published through the verbatim-gated re-record.
    The original scope, kept as the record: the largest recoverable text-loss class:
    two-column reference lists whose
    tight gutter the column split never fires on, and boxed sidebars beside body columns
    that are not page-level columns at all; y-order then shreds both, destroying adjacency
    while every word survives — which is also what feeds the 6.1% resequenced share. High
    regression risk of the table-guard kind, so the same discipline: tune against the
    development corpus with the lost-block diff as the instrument, A/B every guard, validate
    on the holdout without tuning against it. This is geometry work — the batch advances
    Theme 8 Stage 4 under a recall number.
16. **Leg 3: the Docling table study** (Theme 2) — **landed 2026-08-20** (PRs
    [#418](https://github.com/thomas-villani/all2md/pull/418),
    [#420](https://github.com/thomas-villani/all2md/pull/420)), and the study refuted its
    own premise. Docling's 82.2%-vs-69.9% table lead was not "cell extraction keeps words
    ours drops": word-level survival was at parity (99.5% vs 99.4%) and continuous gram
    recall tied — the whole published gap sat at the binary 0.80 per-table bar, fed by
    *adjacency* damage, not lost text. The mechanisms, measured and fixed behind guards:
    wrapped cells emitted one row per printed line
    ([#416](https://github.com/thomas-villani/all2md/issues/416), the word-gutter side),
    and the same shred plus ``Table.extract()`` clipping characters at cell rects on the
    ``find_tables()`` side ([#417](https://github.com/thomas-villani/all2md/issues/417) —
    cell text now rebuilt from the page's own word boxes when a digit-aware loss test
    fires). Dev table survival 69.1% → **77.3%**, lane precision 94.8 → 94.9, novel share
    0.84 → 0.80%, zero collateral. The residue has names now: column boundaries drawn
    through cell content and bbox-clipped regions
    ([#419](https://github.com/thomas-villani/all2md/issues/419)). **Closed 2026-08-21**
    by the arc's single untuned holdout validation: table survival 69.9% → **76.0%**
    (+6.1 points on a corpus the fixes never saw, against +8.2 on dev — no overfit
    signature), overall attainable recall 98.5%, precision 94.9%, novel 0.7%. The gap to
    Docling's 82.2% narrows from 12.3 to 6.2 points, and per the discipline no tuning
    follows this reading.
17. **Theme 8: positional fidelity** (OCR geometry → provenance → layout). Stage 1 is
    substantially done; the open pieces are span granularity, carrying OCR confidence through,
    and the EasyOCR adapter that still flattens. Then Stage 2 (decouple the contract from
    PyMuPDF, *then* socket it) and Stage 3 (node-level provenance), which is the RAG-trust
    differentiator and the largest remaining bet on this roadmap. Both lanes can now measure
    it: the raster one exercises the OCR path directly, and the born-digital one is the
    control that says whether a geometry change broke the text-layer path.
    **(2026-08-23) Re-sequenced behind the DOCX fidelity batch (item 21) — a decision, not
    drift**, recorded the way the async facade's demotion was: three batches running, this
    item has lost the leverage-per-effort contest to measurable defect streams, and that was
    correct while the PDF stream was rich. The PDF residue is now named and small
    (#419, #414, caption snapping — the first two closed since, leaving #440 and #442 open
    and neither reachable by the levers already tried), DOCX has an agreed spike sequence
    *and* a new
    ground-truth instrument (`wordlive`, Theme 2), so DOCX goes first. Stages 2–3 are next
    after it, and structured extraction (item 19) stays queued directly behind Stage 3.
18. **Script coverage in the benchmarks** (Theme 2, cheap, blind spot). Every corpus here is
    English, so a change that deleted all CJK, Cyrillic and Arabic content would score
    perfectly on all three lanes. Until a non-Latin corpus exists, a character-level change
    is unmeasured no matter how green the run — write cross-script tests rather than reading
    the benchmarks as coverage. M6Doc (scanned + CJK) is the obvious candidate corpus.
19. **Structured extraction** (Theme 1, promoted 2026-08-13). `all2md extract doc.pdf
    --schema invoice.json` → typed, schema-validated JSON — document → *data*, not prose.
    The biggest unstarted user-visible item on the board. Sequenced *behind* Theme 8 Stage 3
    rather than before it, deliberately: extraction wants the same provenance the loader
    adapters want, and a typed field that can cite the page and bbox it came from is the
    version nobody else ships.
20. **Math support** (Theme 2) — deepens the fidelity moat; pairs with the arXiv source↔PDF
    ground-truth corpus. Note that neither external lane can grade it: OmniDocBench's 260
    formula pages are rasters, so recovering them is OCR-side maths recognition rather than
    parsing, and the PMC lane's JATS records maths as MathML the page does not print in that
    form. The arXiv source↔PDF pairs are the instrument that would actually measure it.
21. **The DOCX fidelity batch** (Theme 2, added 2026-08-23) — the next *engineering* batch,
    slotted between the outward push (13) and Theme 8 Stages 2–3 (17). DOCX is the next
    fidelity frontier by the same logic that opened the PDF arc: real defects are already
    named (tracked changes vanish silently, `HYPERLINK`/`REF`/`SEQ` fields never read,
    style-inherited numbering lost on corporate templates, `w:sdt` blocks dropping an
    author's name — every one of those but the fields now fixed) and the instrument gap is
    now closable. Shape, in order:
    - **The `wordlive` ground-truth lane first** — see the Theme 2 entry. The PDF arc
      worked because the PMC lane produced a defect stream and a gate *before* the fixes;
      walking into DOCX with only the self-referential `roundtrip` score would repeat the
      pre-instrument era this roadmap spent v1.11–v1.12 climbing out of. A modest scripted
      corpus plus the real-document counterpart is enough to start; it does not need the
      PMC lane's scale to be a gate.
    - **The two free-standing fixes** that need no dependency: the `w:sdt` block descent
      and the `numFmt` whitelist gap. **Both are DONE (2026-09-01)**, and both taught the
      same lesson — a corpus case names a defect, it does not size one.

      The **`w:sdt` descent** turned out not to be a descent. One corpus case asserted one
      thing (a block control swallows its paragraph); probing the same wrapper everywhere
      Word writes it found **five** silent total losses, because `python-docx` looks at
      direct children in five separate readers: the body block walk, `Paragraph.runs`,
      `tbl.tr_lst`, `tc.p_lst`, and inline content iteration. A fix at one seam would have
      left four for a user to find, so the wrapper is unwrapped on the element tree before
      any reader sees the document — the same treatment tracked changes already get, and
      the module says so. Placeholder text is kept rather than skipped as originally
      planned: it is what the page prints.

      The **`numFmt` whitelist** was **sized** first (2026-08-31,
      `benchmarks/docx/generate/numfmt-map.json`): Word writes 46 distinct `w:numFmt`
      values and `_map_numbering_format` recognised five — and that set was almost entirely
      CJK, Hebrew and Arabic numbering, which makes it item 18's script blind spot showing
      up in the parser rather than only in the corpora. Two things about it were
      **measured before starting and both were wrong on the record** (2026-09-01). The
      symptom is not an ordered list going undetected: with the numbering reachable, an
      unrecognised `numFmt` leaves the list intact and **demotes it to bullets**, because
      `_map_numbering_format` returns `None` and the fallback text sniff defaults to
      bullet. And the corpus could not isolate it at all — both numbering cases put
      `numPr` on the *style*, so the whitelist sat behind the style-descent defect and
      widening it alone would have flipped zero checks. Hence the order below: the style
      descent landed first, `numbering/numfmt-decimal-zero` then failed for its own stated
      reason, and the whitelist fix flipped it the same day — the `numbering` family is
      clean. The fix was an inversion, not a wider whitelist: only `bullet` and `none` are
      not counters, so everything else is ordered, including values Word has yet to invent.
    - **The agreed `docx-plus` three-PR sequence** (2026-08-21): tracked changes, then
      fields + bookmarks, then effective formatting + style-inherited numbering — the last
      being the one with the flagged regression path, which is exactly what the new lane
      exists to gate. **The first is DONE**
      ([#480](https://github.com/thomas-villani/all2md/issues/480), 2026-09-01): revision
      markup is resolved away on the element tree before any reader touches the document,
      under a `revisions` option of `accept` (default) / `reject` / `mark`. Resolving at
      the tree rather than at each reader is the load-bearing decision — `w:ins` reaches
      paragraph text, run iteration, list and heading detection, image discovery and table
      cells alike, and patching them one at a time would have left the next one to be
      found by a user. `mark` reuses the existing AST (`Strikethrough` plus a `revision`
      entry in node `metadata`) rather than adding a node type, a **user decision** that
      knowingly accepts the GFM-flavour limitation. **The style-inherited numbering half
      of the third is also DONE** (2026-09-01), taken out of order because it was blocking
      the `numFmt` measurement: the `w:basedOn` chain is walked and `ilvl`/`numId` are
      each taken from the nearest place that sets them, the way Word merges paragraph
      properties. The flagged regression path was real and the lane caught both halves of
      it — numbering markup that used to be unreachable brought its own traps (a `numPr`
      with an `ilvl` and no `numId`, which Word's own Subtitle style carries and which is
      not a list), and a level inherited from a style cannot express nesting, so
      indentation still nests where `ilvl` is not set on the paragraph itself.

    **The lane is designed (2026-08-23), step 1 landed (2026-08-31), and the first six
    fixes it found have shipped (#481, #480, style-inherited numbering, the `numFmt`
    whitelist, content controls, `w:numStyleLink`)** — the
    design is now `benchmarks/docx/README.md` and the live-probed generation machinery,
    every recipe verified in the saved file's XML, is `benchmarks/docx/generate/`. It was
    written under `design/` first and moved in-tree before any code depended on it, per
    the lesson of the lost docx-plus writeup: `design/` is gitignored. Every family is
    generatable: raw
    `HYPERLINK`/`REF`/`SEQ` fields, real `w:ins`/`w:del`, style-inherited numbering via
    a `LinkToListTemplate` COM hatch (numPr on the style only, verified), content
    controls with genuine `w:showingPlcHdr`, style-carried weight. Decisions taken:
    **v1 is ~2–4 cases per family (≈25–30 documents)**, hand-reviewed before blessing,
    scaled after the first defect stream (the PMC 12→66 pattern); **the lane publishes
    per-family defect counts first** — a defect ledger, honest about being a new
    instrument — with a scored headline number waiting until the docx-plus fixes give
    it a story. Truth records carry Word-verified positional facts (paragraph index,
    char span, laid-out page) from v1, informational until Theme 8 Stage 3 makes them
    scoreable — at which point this corpus is the DOCX provenance oracle for free.
    One measured limitation: wordlive's display equations write `m:oMath`, not
    `m:oMathPara`, so scripted display math parses as `MathInline`; the truth records
    say so rather than asserting a `MathBlock` the generator cannot produce. A side
    finding for the ledger: OMML→LaTeX conversion already exists in the parser
    (fractions/scripts/radicals/n-ary correct; matrices/delimiters/accents degrade),
    so the "Math everywhere" entry's OMML→LaTeX clause is stale — the gap is coverage,
    not existence. A follow-on is queued behind this batch on its own dependency:
    **PDF → DOCX fidelity** (Theme 2 entry, 2026-08-23), whose cheapest instrument —
    re-parse scoring through our own DOCX parser — is only trustworthy once this
    batch's parser fixes land.

**Smaller open items**, none blocking:
**the `docx-plus` Tier 1 spike** (Theme 2, three-PR sequence agreed 2026-08-21, tracked
changes first — the roadmap entry above is the full record; the design doc it once cited
was never committed) is *scheduled as of 2026-08-23: item 21 is that batch*;
[#257](https://github.com/thomas-villani/all2md/issues/257) (stratify the raster lane's
score — demoted from the numbered list 2026-08-13; two of its three parts already resolved,
and what remains costs an ~80-minute re-baseline, so batch it with the next oracle change
rather than running it alone — *scheduled: item 14 is that oracle change*);
[#328](https://github.com/thomas-villani/all2md/issues/328) (triage the 16 Semgrep findings
outside `src/` — `defusedxml` in the two corpus fetchers is worth doing on its own merits;
the rest is a suppress-or-scope decision);
[#183](https://github.com/thomas-villani/all2md/issues/183) (corpus throughput gate, parked
on runner variance, and the variance study it waits on is accumulating on every push);
**widen the generative strategy's node-type coverage** (Theme 2, one node-type group per PR
— footnotes first, where `benchmarks/roundtrip` already found real bugs; see the fuzzer
entry for why this is not the same request as raising `max_examples`);
**OCR the embedded image, not a 200-dpi re-render**, when a PDF page is one full-page image
(Theme 8, small) — measured at up to **4.3x** the pixels for zero detail gain, so a speed
and cost item that should not be sold as fidelity. Two CI gaps also remain: `scripts/` is in
no gate — `mypy` covers `src/` and `benchmarks/` only — and the Windows leg runs tests but
not `mypy`, so the `msvcrt` branch has never been type-checked in CI. The **async facade**
(Theme 3) also comes off the numbered list (2026-08-13): it has lost the
leverage-per-effort argument three batches running, which is a verdict rather than an
accident — it becomes urgent exactly when the server/MCP story or multi-worker
training-corpus loading finds a real user, so pull it forward then, not before.

Two of the fuzzer's defects were worth doing regardless of how the batch went, because they
are reachable from ordinary input rather than from a generated AST:

- 🚢 **#211 — odt/odp nested link.** Browsers accept nested `<a>` and our HTML parser preserves
  the nesting, so `all2md page.html -t odt` failed on real pages. Fixed.
- 🚢 **#212 — `from_ast` can raise bare `ValueError`/`KeyError`.** A documented contract that two
  renderers did not honour, so `except All2MdError` did not catch what the docs said it would.
  Fixed.
- 🚢 **#343 — a list item's text may run onto the lines below it (AsciiDoc).** `* a` / `b` /
  `** c` is three lines of ordinary hand-written AsciiDoc and it raised outright; without the
  nested item it merely leaked the run-on line out of the list as a sibling paragraph. Fixed
  by sharing the paragraph joiner rather than giving list items a second copy of it.

The batch closed as intended: the instrument that generated the backlog was made trustworthy
before we leaned on it further — twice, as it turned out. Make that three times: the same
instrument later needed its *runtime* explained (a verbose profile, not the gates) and its
discovery sweep shown capable of drawing anything at all, before it could be trusted back
into per-PR CI.

Everything below 🚀/🌙 is opportunistic — pull forward whatever a real user asks for. The
RAG-framework loader adapters (Theme 1) remain the cheapest filler on the board (~a day each)
if a later batch needs something user-visible to announce.
