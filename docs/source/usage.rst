Usage Guide
===========

This comprehensive guide covers all aspects of using all2md for document conversion.

Core Concepts
-------------

File Type Detection
~~~~~~~~~~~~~~~~~~~

all2md automatically detects file types using:

1. **File extensions** - Primary method for format detection
2. **MIME type analysis** - Secondary validation
3. **Content inspection** - For ambiguous cases

.. code-block:: python

   from all2md import parse_file

   # Automatic detection based on filename
   with open('document.pdf', 'rb') as f:
       content = parse_file(f, 'document.pdf')

   # Get MIME type information
   content, mimetype = parse_file(f, filename, return_mimetype=True)

Supported Extensions
~~~~~~~~~~~~~~~~~~~~

all2md supports these file extensions:

* **Documents**: ``.pdf``, ``.docx``, ``.pptx``, ``.html``, ``.eml``
* **Spreadsheets**: ``.xlsx``, ``.csv``, ``.tsv``
* **Images**: ``.png``, ``.jpg``, ``.jpeg``, ``.gif``
* **Text**: ``.txt``, ``.md``, ``.json``, ``.xml``, ``.py``, and 200+ more

Advanced Usage
--------------

PDF Processing
~~~~~~~~~~~~~~

PDF conversion offers the most advanced features:

**Basic PDF Conversion**

.. code-block:: python

   from all2md.pdf2markdown import pdf_to_markdown
   from io import BytesIO

   with open('document.pdf', 'rb') as f:
       filestream = BytesIO(f.read())
       markdown = pdf_to_markdown(filestream)

**Page Range Selection**

.. code-block:: python

   # Convert specific pages (0-indexed)
   markdown = pdf_to_markdown(doc, pages=[0, 1, 2])  # First 3 pages
   markdown = pdf_to_markdown(doc, pages=list(range(5, 10)))  # Pages 6-10

**Table Detection**

PDF processing includes advanced table detection:

.. code-block:: python

   # Tables are automatically detected and converted to Markdown format
   markdown = pdf_to_markdown(filestream)
   # Output includes tables like:
   # | Column 1 | Column 2 |
   # |----------|----------|
   # | Value 1  | Value 2  |

Word Document Processing
~~~~~~~~~~~~~~~~~~~~~~~~

**Text Formatting Preservation**

.. code-block:: python

   from all2md.docx2markdown import docx_to_markdown

   # Preserves bold, italic, underline, strikethrough
   with open('formatted.docx', 'rb') as f:
       markdown = docx_to_markdown(f)
   # Output: **bold text**, *italic text*, etc.

**List Handling**

.. code-block:: python

   # Automatic detection of bulleted and numbered lists
   markdown = docx_to_markdown(docx_file)
   # Output preserves nesting:
   # 1. First item
   #    - Nested bullet
   #    - Another nested item
   # 2. Second item

**Table Conversion**

.. code-block:: python

   # Word tables become Markdown tables
   markdown = docx_to_markdown(docx_file)
   # Tables maintain structure and basic formatting

**Image Handling**

.. code-block:: python

   # Embed images as base64 data URIs
   markdown = docx_to_markdown(docx_file, convert_images_to_base64=True)
   # Images appear as: ![alt text](data:image/png;base64,...)

PowerPoint Processing
~~~~~~~~~~~~~~~~~~~~~

**Slide-by-Slide Conversion**

.. code-block:: python

   from all2md.pptx2markdown import pptx_to_markdown

   markdown = pptx_to_markdown(pptx_file)
   # Each slide becomes a section with:
   # - Slide title as header
   # - Bullet points preserved
   # - Tables converted to Markdown
   # - Images embedded as base64

**Content Structure**

PowerPoint conversion maintains logical structure:

.. code-block:: text

   # Slide 1: Title Slide

   Presentation content here

   ---

   # Slide 2: Content Slide

   - Bullet point 1
   - Bullet point 2

Email Processing
~~~~~~~~~~~~~~~~

**Email Chain Parsing**

