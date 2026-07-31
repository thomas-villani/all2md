# OmniDocBench PDF fidelity gate

This benchmark compares one `all2md` PDF AST with independent OmniDocBench annotations. It does not render the AST to Markdown, parse a prediction, or call `roundtrip_report`. A parser and renderer therefore cannot agree on the same wrong structure and receive a perfect score.

The scheduled workflow runs the full 981-page corpus. Pull request and release workflows do not run it. The corpus includes about 410 MB of page-level PDFs, and OCR makes a complete run too expensive for per-commit CI.

## Pinned inputs

The benchmark fixes each external input by immutable identity:

- OmniDocBench v1.0 dataset: `f5f559bddf50e36f7f9899d842d0006f13ce8afc`
- `OmniDocBench.json` SHA-256: `2fafe9329dc92fc426b30036aee51c716b3fcdcc1d20cb964dc7670579533817`
- Expected annotations and page PDFs: 981
- Local oracle schema: 3
- Normalized result schema: 2

The OmniDocBench evaluator source is Apache-2.0, but this lane does not execute it. The dataset is different. Its card states that collected PDFs are for research purposes only and must not be used commercially. The adapter downloads corpus bytes into `benchmarks/omnidocbench/.cache/`, which Git ignores. Do not commit the cache, annotation JSON, page PDFs, or images. CI artifacts contain only derived scores.

## Install the tools

Reproduce the CI runtime with the locked environment the scheduled workflow uses. The full corpus includes English and simplified Chinese pages:

```bash
uv sync --frozen --extra pdf_layout --extra ocr
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim
```

Any other environment, including a plain `python -m pip install -e ".[pdf_layout,ocr]"` on another distribution, resolves different parser-runtime identity and cannot match a CI-recorded baseline. Run full runs from such an environment with `--skip-gate`.

The pinned parser policy uses enabled layout analysis and automatic Tesseract OCR at 200 DPI.
It requests `eng+chi_sim` by default. The ratchet treats parser-policy and parser-runtime changes as identity drift. Runtime identity records the PyMuPDF, pymupdf-layout, pytesseract, Pillow, Tesseract, and Tesseract language-data versions.

A complete local run downloads and validates the corpus, calls `all2md.to_ast` once for each page, projects supported AST facts, and compares the result with `baseline.json`. Page conversion is serial because PyMuPDF is not thread-safe; `--download-workers` controls only corpus download and first-pass cache validation parallelism, and revalidating an already-indexed warm cache is serial:

```bash
python -m benchmarks.omnidocbench
```

Use a deterministic subset only for integration smoke tests. A limited run must skip the gate because it does not have the full denominator. Fifty pages include text, tables, and formula ground truth:

```bash
python -m benchmarks.omnidocbench \
  --limit 50 --download-workers 1 --skip-gate
```

## Score contract

The local oracle loads annotation fields directly and projects these AST nodes:

- `Heading`, `Paragraph`, and `CodeBlock` for text content, against every text-bearing annotation category: `text_block`, `title`, `code_txt`, `header`, `footer`, `page_number`, `figure_caption`, `table_caption`, `equation_caption`, `figure_footnote`, `table_footnote`, `page_footnote`, and `reference`. Scoring a filtered subset would compare part of the page with the whole AST, so dropping captions or references would raise the score. Table cell text joins the text stream on both sides, so failing to build a `Table` node is not scored worse than deleting the table outright.
- The ordered `Heading`, `Paragraph`, `CodeBlock`, `Table`, and `MathBlock` sequence for reading order. Every `header`, `footer`, `page_number`, and `page_footnote` annotation carries `order: null`, so those are placed by the vertical centre of their polygon relative to the page height. Sorting them last would rank a running head after the body, which made deleting the header outscore emitting it.
- `Table`, `TableRow`, and `TableCell` for table rows, columns, spans, and cell text.
- `MathBlock` against top-level `equation_isolated` annotations and `MathInline` against `equation_inline` annotations, both top-level detections and non-ignored nested spans. Spans nested inside `code_txt` are skipped, because a `CodeBlock` holds a plain string and cannot expose them.

The normalized result can record six higher-is-better metrics:

| Dimension | Eligible pages |
| --- | --- |
| Text content similarity | Every page |
| Reading-order similarity | Every page |
| Formula presence accuracy | Pages with annotated or emitted inline or isolated formulae |
| Table structure similarity | Pages with annotated or emitted tables |
| Table content similarity | Pages with annotated or emitted tables |
| Formula content similarity | Pages with annotated or emitted inline or isolated formulae |

Each dimension records the aggregate, eligible-page denominator, population variance, and exact page scores. Text comparison uses exact normalized Levenshtein similarity after Unicode normalization and case folding. Whitespace is deleted only where it touches ideographic text, because OCR inserts spurious spaces between CJK glyphs; every other whitespace run collapses to a single space, so losing Latin word boundaries costs score. The deletion runs on both sides of NFKC, since NFKC folds fullwidth punctuation to ASCII and would otherwise leave the spurious spaces beside those glyphs in place: of the 743 pinned pages whose text contains such a glyph, padding it with spaces cost score on 588 before the class was widened and on none after. Table structure compares row, column, and expanded cell-slot counts; table structure and content share one exact best order-preserving alignment. Formulae use the same alignment rule, with unmatched items scored as zero. Inline and isolated formulae align only with the same kind; their LaTeX comparison preserves case and semantic whitespace.

