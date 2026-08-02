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

The normalized result can record seven higher-is-better metrics:

| Dimension | Eligible pages |
| --- | --- |
| Text content similarity | Every page |
| Reading-order similarity | Every page |
| Block structure similarity | Every page |
| Formula presence accuracy | Pages with annotated or emitted inline or isolated formulae |
| Table structure similarity | Pages with annotated or emitted tables |
| Table content similarity | Pages with annotated or emitted tables |
| Formula content similarity | Pages with annotated or emitted inline or isolated formulae |

Each dimension records the aggregate, eligible-page denominator, population variance, and exact page scores. Text comparison uses exact normalized Levenshtein similarity after Unicode normalization and case folding. Whitespace is deleted only where it touches ideographic text, because OCR inserts spurious spaces between CJK glyphs; every other whitespace run collapses to a single space, so losing Latin word boundaries costs score. The deletion runs on both sides of NFKC, since NFKC folds fullwidth punctuation to ASCII and would otherwise leave the spurious spaces beside those glyphs in place: of the 743 pinned pages whose text contains such a glyph, padding it with spaces cost score on 588 before the class was widened and on none after. Table structure compares row, column, and expanded cell-slot counts; table structure and content share one exact best order-preserving alignment. Formulae use the same alignment rule, with unmatched items scored as zero. Inline and isolated formulae align only with the same kind; their LaTeX comparison preserves case and semantic whitespace.

Reading order measures ordering, and nothing else. Each annotated block is located inside the *concatenated* emitted text, and the order of those positions is compared with the order the annotation gives them; the score is the fraction of blocks that could be located, scaled by the order agreement among them. Locating rather than pairing is the point. An earlier version matched each emitted block to its most similar annotated block one-to-one, which measured segmentation as much as ordering, because a converter may split or merge blocks without moving a single word: text reproduced exactly but emitted as one block scored 0.0, and splitting every block in two scored 0.44. On the pinned corpus that left 894 of the 981 pages at exactly zero, 128 of them scoring 0.9 or better on text content, which is a metric with no dynamic range left to detect a regression with. A block still has to be found before it votes on the ordering: below 0.5 of its characters aligned it is not evidence of anything, which is what stops absent content from buying order credit — blanking every block used to score a *perfect* reading order, better than emitting all of them correctly but reversed. Alignment counts every matched character rather than the longest unbroken run, so a substitution as ordinary as `o` for `0` does not read as a block that went missing. Reversal still scores 1.0 on the 15 pages that carry fewer than two text blocks, where there is no order to disagree about.

Block structure is a separate dimension over the block-category sequence, and it is deliberately not a factor of the reading-order score — folding it in was the other way segmentation got into a metric about order, costing four correctly merged blocks three quarters of their score for a reason unconnected to ordering. It also cannot answer the ordering question itself: eleven text categories collapse to one `text_block` token, so fully reversed output scores exactly 1.0 on it on 153 of the 981 pinned pages, and any permutation is free on the 113 pages whose kinds are a single repeated token. Recovering a table's cells as a paragraph costs exactly one kind substitution here and nothing on the other two dimensions, so it strictly beats deleting the table on all 317 pages that have table ground truth.

Read the recorded 0.1176 as a segmentation-granularity ratio, not as a verdict on structure. Edit distance is at least the length difference, so the score can never exceed `min/max` of the two block counts, and with eleven text categories collapsed to one token the two are equal in practice: the median page scores 0.077, meaning all2md emits up to thirteen blocks for every region the dataset annotates. Much of that gap is definitional rather than a defect — `_semantic_blocks` yields each list item's paragraph separately, while OmniDocBench annotates a whole list as one `text_block` region. The dimension is also blind to content, because it compares kinds and never the text under them: every one of the eight pages scoring a perfect 1.0 is a sparse slide, and one of them reproduces 7% of its text. That is the same shape as the blank-block defect the reading-order identification floor closed, and it is why this dimension is a second instrument rather than a quality score. It cannot let a regression through the gate on its own, since text content scores those same pages, and its independence is what earns it a place: across the 981 pinned pages it correlates +0.03 with reading order and +0.05 with text content, where those two correlate +0.84 with each other.

On the pinned corpus a projection that reproduces the annotation exactly scores 1.0 on every dimension. Reversing the blocks, and replacing every block with empty or unrelated text, score strictly below that; merging every text block into one paragraph now costs block structure alone, which is the dimension that question belongs to. Eleven degraded variants were swept across all six dimensions on all 981 pages and every one scored at or below exact reproduction. That sweep predates both the identification term and the split, and each of its variants deleted blocks, so the variants that keep the block structure and destroy the content — and the ones that keep both and only re-chunk — are pinned as unit tests instead. The sweep was an ad-hoc analysis rather than a committed harness, so the bootstrap run did not reproduce it and its per-variant figures are still the pre-split ones; treat them as indicative of the dimensions they were measured on, not as current. What the bootstrap run does establish is recorded below.

