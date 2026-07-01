Quick Start Guide
=================

Get up and running with all2md in just 5 minutes! This guide will walk you through installation, basic usage, and common scenarios.

Installation
------------

Start with the basic installation:

.. code-block:: bash

   pip install all2md

This includes support for HTML, CSV/TSV, text files, and images. For other formats, install the specific dependencies you need:

.. code-block:: bash

   # For PDF support
   pip install all2md[pdf]

   # For Word documents
   pip install all2md[docx]

   # For all formats
   pip install all2md[all]

See the :doc:`installation` guide for complete details.

Your First Conversion
---------------------

Let's convert a document to Markdown:

**Command Line**

.. code-block:: bash

   # Convert a PDF to Markdown (output to console)
   all2md document.pdf

   # Save the output to a file
   all2md document.pdf --out document.md

**Python API**

.. code-block:: python

   from all2md import to_markdown

   # Convert to Markdown string
   markdown = to_markdown('document.pdf')
   print(markdown)

   # Save to file
   with open('document.md', 'w', encoding='utf-8') as f:
       f.write(markdown)

That's it! all2md automatically detects the file format and converts it to clean Markdown.

Bidirectional Conversion
------------------------

all2md isn't just for converting *to* Markdown—it supports full bidirectional conversion between formats. The ``convert()`` function is the core API for any format-to-format conversion.

.. note::

   ``to_markdown()`` and ``convert()`` are peer entry points that share the same parse → AST → render pipeline. ``to_markdown(src)`` is the ergonomic shortcut for Markdown output — equivalent to ``convert(src, target_format="markdown")`` for file/bytes/stream inputs. Use ``convert()`` when you need to convert to other formats or between non-Markdown formats directly.

Converting Markdown to Rich Formats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generate Word documents, PDFs, and more from your Markdown files:

**Command Line**

.. code-block:: bash

   # Convert Markdown to Word document
   all2md report.md --out report.docx

   # Convert Markdown to PDF
   all2md notes.md --out notes.pdf

   # Convert Markdown to HTML
   all2md readme.md --out readme.html

   # Convert Markdown to PowerPoint
   all2md slides.md --out presentation.pptx

**Python API**

.. code-block:: python

   from all2md import convert

   # Convert Markdown to DOCX
   convert("report.md", "report.docx", target_format="docx")

   # Convert Markdown to PDF
   convert("notes.md", "notes.pdf", target_format="pdf")

   # Convert Markdown to HTML
   convert("readme.md", "readme.html", target_format="html")

This is particularly useful for AI/LLM workflows: ingest documents as Markdown for processing, then convert the LLM's Markdown output back to rich formats.

Converting Between Any Formats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also convert directly between non-Markdown formats:

**Command Line**

.. code-block:: bash

   # Convert PDF to Word document
   all2md document.pdf --out document.docx

   # Convert PDF to HTML
   all2md report.pdf --out report.html

   # Convert HTML to PDF
   all2md webpage.html --out webpage.pdf

   # Convert Word to HTML
   all2md manual.docx --out manual.html

**Python API**

.. code-block:: python

   from all2md import convert

   # PDF to DOCX
   convert("document.pdf", "document.docx", target_format="docx")

   # PDF to HTML
   convert("report.pdf", "report.html", target_format="html")

   # HTML to PDF
   convert("webpage.html", "webpage.pdf", target_format="pdf")

   # DOCX to HTML
   convert("manual.docx", "manual.html", target_format="html")

Under the hood, all2md parses the source document into an Abstract Syntax Tree (AST), then renders it to the target format. This ensures consistent, high-quality conversions regardless of the source and target formats.

.. note::

   **Output Normalization:** The ``to_markdown()`` function always returns a string with normalized line endings. Specifically:

   * All line endings (``\r\n``, ``\r``) are converted to Unix-style (``\n``)
   * This ensures consistent output across Windows, macOS, and Linux
   * Makes string comparison and processing predictable
   * If you need Windows-style line endings, convert after receiving the result:

   .. code-block:: python

      markdown = to_markdown('document.pdf')
      # Output uses \n line endings

      # Convert to Windows line endings if needed
      windows_markdown = markdown.replace('\n', '\r\n')

      # Or use Python's text mode when writing files
      with open('output.md', 'w', newline='') as f:
          f.write(markdown)  # Preserves \n

      with open('output.md', 'w') as f:
          f.write(markdown)  # Python handles newline conversion

Common Use Cases
----------------

1. Converting PDFs with Images
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, PdfOptions

   # Download images to a local directory
   options = PdfOptions(
       attachment_mode='save',
       attachment_output_dir='./pdf_images'
   )

   markdown = to_markdown('report.pdf', parser_options=options)

