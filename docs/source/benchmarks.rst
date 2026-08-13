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

Did the text survive?
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 46 18 36

   * - Measure
     - Value
     -
   * - Raw recall
     - 60.2%
     - of 8,905 ground-truth blocks
   * - Attainable ceiling
     - 62.4%
     - what the PDF's own text layer reproduces
   * - **Recall of what is attainable**
     - **95.3%**
     - the number worth reading
   * - Control: the *wrong* article
     - 0.4%
     - wants to be ~0%

Raw recall is 60.2%, and that figure is close to meaningless on its own. A large share of
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
     - 3,115
     - **97.6%**
   * - Titles
     - 2,291 of 2,426
     - 2,151
     - **92.8%**
   * - Tables
     - 110 of 123
     - 93
     - **83.6%**

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
     - **93.9%**
     - the n-gram appears in the document's text layer
   * - Resequenced
     - 5.2%
     - every word is in the document, in a new adjacency
   * - **Novel**
     - **1.0%**
     - at least one word appears nowhere — the number worth reading
   * - Duplication
     - 0.5%
     - supported text emitted more than once
   * - Control: the *wrong* article
     - 0.7%
     - wants to be ~0%

Over 443,281 emitted n-grams, 4,287 are novel. Reporting the raw unsupported figure instead
would have made the result roughly six times worse than the parser deserves.

Duplication is counted apart from both, because it is invisible to either. Text emitted
twice is an unchanged *set* and a doubled *multiset* — no set-based score can see it at all.

Tables
~~~~~~

Tables are the weakest area and the artifact says so plainly: **92 emitted against 121
expected**, on 69 of 94 pages that should carry one.

The bottleneck is detection rather than extraction. On the pages that miss, the table's text
is usually present in the output as ordinary prose — the content survived, the *structure*
did not. Missed tables skew narrow and sparse compared with matched ones, which is
consistent with a detector that needs enough ruling lines or column evidence to commit.
Some are not recoverable as tables at all: a share of JATS ``<table-wrap>`` elements hold
what is really a list.

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
     - 0.506
     - over 981 pages
   * - ``reading_order_similarity``
     - 0.603
     - over 981 pages
   * - ``block_structure_similarity``
     - 0.118
     - **not gated** — see below

``block_structure_similarity`` is recorded but excluded from the verdict. It compares
sequences of block *categories* without ever inspecting the text underneath, so output with
no correct content at all can score well on it. A measurement that cannot distinguish those
two cases must not be allowed to support one.

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
