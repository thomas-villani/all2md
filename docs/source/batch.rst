Batch Conversion
================

all2md has first-class support for converting many documents in a single command:
glob and directory inputs, parallel workers, output-tree control, and per-file
attachment handling. This page is the detailed reference for the batch workflow from
the command line. For a quick taste, see the batch section of the :doc:`quickstart`.

.. contents::
   :local:
   :depth: 2

When to Use Built-in Batch
--------------------------

Reach for the built-in batch features (rather than a hand-written Python loop) when you
want parallelism, structure-preserving output, progress reporting, and consistent
attachment handling without writing glue code:

.. code-block:: bash

   all2md '**/*.pdf' --output-dir converted/ --preserve-structure --attachment-mode save -p 3

If you need programmatic control over each file, the Python API loop shown in the
:doc:`quickstart` remains available; everything below is about the CLI.

Selecting Input Files
---------------------

Inputs can be one or more paths, glob patterns, or directories:

.. code-block:: bash

   # Explicit glob (quote it so your shell doesn't expand it first)
   all2md '**/*.pdf' --output-dir converted/

   # A directory, processed recursively
   all2md ./documents --recursive --output-dir converted/

   # Multiple inputs mixed together
   all2md report.pdf ./more-docs '*.docx' --output-dir converted/

Filtering and exclusion:

.. code-block:: bash

   # Skip patterns (repeatable)
   all2md ./project --recursive --exclude '*.tmp' --exclude '__pycache__' --output-dir converted/

   # Include dot-files / dot-folders (skipped by default)
   all2md ./project --recursive --include-hidden --output-dir converted/

   # Drive the list from a file (one path per line; '#' comments; '-' reads stdin)
   all2md --batch-from-list files.txt --output-dir converted/

.. tip::
   Quote glob patterns (``'**/*.pdf'``) so all2md performs the expansion consistently
   across shells, including recursive ``**`` matching.

Output Location and Structure
-----------------------------

``--output-dir`` writes one Markdown file per input. By default all outputs are placed
flat in that directory. ``--preserve-structure`` mirrors the input tree relative to the
common parent of the inputs:

.. code-block:: text

   # Inputs                          # all2md '**/*.pdf' --output-dir converted/ --preserve-structure
   docs/                             converted/
     guide/intro.pdf                   guide/intro.md
     guide/setup.pdf                   guide/setup.md
     ref/api.pdf                       ref/api.md

Control the output extension and target format with ``--output-format`` and
``--output-extension`` (the latter is mostly useful for non-Markdown targets or
custom suffixes).

Attachments in Batch Mode
-------------------------

With ``--attachment-mode save``, images and embedded files are written to disk instead
of being inlined. Two layouts are available:

**Default (no structure preservation).** Attachments for every document are written to a
single ``attachments/`` folder relative to the current directory:

.. code-block:: bash

   all2md '*.pdf' --output-dir converted/ --attachment-mode save

**Near-source layout (with --preserve-structure).** When you preserve structure and do
**not** set ``--attachment-output-dir`` explicitly, all2md co-locates attachments with
their output files: each output directory gets a shared ``.attachments`` folder, and the
Markdown links to it with a relative path so the documents are portable:

.. code-block:: bash

   all2md '**/*.pdf' --output-dir converted/ --preserve-structure --attachment-mode save

.. code-block:: text

   converted/
     sub/
       report.md          # links read ![](.attachments/report_img1.png)
       memo.md
       .attachments/
         report_img1.png
         memo_img1.png

This near-source behavior triggers only when **all** of these hold: ``--preserve-structure``
is set, the attachment mode is ``save``, an ``--output-dir`` is given, and neither
``--attachment-output-dir`` nor ``--attachment-base-url`` was passed explicitly.

**Explicit override.** Passing ``--attachment-output-dir`` always wins and disables the
near-source layout — every attachment goes to the directory you name:

.. code-block:: bash

   all2md '**/*.pdf' --output-dir converted/ --preserve-structure \
       --attachment-mode save --attachment-output-dir ./assets

See :doc:`attachments` for the full attachment model, filename templates, deduplication,
and the other ``save``-mode options.

Parallelism and Error Handling
------------------------------

``--parallel`` / ``-p`` converts files concurrently across worker processes:

.. code-block:: bash

   all2md '**/*.pdf' --output-dir converted/ -p 3   # 3 workers
   all2md '**/*.pdf' --output-dir converted/ -p     # auto-detect worker count

By default the batch stops on the first failure. ``--skip-errors`` keeps going and
reports the failures in the summary at the end:

.. code-block:: bash

   all2md ./documents --recursive --output-dir converted/ --skip-errors

Combining Into a Single Document
--------------------------------

Batch conversion writes one output per input. To merge inputs into a single document
instead, use ``--collate`` (concatenate) or ``--merge-from-list`` (ordered merge with
optional section titles and a generated table of contents):

.. code-block:: bash

   all2md chapter_*.pdf --collate --out book.md

These are documented in :doc:`cli`; they are a distinct workflow from per-file batch
conversion.

Interactive Walkthrough: ``all2md batch``
-----------------------------------------

If you would rather be guided through the options, run the interactive batch wizard:

.. code-block:: bash

   all2md batch

It walks you through five steps — choosing and previewing the input files, the output
location and structure, attachment handling, a few file-type-specific options for the
formats it detects, and advanced parameters such as worker count. At the end it prints
the equivalent ``all2md ...`` command (so you can save or reuse it) and offers to run it.

.. note::
   The wizard uses the optional Rich UI. If it is not installed, run
   ``pip install 'all2md[cli_extras]'`` (or ``uv pip install 'all2md[cli_extras]'``) for
   the best experience; a plain-text fallback is used otherwise.

See Also
--------

* :doc:`cli` — full command-line reference, including collation and merge.
* :doc:`options` — every parser/renderer option and its CLI flag.
* :doc:`attachments` — attachment modes, filename templates, and ``save``-mode details.
* ``all2md help batch`` — the batch options at a glance from the terminal.
