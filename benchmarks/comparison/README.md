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

1. **Held-out corpus only.** The 110 articles of
   `benchmarks/pmc/manifest-holdout.json` — the corpus development work has never tuned
   against. Comparing on the 66-article development corpus would flatter all2md with
   in-sample numbers.
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

## Reading, 2026-08-19 (`results-2026-08-19.json`)

110 of 110 articles converted by every tool; zero conversion failures anywhere.

| | all2md @ 99a0eb0 | pymupdf4llm 1.28.2 | docling 2.120.3 |
| --- | --- | --- | --- |
| Recall of attainable | 93.5% | **98.3%** | 95.5% |
| — titles | 93.4% | 99.3% | 95.4% |
| — table text | 69.9% | 65.1% | **82.2%** |
| **Novel (invented) share** | **0.84%** | 5.49% | 2.87% |
| Duplication | 0.61% | 0.19% | 0.62% |
| Tables emitted / expected | 228 / 166 | 208 / 166 | 201 / 166 |
| Seconds per article (CPU) | ~10 | ~35 | ~92 |

(The all2md row is the re-parsed figure per rule 3; its direct payload figure on the
same corpus is 93.8%. Docling's timing mean is inflated by model warmup and by the run
being suspended mid-flight; treat all timings as rough.)

The honest positioning, with each tool's structural advantage named:

- **pymupdf4llm wins raw text survival and loses trustworthiness.** Its 5.5% novel
  share — 6.5× ours — is not a scoring artifact: pymupdf4llm 1.28+ bundles
  `pymupdf-layout` and auto-fires RapidOCR on born-digital pages, and OCR of pages that
  already have a text layer mints text the document never contained. This is the same
  misfire class the PMC lane measured and gated out of all2md with the
  largest-single-image threshold.
- **Docling has the best table cell preservation** (82.2% vs our 69.9%) at ~9× our
  runtime. Its table extraction keeps cell text ours drops — a study target, not a
  mystery to live with.
- **all2md wins invented text decisively** (0.84%) and is the fastest of the three.

## What the reading produced

The point of the lane is the diff, not the leaderboard. `lost_blocks.py` names every
truth block a baseline recovers that all2md loses; the 2026-08-19 run (528 blocks
against pymupdf4llm) became:

- **#405** — side-by-side regions interleaved line-by-line (~405 of 528 blocks at
  partial containment 0.4–0.8): two-column reference lists with tight gutters, and boxed
  sidebars beside body columns. Words survive; adjacency is destroyed.
- **#406** — figure captions absent entirely (66 caption blocks at share ~0: the words
  appear nowhere in the output, so this is not a binding failure).
- Docling table-extraction study — what does it preserve that our cell extraction drops?

## Caveats that bound the numbers

- **The recording machine had no Tesseract binary**, so all2md's would-be OCR firings
  fall back silently. Do not quote OCR misfire counts from this lane; the PMC lane on
  Linux is the instrument for that.
- **These results never go on the docs fidelity page.** `docs/source/benchmarks.rst` is
  verbatim-gated against committed artifacts of *this repo's* lanes; third-party numbers
  age with every baseline release and belong here, dated, instead.
- Article-level text survival favors low-structure output (the asymmetry under
  "deliberately narrow" above). A tool
  "beating" all2md on attainable recall while inventing 6× more text is not ahead; the
  two columns must travel together.

## Running it

```bash
# 1. Materialize the held-out corpus (project venv, digest-verified).
.venv/Scripts/python.exe -m benchmarks.pmc load --manifest benchmarks/pmc/manifest-holdout.json

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
