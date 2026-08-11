# PMC born-digital corpus

External ground truth for **born-digital** PDF conversion: text-layer extraction, vector
table detection, layout-derived reading order. This is the gap the OmniDocBench lane does
not cover — that corpus is 981 rasters, so it measures the OCR path.

**This directory is step 1 of that lane, and step 1 only: the corpus fetcher.** There is
no oracle and no gate here yet, by design.

## What it is

Articles come from the PMC Open Access AWS bucket, `pmc-oa-opendata`, which stores each
article under a versioned per-article prefix with the publisher PDF beside its JATS XML:

```
PMC11000001.1/PMC11000001.1.pdf     <- born-digital publisher PDF
PMC11000001.1/PMC11000001.1.xml     <- JATS ground truth, same prefix
```

JATS is publisher-produced and already structured — sections, paragraphs, captions, and
tables with real cell markup. That is why PMC was chosen over arXiv, where LaTeX means
macro expansion and moving floats and you end up fighting the ground truth.

## The manifest is the pin

This bucket has **no corpus-wide revision**. Article versions bump independently and
decade-old articles carry recent reprocessing timestamps, so there is nothing to pin the
way the OmniDocBench lane pins a Hugging Face dataset revision.

`manifest.json` plays that role: it records a SHA-256 and size for **both** the PDF and
the XML of every selected article, and it is committed. `load_corpus` never lists the
bucket — it materializes exactly what the manifest names and revalidates every byte
against it. The manifest's own digest keys the cache directory, so editing the manifest
produces a new cache rather than re-blessing files chosen under different rules.

Article bytes are never committed. Only the manifest is.

## Selection

An article is kept when **its JATS has at least one `<p>` and its PDF carries vector
drawings on some page**.

### Which half of that filter actually works — measured, and not what was expected

The build ledger settled this. Of 105 candidates: **32 rejected `no_paragraphs`, 0
rejected `no_vector_drawings`.**

A filter arm that never fires deserves suspicion, so it was checked directly. The
`no_paragraphs` articles turned out to be the scanned 19th-century back catalogue: their
JATS `<body>` holds a single `<preformat>` element containing raw OCR dump
(`"Editorial\r\nCHICAGO MEDICAL SOCIETY.\r\nJan. 18th…"`), 24–99 KB of it, with zero
structural markup. **The `<p>` test is the real discriminator, and it caught every scan
before the PDF was ever fetched** — which is also why the vector arm never got the chance
to fire.

Testing the vector arm against those articles on its own exposed something sharper: the
bucket holds **two different kinds of non-born-digital material**, and only one of them is
a scan.

| article | producer | fonts | pages | vector pages | ≥80%-area image pages |
| --- | --- | --- | --- | --- | --- |
| `PMC10000000.1` | ABBYY FineReader 14 | 2 | 11 | **0** | **11** |
| `PMC5000000.1` | iTextSharp 5.4.1 | **1** (`CourierStd`) | 28 | **28** | 0 |
| `PMC5000022.1` | iTextSharp 5.4.1 | **1** | 22 | **22** | 0 |

1. **Raster scans with an OCR text layer** (`PMC10000000.1`, ABBYY). Both geometric tests
   catch these: no vector drawings, and a page-sized image on every page.
2. **OCR text dumps re-typeset into a PDF** (`PMC5000000.1`, iTextSharp, a single Courier
   face, 1722 characters of monospace on page one). **No PDF-geometry test catches these**
   — geometrically they *are* born-digital. They have a text layer on every page, no large
   images at all, and their one "vector drawing" per page is a page-sized background
   rectangle that `bool(page.get_drawings())` happily reads as a figure.

**This corrects the plan**, which called vector drawings "the clean discriminator" on the
strength of a nine-article spike. Against kind 1 it is redundant with the image test;
against kind 2 it is actively fooled. Only the ground-truth side — does the JATS have
paragraphs — reveals kind 2 at all.

The corpus is unaffected: every accepted article passed both arms, none was admitted on
the weak one alone, and neither kind survives (see below).