.. code-block:: python

   from all2md.emlfile import parse_email_chain

   # Parse as structured data
   messages = parse_email_chain('conversation.eml')
   for msg in messages:
       print(f"From: {msg['from']}")
       print(f"To: {msg['to']}")
       print(f"Subject: {msg['subject']}")
       print(f"Date: {msg['date']}")
       print(f"Content: {msg['content'][:100]}...")

**Markdown Output**

.. code-block:: python

   # Get formatted Markdown
   markdown = parse_email_chain('conversation.eml', as_markdown=True)
   # Output includes headers, threading, and clean content

**Thread Reconstruction**

The email parser automatically:

- Detects reply chains
- Reconstructs conversation threads
- Handles forwarded messages
- Cleans quoted content
- Preserves metadata (dates, recipients)

HTML Processing
~~~~~~~~~~~~~~~

**Configurable Conversion**

.. code-block:: python

   from all2md.html2markdown import HTMLToMarkdown

   # Default settings
   converter = HTMLToMarkdown()
   markdown = converter.convert(html_content)

   # Custom configuration
   converter = HTMLToMarkdown(
       hash_headings=True,        # Use # for headers (vs underline)
       emphasis_symbol="*",       # Use * for emphasis (vs _)
       bullet_symbols="*-+",      # Bullet symbols to cycle through
       remove_images=False,       # Keep images in output
       extract_title=True         # Extract <title> from HTML
   )

**Complex HTML Support**

.. code-block:: python

   html = """
   <article>
       <h1>Article Title</h1>
       <p>Paragraph with <strong>bold</strong> and <em>italic</em>.</p>
       <ul>
           <li>List item 1</li>
           <li>List item 2
               <ul>
                   <li>Nested item</li>
               </ul>
           </li>
       </ul>
       <table>
           <thead>
               <tr><th>Header 1</th><th>Header 2</th></tr>
           </thead>
           <tbody>
               <tr><td>Cell 1</td><td>Cell 2</td></tr>
           </tbody>
       </table>
   </article>
   """

   converter = HTMLToMarkdown()
   markdown = converter.convert(html)

Reverse Conversion
------------------

Markdown to Word
~~~~~~~~~~~~~~~~

**Basic Conversion**

.. code-block:: python

   from all2md.markdown2docx import markdown_to_docx

   markdown_text = """
   # Document Title

   This is a paragraph with **bold** and *italic* formatting.

   ## Section Header

   - Bullet point 1
   - Bullet point 2

   1. Numbered item 1
   2. Numbered item 2

   [Link text](https://example.com)
   """

   doc = markdown_to_docx(markdown_text)
   doc.save('output.docx')

**Advanced Features**

.. code-block:: python

   # Tables in Markdown become Word tables
   markdown_with_table = """
   # Report

   | Metric | Q1 | Q2 | Q3 |
   |--------|----|----|----|
   | Sales  | 100| 150| 200|
   | Profit | 20 | 30 | 45 |

   The table above shows quarterly results.
   """

   doc = markdown_to_docx(markdown_with_table)
   doc.save('report.docx')

PDF to Images
~~~~~~~~~~~~~

**High-Quality Conversion**

.. code-block:: python

   from all2md.pdf2image import pdf_to_images

   # High resolution conversion
   images = pdf_to_images(
       'document.pdf',
       zoom=3.0,              # 3x resolution
       fmt='png',             # PNG for quality
       first_page=1,          # Start page (1-indexed)
       last_page=10           # End page
   )

**Web-Ready Output**

.. code-block:: python

   # Get base64 encoded images for web use
   images_b64 = pdf_to_images(
       'document.pdf',
       zoom=1.5,
       fmt='jpeg',            # JPEG for smaller size
       as_base64=True
   )

   # Use in HTML
   for i, img_b64 in enumerate(images_b64):
       html = f'<img src="data:image/jpeg;base64,{img_b64}" alt="Page {i+1}">'

Batch Operations
----------------