A dimension that the PDF parser cannot expose is reported in `unsupported_dimensions`. Scoring is union-scoped, so a page with neither an annotated nor an emitted item of that kind is never scored: when all2md emits no math nodes at all, the alternative to reporting `formula_fidelity` unsupported is a dimension that is uniformly zero across every eligible page, which the ratchet reds as a vacuous aggregate. Each message names both how many pages converted and how many pages carry that kind of ground truth, so the erased eligibility stays measurable; it is also visible in `unscored_annotation_categories` and the page counts. If the parser later starts emitting that AST capability, the new dimensions are a ratchet change that requires baseline review.

A page whose conversion degrades, for example an OCR fallback recorded in `confidence.degraded_events`, is recorded as a conversion failure and scores zero in every dimension it is eligible for. A `table_rejected` event is the exception: refusing a non-tabular grid is a correct parser decision, and its cost still lands on text content and reading order because the cell text stays in the annotation's text stream. Every degraded-event kind observed in a run is counted in `degraded_events`, so an exempted degradation still leaves evidence in the payload.

The ratchet fails closed for missing or duplicate pages, corpus, oracle, parser-policy, or parser-runtime drift, malformed or non-finite scores, missing or stale dimensions, changed denominators, new conversion failures, fixed recorded failures, regressions, and improvements that have not been accepted in the baseline. The recorded `worktree_dirty` flag is compared like every other identity field, so a measurement taken from an unclean tree can never match a baseline recorded from a clean one. A dimension that loses all page-to-page spread is red unless the baseline records that unanimity, which keeps a genuinely 0/1-per-page metric such as formula presence reviewable instead of permanently red.

Its sensitivity is the recorded per-metric tolerance, which `--default-tolerance` sets to 0.005. Re-measured on the recorded baseline's own full-corpus result: scaling the page scores so an aggregate falls by exactly 0.005 stays green, and 0.006 is red, both for all three dimensions together and for each one alone. Move the page scores rather than the aggregate when reproducing this — an aggregate edited on its own is recomputed from `sample_scores` and reported as `IDENTITY_DRIFT` before the tolerance is ever consulted. A regression smaller than the tolerance is therefore invisible by construction, which is the price of not going red on measurement noise. Tighten the tolerance in the baseline for a metric whose page scores are stable enough to justify it. A tolerance of 1 or more is rejected outright, because every score lives in `[0, 1]` and such a band could never be breached by any run.

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

`baseline.json` records the run of 2026-08-01 over all 981 pinned pages at `935df18`: text content 0.5058, reading order 0.6034, block structure 0.1176. Re-record it the same way it was bootstrapped — dispatch the `OmniDocBench PDF Fidelity Gate` workflow with `record_baseline` enabled, review the uploaded candidate, and commit it. Recording the baseline from CI is required: a local run resolves different parser-runtime identity and every later CI run would report `IDENTITY_DRIFT`.

`provenance.corpus_characterization` records what the corpus actually contains, counted
over the pages that could be read: how many carry a text layer, vector drawings, or the
single-full-page-image shape of a scan, and how many the parser ran OCR on. It exists
because this lane was built, gated and baselined before anyone asked that question, and
the answer turned out to decide what the scores mean — every page is a raster, so they
grade OCR rather than the PDF text and table paths. `pages_characterized` is the
denominator for the rest, and a file that cannot be read at all is excluded from it
rather than counted as having no traits. The counts are read from the PDF directly rather
than from an all2md projection, so a parser change cannot alter what the corpus is
reported to contain. They are evidence, not identity: the corpus is already pinned by
`dataset_revision` and `annotation_sha256`, so they cannot drift without those changing,
and keeping them out of the gate's identity fields is what lets such evidence be added
without invalidating a recorded baseline. **Characterize the inputs, not just the
annotations** — schema-validating one side of a comparison proves nothing about the other.

Review the candidate's numbers before committing one, rather than only its shape. Both metric defects this lane has had were caught that way and neither showed up as an error: a dimension reading 0.0267 with 894 of 981 pages at exactly zero is a passing measurement of a broken metric, and 128 of those pages scored 0.9 or better on text content at the time. A dimension pinned at one value has no range left to detect a regression with, whatever its value.

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