### The other two calibrations, which held

- **A text layer is not a born-digital signal.** Scans ship an embedded OCR layer; a
  sample of scanned back-catalogue pages was 100% scans and 100% text-layer. Confirmed
  again above: all three known scans have text on every page.
- **`<p> > 0`, not `<sec> > 0`.** `PMC3500001.1` has 13 paragraphs and zero sections.
  Requiring sections would bias the corpus toward long research papers and quietly narrow
  what the lane measures. The build bears this out — `PMC10500000.1` was accepted with 3
  paragraphs and `PMC8500015.1` with 4.

### Sampling

Selection walks from seeds spread every 500k across the ID range, taking every 11th listed
prefix so a run of same-issue articles from one publisher cannot stand in for a corpus.
`limit` on the load side selects an **evenly spaced** subset for the same reason, never
the first N.

**The scanned material is not confined to the front of the ID range** — another
correction. `PMC10000000.1`, a 2023-era identifier, is a scanned 1890s medical society
editorial: back-catalogue digitization projects receive *modern* PMCIDs when deposited.
Sampling off the front is still wrong, but spreading the seeds is not by itself protection
against scans; the `<p>` filter is.

Note also that bucket listing is **lexicographic, not numeric**: `start-after=PMC1000000`
lands on `PMC10000000`, because an 8-digit id sorts before a 7-digit one. Seeds are
`start-after` anchors, not positions in the ID range.

## Rejections are recorded; network failures are not rejections

Every dropped candidate is written into the manifest by article id with its reason. A
silent filter is the same defect as a silent truncation.

Network failures are tracked **separately** and never enter the rejection ledger. A
rejection is a statement about an article; an unreachable host is a statement about the
run. A build that loses more than 10% of its candidates to network failure aborts rather
than committing a manifest that a bad link quietly thinned out.

## Usage

```bash
# Summarize the committed manifest. No network access.
.venv/Scripts/python.exe -m benchmarks.pmc show

# Materialize and verify the pinned corpus.
.venv/Scripts/python.exe -m benchmarks.pmc load
.venv/Scripts/python.exe -m benchmarks.pmc load --limit 10     # evenly spaced subset

# Rebuild the manifest by walking the bucket. Run by hand; commit the result.
.venv/Scripts/python.exe -m benchmarks.pmc build --per-seed 3
```

## What comes next, and what must not be assumed

**Step 2 — characterization: DONE, and it agrees with the spike.** Measured over all 66
articles / **750 pages** with the sibling lane's own `_input_traits`, so the two lanes are
comparable:

| trait | corpus | OmniDocBench (the OCR lane) |
| --- | --- | --- |
| text layer | **100.0%** | — |
| vector drawings | **81.1%** | ~2% |
| one ≥80%-area image (scan shape) | **0.0%** | ~100% |

Median 10 pages per article; drawings per page median 5.0, with 76.1% of pages carrying
two or more. The exact inverse of the raster lane, which is the point.

**`0.0%` was checked for vacuity before being believed.** A zero is only evidence if the
instrument can produce a non-zero: run against the known raster scan, the scan-shape test
fires on **11 of 11** pages. It works.

Neither kind of junk survived into the corpus:

- **Raster scans:** 0 of 750 pages have the scan shape.
- **Re-typeset OCR dumps:** the giveaway is a single embedded font. The **minimum font
  count across all 66 articles is 6**; the dump had exactly 1.

A caution for anyone extending this: `"modified using iText"` in the producer string is
**not** the dump signature — PMC post-processes ordinary publisher PDFs with iText, and 14
of the 66 carry it while having 6+ diverse subset fonts and 39–175 JATS paragraphs. The
signature is iText *as sole producer* with a single monospace face.

This is also why the manifest deliberately records **no PDF page traits**. The
characterization above had to be an independent measurement; reading the filter's own
premise back out of the manifest and calling it a result would have been a measurement
that cannot fail.

