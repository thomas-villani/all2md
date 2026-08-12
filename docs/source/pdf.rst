PDF Conversion
==============

PDF is the format all2md works hardest at, because a PDF does not describe a
document — it describes ink on a page. There are no headings, no paragraphs, no
tables and no reading order in the file; there are positioned glyphs, and
sometimes vector lines. Everything structural that comes out the other side was
inferred.

This page explains what those inferences are, which knobs change them, and what
they are worth. Numbers quoted here are measured against a pinned corpus of 66
born-digital PubMed Central articles with publisher JATS XML as ground truth
(``benchmarks/pmc``); where a number comes from the scanned-page corpus instead,
it says so.

For the exhaustive option reference see :doc:`options`. For searching the option
space automatically on one of your own documents, see :doc:`optimizations`.

Two paths through a PDF
-----------------------

Every page goes down one of two routes, and they behave very differently:

**The text layer.** Born-digital PDFs — anything produced by a word processor,
LaTeX, or a publisher's typesetting pipeline — carry the characters as data.
all2md reads them with their font, size, weight and bounding box, which is what
makes heading detection, table extraction and column ordering possible at all.

**OCR.** Scanned pages carry only a picture. Text has to be recovered by an OCR
engine, which returns lower-confidence characters and coarser geometry. Some
structure survives (see :ref:`pdf-ocr`), but less of it.

The two are decided per page, not per document, so a report with three scanned
appendix pages takes both routes in one conversion.

.. code-block:: bash

   # Install the PDF extra (PyMuPDF)
   pip install all2md[pdf]

   # Convert, keeping the default inference
   all2md report.pdf --out report.md

Layout analysis
---------------

By default all2md infers structure from geometry alone: font sizes, gaps and
alignment. Installing the optional ``pdf_layout`` extra adds a machine-learning
layout model that labels regions semantically — ``title``, ``section-header``,
``list-item``, ``table``, ``caption``, ``footnote``, ``picture``, ``formula``.

.. code-block:: bash

   pip install all2md[pdf_layout]

.. note::

   ``pdf_layout`` is deliberately **excluded** from the ``all`` extra. Its
   dependency, ``pymupdf-layout``, is distributed under the Polyform
   Noncommercial license, so it cannot be pulled in by a blanket install. You
   have to ask for it. Everything on this page works without it; the table and
   heading numbers are simply better with it.

``--pdf-layout-analysis-mode`` (``auto`` / ``enabled`` / ``disabled``, default
``auto``) controls whether the model is consulted. ``auto`` uses it when it is
installed and silently skips it when it is not.

``--pdf-layout-feature-set`` picks which bundled classifier reads the page:

.. list-table::
   :header-rows: 1
   :widths: 12 30 58

   * - Value
     - Features
     - When it helps
   * - ``imf+rf``
     - image + text geometry
     - The default. Balanced across document kinds.
   * - ``rf``
     - text geometry only
     - Dense multi-column text. ~29% faster for skipping image inference.
   * - ``imf``
     - image only
     - Pages where geometry is uninformative.

The difference is not cosmetic. On a two-column reference page the
image-feature models read the dense left column as a table and deleted nine
reference entries; ``rf`` labelled all 41 entries correctly and predicted no
table at all. Across 20 articles ``rf`` led on every axis measured. **The
default is deliberately unchanged anyway**, because that is one corpus of one
document kind, containing no scanned pages — where image features plausibly
earn their place. If your documents look like journal articles, try ``rf``.

Tables
------

``--pdf-table-detection-mode`` (default ``both``) chooses the strategy:

- ``pymupdf`` — PyMuPDF's own detector
- ``ruling`` — ruled lines on both axes
- ``both`` — try each
- ``none`` — never emit a table

Journal tables are typically *booktabs*-style: horizontal rules only, or none at
all. Line-based strategies find nothing on those, so with layout analysis on, a
region the model predicts to be a table also gets a text-alignment fallback
(``--pdf-table-fallback-extraction-mode``, default ``grid``).

That fallback is held to one test the line strategies are not: **its columns
must not cut through words.** It has no ruling lines corroborating it and the
layout model over-fires, so without that guard a mis-predicted region rendered a
page of ordinary prose as a seven-column table of half-words
(``study was condu | cted to explore``). Every table metric improved while
whole-article text recall fell from 92.6% to 83.8% — a good example of why one
instrument is never enough. Grid shape, reading-order preservation and region
corroboration were each tried as guards and each failed to separate real tables
from gridded prose; whole-word integrity, measured against the page's own word
segmentation, separates them cleanly.

Reading order and columns
-------------------------

Column detection is on by default (``--pdf-no-detect-columns`` turns it off),
with ``--pdf-column-detection-mode`` (``auto`` / ``force_single`` /
``force_multi`` / ``disabled``) when you know better than the heuristic, and
``--pdf-column-gap-threshold`` (default 20 points) setting how wide a gutter has
to be to count.

Where a page's gutter is too narrow to split, blocks are ordered by vertical
position — and two columns that *start level* are a hazard, because whichever
column's top edge is a fraction of a point higher would otherwise decide the
order of the whole page. Blocks whose tops fall within a twentieth of the page's
average line height are now treated as starting on the same row and ordered
left-to-right. The tolerance is size-relative rather than a fixed point count,
since what reads as "level" scales with the type size.

Headings, lists and prose
-------------------------

A few inferences are worth knowing about because they explain output that would
otherwise look arbitrary:

**A heading that wraps onto a second printed line is one heading.** A PDF has no
notion of a wrapped heading — it has two lines of type. A second line continues
the first when they share a level, nothing was emitted between them, and the gap
is within a ratio of the line height. A line opening with its own numbering
starts a new heading however tightly it is set.

