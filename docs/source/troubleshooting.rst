Troubleshooting
===============

This guide covers common issues, error messages, and solutions when using all2md. Most problems fall into a few categories: missing dependencies, file access issues, or format-specific problems.

.. contents::
   :local:
   :depth: 2

Quick Diagnostic Steps
----------------------

When encountering issues, try these steps first:

1. **Check Python Version**

   .. code-block:: bash

      python --version
      # Should be 3.12 or higher

2. **Verify Installation**

   .. code-block:: python

      import all2md
      print(all2md.__version__)

3. **Test with Simple File**

   .. code-block:: bash

      echo "# Test" | all2md -

4. **Enable Debug Logging**

   .. code-block:: bash

      all2md document.pdf --log-level DEBUG

5. **Check File Access**

   .. code-block:: bash

      ls -la document.pdf
      file document.pdf

Installation Issues
-------------------

Missing Dependencies
~~~~~~~~~~~~~~~~~~~~

**Error Messages:**
   * ``ImportError: No module named 'fitz'``
   * ``ModuleNotFoundError: No module named 'docx'``
   * ``ImportError: PyMuPDF is required for PDF processing``

**Problem:**
   Format-specific dependencies are not installed.

**Solutions:**

.. code-block:: bash

   # For PDF support
   pip install all2md[pdf]

   # For Word documents
   pip install all2md[docx]

   # For PowerPoint
   pip install all2md[pptx]

   # For all formats
   pip install all2md[all]

   # Check what's installed
   pip list | grep -E "(all2md|pymupdf|docx|pptx|beautifulsoup4)"

Python Version Issues
~~~~~~~~~~~~~~~~~~~~~

**Error Messages:**
   * ``ERROR: Package 'all2md' requires a different Python``
   * ``SyntaxError: invalid syntax`` (on import)

**Problem:**
   all2md requires Python 3.12 or higher.

**Solutions:**

.. code-block:: bash

   # Check current version
   python --version

   # Install Python 3.12+ (various methods)
   # Via pyenv (recommended)
   pyenv install 3.12.0
   pyenv global 3.12.0

   # Via conda
   conda install python=3.12

   # Via system package manager
   # Ubuntu/Debian: sudo apt install python3.12
   # macOS: brew install python@3.12

Virtual Environment Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Error Messages:**
   * ``Permission denied`` errors
   * ``ERROR: Could not install packages due to an EnvironmentError``

**Problem:**
   Conflicting system packages or permission issues.

**Solutions:**

.. code-block:: bash

   # Create fresh virtual environment
   python -m venv all2md_env

   # Activate it
   # Windows:
   all2md_env\Scripts\activate
   # macOS/Linux:
   source all2md_env/bin/activate

   # Install all2md
   pip install all2md[all]

   # Verify installation
   which all2md
   all2md --version

File Access Problems
--------------------

File Not Found
~~~~~~~~~~~~~~

**Error Messages:**
   * ``FileNotFoundError: [Errno 2] No such file or directory``
   * ``File not found: document.pdf``

**Solutions:**

.. code-block:: bash

   # Check file exists and permissions
   ls -la document.pdf

   # Use absolute path
   all2md /full/path/to/document.pdf

   # Check current directory
   pwd
   ls *.pdf

Permission Denied
~~~~~~~~~~~~~~~~~

**Error Messages:**
   * ``PermissionError: [Errno 13] Permission denied``
   * ``Permission denied: './output'``

**Solutions:**

.. code-block:: bash

   # Check file permissions
   ls -la document.pdf

   # Make file readable
   chmod +r document.pdf

   # Check output directory permissions
   ls -la ./output
   mkdir -p ./output
   chmod +w ./output

Corrupted or Invalid Files
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Error Messages:**
   * ``MarkdownConversionError: Invalid PDF file``
   * ``Error: Could not decode file as UTF-8``

**Solutions:**

.. code-block:: bash

   # Verify file integrity
   file document.pdf
   head -c 20 document.pdf

   # Try forcing format detection
   all2md document.pdf --format pdf --log-level DEBUG

   # For text encoding issues
   all2md document.txt --format txt --log-level DEBUG

Format-Specific Issues
----------------------

PDF Problems
~~~~~~~~~~~~

**Cannot Extract Text**

*Error:* PDF appears to process but produces empty or garbled output.

*Causes:*
  * Scanned PDF (image-based)
  * Encrypted PDF
  * Corrupted file
  * Font embedding issues

*Solutions:*

.. code-block:: python

   # Check if PDF is text-based
   from all2md import to_markdown, PdfOptions

   options = PdfOptions(pages=[1])  # Test first page only
   markdown = to_markdown('document.pdf', options=options)

   if not markdown.strip():
       print("PDF may be image-based or encrypted")

.. code-block:: bash

   # For encrypted PDFs
   all2md encrypted.pdf --pdf-password "password"

   # Enable debug logging
   all2md document.pdf --log-level DEBUG

**Table Detection Issues**

*Problem:* Tables not detected or poorly formatted.

*Solutions:*