**Step 3 — the oracle, and the alignment decision.** JATS describes a whole *article* with
no page boundaries; OmniDocBench annotates *pages*. `benchmarks.pmc align` measures
whether article truth can be projected onto pages well enough to score per page.

Over all 66 articles / 4,153 blocks, matching **content only**:

| outcome | share |
| --- | --- |
| **clean** — one page clearly wins | 86.2% |
| **spans** — two *adjacent* pages, an ordinary page break | 9.5% |
| **split** — two *non-adjacent* pages, a real ambiguity | 2.4% |
| **missing** — not found | 1.9% |
| | **95.7% placeable** |

Per kind: `<p>` 95.5% placeable / 2.0% missing, `<table-wrap>` 95.7% / 1.4%,
`<fig>` **97.8% / 0.4%** — figures are the *best*-behaved category.

**Completeness is checked before ambiguity, and that ordering was a real defect once.**
A page holding essentially all of a block holds the block; another page echoing its
wording — body text restating a figure caption, a running header, a repeated table label
— does not make it two-paged. Checking the runner-up first made **71% of `split` blocks,
and 88% of split figures**, read as ambiguous when their top page already held 100% of
them. Fixing the order moved placement from 90.2% to 95.7% and cut the error budget from
9.8% to 4.3%, **with the mismatch control unchanged at 0.8%** — so the gain was real and
not bought with false positives. Figures went from apparently worst (61.8% clean) to best
(92.5%).

Equal-scoring pages break toward the **earliest**; without that the sort silently
preferred the last page.

**The probe validates itself on every run.** Scoring the same blocks against a *different*
article's pages gives a false-placement rate of **0.8%**. A placement rate means nothing
unless the method can fail, and two earlier versions of this probe produced confident
wrong answers — see the module docstring, which records both.

**Placement is order-free on purpose.** It never consults the reading order all2md
extracts, only whether a page's text contains a block's n-grams. Aligning by extracted
order would make page assignment depend on the very thing this lane grades. A useful
consequence: float displacement stops mattering for *assignment*, because a figure is
found where it renders rather than where JATS cites it.

Where that does **not** help is reading order *within* a page: JATS gives document order,
and for a page carrying a floated figure the correct order is a layout question JATS does
not answer. That is where the residual risk sits.

**The ~4.3% `split` + `missing` is the error budget.** Those blocks must be excluded *and
reported*, never quietly dropped.

## The oracle: `benchmarks.pmc score`

`score` converts each article once and scores every page of it against the JATS truth
projected onto that page, through the **same oracle the OmniDocBench lane uses**. The metric
definitions are not duplicated: each carries a calibration story that took a corpus to
settle, and reusing them is what makes a number here mean the same thing as a number there.

```bash
.venv/Scripts/python.exe -m benchmarks.pmc score --limit 8
.venv/Scripts/python.exe -m benchmarks.pmc score --out result.json
```

### The plan said "score whole articles too". Measurement said no, and why

The intent was a second, article-level endpoint for overall layout and reading order,
carrying a larger denominator because it pays no alignment tax. Two measurements killed
that design and one killed its motivation.

**The shared oracle's block-locating threshold does not survive an article-length haystack.**
`_IDENTIFIED_MATCH` counts a ground-truth block as *found* once half its characters align
monotonically. Over one page that is sound. Over a whole article, **77–86% of one article's
blocks "locate" inside a completely different article's output**, at a median alignment of
0.62–0.72 against 0.93–1.00 for their own. The safeguard that stops absent content from
earning reading-order credit is inoperative at that length. Reading order is therefore
scored **per page only**, where the calibration holds.

**Page order cannot fail, so it is not scored.** Page attribution comes from the parser's own
per-page loop, which emits a separator per PDF page, so content cannot migrate between page
groups and a dropped page raises `PageBoundaryError` rather than scoring. A page-sequence
metric would report a perfect score by construction — which is the definition of a
measurement not worth having. The cross-page blindness that motivated an article-level
endpoint is handled structurally instead.

What survives at article level is a narrower question — **did this block's text survive
anywhere in the output?** — measured with n-gram containment, the one instrument on this
corpus with a published false-positive rate.

