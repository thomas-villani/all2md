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
       attachment_mode='download',
       attachment_output_dir='./pdf_images'
   )

   markdown = to_markdown('report.pdf', options=options)

.. code-block:: bash

   # Command line equivalent
   all2md report.pdf --attachment-mode download --attachment-output-dir ./pdf_images

2. Processing Word Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, DocxOptions

   # Preserve all formatting and download images
   options = DocxOptions(
       attachment_mode='download',
       attachment_output_dir='./doc_images'
   )

   markdown = to_markdown('document.docx', options=options)

3. Custom Markdown Formatting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, MarkdownOptions

   # Use underscores for emphasis and custom bullets
   md_options = MarkdownOptions(
       emphasis_symbol='_',
       bullet_symbols='•◦▪',
       use_hash_headings=True
   )

   # Apply to any converter
   markdown = to_markdown('document.pdf', markdown_options=md_options)

.. code-block:: bash

   # Command line equivalent
   all2md document.pdf --markdown-emphasis-symbol "_" --markdown-bullet-symbols "•◦▪"

4. Batch Processing
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import os
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

               print(f"✓ Converted {file_path.name} -> {output_file.name}")

           except Exception as e:
               print(f"✗ Failed to convert {file_path.name}: {e}")

5. Working with File Objects
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
       markdown = to_markdown(f, format='pdf')

Handling Different Formats
---------------------------

all2md automatically detects file formats, but you can also be explicit:

.. code-block:: python

   from all2md import to_markdown

   # Automatic detection (recommended)
   markdown = to_markdown('document.pdf')

   # Explicit format (useful for edge cases)
   markdown = to_markdown('document.pdf', format='pdf')

   # Force text processing for unknown files
   markdown = to_markdown('unknown_file', format='txt')

Email Processing Example
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, EmlOptions

   options = EmlOptions(
       attachment_mode='download',
       attachment_output_dir='./email_attachments',
       detect_reply_separators=True,  # Clean up email chains
       clean_wrapped_urls=True        # Fix broken URLs
   )

   markdown = to_markdown('message.eml', options=options)

Jupyter Notebook Example
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, IpynbOptions

   options = IpynbOptions(
       truncate_long_outputs=100,        # Truncate outputs after 100 lines
       truncate_output_message='... (output truncated) ...',  # Custom truncation message
       attachment_mode='base64'          # Embed plots as base64
   )

   markdown = to_markdown('analysis.ipynb', options=options)

Error Handling
--------------

.. code-block:: python

   from all2md import to_markdown
   from all2md.exceptions import MarkdownConversionError, InputError

   try:
       markdown = to_markdown('document.pdf')
       print("Conversion successful!")

   except FileNotFoundError:
       print("File not found. Please check the path.")

   except ImportError as e:
       print(f"Missing dependency: {e}")
       print("Try: pip install all2md[pdf]")

   except MarkdownConversionError as e:
       print(f"Conversion failed: {e}")

   except InputError as e:
       print(f"Input error: {e}")

Next Steps
----------

Now that you've got the basics down:

1. **Explore formats**: See :doc:`formats` for detailed examples of each supported format
2. **Learn the CLI**: Check out :doc:`cli` for all command-line options
3. **Dive into options**: Visit :doc:`options` for complete configuration reference
4. **Get help**: See :doc:`troubleshooting` for common issues and solutions

You're ready to start converting documents! 🚀