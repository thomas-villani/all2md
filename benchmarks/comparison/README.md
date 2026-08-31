# Third-party converter comparison

Scores other PDF→Markdown converters with the PMC lane's own instruments, on the
held-out corpus, so all2md's numbers get the context a single-tool benchmark cannot
provide: what do the strongest alternatives recover that we lose, and at what cost in
invented text?

**This lane never runs in CI.** It exists to be run by hand when a reading is wanted —
each run downloads nothing from this repo's pins that isn't already pinned, but it does
execute two third-party ML stacks and takes hours of CPU. Its job is to produce
*targets* (see below), not a gate.

## Ground rules

The numbers are only comparable because of four rules, all of which cost us something:

1. **Held-out corpus only.** The 103 articles of
   `benchmarks/pmc/manifest-holdout.json` — the corpus development work has never tuned
   against. Comparing on a development corpus would flatter all2md with in-sample numbers.
   Materialize it under its own cache root: `python -m benchmarks.pmc load --manifest
   benchmarks/pmc/manifest-holdout.json --cache benchmarks/pmc/.cache-holdout`.

   **This corpus was redrawn on 2026-08-27.** The holdout the older readings used is now
   `benchmarks/pmc/manifest-tuned.json`: it had been tuned against — six tracked files name
   its articles, five of them source or tests — so those numbers are in-sample and are
   labeled that way below. `benchmarks/pmc/README.md` carries the full burn record. The
   2026-08-28 reading is the first measured on the sealed corpus; readings either side of
   the redraw confound a corpus change with a code change and must not be diffed.
2. **Baselines run at their defaults.** The comparison is against what a user of each
   tool gets without tuning. all2md runs the PMC lane's parser policy (layout analysis
   enabled, OCR auto) — its own measured configuration, disclosed rather than hidden.
3. **One normalization path.** Every tool's markdown — all2md's included — is re-parsed
   through all2md's markdown parser and projected with the shared oracle before scoring.
   Nobody is scored on raw strings. The identical-path check measured what this costs:
   all2md's re-parsed markdown scores 0.3pp below its direct payload figure, novel share
   unchanged, so the re-parse does not tilt the field. `reparse_word_ratio` in the
   output is the per-tool guard: far below ~0.9 means the re-parse is eating that tool's
   content (e.g. raw HTML blocks) and its recall is understated — investigate before
   quoting.
4. **Versions are pinned.** `baselines.txt` records the exact baseline versions each
   committed `results-*.json` was recorded against. A new reading against new versions
   is a new dated file, never an edit to an old one.

**What this lane measures is deliberately narrow: article-level text survival, invented
text, and section headings.** Those are the instruments with published false-positive
controls that third-party output can enter. Reading order, and table structure *as the
main lane scores it*, require all2md's page attribution and cannot score other tools.

One piece of table structure does cross the line and is scored for every tool, because it
needs no page attribution: how many rows each tool cuts a table into, against the truth
table's own row count. That, and the order-free companion to the table figure, are
`tablediag.py` below.

Text survival alone structurally favors low-structure converters — the highest-recall
converter imaginable dumps the raw text layer with no structure at all — and that is the
asymmetry the heading measure counterweights. Quote the recall numbers with it attached.

## Section headings (`headings.py`)

`score.py` cannot see a heading: `MIN_NGRAMS = 4` drops any block under about eight words,
which removes 87% of section headings, and lowering the floor does not rescue them because
`Introduction` appears in any article's prose and containment would read near 100% for
everyone. So headings are scored by *structure* instead — a truth heading counts as
recovered only when the tool emitted a heading with the same text. That rule needs no
threshold and no page attribution, which is why it scores third-party output as readily as
our own.

Run it after the converters, against the same `out/` tree `score.py` reads:

```
python benchmarks/comparison/headings.py
```

It prints rather than writing to `results-*.json`, so the reading is recorded here.
**2026-08-29 outputs, sealed holdout, 1,790 section headings.** The figure is the share of
headings *the page actually printed* that were emitted as headings:

| tool | printed headings recovered as headings |
|---|---|
| all2md | 79.0% |
| docling | 80.3% |
| pymupdf4llm | 79.2% |

**Every tool loses about a fifth of section headings into the prose stream**, and the three
are within about a point of each other — this is a shared blind spot of the whole field,
not a place all2md trails. Two controls are reported because the shared vocabulary of
`Introduction`/`Discussion`/`Funding` keeps the whole-corpus control off zero at 15.6%;
restricted to headings appearing in fewer than five articles it falls to 1.4%, and that is
the sharper number.

**These replace a first reading of 76.4 / 77.4 / 76.6, which charged every tool with losing
headings it had printed correctly.** JATS keeps a section number in a `<label>` sibling of
`<title>` and the projection reads only the title, so truth said `Discussion` where the page
— and any tool faithful to it — said `4 Discussion`. The number is now stripped from both
sides before matching. On the development corpus it was 8.4% of all headings: of 99 numbered
headings all2md was charged with losing, **97 had been emitted correctly, number and all**.
It moved all three tools by a similar amount, so the ordering and the shared-blind-spot
reading are unchanged; what changes is that a fifth of the reported loss was the measure's.

A depth-agreement metric is deliberately absent. Aligning each article's best offset makes
it gameable by a converter that emits every heading at one level, and in probing, a flat
emitter led on it. The sound version is pairwise relative depth, and it lands with the
measure rather than as a script.

## Where the table gap is (`tablediag.py`)

The table figure above is n-gram containment, and the scoring audit established what that
actually measures on tables: the median cell is two words, and 69–83% of a truth table's
5-grams cross a cell boundary. So it is overwhelmingly a measure of *cell adjacency and
reading order*, not of cell content — and quoted alone it reads as "share of table content
recovered", which it is not.

`tablediag.py` scores every attainable truth table twice against the same output.
**Multiset token containment** ignores order entirely and says how many of the table's words
reached the output at all. **N-gram containment** is the published measure. The difference
is the order tax, and the pair is the point: a tool can only be charged for losing order
once it is shown to have the words.

### The 2026-08-31 reading: the whole gap is order, and none of it is content

Run on the 2026-08-29 cached outputs against the current ground truth, 146 attainable truth
tables.

| | n-gram | **token** | order tax |
| --- | --- | --- | --- |
| all2md | 0.838 | **0.998** | +0.160 |
| docling | 0.865 | 0.991 | +0.126 |
| pymupdf4llm | 0.762 | 0.993 | +0.231 |

**all2md holds 99.8% of every truth table's words** — the best of the three, and at ceiling.
There is no content deficit to close. Whatever separates these tools on tables is
arrangement, and this is the number to quote whenever the table figure is read as content
recovery.

These are unweighted per-table means under this script's own attainability filter, so they
are not the corpus-aggregate table-text figures in the reading tables above and must not be
diffed against them.

### It is a row-count defect, and the disagreement is symmetric

At a 10-point margin, **docling wins 35 tables and all2md wins 29**, with 82 ties. The mean
deficit is the small net of two large opposing populations, not a uniform shortfall. And
**97% of docling's wins are the same words in a different order** — exactly one of the 35
involves words all2md did not extract.

What separates them is how many rows each tool cuts the table into:

| rows against the truth's own count | right | over-merged | over-split | no grid |
| --- | --- | --- | --- | --- |
| all2md | 54% | 23% | 18% | 5% |
| docling | **81%** | 12% | 5% | 3% |
| pymupdf4llm | 73% | 10% | 14% | 3% |

On the tables docling wins, all2md's row count is right only 9 times in 35; on the tables
all2md wins, 16 in 29. But the pymupdf4llm row is the guard against over-reading this: it
gets more row counts right than all2md and still scores worst of the three, because a row
count can be right while the cells inside it are cut wrongly. Row grouping is what separates
*these two* tools on *this* corpus, not a general ranking.

