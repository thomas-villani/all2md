Conversion Fidelity
===================

:doc:`performance` answers how *fast* all2md converts a document. This page answers a
harder question: how much of the document survives, and how would you know?

Every figure here comes from an evidence artifact committed to the repository, and every one
is published beside a control — the same measurement applied where it ought to fail. That
pairing is not decoration. On most text metrics the highest-scoring converter is one that
dumps the raw text layer with no structure at all, so a fidelity score with nothing to
falsify it is not evidence of fidelity.

.. contents::
   :local:
   :depth: 2

What is measured, and against what
----------------------------------

Ground truth is the hard part of measuring conversion. all2md uses three independent
sources, each blind to something the others can see:

.. list-table::
   :header-rows: 1
   :widths: 16 24 30 30

   * - Lane
     - Corpus
     - Ground truth
     - What it structurally cannot see
   * - ``pmc``
     - 66 born-digital journal PDFs
     - JATS XML published beside the PDF
     - OCR quality; JATS records some text in an order the page never prints
   * - ``omnidocbench``
     - 981 scanned pages
     - Human annotation
     - The born-digital PDF path, which never runs on a raster
   * - ``roundtrip``
     - Markdown documents
     - The input itself
     - Fidelity *from* the original format — only fidelity through Markdown

The complementarity is structural, not a matter of taste. OmniDocBench is rasters, so it
exercises OCR and never the PDF table detector; PMC is publisher PDFs, so it exercises the
born-digital path and almost never OCR. Neither substitutes for the other.

.. _fidelity-born-digital:

Born-digital PDFs
-----------------

The ``pmc`` lane converts publisher PDFs from the PubMed Central Open Access bucket and
scores the result against the JATS XML the publisher deposited alongside them. The corpus is
pinned by a committed manifest of per-file SHA-256 digests, revalidated on every load.

The figures below are :file:`benchmarks/pmc/reference.json`, recorded on Linux with
dependencies resolved from the lockfile. It covers **66 articles and 706 pages**.

A second manifest, :file:`benchmarks/pmc/manifest-holdout.json`, pins a 110-article
**held-out** corpus drawn from bucket regions the committed manifest never touched.
Development tunes against the 66; the held-out set exists to be scored and never tuned
against, so the figures here can be checked for overfitting. Its first validation run
landed within a point of the development corpus on every text instrument.

Did the text survive?
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 46 18 36

   * - Measure
     - Value
     -
   * - Raw recall
     - 62.1%
     - of 8,905 ground-truth blocks
   * - Attainable ceiling
     - 62.4%
     - what the PDF's own text layer reproduces
   * - **Recall of what is attainable**
     - **98.6%**
     - the number worth reading
   * - Control: the *wrong* article
     - 0.4%
     - wants to be ~0%

Part of the most recent movement in these figures is a *measurement* correction, not a
parser change, and it is flagged as such: the shared oracle was blind to captions the
parser had correctly bound to their figures — the text left the paragraph stream for a
``caption`` attribute the projection never read, so recall *fell* as figure binding
improved. On the held-out corpus, 101 of the 103 caption blocks the instruments called
lost were in the output the whole time. The oracle now reads what the AST carries
(oracle schema 6), and both lanes' artifacts are re-recorded against it.