### Raw recall is unreadable without its ceiling

Much of a JATS article cannot be recovered from the PDF by **any** parser, because the markup
does not record words in the order the page prints them: `<element-citation>` lists the
journal before the authors, `<surname>` precedes `<given-names>` against the rendered byline.
Measured against the PDF's **own text layer**, only **61.1%** of blocks are recoverable at
all. So a raw 54.6% recall is **88.9% of what was available**, not a parser losing half the
document. The ceiling is computed every run, because it is a property of the corpus and the
extraction rather than a constant.

### Projection rules, and what each one cost

| rule | why | measured |
| --- | --- | --- |
| a `spans` block is **split** across its two pages | it belongs to both, but scoring it *whole* against both guarantees a mismatch on both | split point comes from the same n-gram evidence as the placement; when the token stream cannot be mapped back onto raw text the block counts whole on both, and that is counted |
| short blocks try an **exact phrase**, then inherit | a three-word heading has no five-grams | headings are kept with the text they introduce, so the next placed block's page is the heading's page |
| structured blocks fall back to **token containment** | see below | recovers 89.1% of n-gram misses at 0.6% false placement |
| `split` and `missing` blocks are **excluded and reported** | they are the alignment's failures, not the parser's | ~2–5% error budget, printed with every run |

**The token fallback is the one addition that changed the numbers, and it was calibrated
rather than chosen.** N-gram containment assumes the page renders a block's words in the
order JATS declares them, which structured markup breaks without changing a single word — a
citation fully present on its page scores *zero* n-gram containment. At a 0.65 token-share
threshold the fallback recovers **89.1%** of the blocks n-gram containment calls missing,
agrees with n-gram placement on **99.0%** of blocks where that method already gives a
confident answer, and places only **0.6%** of blocks onto a *different article's* pages.
Raising it to 0.85 buys nothing and gives up half the recoveries. It is kept as a separate
rule from `place_block` so the feasibility numbers above still describe what they measured.

### Three findings from building it

**A nested `<table-wrap>` inside a `<p>` corrupted three things at once.** JATS puts floats
inside the prose that introduces them. Taking the paragraph's full text fused the paragraph,
the caption and every cell into one string — so the table vanished from the ground truth, the
caption stopped being its own page object, and the fused block straddled the paragraph's page
and the table's page and was placed on the wrong one. Found by reading a single page's truth
beside its output, not by any aggregate.

**Ordering ground truth by position on the page is worse than JATS order — tested, refuted.**
Within a page, JATS document order puts a floated table where the prose cites it rather than
where it renders, which costs real score on float-heavy pages. The obvious fix is to order
blocks by where their text appears in the page's own token stream. Measured, that ordering
disagrees with JATS on **25% of block pairs** and makes **every dimension worse**
(reading order 0.748 → 0.663). PyMuPDF's extraction order is not rendered reading order, and
grading against it would punish correct column handling. JATS order stays; the float cost is
a documented bias, not a bug.

**`block_structure_similarity` must not be gated on here.** It separates own-page from
wrong-page output by only ~0.06, and it *rises* when half the emitted content is deleted —
so gating on it would reward dropping blocks. It stays in the payload as evidence, flagged
`ungateable` with the measurement that disqualified it.

### Controls that ship inside every run

- **Mismatch.** Every page is scored again against the *next page of the same article* — a
  harder confounder than a different article, sharing the running head, the vocabulary and a
  sentence that continues across the break. A dimension that does not clearly beat that is
  not measuring the page.
- **Mutation.** Every page is scored against output that has been reversed, scrambled and
  halved. A dimension that does not move cannot detect that class of defect.
- **Input shape.** OCR is left **enabled in auto mode** rather than switched off. Disabling
  it would make "no page needed OCR" true by construction; leaving it on makes it a
  measurement that can fail, and the run names any article where it fired.

**Decided 2026-08-05:** a `spans` block **counts on both** of its pages. `<fig>` needs no
special handling — the case for excluding it rested on a 14.5% split rate that was a
classifier artifact; the real figure is 1.8%.

