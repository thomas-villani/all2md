Quick Start Guide
=================

This guide will get you up and running with all2md in just a few minutes.

Basic Usage
-----------

The simplest way to use all2md is with the main ``parse_file`` function:

.. code-block:: python

   from all2md import parse_file

   # Convert any supported file to Markdown
   with open('document.pdf', 'rb') as f:
       markdown_content = parse_file(f, 'document.pdf')
       print(markdown_content)

With MIME Type Detection
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   content, mimetype = parse_file(file_obj, filename, return_mimetype=True)
   print(f"Detected type: {mimetype}")
   print(content)

Format-Specific Examples
------------------------

PDF Documents
~~~~~~~~~~~~~

.. code-block:: python

   from all2md.pdf2markdown import pdf_to_markdown
   from io import BytesIO

   with open('report.pdf', 'rb') as f:
       filestream = BytesIO(f.read())
       markdown = pdf_to_markdown(filestream)
       print(markdown)

   # Convert specific pages
   markdown = pdf_to_markdown(filestream, pages=[0, 1, 2])  # First 3 pages

Word Documents
~~~~~~~~~~~~~~

.. code-block:: python

   from all2md.docx2markdown import docx_to_markdown

   # Basic conversion
   with open('document.docx', 'rb') as f:
       markdown = docx_to_markdown(f)

   # Include images as base64
   with open('document.docx', 'rb') as f:
       markdown = docx_to_markdown(f, convert_images_to_base64=True)

PowerPoint Presentations
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md.pptx2markdown import pptx_to_markdown

   with open('presentation.pptx', 'rb') as f:
       markdown = pptx_to_markdown(f)
       print(markdown)

Email Files
~~~~~~~~~~~

.. code-block:: python

   from all2md.emlfile import parse_email_chain

   # Get structured data
   messages = parse_email_chain('conversation.eml')
   for msg in messages:
       print(f"From: {msg['from']}")
       print(f"Subject: {msg['subject']}")
       print(f"Date: {msg['date']}")
       print("---")

   # Get Markdown format
   markdown = parse_email_chain('conversation.eml', as_markdown=True)
   print(markdown)

HTML Content
~~~~~~~~~~~~

.. code-block:: python

   from all2md.html2markdown import HTMLToMarkdown

   converter = HTMLToMarkdown()

   html = '''
   <h1>My Document</h1>
   <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
   <ul>
       <li>Item 1</li>
       <li>Item 2</li>
   </ul>
   '''

   markdown = converter.convert(html)
   print(markdown)

Reverse Conversion Examples
---------------------------

Markdown to Word
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md.markdown2docx import markdown_to_docx

   markdown_text = """
   # My Document

   This is **bold** text with a [link](https://example.com).

   ## Features
   - Feature 1
   - Feature 2

   | Name | Value |
   |------|-------|
   | Item | 123   |
   """

   doc = markdown_to_docx(markdown_text)
   doc.save('output.docx')

PDF to Images
~~~~~~~~~~~~~

.. code-block:: python

   from all2md.pdf2image import pdf_to_images

   # Convert all pages to images
   images = pdf_to_images('document.pdf', fmt='png', zoom=2.0)
   print(f"Generated {len(images)} images")

   # Convert specific page range
   images = pdf_to_images(
       'document.pdf',
       first_page=1,
       last_page=5,
       fmt='jpeg',
       zoom=1.5
   )

   # Get base64 encoded for web use
   images_b64 = pdf_to_images('document.pdf', as_base64=True)

Working with File Objects
--------------------------

From Memory
~~~~~~~~~~~

.. code-block:: python

   from io import BytesIO
   from all2md import parse_file

   # Load file into memory
   with open('document.pdf', 'rb') as f:
       file_data = f.read()

   # Convert from memory
   file_obj = BytesIO(file_data)
   markdown = parse_file(file_obj, 'document.pdf')

From URL
~~~~~~~~

.. code-block:: python

   import requests
   from io import BytesIO
   from all2md import parse_file

   # Download and convert
   response = requests.get('https://example.com/document.pdf')
   file_obj = BytesIO(response.content)
   markdown = parse_file(file_obj, 'document.pdf')

Batch Processing
----------------

Multiple Files
~~~~~~~~~~~~~~

.. code-block:: python

   import os
   from all2md import parse_file

   input_folder = 'documents'
   output_folder = 'markdown'

   for filename in os.listdir(input_folder):
       if filename.endswith(('.pdf', '.docx', '.pptx')):
           input_path = os.path.join(input_folder, filename)
           output_path = os.path.join(output_folder, filename + '.md')

           with open(input_path, 'rb') as f:
               markdown = parse_file(f, filename)

           with open(output_path, 'w', encoding='utf-8') as f:
               f.write(markdown)

           print(f"Converted: {filename}")

Directory Processing
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pathlib import Path
   from all2md import parse_file

   def convert_directory(input_dir, output_dir):
       input_path = Path(input_dir)
       output_path = Path(output_dir)
       output_path.mkdir(exist_ok=True)

       supported_extensions = {'.pdf', '.docx', '.pptx', '.html', '.eml'}

       for file_path in input_path.rglob('*'):
           if file_path.suffix.lower() in supported_extensions:
               with open(file_path, 'rb') as f:
                   markdown = parse_file(f, file_path.name)

               output_file = output_path / (file_path.stem + '.md')
               with open(output_file, 'w', encoding='utf-8') as f:
                   f.write(markdown)

               print(f"Converted: {file_path.name}")

   convert_directory('input_docs', 'output_markdown')

Error Handling
--------------

Basic Error Handling
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import parse_file

   try:
       with open('document.pdf', 'rb') as f:
           markdown = parse_file(f, 'document.pdf')
   except ImportError as e:
       print(f"Missing dependency: {e}")
       print("Install required packages for PDF processing")
   except FileNotFoundError:
       print("File not found")
   except Exception as e:
       print(f"Conversion failed: {e}")

Checking File Support
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import ALL_ALLOWED_EXTENSIONS
   import os

   def is_supported(filename):
       _, ext = os.path.splitext(filename)
       return ext.lower() in ALL_ALLOWED_EXTENSIONS

   filename = 'document.pdf'
   if is_supported(filename):
       print(f"{filename} is supported")
   else:
       print(f"{filename} is not supported")

Configuration Examples
----------------------

HTML Converter
~~~~~~~~~~~~~~

.. code-block:: python

   from all2md.html2markdown import HTMLToMarkdown

   # Custom configuration
   converter = HTMLToMarkdown(
       hash_headings=False,       # Use underline-style headers
       emphasis_symbol="_",       # Use _ for emphasis instead of *
       bullet_symbols="+-*",      # Custom bullet symbols
       remove_images=True         # Strip images from output
   )

   html_content = "<h1>Title</h1><p>Content</p>"
   markdown = converter.convert(html_content)

Common Use Cases
----------------

Document Conversion Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import parse_file
   from all2md.markdown2docx import markdown_to_docx

   def convert_to_word_via_markdown(input_file, output_file):
       # Step 1: Convert input to Markdown
       with open(input_file, 'rb') as f:
           markdown = parse_file(f, input_file)

       # Step 2: Convert Markdown to Word
       doc = markdown_to_docx(markdown)
       doc.save(output_file)

   convert_to_word_via_markdown('report.pdf', 'report.docx')

Content Extraction
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import parse_file
   import re

   def extract_headers(file_path):
       with open(file_path, 'rb') as f:
           markdown = parse_file(f, file_path)

       # Extract all headers
       headers = re.findall(r'^(#{1,6})\s+(.+)$', markdown, re.MULTILINE)
       return [(len(level), text.strip()) for level, text in headers]

   headers = extract_headers('document.pdf')
   for level, text in headers:
       print(f"{'  ' * (level-1)}• {text}")

Next Steps
----------

- Read the :doc:`usage` guide for detailed information
- Explore the :doc:`api` reference for all available functions
- Check :doc:`formats` for complete format support details
- See :doc:`contributing` if you want to help improve all2md