The movement after that correction is the opposite kind: a parser fix (#405).
Side-by-side regions with tight gutters — two-column reference lists above all — were
read as one column and interleaved line-by-line, so every word survived while every
adjacency died. Admitting those gutters on structural evidence and joining words
hyphenated at block seams raised attainable recall from 95.4% to 98.3% (98.6% after
the table repairs below), and the held-out corpus moved the same way it was never
tuned against.

Raw recall is 62.1%, and that figure is close to meaningless on its own. A large share of
any JATS article cannot be recovered by *any* parser, because the markup records words in an
order the page never prints — author affiliation blocks, structured metadata, citation
fields. Charging a PDF parser for failing to reproduce text the PDF does not contain
measures the ground truth, not the converter.

So the lane measures the ceiling directly: it asks how much of the ground truth the PDF's
**own text layer** reproduces, and reports recovery as a share of that. Both numbers are
published, so the ceiling cannot quietly do the work of the score.

By block kind:

.. list-table::
   :header-rows: 1
   :widths: 22 26 26 26

   * - Kind
     - Attainable
     - Recovered
     - Share of attainable
   * - Text blocks
     - 3,160 of 6,356
     - 3,155
     - **98.9%**
   * - Titles
     - 2,291 of 2,426
     - 2,287
     - **98.9%**
   * - Tables
     - 110 of 123
     - 92
     - **82.7%**

Table blocks are the outlier, and deliberately so — their text now routes through
structured table extraction rather than flowing out as prose. What that buys and what it
costs is the subject of the Tables section below.

Did the output invent anything?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Recall alone rewards emitting everything; precision alone rewards emitting nothing. Both are
published for that reason. But *raw* precision needs a denominator of its own, for the same
reason raw recall needed a ceiling.

Most of what a **correct** conversion emits "unsupported" is the document's own words in an
adjacency the text layer does not have. all2md orders columns and joins wrapped lines; the
text layer comes out in the extraction library's order; every disagreement between the two
mints new n-grams at the seam. That is what column ordering is *for*.

Unsupported output is therefore split in two:

.. list-table::
   :header-rows: 1
   :widths: 30 18 52

   * - Category
     - Share
     - Meaning
   * - Supported
     - **95.0%**
     - the n-gram appears in the document's text layer
   * - Resequenced
     - 4.2%
     - every word is in the document, in a new adjacency
   * - **Novel**
     - **0.9%**
     - at least one word appears nowhere — the number worth reading
   * - Duplication
     - 0.8%
     - supported text emitted more than once
   * - Control: the *wrong* article
     - 0.7%
     - wants to be ~0%

Over 446,252 emitted n-grams, 3,822 are novel. Reporting the raw unsupported figure instead
would have made the result roughly six times worse than the parser deserves.

Duplication is counted apart from both, because it is invisible to either. Text emitted
twice is an unchanged *set* and a doubled *multiset* — no set-based score can see it at all.

Duplication is under a point, and the path it took there is the point. It read 0.5% while
the oracle was blind to captions, jumped to 2.0% when the corrected oracle could finally
see that multi-panel figures re-bound one printed caption to every panel, and fell by two
thirds when that defect was fixed (issue #410). The middle figure was the honest one: the
defect predated the re-record, and what changed first was only that a measurement became
able to report it.

Tables
~~~~~~

The bottleneck has moved. An earlier recording under-emitted — 92 tables against 121
expected, with detection refusing to commit on the borderless *booktabs*-style tables
journals actually print — and after word-gutter grids and two-column regions were admitted
behind measured guards, the artifact reads **164 emitted against 121
expected**, with tables emitted on 120 pages
against the 94 that carry one in the ground truth.

The surplus is mostly an accounting gap rather than invention: a table that continues
across pages is one JATS ``<table-wrap>`` but several printed tables, and the expected
count does not yet credit continuations. The remaining deficit is a handful of table
classes with no shared mechanism.

The cost sat one section up: table blocks are the one kind whose attainable-recall figure
*fell* across those recordings, from 83.6% to 69.1%. The first explanation written here —
that cell extraction "does not yet preserve every word of every cell" — turned out to be
wrong when measured: word-level survival inside committed tables is above 99%. What the
commitment actually costs is *adjacency*. A missed table flows out as prose in reading
order, and n-grams reward that order; a committed table re-cuts the same words at every
cell boundary, and each boundary in the wrong place breaks a run of them. The two
mechanisms that dominated — every printed line emitted as its own row, splitting wrapped
cells mid-sentence, and ``Table.extract()`` clipping characters at cell rects — were
measured, fixed behind guards (#416, #417), and the figure recovered to 77.3%. A third
mechanism followed the same route: ``find_tables()`` drew column boundaries and bbox edges
straight through cell content, cutting values mid-word where neither guard could see it —
dissolving those boundaries on structural evidence and healing the cut values in place
(#419) took the figure to **82.7%**. The trade still stands with eyes open — a table
recovered *as a table* is what downstream consumers need — but it is a trade, and the
artifact says so rather than netting the two effects into one flattering number.

Did it come out in the right order?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Recall counts whether a block's words came out. It says nothing about whether they came out
in the order the page prints them, and a converter can score well on every measure above
while emitting a page as a shuffled bag of correct paragraphs. So the born-digital lane also
runs the *same* dimensions as the scanned lane below, through the same oracle, over its 706
pages:

.. list-table::
   :header-rows: 1
   :widths: 40 14 20 26

   * - Dimension
     - Value
     - Wrong page
     - Gap
   * - ``reading_order_similarity``
     - 0.828
     - 0.292
     - **0.536**
   * - ``text_content_similarity``
     - 0.676
     - 0.234
     - **0.442**
   * - ``table_content_similarity``
     - 0.606
     - 0.039
     - **0.567**
   * - ``table_structure_similarity``
     - 0.613
     - 0.095
     - **0.519**
   * - ``block_structure_similarity``
     - 0.548
     - 0.444
     - 0.104 — **not gated**

The two table dimensions score only the 124 pages that carry a table on either side; the
other three score all 706.

The middle column is each dimension scored against the *wrong* page of the same article, and
the gap is what is left. A measure with no gap is not measuring the output. That is the case
against ``block_structure_similarity``, which is recorded here and excluded from the verdict
in both lanes, for the reasons set out in the scanned-pages section below: on this corpus it
separates own-page from wrong-page output by 0.10, and it *rises* when half the emitted
content is deleted.

These are the numbers the figure-placement work moves. Figures and their captions used to be
flushed at the end of whichever page they appeared on, no matter where on the page they were
printed, so every block after them on the page was reported out of order. Emitting them at
the position they occupy in the column (#429) took reading order from 0.815 to 0.828 and text
content from 0.667 to 0.676, with recall, figure binding and the table counts unchanged — and
left all three scanned-lane dimensions byte-identical across 981 pages, because the guard
that keeps OCR pages in engine order held.

The two lanes' values are not comparable to each other as quality scores: born-digital pages
carry a text layer and scanned pages do not, and the ground truths are differently strict.
What the shared dimensions buy is that a change can be watched in both places at once.

Scanned pages
-------------

The ``omnidocbench`` lane scores 981 scanned pages against human annotation, from
:file:`benchmarks/omnidocbench/baseline.json`:

.. list-table::
   :header-rows: 1
   :widths: 44 20 36

   * - Dimension
     - Value
     -
   * - ``text_content_similarity``
     - 0.504
     - over 981 pages
   * - ``reading_order_similarity``
     - 0.603
     - over 981 pages
   * - ``block_structure_similarity``
     - 0.400
     - **not gated** — see below

``block_structure_similarity`` is recorded but excluded from the verdict. It compares
sequences of block *categories* without ever inspecting the text underneath, so output with
no correct content at all can score well on it. A measurement that cannot distinguish those
two cases must not be allowed to support one.

This baseline carries the resolution of issue #411. An earlier re-recording had exposed
a drift across the v1.12/v1.13 parser arc (text 0.506 → 0.482, order 0.603 → 0.578) —
attributed cleanly, since two record runs on the same runner image and corpus pin, with
and without the corrected oracle, produced **byte-identical per-page scores on all 981
pages**. Bisecting the arc with further record runs put the entire movement on the OCR
block-segmentation work, whose column re-sort scrambled blocks the engine had already
emitted in reading order; removing that re-sort recovered 94% of the text movement and
98% of the order movement while keeping the segmentation's block-structure gain whole.
The payload also reports every dimension
per corpus stratum: the whole-corpus mean averages handwritten notes scoring near zero
with academic papers scoring far above it, and the strata are what make the number
actionable.

Round-trip fidelity
-------------------

The ``roundtrip`` lane converts a Markdown document to another format and back, and compares
the result with the input. It is the one lane that gates every pull request: all six
top-level ``*.md`` files tracked in the repository must round-trip at a fidelity of **100**,
with no headroom whatsoever.

That gate is narrower than it sounds — it measures fidelity *through* Markdown, not from a
PDF or a DOCX — but it is cheap, it is exact, and it has caught real defects: HTML escaping
that fought with footnotes, tables breaking out of list items, and multi-paragraph footnotes
collapsing into one.

Reading these numbers honestly
------------------------------

Some limits bound what everything above can support. They are worth stating plainly rather
than leaving for a reader to discover.

**Every corpus here is English.** A change that deleted all CJK, Cyrillic, Arabic and Indic
text would score perfectly on all three lanes. For anything touching character handling,
these benchmarks are not evidence — write targeted cross-script tests instead.

**The corpora are pinned by digest, not by availability.** Publishers withdraw superseded
versions. One PMC article was fetched successfully one morning and had vanished by that
evening. A run that loses an article records it as ``corpus.articles_unavailable`` and stops
reporting itself as a complete corpus, rather than failing outright or quietly scoring a
smaller corpus under the same pin.

**Most lanes are deliberately ungated.** They exist to surface defects right now, and
recording a pass/fail baseline would ratchet the current floor in as accepted — the table
scores above are exactly the sort of number that should not be blessed. Round-trip fidelity
is the exception, and OmniDocBench ratchets against a recorded baseline monthly.

**A single lane's score is not a quality claim.** Each was built to answer one question, and
each is blind to what the others were built for.

Reproducing them
----------------

The born-digital lane, from the committed manifest — no bucket listing, no live query:

.. code-block:: bash

   python -m benchmarks.pmc show               # summarize the pinned manifest, offline
   python -m benchmarks.pmc load               # download and digest-verify the corpus
   python -m benchmarks.pmc score --out out.json

``--limit N`` scores an evenly spaced subset rather than the first *N*, since manifest order
is lexicographic by PMCID and a prefix would draw one era of the archive.

The other lanes:

.. code-block:: bash

   python -m benchmarks.roundtrip              # Markdown fidelity, the CI gate
   python -m benchmarks.omnidocbench           # 981 scanned pages