Note also that all2md over-merges and over-splits at comparable rates. "all2md over-merges"
is too simple a summary: on this corpus the larger excess over docling is on the over-split
side.

### The disagreement is article-level, and nothing measured explains it

Within-article agreement of the win direction is **64.1% against a 31.6% permutation null
(p = 0.004)** — the null matters, because a few articles carrying many tables would
manufacture apparent clustering on their own. So the cause lives at the document level.

Every document-level variable probed came back flat: ruling density on table pages (8.0 vs
6.8 rules per page), rules drawn as thin rectangles rather than line items (a real blind
spot in `_extract_ruling_lines`, but 7 of 40 articles), journal identity (the corpus draw
spread publishers, so almost none repeat), two-column layout (median widest rule spans 0.86
against 0.83 of page width, and tables confined to one column lean the *other* way),
landscape pages (none), and table shape — rows, columns, cell slots, words — where the two
sets are indistinguishable.

One limit this cannot resolve: the clustering may be partly truth-side, since an article's
tables share a JATS structure and so could score alike for reasons belonging to neither
parser.

### One mechanism looked decisive and priced out at nothing

`_table_row_extents` takes row boxes from PyMuPDF's `find_tables()`. On a ruled table those
boxes share edges exactly, so **51% of recorded grids arrive with no vertical gap between
any two lines** — and on those the merge rule's strongest signal, the inter-line gap, is
constant zero. Measured against a grouping oracle on the development corpora, merge recall
collapses from **79.5% on grids with real gaps to 29.2% on tiled ones**, at unchanged
precision: those grids are not merged wrongly, they are not merged at all.

It is worth almost nothing. Priced in containment against a perfect-grouping ceiling, tiled
grids carry **+0.017 / +0.032** of headroom (dev / tuned) against **+0.054 / +0.101** for
gapped ones. Tiled grids are already correctly rowed — that is *why* they tile, the rulings
having marked the real rows — so they want 1.7 merges each against 8.7, and the ones missed
barely touch a gram. Recorded here because the reverse mistake is easy: a merge-recall
number can look catastrophic and be worthless, and a grouping lead must be priced in
containment before it is chased.

### Verdict: the residue is a model-class difference, not a missing rule

Perfect row grouping is worth **+0.055** across the development corpora; the per-table gap
to docling is 0.027. The whole deficit fits inside the row-grouping ceiling, and docling
captures about half of a headroom all2md does not.

But that headroom sits on grids where the rule already has full geometry and already makes
79.5% of the available merges. Buying the last fifth costs ten points of precision, and a
wrong merge interleaves two real rows and destroys the grams in both, where a missed merge
costs only the grams spanning the wrap. Every other avenue is measured closed: new features
at the detection seam, recombining the existing ones, column splitting, both merge
directions, and the section-heading fold.

docling runs a learned table-structure model over the page image; all2md runs geometry rules
over extracted words. On this evidence the remainder is that difference, and no further
heuristic is expected to close it. The table work stops here rather than continuing to fit
rules to a corpus.

## Reading, 2026-08-29 (`results-2026-08-29.json`) — the sealed holdout, corrected truth