.. code-block:: python

   from all2md import PdfOptions

   # Enable table detection with fallback heuristics
   options = PdfOptions(
       enable_table_fallback_detection=True,  # Enable heuristic fallback
       attachment_mode='skip'  # Skip images for faster processing
   )

.. code-block:: bash

   # CLI equivalent
   all2md document.pdf --pdf-no-enable-table-fallback-detection  # To disable fallback

**Column Layout Problems**

*Problem:* Multi-column text merged incorrectly.

*Solutions:*

.. code-block:: python

   # Disable column detection for simple layouts
   options = PdfOptions(detect_columns=False)

   # Adjust column gap threshold
   options = PdfOptions(
       detect_columns=True,
       column_gap_threshold=30  # Increase for wider gaps
   )

Word Document Issues
~~~~~~~~~~~~~~~~~~~~

**Missing Formatting**

*Problem:* Bold, italic, or other formatting not preserved.

*Solutions:*

.. code-block:: python

   from all2md import DocxOptions, MarkdownOptions

   # Ensure formatting is preserved
   md_options = MarkdownOptions(
       emphasis_symbol='*',  # or '_'
       escape_special=True
   )

   options = DocxOptions(
       preserve_tables=True,
       markdown_options=md_options
   )

.. code-block:: bash

   # CLI equivalent
   all2md document.docx --markdown-emphasis-symbol "*"

**Image Problems**

*Problem:* Images missing or not extracted.

*Solutions:*

.. code-block:: python

   from all2md import DocxOptions

   # Download images to directory
   options = DocxOptions(
       attachment_mode='download',
       attachment_output_dir='./word_images'
   )

   # Or embed as base64
   options = DocxOptions(attachment_mode='base64')

.. code-block:: bash

   # CLI equivalents
   all2md document.docx --attachment-mode download --attachment-output-dir ./word_images
   all2md document.docx --attachment-mode base64

HTML Issues
~~~~~~~~~~~

**Dangerous Content**

*Problem:* JavaScript or CSS interfering with conversion.

*Solutions:*

.. code-block:: python

   from all2md import HtmlOptions

   options = HtmlOptions(strip_dangerous_elements=True)

.. code-block:: bash

   # Basic sanitization
   all2md webpage.html --html-strip-dangerous-elements

   # Or use security presets for quick configuration
   all2md webpage.html --strict-html-sanitize  # Maximum sanitization, blocks all fetching
   all2md webpage.html --safe-mode             # Balanced security with HTTPS-only
   all2md webpage.html --paranoid-mode         # Maximum security with 5MB limits

.. note::

   **Security Presets:** The new ``--strict-html-sanitize``, ``--safe-mode``, and ``--paranoid-mode`` flags provide pre-configured security settings for common scenarios. These are especially useful when processing untrusted HTML content. See :doc:`cli` for details.

**Relative Links Broken**

*Problem:* Images or links not resolving correctly.

*Solutions:*

.. code-block:: python

   from all2md import HtmlOptions

   options = HtmlOptions(
       attachment_mode='download',
       attachment_base_url='https://example.com'
   )

.. code-block:: bash

   all2md webpage.html --attachment-mode download --attachment-base-url "https://example.com"

Email Processing Issues
~~~~~~~~~~~~~~~~~~~~~~~

**Encoding Problems**

*Problem:* Special characters or non-English text garbled.

*Solutions:*

.. code-block:: python

   from all2md import EmlOptions

   # Enable HTML conversion for better encoding handling
   options = EmlOptions(
       convert_html_to_markdown=True,
       clean_quotes=True
   )

**Thread Structure Issues**

*Problem:* Reply chains not handled correctly.

*Solutions:*

.. code-block:: python

   from all2md import EmlOptions

   # Adjust thread processing
   options = EmlOptions(
       preserve_thread_structure=True,
       detect_reply_separators=True,
       clean_quotes=True
   )

   # Or disable for simple conversion
   options = EmlOptions(
       preserve_thread_structure=False,
       include_headers=False
   )

.. code-block:: bash

   # CLI equivalents
   all2md message.eml --eml-no-preserve-thread-structure --eml-no-include-headers

Performance Issues
------------------

Slow Processing
~~~~~~~~~~~~~~~

**Problem:** Large documents taking too long to process.

**Solutions:**

.. code-block:: python

   from all2md import PdfOptions

   # Process specific pages only
   options = PdfOptions(pages=[1, 2, 3])  # First 3 pages

   # Skip images for faster processing
   options = PdfOptions(attachment_mode='skip')

   # Disable complex features
   options = PdfOptions(
       detect_columns=False,
       enable_table_fallback_detection=False
   )

.. code-block:: bash

   # CLI equivalents
   all2md document.pdf --pdf-pages "0,1,2"
   all2md document.pdf --attachment-mode skip
   all2md document.pdf --pdf-no-detect-columns --pdf-no-enable-table-fallback-detection

Memory Issues
~~~~~~~~~~~~~

**Problem:** Out of memory errors with large files.

**Solutions:**

