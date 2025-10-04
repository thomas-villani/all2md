Bidirectional Conversion
========================

While all2md is primarily known for converting various formats **to** Markdown, it also supports converting **from** Markdown to other formats like DOCX, HTML, and PDF. This bidirectional capability makes all2md a complete document transformation toolkit.

.. contents::
   :local:
   :depth: 2

Overview
--------

Bidirectional conversion works through all2md's AST (Abstract Syntax Tree) architecture:

.. code-block:: text

   Input Format → Parser → AST → Renderer → Output Format

For Markdown-to-X conversion, the flow is:

.. code-block:: text

   Markdown → MarkdownParser → AST → DocxRenderer/HtmlRenderer/PdfRenderer → Output

Quick Start
-----------

Converting Markdown to Other Formats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``from_markdown()`` or ``from_ast()`` functions:

.. code-block:: python

   from all2md import from_markdown

   # Convert Markdown to DOCX
   from_markdown('document.md', output_format='docx', output_path='document.docx')

   # Convert Markdown to HTML
   from_markdown('document.md', output_format='html', output_path='document.html')

   # Convert Markdown to PDF
   from_markdown('document.md', output_format='pdf', output_path='document.pdf')

Using the AST Directly
~~~~~~~~~~~~~~~~~~~~~~~

For more control, work with the AST:

.. code-block:: python

   from all2md import to_ast, from_ast
   from all2md.renderers.docx import DocxRenderer
   from all2md.renderers.html import HtmlRenderer

   # Parse Markdown to AST
   doc_ast = to_ast('document.md')

   # Render to different formats
   docx_bytes = from_ast(doc_ast, output_format='docx')
   html_string = from_ast(doc_ast, output_format='html')

   # Or use renderers directly
   docx_renderer = DocxRenderer()
   docx_bytes = docx_renderer.render(doc_ast)

Markdown to Word (DOCX)
------------------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.docx import DocxRendererOptions

   # Simple conversion
   from_markdown('report.md', output_format='docx', output_path='report.docx')

   # With options
   options = DocxRendererOptions(
       preserve_formatting=True,
       include_toc=True,
       page_size='A4'
   )
   from_markdown('report.md', output_format='docx', output_path='report.docx', renderer_options=options)

Preserving Markdown Features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DOCX renderer supports:

- **Headings** (H1-H6) → Word heading styles
- **Bold/Italic/Strikethrough** → Character formatting
- **Lists** (ordered, unordered, nested) → Word list styles
- **Tables** → Word tables with borders
- **Code blocks** → Monospace font with background
- **Links** → Hyperlinks
- **Images** → Embedded images (if paths are accessible)
- **Block quotes** → Indented paragraphs

.. code-block:: python

   from all2md import from_markdown

   markdown_content = """
   # Annual Report 2024

   ## Executive Summary

   This report covers **fiscal year 2024** with the following highlights:

   - Revenue increased by *15%*
   - Customer base grew to **10,000 users**
   - New product launch successful

   ### Key Metrics

   | Metric | 2023 | 2024 | Change |
   |--------|------|------|--------|
   | Revenue | $1M | $1.15M | +15% |
   | Users | 8,500 | 10,000 | +17.6% |

   > "Our best year yet!" - CEO
   """

   from_markdown(
       markdown_content,
       output_format='docx',
       output_path='annual_report.docx'
   )

Advanced DOCX Customization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_ast, from_ast
   from all2md.renderers.docx import DocxRendererOptions

   # Parse Markdown
   doc_ast = to_ast('document.md')

   # Customize rendering
   options = DocxRendererOptions(
       preserve_formatting=True,
       default_font='Calibri',
       default_font_size=11,
       heading_font='Arial',
       include_toc=True,
       page_size='letter',
       margin_inches=1.0
   )

   # Render to DOCX
   docx_bytes = from_ast(doc_ast, output_format='docx', renderer_options=options)

   # Write to file
   with open('output.docx', 'wb') as f:
       f.write(docx_bytes)

Markdown to HTML
----------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   # Simple conversion
   html = from_markdown('document.md', output_format='html')

   # With options
   options = HtmlRendererOptions(
       include_css=True,
       css_framework='github',
       syntax_highlighting=True,
       add_header_ids=True
   )
   html = from_markdown('document.md', output_format='html', renderer_options=options)

   # Write to file
   with open('document.html', 'w', encoding='utf-8') as f:
       f.write(html)

