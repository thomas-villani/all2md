Agent Skills
============

all2md ships with pre-built **agent skills** — structured instruction files that teach AI coding assistants (Claude Code, Cursor, Windsurf, etc.) how to use all2md effectively. Each skill is a focused, self-contained reference covering a specific workflow.

.. contents::
   :local:
   :depth: 2

Overview
--------

Agent skills are Markdown files (``SKILL.md``) that live in a ``skills/`` directory and get loaded by AI assistants when relevant tasks arise. They contain CLI examples, Python API snippets, and option references — everything an agent needs to use all2md without guessing.

all2md bundles **6 skills** that cover the full range of document workflows:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Skill
     - Purpose
   * - ``all2md-read``
     - Read, extract text from, or parse any document to Markdown
   * - ``all2md-convert``
     - Convert documents between formats (PDF→DOCX, HTML→PDF, etc.)
   * - ``all2md-generate``
     - Create new documents from Markdown (DOCX, PDF, PPTX, EPUB, sites)
   * - ``all2md-grep``
     - Pattern matching inside documents (like grep for PDFs)
   * - ``all2md-search``
     - Ranked/semantic search across document collections
   * - ``all2md-diff``
     - Compare any two documents regardless of format

Installing Skills
-----------------

Use the ``install-skills`` CLI command to copy the bundled skills to your agent's skills directory:

.. code-block:: bash

   # Install to default location
   # (uses ./.agents/skills/ if it exists, otherwise ~/.agents/skills/)
   all2md install-skills

   # Install to local project directory
   all2md install-skills --local

   # Install to global home directory
   all2md install-skills --global

   # Install to a custom directory
   all2md install-skills --target /path/to/skills

   # Overwrite existing skills
   all2md install-skills --force

   # List bundled skills without installing
   all2md install-skills --list

   # Remove previously installed skills
   all2md install-skills --uninstall

After installation, each skill directory contains a ``SKILL.md`` file that agents automatically discover and use.

Skill Details
-------------

all2md-read
~~~~~~~~~~~

The most common agent use case — "read this document and give me the text."

**Triggers:** Reading PDFs, Word docs, PowerPoint, Excel, HTML, emails, images, or any other document format; extracting text or tables; parsing document structure.

Key capabilities covered:

* Basic conversion: ``all2md document.pdf``, ``all2md report.docx -o report.md``
* Stdin: ``cat doc.pdf | all2md -``
* Format-specific options: ``--pdf-pages``, ``--pdf-detect-tables``, ``--pdf-ocr-enabled``, ``--docx-preserve-formatting``, ``--html-extract-title``, ``--eml-include-attachments``
* Section extraction: ``--extract "Chapter 3"``, ``--outline``
* Batch: ``-r``, ``--parallel``, ``--collate``
* Python API: ``to_markdown()``, ``to_ast()``, parser options

all2md-convert
~~~~~~~~~~~~~~

Any-to-any format conversion beyond just reading to Markdown.

**Triggers:** Converting PDF to Word, HTML to DOCX, DOCX to PDF, any-to-any format conversion, changing file formats.

Key capabilities covered:

* Common conversions: ``all2md input.pdf --output-format docx -o output.docx``
* AST transforms during conversion: ``--transform remove-images``
* Format listing: ``all2md list-formats``, ``all2md list-transforms``
* Python API: ``convert()``, ``from_markdown()``, ``to_ast()`` / ``from_ast()``

all2md-generate
~~~~~~~~~~~~~~~

Create documents from scratch using Markdown as input.

**Triggers:** Creating Word documents, generating PDFs, making slides, producing EPUB ebooks, building static sites, ArXiv packaging.

Key capabilities covered:

* Document generation: ``all2md report.md --output-format docx -o report.docx``
* Per-format options: DOCX templates, PDF page size, HTML standalone, EPUB
* Template rendering: ``--output-format jinja --jinja-template template.html``
* Static sites: ``all2md generate-site ./docs --output-dir site``
* ArXiv: ``all2md arxiv paper.md -o submission.tar.gz``
* Python API: ``from_markdown()``, renderer options, ``ArxivPackager``

all2md-grep
~~~~~~~~~~~

The agent equivalent of ``grep`` but for any document format.

**Triggers:** Searching inside PDFs, grepping Word documents, finding text in PowerPoint slides, pattern matching in non-plaintext files.

Key capabilities covered:

* Basic grep: ``all2md grep "pattern" document.pdf``
* Multiple files: ``all2md grep "pattern" *.pdf ./docs/*.docx``
* Flags: ``-i``, ``-n``, ``-c``, ``-v``, ``-B``/``-A``/``-C``
* JSON output: ``--output json``
* Stdin: ``cat doc.pdf | all2md grep "pattern" -``
* Recursive: ``all2md grep "pattern" ./documents -r``

all2md-search
~~~~~~~~~~~~~

Advanced ranked search across document collections.

**Triggers:** Searching across many documents, semantic search, keyword ranking, building search indexes.

Key capabilities covered:

* Search modes: ``--mode keyword``, ``--mode bm25``, ``--semantic``, ``--mode hybrid``
* Result control: ``--top-k 5``, ``--show-snippet``
* Persistent indexes: ``--index-dir ./search-index``
* Output formats: ``--output rich``, ``--output plain``, ``--output json``
* Chunk size: ``--chunk-size 500``

all2md-diff
~~~~~~~~~~~

Compare any two documents, regardless of format.

**Triggers:** Comparing documents, diffing files, version comparison, finding differences.

Key capabilities covered:

* Basic diff: ``all2md diff original.docx modified.docx``
* Cross-format: ``all2md diff document.pdf document.docx``
* Output formats: default unified, ``--format html``, ``--format json``
* Options: ``--ignore-whitespace``, ``--context 5``, ``-C 0``
* Granularity: ``--granularity block``, ``sentence``, ``word``
* Color: ``--color always``, ``--color never``

How Skills Work
---------------

Each skill follows the `SKILL.md specification <https://github.com/anthropics/claude-code/blob/main/docs/skills.md>`_:

* **Frontmatter** — YAML block with ``name``, ``description``, and ``metadata`` fields
* **Description** — Trigger phrases that help the agent decide when to load the skill
* **Body** — CLI examples, Python API patterns, option reference, and tips

When an agent encounters a document-related task, it matches the user's intent against skill descriptions and loads the most relevant skill for context.

Customizing Skills
------------------

After installing, you can edit the ``SKILL.md`` files to add project-specific patterns or remove sections you don't need. For example, if your project only uses PDF and DOCX, you could trim the format-specific sections to reduce noise.

To reset to the defaults, run ``all2md install-skills --force``.

See Also
--------

* :doc:`mcp` — MCP server for AI assistant integration
* :doc:`cli` — Full CLI reference
* :doc:`python_api` — Python API documentation