**Re-read after two corrections.** The ground truth changed under everyone (#470), and
all2md's outputs were regenerated at `2925f5c`, which carries the row-grouping fixes #468
and #469 that the 2026-08-28 outputs predate. The baselines were deliberately **not** re-run:
docling's and pymupdf4llm's markdown is byte-identical to the previous reading, re-scored
against the corrected truth, so the baseline side is held fixed and the movement is
attributable.

| | all2md @ 2925f5c | pymupdf4llm 1.28.2 | docling 2.120.3 |
| --- | --- | --- | --- |
| Recall of attainable | **97.3%** | 97.1% | 96.2% |
| — text blocks | **98.1%** | 97.0% | 96.0% |
| — titles | 97.2% | **98.5%** | 97.0% |
| — table text | 73.1% | 60.7% | **79.3%** |
| **Novel (invented) share** | **0.55%** | 6.26% | 2.05% |
| Precision (raw) | **93.9%** | 87.2% | 91.8% |
| Duplication | 0.28% | **0.13%** | 1.72% |
| Tables emitted / expected | 226 / 164 | 276 / 164 | **206 / 164** |
| OCR firings over the corpus | **0** | 432 | sparse |

**The control comes first.** `control_recall` is 0.0042 / 0.0049 / 0.0044 against attainable
recall near 0.97. And this reading carries a second control the others could not: **every
precision-side figure — novel share, raw precision, duplication, the mismatch control —
reproduced to every recorded digit** when the same cached outputs were re-scored against the
corrected truth. Those instruments never touch JATS, so they must not move; they did not.
That is what licenses reading the recall movement as real.

### The table gap to docling is 6.2 points, not 16.7

Of the 10.5 points closed, **7.1 are the truth correction and 4.1 are #468 + #469.**

The truth half is not all2md gaining, and the obvious reading of it is wrong. On the 132
tables attainable under **both** truths, no tool's recovery changed at all — all2md 92,
docling 114, pymupdf4llm 83, before and after. The entire movement is **13 tables that became
attainable**, and none stopped being. Of those 13, **all2md recovers 8, pymupdf4llm 5 and
docling 1.**

Those 13 are the tables dense in glued inline markup: `X1`/`X2` design factors, `M1/M2`,
`RRHF`, `ITotal`, footnote markers welded to values (`0.552a`, `NSCLCb`, `P-valuea`),
superscript citations (`Willis43`). The old truth spelled them `X 1` and `0.552 a`, which the
PDF's own text layer does not contain, so they sat outside the ceiling **for every tool**. So
the correct statement is not "the broken truth flattered docling" — it is that the broken
truth hid a whole class of table, and docling is much weaker on that class than we could see.
Checked on exemplars rather than inferred from the delta: inside a table cell docling prints
`X 1 (W)` where all2md prints `X1 (W)`, and `0.552 a` where all2md prints `0.552a`
(pymupdf4llm drops the marker). Both tools get `X1` right in *prose* — it is docling's table
pipeline, not its text extraction.

### What else moved

**all2md now leads recall of attainable outright** (97.3% against 97.1% and 96.2%), where the
previous reading had it mid-pack in a three-way tie. The corrected truth is what changed;
all2md's text-block and title figures are otherwise untouched by #468/#469, as designed —
those were table-only changes and `tables_emitted` is unchanged at 226, so they moved grouping
and not detection.

**Novel share is unmoved at 0.55%** against docling's 2.05% and pymupdf4llm's 6.26%. It has now
survived a corpus reseal *and* a ground-truth correction without shifting, which is the
strongest thing this lane can say about a number.

**The speed column is carried over unchanged for the baselines** and is not comparable across
readings; see the caveat under the 2026-08-28 reading. all2md re-measured at 33.2 s/article
against 31.6 in the previous session, on a box that was not otherwise idle.

## Reading, 2026-08-28 (`results-2026-08-28.json`) — the sealed holdout

**The first genuinely held-out reading since v1.13.0.** 103 of 103 articles converted by
every tool; zero conversion failures and zero parse failures anywhere.

| | all2md @ 689ca1a | pymupdf4llm 1.28.2 | docling 2.120.3 |
| --- | --- | --- | --- |
| Recall of attainable | 97.5% | **97.8%** | 97.2% |
| — text blocks | **98.4%** | 98.0% | 97.4% |
| — titles | 97.3% | **98.7%** | 97.3% |
| — table text | 69.7% | 62.9% | **86.4%** |
| **Novel (invented) share** | **0.55%** | 6.26% | 2.05% |
| Precision (raw) | **93.9%** | 87.2% | 91.8% |
| Duplication | 0.28% | **0.13%** | 1.72% |
| Tables emitted / expected | 226 / 164 | 276 / 164 | **206 / 164** |
| Seconds per article (CPU) | **31.6** | 54.8 | 95.8 |
| OCR firings over the corpus | **0** | 432 | sparse |

**The control comes first, because it is what licenses the rest.** `control_recall` is
0.0042 / 0.0049 / 0.0044 against attainable recall near 0.97, so the instrument is not
crediting text that is not there. `reparse_word_ratio` is 0.99 / 1.04 / 0.96, so the shared
normalization path is not eating any tool's content.

### What the seal cost us to learn

> **Superseded by the 2026-08-29 reading.** The table figures in this section were measured
> against a ground truth that printed a space at every JATS element boundary (#470). The gap
> stated below is 16.7 points; on the corrected truth the same outputs read 10.3, and with
> #468/#469 it is 6.2. The *reasoning* about in-sample measurement still stands — the seal
> did cost us a real number — but do not quote the 16.7.

**The table gap to docling is 16.7 points, not 4.8.** That is the finding. On the burned
corpus all2md read 77.4% against docling's 82.2%; on a corpus neither of us tuned against,
it is **69.7% against 86.4%**. Both tools moved, so this is not all2md losing ground — it is
the previous gap having been measured on data that the table work had been developed
against, which flattered us by roughly two-thirds of the true distance. The exemplars are in
`manifest-tuned.json`; `test_pdf_wrapped_cell_rows.py` transcribes one of its tables verbatim.

**Novel share is the claim that survives contact with a sealed corpus.** 0.55% against
docling's 2.05% and pymupdf4llm's 6.26% — 3.7x and 11.4x cleaner. It moved barely at all
from the in-sample reading (0.62%), which is what an honest number looks like when the
corpus changes underneath it. all2md also leads raw precision at 93.9%.

**all2md is no longer the worst table over-emitter; pymupdf4llm is.** 276 tables against 164
expected (1.68x) versus our 226 (1.38x) and docling's 206 (1.26x). Earlier notes in this repo
called our over-emission the worst of the three on the strength of the in-sample reading;
that is now false and should not be repeated.

**Recall is a three-way tie.** 97.2%-97.8% spans all three tools, a range narrower than the
gap any single table figure shows. Text survival alone does not separate these converters,
which is exactly why this lane also measures invented text.

### Read the speed column only as an ordering

`seconds_per_article_mean` is **not comparable to the 2026-08-23 reading**. Every tool
measured 1.8-2.5x slower than its own record in this session. That is not a regression:
all2md v1.13.0, built from its tag in a worktree, measured within 2% of HEAD on the same nine
articles minutes apart. Two unrelated third-party tools drifting the same direction points at
ambient machine state — the earlier reading ran overnight on an idle laptop, this one shared
the box, and a 15W U-series part throttles under sustained ONNX load. The *ordering* is
robust and is what the column is good for: all2md is the fastest of the three, 1.7x over
pymupdf4llm and 3.0x over docling. Pinning to logical cores 0-7 on a hybrid CPU costs a
further 2.3x on the ONNX layout path, so a speed figure needs the layout mode and the core
topology recorded, not just a thread count.

## Reading, 2026-08-23 (`results-2026-08-23.json`) — in-sample, superseded corpus

110 of 110 articles converted by every tool; zero conversion failures anywhere. Measured
on what is now `manifest-tuned.json`; see ground rule 1.

| | all2md @ 073e4da | pymupdf4llm 1.28.2 | docling 2.120.3 |
| --- | --- | --- | --- |
| Recall of attainable | 98.2% | **98.3%** | 95.5% |
| — text blocks | **98.4%** | 98.4% | 95.9% |
| — titles | 98.7% | **99.3%** | 95.4% |
| — table text | 77.4% | 65.1% | **82.2%** |
| **Novel (invented) share** | **0.62%** | 5.64% | 2.87% |
| Duplication | 0.46% | 0.19% | 0.62% |
| Tables emitted / expected | 238 / 166 | 212 / 166 | 201 / 166 |
| Seconds per article (CPU) | **12.7** | 26.9 | 55.2 |
| OCR firings over the corpus | **0** | 423 | sparse |

**The control comes first, because it is what licenses the rest.** Both baselines were
re-run unchanged, at the versions `baselines.txt` still pins. **docling reproduced every
recorded figure to six decimal places.** pymupdf4llm reproduced its deterministic figures
exactly and drifted only on OCR-dependent ones (novel share +0.0015, tables +4) — RapidOCR
is not bit-deterministic across thread counts. Two unchanged tools reproducing is what makes
all2md's movement attributable to all2md rather than to the instrument.

### What moved, against 2026-08-19 (`99a0eb0` → `073e4da`)

Same corpus pin, same platform, same baseline versions; the only variable is our own commit.

| | then | now |
| --- | --- | --- |
| Recall of attainable | 93.5% | **98.2%** (+4.71) |
| — text blocks | 94.3% | **98.4%** (+4.15) |
| — titles | 93.4% | **98.7%** (+5.30) |
| — table text | 69.9% | **77.4%** (+7.53) |
| Novel share | 0.84% | **0.62%** (−0.22) |
| Duplication | 0.61% | **0.46%** (−0.15) |
| `reparse_word_ratio` | 0.957 | 0.983 |

Recall rose 4.7 points while invented text *fell*. That is the combination worth having:
the highest-recall converter imaginable dumps the text layer with no structure, and
pymupdf4llm shows what buying recall with OCR costs — it reaches the same 98.3% with 423
OCR firings on a corpus where **no page needs OCR at all** (0 of 1,184 pages carry a text
layer under 20 characters), and pays 5.64% novel share for it. all2md fired zero times.

On this corpus all2md now leads docling overall, leads both on text blocks, and trails only
pymupdf4llm on titles (98.7% vs 99.3%) and docling on table text.

### The lost-block diff

`lost_blocks.py` names every truth block a baseline recovers that all2md loses. Against
pymupdf4llm it went **528 → 108** (title 49, text block 47, table 12); against docling, 113.

The residue is almost entirely *shredded* rather than absent — 79 of the 108 sit at
containment 0.4–0.8, only 2 below 0.05 — and it is concentrated: 45 of 108 fall in two
articles (`PMC7250022.1`, `PMC7250011.1`). Its mechanism has not been diagnosed yet and is
not assumed here.

**#414 is answered by this diff.** Its exemplar, `PMC11000022.1`, now loses **zero** blocks
against either baseline. The issue's own stated trigger was the class rising in a holdout
block-diff; it has not risen.

**Table misses became #438.** Of 146 attainable tables we recover 113, and of the 33 we miss,
**none are absent** — word containment across all 33 is mean 0.998, median 1.000. Every miss
is adjacency: wrapped cell text becomes extra table rows, so the words are all present and
non-contiguous. docling recovers 20 of the 33 (twelve at containment 1.000), so they are
reachable; its lead is merging wrapped cells, not reading text we cannot reach.

The honest positioning, with each tool's structural advantage named:

- **pymupdf4llm wins raw text survival by 0.03 points and loses trustworthiness by 9×.**
  Its 5.6% novel share is not a scoring artifact: pymupdf4llm 1.28+ bundles `pymupdf-layout`
  and auto-fires RapidOCR on born-digital pages, and OCR of pages that already have a text
  layer mints text the document never contained. Measured this run: 423 firings, zero needed.
- **Docling has the best table cell preservation** (82.2% vs our 77.4%, a gap down from 12.3
  points to 4.8) at ~4× our runtime. It is not OCR doing that — its OCR is sparse and
  region-scoped. It is TableFormer merging wrapped cells. See #438.
- **all2md wins invented text decisively** (0.62%) and is the fastest of the three.

## Earlier readings

- **2026-08-19** (`results-2026-08-19.json`, all2md `99a0eb0`). all2md 93.5% recall / 0.84%
  novel; pymupdf4llm 98.3% / 5.49%; docling 95.5% / 2.87%. Its lost-block diff ran to 528
  blocks against pymupdf4llm and became **#405** (side-by-side regions interleaved
  line-by-line, ~405 blocks at partial containment 0.4-0.8) and **#406** (figure captions
  absent entirely, 66 blocks at share ~0). Both are fixed; the diff is now 108.