### First full-corpus run, 2026-08-05

66 of 66 articles converted, **720 pages scored**, coverage median 0.98 ground-truth words
per PDF word, **error budget 4.1%** (325 `missing`, 105 `split`, 44 trailing `too_short`).
No gate is recorded from this — it is the first reading, not a baseline.

| dimension | mean | median | wrong page | gap | sd | n |
| --- | --- | --- | --- | --- | --- | --- |
| `reading_order_similarity` | 0.757 | 0.786 | 0.294 | **0.463** | 0.222 | 720 |
| `text_content_similarity` | 0.558 | 0.531 | 0.231 | **0.327** | 0.234 | 720 |
| `table_structure_similarity` | 0.106 | **0.000** | 0.033 | 0.074 | 0.277 | 111 |
| `table_content_similarity` | 0.097 | **0.000** | 0.017 | 0.080 | 0.256 | 111 |
| `block_structure_similarity` | 0.494 | 0.500 | 0.424 | 0.070 | 0.212 | 720 | *(ungateable)* |

**The scores spread, which was the second thing worth checking before trusting any of this.**
Standard deviations of 0.21–0.28 with minima near 0 and maxima at 1.0 — these are not gates
pinned at 0.98 that cannot fail.

Whole-article recall: **94.2% of what is attainable** (raw 59.3%, ceiling 62.2%), against a
mismatched-article control of **0.4%**. Per kind, of what was attainable: `text_block` 97.0%,
`table` 96.5%, **`title` 90.2%** — headings are the weakest, and their ceiling is the highest
at 94.4%, so that gap is the parser's.

**Born-digital tables are the headline, and the parser's own telemetry sharpens it.** Median
0.000 on both table dimensions across the 111 pages carrying table ground truth. On a
12-article spot check: **32 ground-truth tables against 4 emitted `Table` nodes**, 28 pages
with a table against 4.

Table **cell text** is recovered at **96.5% of attainable** — the words reach the output, so
this is a structure failure and not text loss.

The run also records **76 `table_rejected` degraded events**, which first read as "the parser
finds table candidates and rejects them" — a guard-tuning problem. **That reading was wrong,
and the counter is what misled it.** 31 of those events are `layout_region_not_tabular`, which
the code recorded whenever a layout-predicted region failed to *become* a table — including
when nothing tabular was found there at all. Instrumenting the branch separately showed
`find_tables()` recovering a grid in **0 of 31** such regions. No guard rejected anything; the
detector saw nothing to reject. (The event also double-counted: a region whose grid *was*
found and then rejected recorded both the specific reason and this vaguer one.)

The cause is that PyMuPDF's default strategy needs ruling lines on both axes and journal
tables are booktabs-style — horizontal rules only, or none. `strategy="text"` recovers a ≥2×2
grid in **all 31**. See the "Fixing it" section below for why that alone is not the fix.

This is also the gap the raster lane structurally cannot report: every OmniDocBench page is an
image, so its PDF table path never runs and the whole table dimension is erased as
unsupported.

**OCR fired on 11 of 66 articles** — on a corpus characterized as 0.0% scan-shaped. This is
why OCR was left enabled rather than switched off: it is a measurement that could fail, and it
did. Auto mode triggered on **≥50% image area regardless of how much text a page had**, and
`preserve_existing_text` defaults to `False`, so on a figure-heavy born-digital page the
publisher's real text layer was discarded and replaced with OCR output. Fixed — see below.

**Cost:** the full run takes over an hour of CPU on one core, most of it OCR. Use `--limit`
for a spread subset; a per-PR gate over all 66 articles is not practical as it stands.

### Fixing it, and what the fix needed that no table metric could supply

Adding `strategy="text"` as a fallback moved every table number sharply the right way, on a
12-article subset: `table_content_similarity` median **0.000 → 0.824**, `table_structure`
**0.000 → 0.440**, tables emitted 4 → 40 against 32 expected, and both wrong-page gaps widened.
Read on the table dimensions alone, it was an unambiguous win.

