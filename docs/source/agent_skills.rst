Agent Skills
============

all2md ships with a pre-built **agent skill** — a structured instruction file that teaches AI coding assistants (Claude Code, Cursor, Windsurf, etc.) how to use all2md effectively. It follows Anthropic's progressive-disclosure pattern: a lean ``SKILL.md`` overview routes to focused, on-demand reference guides for each document workflow.

.. contents::
   :local:
   :depth: 2

Overview
--------

An agent skill is a directory containing a ``SKILL.md`` file with YAML frontmatter (``name`` + ``description``). Agents load the description at startup, read the full ``SKILL.md`` when a task matches, and pull in the bundled reference files only as needed. This keeps the always-loaded footprint small while making deep, per-task detail available on demand.

all2md bundles a single ``all2md`` skill whose per-task guides live in a ``references/`` directory:

.. code-block:: text

   all2md/
   ├── SKILL.md                # overview + index (routes to the references below)
   └── references/
       ├── read.md             # read / extract text & tables from any document
       ├── convert.md          # convert between formats (PDF→DOCX, HTML→PDF, …)
       ├── generate.md         # create documents from Markdown (DOCX, PDF, PPTX, EPUB, sites)
       ├── grep.md             # pattern matching inside documents (grep for PDFs)
       ├── search.md           # ranked / semantic search across collections
       └── diff.md             # compare any two documents regardless of format

Installing Skills
-----------------

Use the ``install-skills`` CLI command to copy the bundled skill (and its references) to your agent's skills directory:

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

After installation, the ``all2md/`` skill directory contains ``SKILL.md`` plus the ``references/`` guides that agents discover and load on demand.

Reading the guide without installing
-------------------------------------

The same content is available straight from the CLI — handy when an agent is driving all2md from a terminal and hasn't installed the skill:

.. code-block:: bash

   # Print the overview plus every reference, concatenated
   all2md llm-help

   # Print a single topic
   all2md llm-help read        # or convert, generate, grep, search, diff, overview

   # List available topics
   all2md llm-help --list

Reference Topics
----------------

read
~~~~

The most common agent use case — "read this document and give me the text."

**Triggers:** Reading PDFs, Word docs, PowerPoint, Excel, HTML, emails, images, or any other document format; extracting text or tables; parsing document structure.

Key capabilities covered:

* Basic conversion: ``all2md document.pdf``, ``all2md report.docx -o report.md``
* Stdin: ``cat doc.pdf | all2md -``
* Format-specific options: ``--pdf-pages``, ``--pdf-table-detection-mode``, ``--pdf-ocr-enabled``, ``--docx-include-comments``, ``--html-extract-title``, ``--eml-attachment-mode``
* Section extraction: ``--extract "Chapter 3"``, ``--outline``; line-range navigation: ``--outline --line-numbers`` then ``--extract line:42-87``
* Batch: ``-r``, ``--parallel``, ``--collate``
* Python API: ``to_markdown()``, ``to_ast()``, parser options

convert
~~~~~~~

Any-to-any format conversion beyond just reading to Markdown.

**Triggers:** Converting PDF to Word, HTML to DOCX, DOCX to PDF, any-to-any format conversion, changing file formats.

Key capabilities covered:

* Common conversions: ``all2md input.pdf --output-format docx -o output.docx``
* AST transforms during conversion: ``--transform remove-images``
* Format listing: ``all2md list-formats``, ``all2md list-transforms``
* Python API: ``convert()``, ``from_markdown()``, ``to_ast()`` / ``from_ast()``, ``apply()``

generate
~~~~~~~~

Create documents from scratch using Markdown as input.

**Triggers:** Creating Word documents, generating PDFs, making slides, producing EPUB ebooks, building static sites, ArXiv packaging.

Key capabilities covered:

* Document generation: ``all2md report.md --output-format docx -o report.docx``
* Per-format options: DOCX templates (``--docx-renderer-template-path``), PDF page size (``--pdf-renderer-page-size``), HTML standalone (default; ``--html-renderer-no-standalone`` for a fragment), EPUB
* Template rendering: ``--output-format jinja --jinja-renderer-template-file template.html``
* Static sites: ``all2md generate-site ./docs --output-dir site --generator hugo``
* ArXiv: ``all2md arxiv paper.md -o submission.tar.gz``
* Python API: ``from_markdown()``, renderer options, ``ArxivPackager``

grep
~~~~

The agent equivalent of ``grep`` but for any document format.

**Triggers:** Searching inside PDFs, grepping Word documents, finding text in PowerPoint slides, pattern matching in non-plaintext files.

Key capabilities covered:

* Basic grep: ``all2md grep "pattern" document.pdf``
* Multiple files: ``all2md grep "pattern" *.pdf ./docs/*.docx``
* Flags: ``-i``, ``-n``, ``-e``/``--regex``, ``-B``/``-A``/``-C``, ``-M``
* Rich output: ``--rich``
* Stdin: ``cat doc.pdf | all2md grep "pattern" -``
* Recursive: ``all2md grep "pattern" ./documents -r``

search
~~~~~~

Advanced ranked search across document collections.

**Triggers:** Searching across many documents, semantic search, keyword ranking, building search indexes.

Key capabilities covered:

* Search modes: ``--keyword`` (BM25), ``--vector`` (semantic), ``--hybrid`` (or ``--mode keyword|vector|hybrid|grep``)
* Result control: ``--top-k 5``; grep-mode context with ``--mode grep -C 2``
* Persistent indexes: ``--index-dir ./search-index --persist``
* Output formats: default plain, ``--rich``, ``--json``
* Chunk size: ``--chunk-size 500``

diff
~~~~

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

The bundled skill follows the `Agent Skills specification <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>`_:

* **Frontmatter** — a YAML block with ``name`` and ``description`` (plus optional ``metadata``)
* **Description** — states *what* the skill does and *when* to use it, so the agent can decide when to load it
* **Body** — a lean overview that links to the per-task references under ``references/``
* **References** — focused guides loaded on demand (progressive disclosure)

When an agent encounters a document-related task, it matches the user's intent against the skill description, loads ``SKILL.md``, and then reads only the reference file relevant to the task.

Customizing Skills
------------------

After installing, you can edit ``SKILL.md`` or any file under ``references/`` to add project-specific patterns or trim sections you don't need. For example, if your project only uses PDF and DOCX, you could shorten ``references/read.md`` to reduce noise.

To reset to the defaults, run ``all2md install-skills --force``.

See Also
--------

* :doc:`mcp` — MCP server for AI assistant integration
* :doc:`cli` — Full CLI reference
* :doc:`python_api` — Python API documentation