.. code-block:: bash

   # Command line equivalent
   all2md report.pdf --attachment-mode save --attachment-output-dir ./pdf_images

2. Processing Word Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, DocxOptions

   # Preserve all formatting and save images
   options = DocxOptions(
       attachment_mode='save',
       attachment_output_dir='./doc_images'
   )

   markdown = to_markdown('document.docx', parser_options=options)

3. Custom Markdown Formatting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, PdfOptions, MarkdownRendererOptions

   # Use underscores for emphasis and custom bullets
   md_options = MarkdownRendererOptions(
       emphasis_symbol='_',
       bullet_symbols='•◦▪',
       use_hash_headings=True
   )

   pdf_options = PdfOptions(
       attachment_mode='save',
       attachment_output_dir='./pdf_images'
   )
   markdown = to_markdown(
       'document.pdf',
       parser_options=pdf_options,
       renderer_options=md_options,
   )

.. code-block:: bash

   # Command line equivalent
   all2md document.pdf --markdown-emphasis-symbol "_" --markdown-bullet-symbols "•◦▪"

4. Processing ZIP Archives
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extract and convert multiple files from ZIP archives:

.. code-block:: python

   from all2md import to_markdown, ZipOptions

   # Convert all parseable files in the archive
   markdown = to_markdown('project_docs.zip')

   # Filter specific file types and skip system files
   options = ZipOptions(
       include_patterns=['*.md', '*.txt', '*.py'],
       exclude_patterns=['__MACOSX/*', '.DS_Store'],
       create_section_headings=True
   )

   markdown = to_markdown('archive.zip', parser_options=options)

.. code-block:: bash

   # Command line with filtering
   all2md archive.zip --zip-include "*.md" --zip-exclude "__MACOSX/*"

   # Flatten directory structure (disable directory preservation)
   all2md archive.zip --zip-no-preserve-directory --out combined.md

5. Progress Monitoring
~~~~~~~~~~~~~~~~~~~~~~

For long-running conversions, use progress callbacks to track the conversion in real-time:

.. code-block:: python

   from all2md import to_markdown, ProgressEvent

   def show_progress(event: ProgressEvent):
       if event.event_type == "item_done" and event.metadata.get("item_type") == "page":
           print(f"Processed page {event.current}/{event.total}")
       elif event.event_type == "detected" and event.metadata.get("detected_type") == "table":
           count = event.metadata.get('table_count', 0)
           print(f"  Found {count} table(s)")

   markdown = to_markdown('large_document.pdf', progress_callback=show_progress)

This is particularly useful for:

* GUI applications with progress bars
* Long-running batch operations
* Monitoring table detection in PDFs
* Web applications with real-time updates

See :doc:`overview` for detailed progress callback documentation and :doc:`recipes` for GUI integration examples.

6. Batch Processing
~~~~~~~~~~~~~~~~~~~

all2md provides powerful built-in batch processing features for converting multiple files efficiently.

**Command Line (Recommended):**

.. code-block:: bash

   # Convert all PDFs in a directory
   all2md *.pdf --output-dir ./markdown

   # Recursively process all files in a directory tree
   all2md ./documents --recursive --output-dir ./converted

   # Parallel processing with automatic CPU detection
   all2md *.pdf --parallel --output-dir ./markdown

   # Preserve directory structure in output
   all2md ./docs --recursive --preserve-structure --output-dir ./markdown

   # Combine multiple files into a single output
   all2md chapter_*.pdf --collate --out book.md

   # Exclude specific patterns
   all2md ./project --recursive --exclude "*.tmp" --exclude "__pycache__" --output-dir ./markdown

**Python API (Manual Approach):**

For programmatic control, you can process files manually:

.. code-block:: python

   from pathlib import Path
   from all2md import to_markdown

   # Process all documents in a directory
   input_dir = Path('./documents')
   output_dir = Path('./markdown')
   output_dir.mkdir(exist_ok=True)

   for file_path in input_dir.glob('*'):
       if file_path.is_file():
           try:
               markdown = to_markdown(str(file_path))
               output_file = output_dir / f"{file_path.stem}.md"

               with open(output_file, 'w', encoding='utf-8') as f:
                   f.write(markdown)

               print(f"✓ Converted {file_path.name}")
           except Exception as e:
               print(f"✗ Failed: {file_path.name}: {e}")

7. Linting Converted Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run 47 built-in rules against any document all2md can parse. The linter
operates on the AST, so PDF, DOCX, HTML, and Markdown inputs all share the
same ruleset. A subset of rules carry safe auto-fixes that ``--fix`` applies
in place.