HTML Templates and Styling
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   # Custom CSS
   custom_css = """
   body {
       font-family: 'Georgia', serif;
       max-width: 800px;
       margin: 0 auto;
       padding: 20px;
   }
   h1 { color: #2c3e50; }
   h2 { color: #34495e; }
   code { background-color: #f4f4f4; }
   """

   options = HtmlRendererOptions(
       include_css=True,
       custom_css=custom_css,
       syntax_highlighting=True,
       add_header_ids=True,
       wrap_in_html=True  # Include <html>, <head>, <body> tags
   )

   html = from_markdown('document.md', output_format='html', renderer_options=options)

Standalone HTML Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   options = HtmlRendererOptions(
       wrap_in_html=True,
       include_css=True,
       css_framework='default',
       title='My Document',
       meta_description='A document converted from Markdown',
       syntax_highlighting=True
   )

   html = from_markdown('article.md', output_format='html', renderer_options=options)

   # Result is a complete HTML document
   with open('article.html', 'w', encoding='utf-8') as f:
       f.write(html)

Markdown to PDF
---------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.pdf import PdfRendererOptions

   # Simple conversion
   from_markdown('document.md', output_format='pdf', output_path='document.pdf')

   # With options
   options = PdfRendererOptions(
       page_size='A4',
       margin_mm=20,
       font_family='Helvetica',
       font_size=11,
       include_page_numbers=True
   )
   from_markdown('document.md', output_format='pdf', output_path='document.pdf', renderer_options=options)

PDF Styling and Layout
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_ast, from_ast
   from all2md.renderers.pdf import PdfRendererOptions

   # Parse Markdown
   doc_ast = to_ast('report.md')

   # Configure PDF rendering
   options = PdfRendererOptions(
       page_size='letter',
       margin_mm=25,
       font_family='Times-Roman',
       font_size=12,
       line_spacing=1.5,
       include_page_numbers=True,
       page_number_format='Page {page} of {total}',
       header_text='Confidential Report',
       footer_text='© 2025 Company Name'
   )

   # Render to PDF
   pdf_bytes = from_ast(doc_ast, output_format='pdf', renderer_options=options)

   # Save
   with open('formatted_report.pdf', 'wb') as f:
       f.write(pdf_bytes)

Advanced Workflows
------------------

Round-Trip Conversion
~~~~~~~~~~~~~~~~~~~~~

Convert a document through multiple formats while preserving content:

.. code-block:: python

   from all2md import to_ast, from_ast

   # Start with PDF
   original_ast = to_ast('original.pdf')

   # Convert to Markdown for editing
   markdown = from_ast(original_ast, output_format='markdown')
   with open('editable.md', 'w', encoding='utf-8') as f:
       f.write(markdown)

   # Edit markdown file manually...

   # Convert back to DOCX
   edited_ast = to_ast('editable.md')
   docx_bytes = from_ast(edited_ast, output_format='docx')
   with open('final.docx', 'wb') as f:
       f.write(docx_bytes)

Multi-Format Publishing
~~~~~~~~~~~~~~~~~~~~~~~~

Generate multiple output formats from a single Markdown source:

.. code-block:: python

   from pathlib import Path
   from all2md import to_ast, from_ast

   def publish_multiformat(markdown_path: str, output_dir: str):
       """Publish a Markdown document to multiple formats."""
       # Parse once
       doc_ast = to_ast(markdown_path)

       output_path = Path(output_dir)
       output_path.mkdir(exist_ok=True)

       stem = Path(markdown_path).stem

       # Generate DOCX
       docx_bytes = from_ast(doc_ast, output_format='docx')
       (output_path / f'{stem}.docx').write_bytes(docx_bytes)

       # Generate HTML
       html_content = from_ast(doc_ast, output_format='html')
       (output_path / f'{stem}.html').write_text(html_content, encoding='utf-8')

       # Generate PDF
       pdf_bytes = from_ast(doc_ast, output_format='pdf')
       (output_path / f'{stem}.pdf').write_bytes(pdf_bytes)

       print(f"Published {stem} to DOCX, HTML, and PDF")

   # Usage
   publish_multiformat('article.md', './output')

Transform Before Rendering
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Apply AST transforms before rendering to any format:

