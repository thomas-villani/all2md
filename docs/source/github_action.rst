GitHub Action: Conversion-Quality Gate
=======================================

Fail the build when your documents stop converting cleanly.

Most document tooling in CI answers *"did it run?"*. This action answers *"is the
output still as good as it was?"* — it scores every matched document and fails the
job when the worst score falls below a threshold you set.

It can score two things:

* **Round-trip fidelity**, for any format all2md reads (Markdown, reStructuredText,
  Word, HTML, PDF, and the rest): the document is converted to Markdown and parsed
  back, and the score (0–100) is how much of its structure survived the trip. Use it
  to keep a docs folder converting cleanly as the documents, or all2md, change.
* **Conversion confidence**, for PDFs only today: how sure all2md is that it read
  the document at all (scanned pages, OCR fallbacks, guessed structure). Other
  formats have no confidence detector, and the gate will not pretend otherwise.

.. code-block:: yaml

   - uses: thomas-villani/all2md@v1.16.0
     with:
       paths: docs/**/*.md
       roundtrip-fail-under: 97

The action lives in the ``all2md`` repository itself rather than a separate one,
so ``@v1.16.0`` installs all2md 1.16.0. That matters more than it looks: the
gate's verdict *is* the library's score, so if the action version could drift from
the library version, your thresholds would quietly change meaning underneath you.

Quick Start
-----------

.. code-block:: yaml

   name: Document quality

   on: [push, pull_request]

   jobs:
     quality:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v7
         - uses: thomas-villani/all2md@v1.16.0
           with:
             paths: |
               docs/**/*.md
               README.md
             roundtrip-fail-under: 97

To gate PDFs, add the confidence check. It is the one that notices a PDF that was
never really read, such as a scan with no text layer:

.. code-block:: yaml

         - uses: thomas-villani/all2md@v1.16.0
           with:
             paths: reports/**/*.pdf
             roundtrip-fail-under: 90
             report-fail-under: 80

If ``paths`` matches no PDFs at all, setting ``report-fail-under`` fails the run with
exit code ``2``: every document would carry a placeholder score, so the threshold
could only ever pass. In a mixed set, only the PDFs are held to it.

The job summary gets a per-document table, and the worst scores are exposed as
step outputs so later steps can use them:

.. code-block:: yaml

         - uses: thomas-villani/all2md@v1.16.0
           id: gate
           with:
             paths: docs/**/*.md
             roundtrip-fail-under: 97
         - run: echo "worst was ${{ steps.gate.outputs.worst-fidelity }}"

Inputs
------

.. list-table::
   :header-rows: 1
   :widths: 24 12 64

   * - Input
     - Default
     - Description
   * - ``paths``
     - *required*
     - Glob(s) selecting documents, separated by newlines or commas. Expanded in
       Python rather than by the shell, so the result does not depend on the
       runner's shell settings.
   * - ``roundtrip-fail-under``
     - —
     - Fail if any document's round-trip fidelity drops below this (0–100).
   * - ``report-fail-under``
     - —
     - Fail if any document's conversion confidence drops below this (0–100).
       PDF only; see above.
   * - ``via``
     - ``markdown``
     - Intermediate format for the round-trip check.
   * - ``all2md-version``
     - —
     - Empty matches the action's tag. ``latest`` always takes the newest
       release; anything else is an exact pin.
   * - ``extras``
     - ``all``
     - Extras to install. The default covers every bundled format.
   * - ``python-version``
     - ``3.12``
     - Python used to run the gate.
   * - ``working-directory``
     - ``.``
     - Directory the globs resolve against.

At least one of ``roundtrip-fail-under`` or ``report-fail-under`` must be set. With
neither, the action refuses to run rather than pass — see below.

Outputs
-------

``worst-fidelity``, ``worst-confidence``, and ``files-checked``.

.. _calibrating-thresholds:

Calibrating the threshold
-------------------------

**Measure first. Do not guess a round number.**

This is the one part worth reading twice, because getting it wrong produces a gate
that passes forever and looks like evidence of quality.

Documents that convert well score high — in this repository's own fixtures,
99–100 is typical. So a threshold of ``80``, which sounds appropriately strict,
has *twenty points of dead headroom*: your conversion could degrade badly and the
build would stay green the whole way down.

Get your real floor first:

.. code-block:: bash

   all2md roundtrip docs/**/*.md --fail-under 1

Then set the threshold at that floor. The action helps: whenever it finds ten or
more points of headroom between your threshold and your worst actual score, it
prints a note on the job summary telling you what to raise it to.

Treat the number as a ratchet. When a document legitimately gets harder to
convert, re-record the floor deliberately — don't nudge the threshold down to
clear a red build.

.. note::

   **Measure in the environment you gate in.** Scores are deterministic for a
   given interpreter and dependency set, but not guaranteed across them: parsing
   depends on the installed parser version, so a document can score differently
   on a developer machine than on CI from identical bytes. Calibrate from a CI
   run rather than a local one, and leave a point of slack if you gate documents
   that sit right on a boundary.

What this catches, and what it doesn't
--------------------------------------

The two checks fail in different directions, which is why the action offers both:

* ``roundtrip-fail-under`` measures what survives a parse → render → parse cycle.
  It is sharp about structure, but it is blind to a construct that is dropped
  *consistently*: if a feature vanishes on the way out and stays vanished on the
  way back in, both sides agree and the score stays high.
* ``report-fail-under`` measures confidence in the parse itself — scanned pages,
  OCR fallbacks, structural guesses. It catches "this document was never really
  read" cases that round-tripping cannot see, at the cost of being a heuristic.
  Only PDFs have a confidence detector today.

For PDFs that matter, gate on both. Neither is a substitute for the other.

Three ways it refuses to pass
------------------------------

A gate that goes green without measuring is worse than no gate, so the action
fails loudly rather than quietly succeeding when:

#. **No files match** ``paths``. A typo would otherwise produce a permanently
   green check that never opens a document.
#. **No threshold is set.** Running with nothing to compare against is theatre.
#. **A document cannot be converted at all.** That is the worst possible fidelity
   outcome, so it is never quieter than a merely low score.

A configuration problem exits ``2``; a genuine quality failure exits ``1``.

Without the action
------------------

The action is a thin wrapper — the same gate works in any CI system, or locally:

.. code-block:: bash

   all2md roundtrip docs/*.md --fail-under 97
   all2md report inbox/*.pdf --fail-under 80

The difference is that the action scores each document in its own process, so it
reports *every* failing file rather than stopping at the first one, and it writes
the summary table and step outputs.

See also
--------

* :doc:`cli` — ``report`` and ``roundtrip`` in full.
* :doc:`performance` — the speed side of the same idea.