Processing Multiple Files
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import os
   from pathlib import Path
   from all2md import parse_file

   def convert_folder(input_folder, output_folder):
       input_path = Path(input_folder)
       output_path = Path(output_folder)
       output_path.mkdir(exist_ok=True)

       for file_path in input_path.iterdir():
           if file_path.is_file() and file_path.suffix in ['.pdf', '.docx', '.pptx']:
               print(f"Converting {file_path.name}...")

               try:
                   with open(file_path, 'rb') as f:
                       markdown = parse_file(f, file_path.name)

                   output_file = output_path / (file_path.stem + '.md')
                   with open(output_file, 'w', encoding='utf-8') as f:
                       f.write(markdown)

                   print(f"✓ Converted {file_path.name}")

               except Exception as e:
                   print(f"✗ Failed to convert {file_path.name}: {e}")

   convert_folder('documents', 'markdown_output')

Parallel Processing
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from concurrent.futures import ThreadPoolExecutor
   from pathlib import Path
   from all2md import parse_file

   def convert_file(file_path, output_dir):
       try:
           with open(file_path, 'rb') as f:
               markdown = parse_file(f, file_path.name)

           output_file = Path(output_dir) / (file_path.stem + '.md')
           with open(output_file, 'w', encoding='utf-8') as f:
               f.write(markdown)

           return f"✓ {file_path.name}"
       except Exception as e:
           return f"✗ {file_path.name}: {e}"

   def convert_folder_parallel(input_folder, output_folder, max_workers=4):
       input_path = Path(input_folder)
       output_path = Path(output_folder)
       output_path.mkdir(exist_ok=True)

       files = [f for f in input_path.iterdir()
                if f.is_file() and f.suffix in ['.pdf', '.docx', '.pptx']]

       with ThreadPoolExecutor(max_workers=max_workers) as executor:
           results = executor.map(lambda f: convert_file(f, output_folder), files)

           for result in results:
               print(result)

Performance Optimization
------------------------

Memory Management
~~~~~~~~~~~~~~~~~

For large files, use streaming approaches:

.. code-block:: python

   from io import BytesIO

   # Process file in memory to avoid disk I/O
   with open('large_document.pdf', 'rb') as f:
       file_data = f.read()

   file_obj = BytesIO(file_data)
   markdown = parse_file(file_obj, 'large_document.pdf')

   # Clear memory when done
   del file_data, file_obj

Caching Results
~~~~~~~~~~~~~~~

.. code-block:: python

   import hashlib
   import pickle
   from pathlib import Path

   def get_file_hash(filepath):
       with open(filepath, 'rb') as f:
           return hashlib.md5(f.read()).hexdigest()

   def cached_convert(filepath, cache_dir='cache'):
       cache_path = Path(cache_dir)
       cache_path.mkdir(exist_ok=True)

       file_hash = get_file_hash(filepath)
       cache_file = cache_path / f"{file_hash}.pkl"

       # Check cache
       if cache_file.exists():
           with open(cache_file, 'rb') as f:
               return pickle.load(f)

       # Convert and cache
       with open(filepath, 'rb') as f:
           markdown = parse_file(f, Path(filepath).name)

       with open(cache_file, 'wb') as f:
           pickle.dump(markdown, f)

       return markdown

Error Handling
--------------

Common Errors and Solutions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**ImportError: Missing Dependencies**

.. code-block:: python

   try:
       from all2md.pdf2markdown import pdf_to_markdown
       markdown = pdf_to_markdown(file_obj)
   except ImportError as e:
       print("PDF processing requires PyMuPDF. Install with: pip install pymupdf")
       # Handle gracefully or install dependency

**UnicodeDecodeError: Encoding Issues**

.. code-block:: python

   try:
       with open('document.txt', 'rb') as f:
           markdown = parse_file(f, 'document.txt')
   except UnicodeDecodeError:
       # Try different encodings
       for encoding in ['utf-8', 'latin1', 'cp1252']:
           try:
               with open('document.txt', 'r', encoding=encoding) as f:
                   content = f.read()
               break
           except UnicodeDecodeError:
               continue

**Memory Errors: Large Files**