.. code-block:: python

   from all2md import to_ast, from_ast
   from all2md.transforms import (
       HeadingOffsetTransform,
       RemoveImagesTransform,
       AddHeadingIdsTransform
   )

   # Parse Markdown
   doc_ast = to_ast('document.md')

   # Apply transforms
   transforms = [
       HeadingOffsetTransform(offset=1),  # H1 → H2, etc.
       RemoveImagesTransform(),            # Strip images
       AddHeadingIdsTransform()            # Add IDs for TOC
   ]

   for transform in transforms:
       doc_ast = transform.transform(doc_ast)

   # Render to any format with transforms applied
   docx_bytes = from_ast(doc_ast, output_format='docx')
   html = from_ast(doc_ast, output_format='html')

Content Aggregation
~~~~~~~~~~~~~~~~~~~

Combine multiple Markdown files into a single output document:

.. code-block:: python

   from pathlib import Path
   from all2md import to_ast, from_ast
   from all2md.ast import Document
   from all2md.transforms import HeadingOffsetTransform

   def combine_markdown_files(md_files: list[str], output_format: str) -> bytes | str:
       """Combine multiple Markdown files into one document."""
       combined_children = []

       for md_file in md_files:
           # Parse each file
           doc_ast = to_ast(md_file)

           # Offset headings to make them subsections
           transformer = HeadingOffsetTransform(offset=1)
           doc_ast = transformer.transform(doc_ast)

           # Add to combined document
           combined_children.extend(doc_ast.children)

       # Create combined document
       combined_doc = Document(children=combined_children)

       # Render to desired format
       return from_ast(combined_doc, output_format=output_format)

   # Usage
   chapters = ['chapter1.md', 'chapter2.md', 'chapter3.md']
   book_pdf = combine_markdown_files(chapters, 'pdf')

   with open('book.pdf', 'wb') as f:
       f.write(book_pdf)

Supported Features by Format
-----------------------------

Feature Comparison
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 20 20 20

   * - Feature
     - DOCX
     - HTML
     - PDF
   * - Headings (H1-H6)
     - ✓
     - ✓
     - ✓
   * - Bold/Italic/Strike
     - ✓
     - ✓
     - ✓
   * - Lists (ordered/unordered)
     - ✓
     - ✓
     - ✓
   * - Tables
     - ✓
     - ✓
     - ✓
   * - Code blocks
     - ✓
     - ✓ (with highlighting)
     - ✓
   * - Inline code
     - ✓
     - ✓
     - ✓
   * - Links
     - ✓
     - ✓
     - ✓
   * - Images
     - ✓
     - ✓
     - ✓
   * - Block quotes
     - ✓
     - ✓
     - ✓
   * - Horizontal rules
     - ✓
     - ✓
     - ✓
   * - Footnotes
     - ✓
     - ✓
     - ✓
   * - Task lists
     - ✓
     - ✓
     - Partial

Limitations
~~~~~~~~~~~

**DOCX:**
- Nested tables may have layout issues
- Some advanced Markdown extensions not supported
- Image paths must be accessible at render time

**HTML:**
- No automatic styling (unless CSS provided)
- JavaScript not included
- Images embedded as ``<img>`` tags with original URLs

**PDF:**
- Limited font embedding support
- No interactive elements
- Fixed page layout (not responsive)
- Images must be accessible at render time

Best Practices
--------------

1. **Use Relative Paths for Images**

   Ensure images can be found during rendering:

   .. code-block:: python

      # Good: relative to current directory
      markdown = "![diagram](./images/diagram.png)"

      # Better: absolute paths or base64 embedding
      from all2md import to_ast
      doc_ast = to_ast(markdown)  # Resolve paths during parsing

2. **Validate AST Before Rendering**

   Check the AST structure before rendering:

   .. code-block:: python

      from all2md import to_ast
      from all2md.ast import ValidationVisitor

      doc_ast = to_ast('document.md')

      # Validate
      validator = ValidationVisitor()
      doc_ast.accept(validator)  # Raises if invalid

3. **Handle Rendering Errors Gracefully**

   .. code-block:: python

      from all2md import from_markdown
      from all2md.exceptions import MarkdownConversionError

      try:
          from_markdown('document.md', output_format='pdf', output_path='output.pdf')
      except MarkdownConversionError as e:
          print(f"Rendering failed: {e}")
          print(f"Stage: {e.conversion_stage}")

