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

   **This corpus was redrawn on 2026-08-27, and every reading below predates it.** The
   holdout those readings used is now `benchmarks/pmc/manifest-tuned.json`: it had been
   tuned against — six tracked files name its articles, five of them source or tests — so
   its numbers are in-sample and are labeled that way here. `benchmarks/pmc/README.md`
   carries the full burn record. Nothing below has been re-measured against the fresh
   corpus yet, so read every figure in this file as a **dated, in-sample** reading.
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

**What this lane measures is deliberately narrow: article-level text survival and
invented text.** Those are the two instruments with published false-positive controls
that third-party output can enter. The page-level instruments (reading order, table
*structure*, heading fidelity) require all2md's page attribution and cannot score other
tools — and text survival alone structurally favors low-structure converters: the
highest-recall converter imaginable dumps the raw text layer with no structure at all.
Quote these numbers with that asymmetry attached.

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
#    and never the project venv: the separation keeps baseline deps out of the lockfile.
uv venv C:/Users/<you>/AppData/Local/Temp/a2mbl --python 3.13
uv pip install -r benchmarks/comparison/baselines.txt --python C:/Users/<you>/AppData/Local/Temp/a2mbl

# 4. Convert. Each script skips articles already converted, so reruns resume.
C:/Users/<you>/AppData/Local/Temp/a2mbl/Scripts/python.exe benchmarks/comparison/convert_pymupdf4llm.py
C:/Users/<you>/AppData/Local/Temp/a2mbl/Scripts/python.exe benchmarks/comparison/convert_docling.py
.venv/Scripts/python.exe benchmarks/comparison/convert_all2md.py

# 5. Score everything through the one normalization path.
.venv/Scripts/python.exe benchmarks/comparison/score.py

# 6. Diff: what does a baseline keep that we lose?
.venv/Scripts/python.exe benchmarks/comparison/lost_blocks.py pymupdf4llm
```

Publishing a reading: copy `comparison.json` to `results-YYYY-MM-DD.json`, add a
`provenance` block (date, corpus pin, all2md commit, platform, policy note), update the
table above, and bump `baselines.txt` if versions moved.