## Caveats that bound the numbers

- **Tesseract is installed on the recording machine but not on PATH.** For this corpus that
  is moot and was measured rather than assumed: 0 of its 1,184 pages carry a text layer under
  20 characters, so all2md's auto-OCR has nothing to fire on, and it fired 0 times. The
  2026-08-19 reading carried this as an unbounded caveat; it is now bounded. Still do not
  quote all2md OCR *misfire* counts from this lane -- a corpus with no scans cannot measure
  them. The PMC lane on Linux is the instrument for that.
- **These results never go on the docs fidelity page.** `docs/source/benchmarks.rst` is
  verbatim-gated against committed artifacts of *this repo's* lanes; third-party numbers
  age with every baseline release and belong here, dated, instead.
- Article-level text survival favors low-structure output (the asymmetry under
  "deliberately narrow" above). A tool "beating" all2md on attainable recall by 0.03 points
  while inventing 9× more text is not ahead; the two columns must travel together.

## Running it

```bash
# 1. Materialize the held-out corpus (project venv, digest-verified). The separate cache
#    root is part of the seal -- see benchmarks/pmc/README.md.
.venv/Scripts/python.exe -m benchmarks.pmc load --manifest benchmarks/pmc/manifest-holdout.json     --cache benchmarks/pmc/.cache-holdout

# 2. Export the article list for the baselines venv.
.venv/Scripts/python.exe benchmarks/comparison/export_articles.py

# 3. Create the baselines venv — SHORT path on Windows (transformers vs MAX_PATH),
#    NOT under %TEMP% (see below), and never the project venv: the separation keeps
#    baseline deps out of the lockfile.
uv venv C:/a2mbl --python 3.13
uv pip install -r benchmarks/comparison/baselines.txt --python C:/a2mbl

# 4. Convert. Each script skips articles already converted, so reruns resume.
C:/Users/<you>/AppData/Local/Temp/a2mbl/Scripts/python.exe benchmarks/comparison/convert_pymupdf4llm.py
C:/Users/<you>/AppData/Local/Temp/a2mbl/Scripts/python.exe benchmarks/comparison/convert_docling.py
.venv/Scripts/python.exe benchmarks/comparison/convert_all2md.py

# 5. Score everything through the one normalization path.
.venv/Scripts/python.exe benchmarks/comparison/score.py

# 6. Diff: what does a baseline keep that we lose?
.venv/Scripts/python.exe benchmarks/comparison/lost_blocks.py pymupdf4llm

# 7. Headings, and the table content/order split. Both read the same out/ tree as
#    score.py, so they need no conversion of their own.
.venv/Scripts/python.exe benchmarks/comparison/headings.py
.venv/Scripts/python.exe benchmarks/comparison/tablediag.py
```

**Do not put the baselines venv under `%TEMP%`.** It was there until 2026-08-27, and
Windows purged parts of it between readings: `tqdm`, `rapidocr` and several `docling`
submodules were left as empty package directories. The failure does not look like a broken
venv — `import pymupdf4llm` and `import docling` both still succeed, and the breakage only
surfaces deep in a conversion as `cannot import name X from Y (unknown location)`. On the
2026-08-27 run it presented as **103 of 103 articles "FAILED"** with no traceback, because
the converters record `run.json` only after a success. If a baseline fails corpus-wide,
check the venv before suspecting the corpus: `python -c "import rapidocr; print(rapidocr.__file__)"`
printing `None` is the signature.

Publishing a reading: copy `comparison.json` to `results-YYYY-MM-DD.json`, add a
`provenance` block (date, corpus pin, all2md commit, platform, policy note), update the
table above, and bump `baselines.txt` if versions moved.