4. **Test Round-Trip Fidelity**

   For critical documents, test round-trip conversion:

   .. code-block:: python

      from all2md import to_markdown, to_ast, from_ast

      # Original
      original_md = Path('document.md').read_text()

      # Round-trip
      ast1 = to_ast('document.md')
      docx_bytes = from_ast(ast1, output_format='docx')
      ast2 = to_ast(docx_bytes, format='docx')
      roundtrip_md = from_ast(ast2, output_format='markdown')

      # Compare (note: formatting may differ)
      assert len(original_md) > 0
      assert len(roundtrip_md) > 0

Markdown to reStructuredText (RST)
-----------------------------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.rst import RestructuredTextRenderer, RstRendererOptions

   # Simple conversion
   from_markdown('document.md', output_format='rst', output_path='document.rst')

   # With options
   options = RstRendererOptions(
       heading_chars="=-~^*",           # Customize heading underlines
       table_style="grid",              # Use grid tables
       code_directive_style="directive" # Use .. code-block:: directives
   )
   from_markdown('document.md', output_format='rst', output_path='document.rst', renderer_options=options)

Bidirectional RST Support
~~~~~~~~~~~~~~~~~~~~~~~~~~

RST has full bidirectional support, enabling round-trip conversions:

.. code-block:: python

   from all2md.parsers.rst import RestructuredTextParser
   from all2md.renderers.rst import RestructuredTextRenderer
   from all2md.renderers.markdown import MarkdownRenderer

   # RST → Markdown → RST round-trip
   parser = RestructuredTextParser()
   rst_renderer = RestructuredTextRenderer()
   md_renderer = MarkdownRenderer()

   # Parse RST to AST
   doc = parser.parse('input.rst')

   # Convert to Markdown
   markdown = md_renderer.render_to_string(doc)

   # Convert back to RST
   output_rst = rst_renderer.render_to_string(doc)

Features Preserved
~~~~~~~~~~~~~~~~~~

The RST renderer preserves:

- **Headings** → RST section underlines with configurable characters
- **Inline Formatting** → Emphasis (*text*), strong (**text**), literal (``text``)
- **Lists** → Bullet and enumerated lists with nesting
- **Tables** → Grid or simple table styles
- **Code Blocks** → Literal blocks (::) or code-block directives with language
- **Definition Lists** → Term/definition structures
- **Links** → Inline and reference-style links
- **Images** → .. image:: directives with alt text
- **Block Quotes** → Indented blocks
- **Math** → Inline (:math:) and block (.. math::) directives
- **Metadata** → Docinfo blocks for author, date, etc.

Customizing RST Output
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md.renderers.rst import RestructuredTextRenderer, RstRendererOptions

   # Custom heading characters (level 1-5)
   options = RstRendererOptions(
       heading_chars="#*+=",        # Different underline chars
       table_style="simple",        # Simple tables instead of grid
       code_directive_style="double_colon",  # Use :: for code blocks
       line_length=100              # Target line wrapping
   )

   renderer = RestructuredTextRenderer(options)
   rst_output = renderer.render_to_string(doc_ast)

Round-Trip Example
~~~~~~~~~~~~~~~~~~

Complete round-trip conversion example:

.. code-block:: python

   from all2md.parsers.rst import RestructuredTextParser
   from all2md.renderers.rst import RestructuredTextRenderer, RstRendererOptions
   from pathlib import Path

   # Read original RST
   original_rst = Path('documentation.rst').read_text()

   # Parse to AST
   parser = RestructuredTextParser()
   doc = parser.parse(original_rst)

   # Apply transforms if needed
   # (e.g., modify headings, add content, etc.)

   # Render back to RST with custom options
   options = RstRendererOptions(
       heading_chars="=-~^*",
       table_style="grid"
   )
   renderer = RestructuredTextRenderer(options)
   modified_rst = renderer.render_to_string(doc)

   # Save output
   Path('documentation_modified.rst').write_text(modified_rst)

See Also
--------

- :doc:`ast_guide` - Complete AST documentation
- :doc:`formats` - Supported input formats
- :doc:`transforms` - Document transformation guide
- :doc:`recipes` - Real-world conversion patterns

API Reference
-------------

.. autofunction:: all2md.from_markdown
.. autofunction:: all2md.from_ast
.. autoclass:: all2md.renderers.docx.DocxRenderer
   :members:
.. autoclass:: all2md.renderers.html.HtmlRenderer
   :members:
.. autoclass:: all2md.renderers.pdf.PdfRenderer
   :members:
.. autoclass:: all2md.renderers.rst.RestructuredTextRenderer
   :members:
