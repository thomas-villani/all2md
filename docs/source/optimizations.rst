PDF Parsing Optimizations
==========================

Between releases 1.1.0 and 1.1.1 a series of profile-driven changes reduced the
corpus benchmark from **21.4 minutes to 6.7 minutes** — a 3.2x improvement, with
the worst-case single file dropping from **2.1 min to 11.65 s** (10.8x). This
page documents the methodology, the contributing changes, and the work that
remains.

.. contents::
   :local:
   :depth: 2

Methodology
-----------

The work followed a tight measure / fix / re-measure loop with three
complementary tools shipped with the repo:

* **Corpus benchmark** (``benchmarks/corpus/run.py``) — pulls a deterministic
  sample from public corpora (arxiv, govdocs1, Apache POI, Enron), times
  conversion of each doc, and produces stratified p50 / p95 / mean tables
  per source and per format. See :doc:`performance` for a full reference.
* **Single-file profiler** — for the slowest doc in each report, an isolated
  ``cProfile`` run dumps cumulative-time and self-time call graphs to attribute
  wall-clock cost to specific functions.
* **Inspect helper** (``benchmarks/corpus/inspect``) — renders Markdown
  alongside its source PDF for the slowest / largest / random subsets. Timing
  tells you whether a doc is fast; only reading the markdown tells you whether
  it is *correct*. Inspect was decisive several times during this work for
  spotting pathologies that pure timing would have missed (TOC dot-leader
  tables, empty 2-column tables, ``![Image from page N]()`` noise).

The corpus benchmark detects regressions; the profiler attributes them; the
inspect helper verifies correctness. All three were needed.

Headline impact
---------------

Corpus-wide on a single 149-doc run:

.. list-table::
   :header-rows: 1
   :widths: 30 25 25 20

   * - Metric
     - Baseline (b0e4224)
     - Optimized (3516bc9)
     - Improvement
   * - Total wall time
     - 21.4 min
     - 6.7 min
     - 3.2x faster
   * - Aggregate MB/s
     - 0.08
     - 0.37
     - 4.6x
   * - PDF p50
     - 8.54 s
     - 728 ms
     - **11.7x faster**
   * - PDF p95
     - 1.1 min
     - 13.5 s
     - 4.9x
   * - PDF mean
     - 16.0 s
     - 5.0 s
     - 3.2x
   * - govdocs1 p50
     - 5.91 s
     - 194 ms
     - **30x faster**
   * - govdocs1 mean
     - 13.7 s
     - 1.08 s
     - 12.7x

The two underlying reports — ``b0e4224-baseline.md/json`` and
``3516bc9-optimized.md/json`` — are committed under ``benchmarks/reference/``
for verification.

Case study: a 1.25 MB PDF that took 5.6 minutes
------------------------------------------------

The slowest individual doc on a May 15 baseline run was
``govdocs1/000887.pdf``, a 1.25 MB / ~150-page government report on renewable
energy. It took **322 seconds** to convert — roughly 3.7 KB/s.

``cProfile`` attribution of that single conversion:

.. list-table::
   :header-rows: 1
   :widths: 50 20 30

   * - Bucket
     - Time (cumulative)
     - % of total
   * - PyMuPDF ``find_tables()`` (table detection)
     - 202 s
     - **63%**
   * - ``pymupdf-layout`` (ONNX block classifier)
     - ~110 s
     - **34%**
   * - Plain text extraction (``page_get_textpage``)
     - 26 s
     - 8%
   * - all2md code total (parser + render + AST)
     - ~15 s
     - 5%

Two heavyweight passes consumed ~97% of runtime, and *neither was our code*.
``find_tables()`` was running on every page — including the ~100 pages of pure
prose where it would find no tables but still scan 13.5 million character /
rect-containment relationships. The optional ``pymupdf-layout`` ONNX-based
block classifier was likewise running on every page, including pages whose
layout is trivially single-column prose.

After the changes documented below, the same conversion takes **11.65 s** —
a **28x speedup** on the file that drove the investigation.

The contributing changes
------------------------

In order of impact:

find_tables() pre-flight gate (3516bc9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The big one. Added ``page_has_table_signals()`` in ``_pdf_tables.py``: a cheap
scan of ``page.get_drawings()`` that returns ``True`` only when the page has
ruling-line drawings or a sufficiently large closed rectangle. The default
"both" mode in ``_detect_page_tables`` now consults it before calling
``find_tables()`` and skips both the PyMuPDF call and the ruling-line fallback
when there are no table indicators.

``mode == "pymupdf"`` is unchanged — users who explicitly opted into always-on
PyMuPDF table detection keep that behavior.

The gate is conservative on error: any failure to enumerate drawings returns
``True`` so PyMuPDF quirks can't silently lose real tables. Cascading effect
on this case study:

* ``find_tables()`` calls: 171 → 112 (35% of pages skipped)
* ``find_tables()`` cumulative time: 202 s → 102 s
* ``char_in_bbox`` calls: 13.5 M → 9.3 M
* **Layout model time also dropped** (~110 s → ~61 s) because PyMuPDF's
  ``find_tables()`` internally invokes layout analysis to position tables —
  skipping the call avoided the layout invocations it would have triggered.

Net wall time on this file: 322 s → 179 s before the layout toggle, then
179 s → ~120 s after.

Benchmark layout-model toggle (3516bc9)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``layout_analysis_mode`` (``"auto"`` / ``"enabled"`` / ``"disabled"``) already
existed on ``PdfOptions``. The change here was on the *benchmark* side: the
corpus harness now defaults the mode to ``"disabled"`` so wall-clock numbers
are reproducible across machines that may or may not have ``pymupdf-layout``
installed. Pass ``--use-layout-model`` to opt back into the library default
(``"auto"``) for runs that want layout-on numbers.

The library default is unchanged. End users who installed ``pymupdf-layout``
deliberately still get its semantic block classification (title /
section-header / caption / footnote / picture / formula) by default.

Pathological table rejection (cbd5de7)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PyMuPDF's ``find_tables()`` and the ruling-line fallback both occasionally
fire on non-tabular content: decorative frames, oversized empty grids,
dot-leader-heavy TOC regions, and section-header underlines. Shared guards
on row/column counts (``MAX_TABLE_COLS = 25``, ``MAX_TABLE_ROWS = 200``),
empty-cell ratios (``MAX_TABLE_EMPTY_RATIO = 0.70``), and dot-leader
density (``MAX_DOT_LEADER_CELL_RATIO = 0.30``) now reject these in both code
paths.

The guards eliminated hundreds-to-thousands of garbage "table" rows per file
in the inspect output — a correctness win that also reduces downstream
rendering work.

Skip image work in alt_text mode (10227a6)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the default ``attachment_mode="alt_text"``, image extraction has no URL
to point markers at, so it was emitting ``![Image from page N]()``
placeholders — pure noise. An image-heavy 32-page workshop PDF produced 130+
such lines. ``extract_page_images()`` now returns early in that mode, which
both suppresses the markers and avoids decoding every pixmap only to throw
the bytes away (~160 pixmap decodes avoided on the workshop PDF).

``image_placement_markers`` remains meaningful in ``save`` and ``base64``
modes where there is a real URL / path for the marker to reference.

Rotated text grouping (f47874c)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Previously each rotated PDF line emitted its own paragraph with an inline
``*[rotated 90° counter-clockwise]*`` marker, flooding output (~280 markers
on the figure-axis labels of the "Attention Is All You Need" paper).
Consecutive rotated spans now accumulate within blocks and merge across
blocks via metadata. The annotation is opt-in via the new
``annotate_rotated_text`` option (default ``False``).

Heading & whitespace robustness (b0e4224)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Earlier in the cycle: reworks the PDF heading classifier to handle the
``body=11pt / header=12pt`` convention (the prior 1.2 size-ratio default
produced an empty ``header_id``), enforces style requirements that bold-only
header sizes were silently ignoring, and classifies lines by aggregated span
style rather than ``spans[0]`` only. Also filters tiny / page-header images
as ghost markers, collapses long whitespace runs that PDF spans use as
layout padding, and merges split numbering-prefix headings ("I." +
"Background" → "I. Background") that the layout model emitted as two
headings.

New options from this change: ``min_image_dimension``,
``filter_header_footer_images``, ``collapse_excess_whitespace``,
``dedup_running_headings``.

What's still slow
-----------------

The optimizations don't fix every slow case — and the remaining hot spots
are worth naming honestly:

* **Scientific-PDF table fragmentation.** PDFs with many real tables (e.g.,
  benchmark comparison tables across LLMs in the ``2605.13841v1`` arxiv
  paper) still take 1-2 minutes. ``find_tables()`` correctly identifies
  ruling lines on those pages, so the gate doesn't help. But PyMuPDF then
  fragments one logical table into many small sub-tables and mangles
  multi-line headers across rows. Future work: an adjacent-table merging
  pass to recombine fragments.
* **Multi-page single paragraphs.** Some PDFs (notably ``000359.pdf``,
  ``000762.pdf``, and ``000887.pdf``) emit single Markdown paragraphs of
  3,000-5,000 characters where text spans multiple pages without clear
  break signals. This is mostly a correctness issue but may also amplify
  downstream rendering cost.
* **Per-page layout model invocations on long arxiv papers.** Even with
  the gate, papers with real tables on most pages pay the
  ``pymupdf-layout`` cost per page. The current model runs the full ONNX
  graph regardless of page complexity; a heuristic to skip layout
  classification on pages with trivially single-column prose would help
  long-paper conversion.
* **TOC dot-leader pseudo-tables.** ``000887.pdf`` still has 1,431 "table"
  rows in its output, most from TOC pages where the dot-leader guard
  isn't firing on PyMuPDF's multi-line cell format. The dot-leader regex
  ``_DOT_LEADER_TAIL`` matches in isolation but evidently isn't being
  applied to ``find_tables()`` cell content. Bug to investigate.

Reproducing these numbers
-------------------------

Two committed reference reports under ``benchmarks/reference/`` capture the
before / after state:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - File
     - State
   * - ``b0e4224-baseline.md/json``
     - 2026-05-06, 21.4 min total. Code includes the heading-detection
       rework but predates the table guards, image alt-text fix, and the
       ``find_tables()`` gate.
   * - ``3516bc9-optimized.md/json``
     - 2026-05-15, 6.7 min total. Code includes the full v1.1.1 perf work.

Both contain per-doc timings in their ``.json`` form for diffing.

Wall-clock numbers depend on hardware and load — the *ratios* between
runs are far more meaningful than absolute seconds. To verify on a clean
runner, dispatch the corpus benchmark GitHub Action:

.. code-block:: bash

   gh workflow run benchmark.yml                  # against current main
   gh workflow run benchmark.yml --ref <sha>      # against a specific commit

The workflow runs on a fresh ``ubuntu-latest`` VM, caches the ~1 GB corpus
between runs, and uploads the full results JSON + Markdown report as a
90-day artifact.

See Also
--------

* :doc:`performance` - General performance tuning guide (caching, parallelism,
  memory limits, batch processing patterns)
* ``benchmarks/corpus/README.md`` in the source tree - the corpus harness
  configuration reference
* ``benchmarks/reference/README.md`` in the source tree - convention for
  committed historical benchmark snapshots