.. code-block:: python

   from all2md import to_markdown, PdfOptions

   # Process in smaller chunks
   total_pages = 100  # Example total
   for i in range(0, total_pages, 10):
       page_chunk = list(range(i, min(i + 10, total_pages)))
       options = PdfOptions(pages=page_chunk)
       chunk_markdown = to_markdown('large.pdf', options=options)
       # Process chunk_markdown

   # Skip attachment processing
   options = PdfOptions(attachment_mode='skip')

.. code-block:: bash

   # CLI: Process specific page ranges
   all2md large.pdf --pdf-pages "0,1,2,3,4,5,6,7,8,9" --out chunk1.md
   all2md large.pdf --pdf-pages "10,11,12,13,14,15,16,17,18,19" --out chunk2.md

Command Line Issues
-------------------

Command Not Found
~~~~~~~~~~~~~~~~~~

**Error Messages:**
   * ``all2md: command not found``
   * ``'all2md' is not recognized as an internal or external command``

**Solutions:**

.. code-block:: bash

   # Check if installed
   pip list | grep all2md

   # Reinstall if necessary
   pip install all2md

   # Use module form
   python -m all2md document.pdf

   # Check PATH
   echo $PATH
   which all2md

Argument Parsing Issues
~~~~~~~~~~~~~~~~~~~~~~~

**Error Messages:**
   * ``unrecognized arguments``
   * ``error: argument --format: invalid choice``

**Solutions:**

.. code-block:: bash

   # Check available options
   all2md --help

   # Verify format names
   all2md document.pdf --format pdf  # not PDF

   # Quote arguments with spaces
   all2md document.pdf --attachment-output-dir "My Folder"

Stdin/Pipe Issues
~~~~~~~~~~~~~~~~~

**Problem:** Reading from stdin or pipes not working.

**Solutions:**

.. code-block:: bash

   # Explicit stdin
   cat document.pdf | all2md -

   # With format specification
   cat unknown_file | all2md - --format pdf

   # Check pipe status
   echo "# Test" | all2md - --log-level DEBUG

Advanced Debugging
------------------

Enable Detailed Logging
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import logging
   from all2md import to_markdown

   # Configure logging
   logging.basicConfig(level=logging.DEBUG)
   logger = logging.getLogger('all2md')

   # Convert with detailed logging
   markdown = to_markdown('document.pdf')

.. code-block:: bash

   # Command line debugging
   all2md document.pdf --log-level DEBUG > output.md 2> debug.log

Check File Format Detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown

   # Force different formats to test detection
   for fmt in ['auto', 'pdf', 'txt']:
       try:
           result = to_markdown('mysterious_file', format=fmt)
           print(f"Format {fmt}: Success ({len(result)} chars)")
       except Exception as e:
           print(f"Format {fmt}: Failed - {e}")

Test with Minimal Example
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Create minimal test case
   with open('test.html', 'w') as f:
       f.write('<html><body><h1>Test</h1><p>Content</p></body></html>')

   from all2md import to_markdown
   result = to_markdown('test.html')
   print(result)

Examine File Structure
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # For PDF files
   pdfinfo document.pdf
   pdftk document.pdf dump_data

   # For Office files (they're ZIP archives)
   unzip -l document.docx
   unzip -l document.pptx

   # For general files
   file document.pdf
   hexdump -C document.pdf | head -20

Getting Help
------------

When to Report Issues
~~~~~~~~~~~~~~~~~~~~~

Report bugs when you encounter:

* **Crashes or exceptions** with valid input files
* **Incorrect output** that's clearly wrong
* **Missing features** documented but not working
* **Performance issues** with reasonable file sizes

Before Reporting
~~~~~~~~~~~~~~~~

1. **Update to latest version**

   .. code-block:: bash

      pip install --upgrade all2md

2. **Test with minimal example**

   Create the smallest possible file that reproduces the issue.

3. **Check existing issues**

   Search https://github.com/thomas.villani/all2md/issues

4. **Gather information**

   .. code-block:: bash

      # System information
      python --version
      pip list | grep all2md
      uname -a  # Linux/macOS
      systeminfo  # Windows

      # Debug output
      all2md problematic_file.pdf --log-level DEBUG > debug.log 2>&1

How to Report
~~~~~~~~~~~~~

Include in your issue report:

1. **all2md version** and Python version
2. **Operating system** and version
3. **Minimal example** that reproduces the problem
4. **Expected vs. actual behavior**
5. **Complete error message** or debug log
6. **Steps to reproduce** the issue

**Good Issue Report:**

.. code-block::

   Title: PDF table detection fails for merged cells

   Environment:
   - all2md version: 0.1.0
   - Python version: 3.12.0
   - OS: Ubuntu 22.04

   Problem:
   Tables with merged cells are not detected correctly in PDF files.

   Steps to reproduce:
   1. Convert attached PDF file
   2. all2md test_table.pdf --log-level DEBUG
   3. Table structure is lost

   Expected: Table preserved with merged cells
   Actual: Text runs together

   Debug log attached.

Community Resources
~~~~~~~~~~~~~~~~~~~

* **GitHub Issues**: https://github.com/thomas.villani/all2md/issues
* **Documentation**: https://all2md.readthedocs.io/
* **Stack Overflow**: Tag questions with ``all2md``

For installation or environment issues, also check the :doc:`installation` guide.