Reading order measures block segmentation and ordering. It is an edit similarity over the block-category sequence, scaled by the order agreement of the emitted blocks matched to their most similar annotated block. The coverage term alone is not an order metric: eleven text categories collapse to one `text_block` token, so fully reversed output scored exactly 1.0 on 153 of the 981 pinned pages, and any permutation was free on the 113 pages whose kinds are a single repeated token. Reversal still scores 1.0 on the 15 pages that carry fewer than two text blocks, where there is no order to disagree about. On the pinned corpus a projection that reproduces the annotation exactly scores 1.0 on both dimensions; merging every text block into one paragraph scores 0.129 on order and still 1.0 on text; reversing the blocks scores 0.020 on order and 0.331 on text. Recovering a table's cells as a paragraph costs exactly one kind substitution and nothing else, so it strictly beats deleting the table on all 317 pages that have table ground truth. Every degraded variant scores at or below exact reproduction on all six dimensions across all 981 pages.

A dimension that the PDF parser cannot expose is reported in `unsupported_dimensions`. Scoring is union-scoped, so a page with neither an annotated nor an emitted item of that kind is never scored: when all2md emits no math nodes at all, the alternative to reporting `formula_fidelity` unsupported is a dimension that is uniformly zero across every eligible page, which the ratchet reds as a vacuous aggregate. Each message names both how many pages converted and how many pages carry that kind of ground truth, so the erased eligibility stays measurable; it is also visible in `unscored_annotation_categories` and the page counts. If the parser later starts emitting that AST capability, the new dimensions are a ratchet change that requires baseline review.

A page whose conversion degrades, for example an OCR fallback recorded in `confidence.degraded_events`, is recorded as a conversion failure and scores zero in every dimension it is eligible for. A `table_rejected` event is the exception: refusing a non-tabular grid is a correct parser decision, and its cost still lands on text content and reading order because the cell text stays in the annotation's text stream. Every degraded-event kind observed in a run is counted in `degraded_events`, so an exempted degradation still leaves evidence in the payload.

The ratchet fails closed for missing or duplicate pages, corpus, oracle, parser-policy, or parser-runtime drift, malformed or non-finite scores, missing or stale dimensions, changed denominators, new conversion failures, fixed recorded failures, regressions, and improvements that have not been accepted in the baseline. The recorded `worktree_dirty` flag is compared like every other identity field, so a measurement taken from an unclean tree can never match a baseline recorded from a clean one. A dimension that loses all page-to-page spread is red unless the baseline records that unanimity, which keeps a genuinely 0/1-per-page metric such as formula presence reviewable instead of permanently red.

Its sensitivity is the recorded per-metric tolerance, which `--default-tolerance` sets to 0.005. Measured on the full-corpus result: sliding every dimension down by exactly 0.005 stays green, and 0.007 is red on both dimensions. A regression smaller than the tolerance is therefore invisible by construction, which is the price of not going red on measurement noise. Tighten the tolerance in the baseline for a metric whose page scores are stable enough to justify it. A tolerance of 1 or more is rejected outright, because every score lives in `[0, 1]` and such a band could never be breached by any run.

The same reasoning bounds the aggregate itself. A recorded value within its own tolerance of the metric's worst possible score is refused as vacuous, not only a value exactly at that score: no later decline can exceed the tolerance from there, so one degenerate bootstrap run would otherwise mint a permanently green baseline and then report the first working run as an unrecorded improvement. A single page scoring one part in a billion is enough to lift the variance off zero, so the exact-floor test alone did not close this.

A dimension may also not declare more eligible items than the corpus holds pages, since each dimension scores a page at most once. That check is suppressed while the page counts themselves disagree with the baseline, where the deficit is already reported once against `pages`.

## Review a baseline change

Generate a candidate only from a complete run:

```bash
python -m benchmarks.omnidocbench \
  --write-baseline /tmp/omnidocbench-baseline.json \
  --default-tolerance 0.005
```

Review the candidate's metric values, `eligible_items`, `variance`, and `tolerance`, and the run's `unsupported_dimensions`, `unscored_annotation_categories`, page counts, and every expected conversion failure before replacing `baseline.json`. The candidate records only the identity, page, dimension, and expected-failure fields; the unsupported and unscored evidence lives in the result JSON the same run writes. A tolerance is an absolute score delta in the metric's native `[0, 1]` range.

`baseline.json` is not committed yet, so the gate reports `ABSENT_BASELINE` red until a candidate is accepted. Bootstrap it by dispatching the `OmniDocBench PDF Fidelity Gate` workflow with `record_baseline` enabled, reviewing the uploaded candidate, and committing it as `benchmarks/omnidocbench/baseline.json`. Recording the baseline from CI is required: a local run resolves different parser-runtime identity and every later CI run would report `IDENTITY_DRIFT`.

Synthetic adapter, oracle, and ratchet tests run without the corpus:

```bash
pytest -q \
  tests/unit/test_omnidocbench_corpus.py \
  tests/unit/test_omnidocbench_oracles.py \
  tests/unit/test_omnidocbench_benchmark.py \
  tests/unit/test_omnidocbench_pipeline.py \
  tests/unit/test_omnidocbench_gate.py \
  tests/unit/test_omnidocbench_run.py
```