**It was a serious regression.** Whole-article recall fell from **92.6% to 83.8%** of
attainable, `title` from 87.5% to 71.2%. Reading the rendered output said why: the layout model
over-fires, and on a mis-predicted region the text strategy turned a page of abstract prose
into a seven-column table whose columns cut *through words* — `study was condu | cted to
explore`, `micronutr | ients in the`. Emitted character count went **up**; nothing was deleted,
it was shredded. This is the case for pairing a sharp instrument with a noisy one: every table
metric approved, and only whole-article recall objected.

Finding a guard took five measured attempts, four of them refuted. Grid **shape** (rows,
columns, fill ratio, words per cell) does not separate the two — the text strategy chops prose
into one-word cells, so gridded prose looks exactly as tabular as a table (mean words per cell
1.54 vs 1.56). **Reading-order preservation** does not (0.812 vs 0.827). Region
**corroboration** does not, and inverts: mis-predicted regions carried *more* ruling lines
(median 2 vs 0) and 13 of 19 carried a `Table N` caption. A first **word-splitting** measure
appeared to fail too, until the probe itself turned out to be at fault — it built its
vocabulary with `get_text("words", clip=region)`, and clipping truncates words at the boundary,
manufacturing the fragments it was counting.

Measured unclipped, it separates cleanly: clean regions **0.000–0.022**, damaged ones
**0.128–0.333**, with the threshold in an empty gap. On the known-bad article the mis-predicted
abstract scores 0.2415 and its four real tables score exactly 0.0000. The guard is also right
independent of the metric — a grid whose columns split words has corrupted cell text, so it
should be refused whether or not a table is really there.

With the guard, on the same subset: tables emitted **4 → 12**, `table_content_similarity` mean
**0.075 → 0.241**, `table_structure` **0.091 → 0.235**, and recall back at baseline (92.5% vs
92.6%; `title` and `text_block` exactly unchanged). Conservative on purpose — it still refuses
real tables whose extraction splits words, and the medians remain 0.000 — but it buys the table
gain for nothing.

### Fixing the OCR trigger, and the arm that was silently not the baseline

The trigger held two faults, both visible in one pass over all 750 pages. Summing image areas
does not ask whether a page is a scan: one affected page carries six figure panels of a tenth
of the page each, summing past the threshold with nothing page-sized on it. And 0.5 sits far
below where scans live. Measuring the **largest single image** separates the two cleanly —
born-digital pages never pass **0.634**, real scans sit at exactly **1.000** — and 0.8 is the
same boundary `benchmarks/omnidocbench` already calibrated for `one_full_page_image`.

Both directions were checked. The 12 mis-firing born-digital pages stop; a real OmniDocBench
scan raster with a running header painted onto it — enough characters to clear `text_threshold`,
so only this branch can reach the page — still fires 6 of 6. The gated raster lane cannot move
either way: all 52 of its cached pages have **no text layer at all**, so they trigger on the
text branch and never reach this one.

Over the 11 affected articles: `text_content_similarity` median **0.515 → 0.599**,
`block_structure` mean **0.530 → 0.563**, recall of attainable **94.6% → 95.1%**, and 9 of the
11 stop OCR'ing. **`title` recall does not move** (377/394 in both arms) — so the title gap and
the OCR trigger are separate defects, which is what this A/B was run to find out.

**The first baseline arm was not a baseline, and its scores looked fine.** It was produced by
reassigning the `image_area_threshold` dataclass field default, which does nothing — a
dataclass bakes its defaults into the generated `__init__` — so the arm silently ran the
candidate. What exposed it was the payload's own `ocr_articles` field listing 2 articles where
a true baseline must list 11. Patch the *function* the option feeds, and confirm an arm is the
arm from a field recording what the parser did, never from the score it produced.

## Licences

The OA subset is not uniformly licensed. Each article's licence is read out of its own
JATS `ali:license_ref`/`license` element and recorded in the manifest. `show` prints the
breakdown. Nothing here redistributes article content — only digests.
