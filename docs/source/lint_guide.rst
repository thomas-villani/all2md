Linting & Enforcing a Style Guide
=================================

Converting a document is only half the job. A ``.docx`` that looks tidy in Word
routinely carries straight quotes, ``--`` where an em-dash belongs, double
spaces left over from manual justification, heading levels that skip because
someone styled an *H3* to "look like" an *H2*, and figures with no alt text.
None of that is visible until you publish — and then it is everywhere.

The **all2md linter** turns those latent problems into a checklist you can read,
gate CI on, and in many cases fix automatically. Because it runs on the parsed
AST, the *same* rules apply whether the document started life as DOCX, PDF,
HTML, EPUB, or Markdown.

This guide walks the end-to-end workflow — convert, inspect, fix, and lock in a
house style with a **profile**. For the exhaustive rule reference (all 47 codes
and their severities) and the full CLI flag list, see the "Lint Command" section
of the :doc:`CLI reference <cli>`.

.. contents:: On this page
   :local:
   :depth: 2

The four-step workflow
----------------------

Cleaning up a converted document is always the same loop: **convert → inspect →
preview fixes → apply**, then optionally pin a profile so every future document
gets the same treatment.

.. code-block:: bash

   # 1. Convert the source document to Markdown
   all2md report.docx --out report.md

   # 2. Inspect — what's wrong, and where?
   all2md lint report.md

   # 3. Preview the automatic fixes without touching the file
   all2md lint --fix --dry-run report.md

   # 4. Apply the safe fixes in place
   all2md lint --fix report.md

Step 2 prints a report like this:

.. code-block:: text

   report.md:1:1: STR003 error: Heading level skips from H1 to H3
       suggestion: Use H2 for this heading, or promote the preceding section
   report.md:12:1: TYP003 info: Text uses straight quotes around a word
       suggestion: Replace with curly quotes (“” or ‘’)
   report.md:12:40: TYP004 info: Text contains '--' (should be em-dash)
   report.md:31:1: IMG001 warning: Image is missing alt text
   Found 4 violations (1 error, 1 warning, 2 info) in 1 file

Why this matters for DOCX in particular
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Word is a reliable source of exactly the issues the typography and structure
rules catch. A converted DOCX is the linter's ideal first customer:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Symptom Word leaves behind
     - Rule that catches it
   * - Straight ``"`` / ``'`` quotes
     - ``TYP003`` (``straight-quotes``)
   * - ``--`` instead of an em-dash
     - ``TYP004`` (``double-hyphens``)
   * - ``...`` instead of ``…``
     - ``TYP006`` (``ellipsis-character``) — auto-fixable
   * - Double spaces after periods
     - ``TYP002`` (``multiple-spaces``)
   * - Trailing spaces on lines
     - ``TYP001`` (``trailing-spaces``)
   * - Visually-styled heading levels
     - ``STR003`` (``heading-hierarchy``)
   * - Inconsistent heading capitalization
     - ``HDG004`` (``heading-capitalization``)
   * - Pasted images with no description
     - ``IMG001`` (``missing-alt-text``)

Several of these — ``TYP006``, ``TYP007``, and a handful of others — carry
**safe auto-fixes**, so ``--fix`` resolves them with no manual editing. Run
``all2md lint --fix --dry-run`` first to see exactly which violations will be
rewritten; only fixes classified ``SAFE`` are ever applied.

Profiles: a named house style
-----------------------------

Hand-assembling a long ``--rule`` / ``--disable`` / ``--severity`` invocation
gets old fast, and it does not travel between projects. A **profile** packages a
coherent set of rules and severities behind a single flag:

.. code-block:: bash

   all2md lint --profile prose report.md

List the built-in profiles and what each one is for:

.. code-block:: bash

   all2md lint --list-profiles

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Profile
     - Use it when…
   * - ``prose``
     - Polishing long-form writing (articles, reports, a converted DOCX bound
       for publication). Enforces typographic niceties, consistent heading
       style, and high-quality link text; promotes the curly-quote / em-dash /
       ellipsis rules to *warning*.
   * - ``accessibility``
     - Accessibility is the priority. Enforces image alt text, descriptive link
       text, table headers, and a clean heading hierarchy at *error* severity,
       and deliberately skips purely stylistic typography.
   * - ``technical-docs``
     - Engineering / API documentation. Enforces structure, valid links, and
       resolvable images, but relaxes the prose-typography rules that fight
       code, CLI flags (``--foo``), identifiers, and reference-style writing.

Profiles ship as data, built entirely from the existing rules — they are a
convenience, not a separate engine. The same three are available from Python:

.. code-block:: python

   from all2md.linter import (
       LintConfig,
       available_profiles,
       get_profile_config,
       lint_document,
   )
   from all2md import to_ast

   print(available_profiles())            # ['accessibility', 'prose', 'technical-docs']

   config = LintConfig.from_dict(get_profile_config("prose"))
   result = lint_document(to_ast("report.docx"), config=config)
   print(result.total, "violations")

Tuning a profile
~~~~~~~~~~~~~~~~~

A profile is a *base*, not a straitjacket. Configuration layers on top of it in
a fixed precedence — lowest to highest:

1. ``--profile`` bundle
2. the project's ``[tool.all2md.lint]`` config file
3. explicit CLI flags (``--rule`` / ``--disable`` / ``--severity``)

So you can adopt ``prose`` wholesale but silence one rule you disagree with, and
the flag wins:

.. code-block:: bash

   # Everything prose enforces, minus the curly-quote rule
   all2md lint --profile prose --disable TYP003 report.md

Or bake the same idea into ``pyproject.toml`` so every contributor and CI run
inherits it. The config file refines the profile; ``--disable`` lists are
**unioned**, while ``severity`` and per-rule options are merged with the more
specific layer winning:

.. code-block:: toml

   [tool.all2md.lint]
   # Layered on top of `--profile prose`
   disable = ["TYP003"]          # added to anything the profile already disables

   [tool.all2md.lint.severity]
   IMG001 = "error"              # stricter than the profile's default

Gating CI on a clean document
-----------------------------

``all2md lint`` is built to gate a pipeline. It exits non-zero when violations
remain after the severity filter, so a CI step needs no extra glue:

.. code-block:: bash

   # Fail the build on any warning-or-worse, machine-readable report for logs
   all2md lint --profile accessibility --severity warning \
       --format json --output lint-report.json docs/

Exit codes:

* ``0`` — no violations remain after the severity filter
* ``3`` — one or more violations remain (``EXIT_VALIDATION_ERROR``)
* ``4`` — an input file was not found

``--severity`` filters **both** the printed report and the exit code, so the
mental model is "what you see is what fails CI." Pair a profile with a severity
threshold to express a precise gate: ``--profile accessibility --severity error``
fails only on genuine accessibility blockers, while ``--severity warning`` holds
the line on style too.

See also
--------

* :doc:`CLI reference <cli>` ("Lint Command") — every flag and the full 47-rule
  table with default severities.
* :ref:`lint-configuration` — the ``[tool.all2md.lint]`` schema in depth.
* :doc:`python_api` ("Document Linting") — the runner, rule registry, and how to
  ship your own rules via the ``all2md.lint_rules`` entry point.