**A heading must contain a letter or digit.** Large math delimiters are set in a
symbol font well above body size, so they cleared every size and length gate. One
chemistry paper emitted 179 headings for its 9 sections, 122 of them a single
Private Use Area glyph. The gate is ``str.isalnum``, deliberately not an ASCII
test, so headings in CJK, Cyrillic, Arabic, Devanagari, Greek and Hangul still
qualify — an ASCII test would have deleted every one of them while fixing this.

**List markers are read after glyph normalisation, not before.** The parser
rewrites four bullet glyphs (``U+F0B7``, ``U+00B7``, ``U+2022``, ``U+25CF``) to
``-``, and three of the four are not markers in their printed form, so detection
has to run afterwards. Detection descends into inline wrappers, because a bullet
set in a symbol font arrives wrapped in ``Emphasis`` and a line can have no
top-level text node at all.

**A number is held to a stricter rule than a bullet.** A marker and the space
after it are routinely separate spans, so bullet detection is allowed to read
across that boundary. Numbers are not, and the restriction is load-bearing:
nothing in a PDF distinguishes the 44th bibliography entry from the 44th item of
a list, and reading across turned reference lists into ordered lists renumbered
from 1 — so reference 44 came out as item 1 and no citation in the body could be
matched to its reference.

**Words broken across a line are rejoined.** A capitalised continuation keeps its
hyphen (``Anglo-Saxon``) and a digit continuation is never merged.

The honest limit: items the PDF prints with **no marker of any kind** cannot be
recovered by any marker rule, and they are the bulk of what list detection still
misses.

.. _pdf-ocr:

OCR
---

OCR is off unless you ask for it or ``auto`` mode decides a page needs it.

.. code-block:: bash

   # Tesseract (default engine) — needs the Tesseract binary on your system
   pip install all2md[pdf,ocr]

   # EasyOCR — no system binary, but pulls in PyTorch
   pip install all2md[pdf,ocr-easyocr]

.. code-block:: bash

   all2md scan.pdf --pdf-ocr-enabled --pdf-ocr-mode force --pdf-ocr-languages eng+fra

**When ``auto`` fires.** Three conditions, and the third is the one that changed:

.. list-table::
   :header-rows: 1
   :widths: 34 12 54

   * - Option
     - Default
     - Meaning
   * - ``--pdf-ocr-text-threshold``
     - 50
     - Minimum characters for a page to count as text-bearing.
   * - ``--pdf-ocr-doc-text-threshold``
     - 16
     - Whole-document floor. If no page triggered OCR and the result still has
       fewer meaningful characters than this, the parse is retried once with OCR
       forced.
   * - ``--pdf-ocr-image-area-threshold``
     - 0.8
     - Share of the page its **largest single image** must cover to read the
       page as a scan.

That last threshold is measured on the largest image, not on every image's area
added together, and the boundary is calibrated rather than picked: across 101
scanned pages the largest image covers exactly 100% of every one, while across
851 born-digital pages it never passes 64%. The old behaviour — summed area at
0.5 — fired on 20 pages across 11 of 66 born-digital articles that had perfectly
good publisher text, and because ``--pdf-ocr-preserve-existing-text`` defaults to
``False``, that text was **discarded and re-read from a picture**.

.. warning::

   If you set ``--pdf-ocr-image-area-threshold`` explicitly, note its meaning
   changed along with its default. It is now read against the largest single
   image rather than the summed area of all of them.

Remaining OCR knobs: ``--pdf-ocr-engine``, ``--pdf-ocr-dpi`` (default 300),
``--pdf-ocr-languages``, ``--pdf-ocr-auto-detect-language``, ``--pdf-ocr-gpu``
(EasyOCR only), ``--pdf-ocr-tesseract-config`` for raw Tesseract flags, and
``--pdf-ocr-preserve-existing-text`` to merge rather than replace.

**What OCR gives you structurally.** Tesseract reports block, paragraph and line
numbers with per-word boxes, and all2md keeps that segmentation instead of
flattening the page to a string — so an OCR'd page emits real blocks with real
bounding boxes, and each one reaches the AST with its own
``SourceLocation.metadata['bbox']``. One scanned page went from a single box
covering the whole page to 54 distinct ones, which is what lets a citation into a
scanned document resolve to a region rather than to "somewhere on this page".

Engines that cannot report layout — EasyOCR today — fall back to flat text rather
than losing the page, and reading order for OCR'd blocks comes from the engine
rather than being rebuilt from geometry, because OCR boxes are tight to their
glyphs and defeat the column detector.

Working with pages
------------------

.. code-block:: bash

   # A page range
   all2md report.pdf --pdf-pages "1-5"

   # Custom page separator (a parser option, shared with ODP and PPTX)
   all2md report.pdf --pdf-page-separator-template "--- Page {page_num} ---"

   # Drop running headers and footers (off by default)
   all2md report.pdf --pdf-auto-trim-headers-footers

From Python
-----------

.. code-block:: python

   from all2md import OCROptions, PdfOptions, to_markdown

   options = PdfOptions(
       pages="1-20",
       layout_feature_set="rf",              # text-geometry classifier
       table_detection_mode="both",
       ocr=OCROptions(enabled=True, mode="auto", languages="eng"),
   )

   markdown = to_markdown("report.pdf", parser_options=options)

Knowing how much to trust a conversion
--------------------------------------

Because so much of a PDF conversion is inference, it is worth checking rather
than assuming. ``all2md report`` prints a confidence report naming what was
degraded, guessed, or dropped:

.. code-block:: bash

   all2md report report.pdf

See also :doc:`optimizations` for searching the option space against one of your
own documents rather than reasoning about the knobs by hand.