.. code-block:: bash

   # Lint a single document (default: report everything, fail on any violation)
   all2md lint handbook.md

   # Lint a tree and emit machine-readable JSON for CI
   all2md lint docs/ --recursive --format json --output lint-report.json

   # Loosen the gate: only warnings and errors count toward CI exit status
   all2md lint docs/ --severity warning

   # Apply safe auto-fixes in place (or preview with --dry-run)
   all2md lint --fix handbook.md
   all2md lint --fix --dry-run handbook.md

Or from Python:

.. code-block:: python

   from all2md import to_ast
   from all2md.linter import lint_and_fix_document, lint_document

   doc = to_ast('handbook.md')
   result = lint_document(doc)
   print(f"{result.error_count} errors, {result.warning_count} warnings")

   # Apply auto-fixes (mutates doc in place)
   fix_result = lint_and_fix_document(doc)
   print(f"Applied {len(fix_result.applied)} fixes; "
         f"{fix_result.final.total} violations remaining")

See :doc:`cli` for the full rule catalogue, ``--fix`` documentation, output
formats, and severity handling, and :doc:`configuration` for the
``[tool.all2md.lint]`` schema.

8. Working with File Objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown

   # Convert from file object
   with open('document.pdf', 'rb') as f:
       markdown = to_markdown(f)

   # Convert from bytes
   with open('document.pdf', 'rb') as f:
       data = f.read()

   markdown = to_markdown(data)

   # Explicit format specification
   with open('document.pdf', 'rb') as f:
       markdown = to_markdown(f, source_format='pdf')

Handling Different Formats
---------------------------

all2md automatically detects file formats, but you can also be explicit:

.. code-block:: python

   from all2md import to_markdown

   # Automatic detection (recommended)
   markdown = to_markdown('document.pdf')

   # Explicit format (useful for edge cases)
   markdown = to_markdown('document.pdf', source_format='pdf')

   # Force text processing for unknown files
   markdown = to_markdown('unknown_file', source_format='txt')

Email Processing Example
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, EmlOptions

   options = EmlOptions(
       attachment_mode='save',
       attachment_output_dir='./email_attachments',
       detect_reply_separators=True,  # Clean up email chains
       clean_wrapped_urls=True        # Fix broken URLs
   )

   markdown = to_markdown('message.eml', parser_options=options)

Jupyter Notebook Example
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, IpynbOptions

   options = IpynbOptions(
       truncate_long_outputs=100,        # Truncate outputs after 100 lines
       truncate_output_message='... (output truncated) ...',  # Custom truncation message
       attachment_mode='base64'          # Embed plots as base64
   )

   markdown = to_markdown('analysis.ipynb', parser_options=options)

Error Handling
--------------

.. code-block:: python

   from all2md import to_markdown
   from all2md.exceptions import (
       All2MdError,
       DependencyError,
       ParsingError,
       FileNotFoundError as All2MdFileNotFoundError,
       ValidationError
   )

   try:
       markdown = to_markdown('document.pdf')
       print("Conversion successful!")

   except All2MdFileNotFoundError:
       print("File not found. Please check the path.")

   except DependencyError as e:
       print(f"Missing dependency: {e}")
       print("Try: pip install all2md[pdf]")

   except ParsingError as e:
       print(f"Parsing failed: {e}")

   except ValidationError as e:
       print(f"Validation error: {e}")

   except All2MdError as e:
       print(f"Conversion error: {e}")

Advanced: Working with the AST
------------------------------

For document analysis and programmatic transformation, convert to an Abstract
Syntax Tree instead of Markdown:

.. code-block:: python

   from all2md import to_ast

   doc = to_ast('document.pdf')   # a Document node you can traverse and transform

The AST lets you extract elements (headings, links, tables), transform documents
(shift heading levels, rewrite links), and re-render to any output format using
visitors and transformers. See :doc:`ast_guide` for the full guide and
:doc:`transforms` for the built-in transform pipeline.

More CLI Features
-----------------

The command line also supports live **watch mode** (``--watch`` /
``--watch-debounce``), **ZIP bundles** with organised assets (``--zip`` /
``--assets-layout``), and **trace logging** for troubleshooting
(``--trace --log-file``). See :doc:`cli` for the complete command reference and
:doc:`recipes` for end-to-end examples.

Next Steps
----------

Now that you've got the basics down:

1. **Explore formats**: See :doc:`formats` for detailed examples of each supported format
2. **Work with AST**: Visit :doc:`ast_guide` for advanced document manipulation
3. **Learn the CLI**: Check out :doc:`cli` for all command-line options
4. **Dive into options**: Visit :doc:`options` for complete configuration reference
5. **Secure your conversions**: See :doc:`security` for SSRF protection and security best practices
6. **Try recipes**: Check out :doc:`recipes` for real-world examples and patterns
7. **Get help**: See :doc:`troubleshooting` for common issues and solutions

You're ready to start converting documents! 🚀