.. code-block:: python

   import psutil
   from pathlib import Path

   def check_memory_usage(filepath, max_memory_mb=1000):
       file_size = Path(filepath).stat().st_size / (1024 * 1024)  # MB
       available_memory = psutil.virtual_memory().available / (1024 * 1024)

       if file_size * 3 > available_memory:  # Rough estimate
           print(f"Warning: File may be too large ({file_size:.1f}MB)")
           return False
       return True

Robust Error Handling
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import parse_file
   import logging

   def safe_convert(filepath, output_path):
       try:
           with open(filepath, 'rb') as f:
               markdown = parse_file(f, Path(filepath).name)

           with open(output_path, 'w', encoding='utf-8') as f:
               f.write(markdown)

           return True, None

       except ImportError as e:
           error = f"Missing dependency: {e}"
           logging.error(error)
           return False, error

       except FileNotFoundError:
           error = "File not found"
           logging.error(error)
           return False, error

       except MemoryError:
           error = "File too large for available memory"
           logging.error(error)
           return False, error

       except Exception as e:
           error = f"Conversion failed: {e}"
           logging.error(error)
           return False, error

   # Usage
   success, error = safe_convert('document.pdf', 'output.md')
   if success:
       print("Conversion successful")
   else:
       print(f"Conversion failed: {error}")

Best Practices
--------------

File Handling
~~~~~~~~~~~~~

.. code-block:: python

   # Always use context managers
   with open('document.pdf', 'rb') as f:
       markdown = parse_file(f, 'document.pdf')

   # For web applications, validate file types
   allowed_extensions = {'.pdf', '.docx', '.pptx', '.html'}
   file_ext = Path(filename).suffix.lower()
   if file_ext not in allowed_extensions:
       raise ValueError(f"Unsupported file type: {file_ext}")

Output Formatting
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Clean up output Markdown
   def clean_markdown(text):
       # Remove excessive blank lines
       import re
       text = re.sub(r'\n{3,}', '\n\n', text)

       # Trim whitespace
       text = text.strip()

       return text

   markdown = parse_file(f, filename)
   clean_text = clean_markdown(markdown)

Integration Examples
--------------------

Web Application Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from flask import Flask, request, jsonify
   from all2md import parse_file
   from werkzeug.utils import secure_filename
   import tempfile
   import os

   app = Flask(__name__)

   @app.route('/convert', methods=['POST'])
   def convert_file():
       if 'file' not in request.files:
           return jsonify({'error': 'No file provided'}), 400

       file = request.files['file']
       if file.filename == '':
           return jsonify({'error': 'No file selected'}), 400

       filename = secure_filename(file.filename)

       try:
           # Convert file
           markdown = parse_file(file, filename)
           return jsonify({
               'success': True,
               'markdown': markdown,
               'filename': filename
           })

       except Exception as e:
           return jsonify({
               'success': False,
               'error': str(e)
           }), 500

Command Line Tool
~~~~~~~~~~~~~~~~~

.. code-block:: python

   import argparse
   from pathlib import Path
   from all2md import parse_file

   def main():
       parser = argparse.ArgumentParser(description='Convert documents to Markdown')
       parser.add_argument('input', help='Input file path')
       parser.add_argument('-o', '--output', help='Output file path')
       parser.add_argument('-v', '--verbose', action='store_true')

       args = parser.parse_args()

       input_path = Path(args.input)
       if not input_path.exists():
           print(f"Error: {input_path} not found")
           return 1

       output_path = Path(args.output) if args.output else input_path.with_suffix('.md')

       try:
           if args.verbose:
               print(f"Converting {input_path}...")

           with open(input_path, 'rb') as f:
               markdown = parse_file(f, input_path.name)

           with open(output_path, 'w', encoding='utf-8') as f:
               f.write(markdown)

           if args.verbose:
               print(f"Converted to {output_path}")

           return 0

       except Exception as e:
           print(f"Conversion failed: {e}")
           return 1

   if __name__ == '__main__':
       exit(main())

This completes the comprehensive usage guide covering all major features and use cases of all2md.