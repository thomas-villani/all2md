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
   from_markdown('document.md', target_format='docx', output='document.docx')

   # Convert Markdown to HTML
   from_markdown('document.md', target_format='html', output='document.html')

   # Convert Markdown to PDF
   from_markdown('document.md', target_format='pdf', output='document.pdf')

   # Convert Markdown to EPUB
   from_markdown('book.md', target_format='epub', output='book.epub')

   # Convert Markdown to PowerPoint
   from_markdown('slides.md', target_format='pptx', output='presentation.pptx')

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
   docx_bytes = from_ast(doc_ast, target_format='docx')
   html_string = from_ast(doc_ast, target_format='html')

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
   from_markdown('report.md', target_format='docx', output='report.docx')

   # With options
   options = DocxRendererOptions(
       preserve_formatting=True,
       default_font='Arial',
       default_font_size=12
   )
   from_markdown('report.md', target_format='docx', output='report.docx', renderer_options=options)

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
       target_format='docx',
       output='annual_report.docx'
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
       code_font='Courier New',
       code_font_size=10,
       table_style='Light Grid Accent 1',
       use_styles=True
   )

   # Render to DOCX
   docx_bytes = from_ast(doc_ast, target_format='docx', renderer_options=options)

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
   html = from_markdown('document.md', target_format='html')

   # With options
   options = HtmlRendererOptions(
       standalone=True,
       css_style='embedded',
       syntax_highlighting=True,
       include_toc=False
   )
   html = from_markdown('document.md', target_format='html', renderer_options=options)

   # Write to file
   with open('document.html', 'w', encoding='utf-8') as f:
       f.write(html)

HTML Templates and Styling
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   # Custom CSS file
   # Create a custom.css file with your styles:
   # body { font-family: 'Georgia', serif; max-width: 800px; }
   # h1 { color: #2c3e50; }
   # h2 { color: #34495e; }
   # code { background-color: #f4f4f4; }

   options = HtmlRendererOptions(
       standalone=True,
       css_style='external',
       css_file='custom.css',
       syntax_highlighting=True,
       escape_html=True
   )

   html = from_markdown('document.md', target_format='html', renderer_options=options)

Standalone HTML Documents
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.html import HtmlRendererOptions

   options = HtmlRendererOptions(
       standalone=True,
       css_style='embedded',
       syntax_highlighting=True,
       include_toc=True,
       math_renderer='mathjax'
   )

   html = from_markdown('article.md', target_format='html', renderer_options=options)

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
   from_markdown('document.md', target_format='pdf', output='document.pdf')

   # With options
   options = PdfRendererOptions(
       page_size='a4',
       margin_top=72.0,  # 1 inch (72 points)
       margin_bottom=72.0,
       font_name='Helvetica',
       font_size=11,
       include_page_numbers=True
   )
   from_markdown('document.md', target_format='pdf', output='document.pdf', renderer_options=options)

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
       margin_top=72.0,  # 1 inch in points
       margin_bottom=72.0,
       margin_left=72.0,
       margin_right=72.0,
       font_name='Times-Roman',
       font_size=12,
       line_spacing=1.5,
       include_page_numbers=True,
       include_toc=False
   )

   # Render to PDF
   pdf_bytes = from_ast(doc_ast, target_format='pdf', renderer_options=options)

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
   markdown = from_ast(original_ast, target_format='markdown')
   with open('editable.md', 'w', encoding='utf-8') as f:
       f.write(markdown)

   # Edit markdown file manually...

   # Convert back to DOCX
   edited_ast = to_ast('editable.md')
   docx_bytes = from_ast(edited_ast, target_format='docx')
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
       docx_bytes = from_ast(doc_ast, target_format='docx')
       (output_path / f'{stem}.docx').write_bytes(docx_bytes)

       # Generate HTML
       html_content = from_ast(doc_ast, target_format='html')
       (output_path / f'{stem}.html').write_text(html_content, encoding='utf-8')

       # Generate PDF
       pdf_bytes = from_ast(doc_ast, target_format='pdf')
       (output_path / f'{stem}.pdf').write_bytes(pdf_bytes)

       # Generate EPUB
       from all2md.renderers.epub import EpubRendererOptions
       epub_options = EpubRendererOptions(title=stem, generate_toc=True)
       from_ast(doc_ast, target_format='epub', output=output_path / f'{stem}.epub', renderer_options=epub_options)

       # Generate PPTX
       from_ast(doc_ast, target_format='pptx', output=output_path / f'{stem}.pptx')

       print(f"Published {stem} to DOCX, HTML, PDF, EPUB, and PPTX")

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
   docx_bytes = from_ast(doc_ast, target_format='docx')
   html = from_ast(doc_ast, target_format='html')

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
       return from_ast(combined_doc, target_format=output_format)

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
   :widths: 25 12 12 12 12 12 15

   * - Feature
     - DOCX
     - HTML
     - PDF
     - EPUB
     - PPTX
     - RST
   * - Headings (H1-H6)
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Bold/Italic/Strike
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Lists (ordered/unordered)
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Tables
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Code blocks
     - ✓
     - ✓ (highlighting)
     - ✓
     - ✓
     - ✓
     - ✓
   * - Inline code
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Links
     - ✓
     - ✓
     - ✓
     - ✓
     - Partial
     - ✓
   * - Images
     - ✓
     - ✓
     - ✓
     - ✓
     - Partial
     - ✓
   * - Block quotes
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Horizontal rules
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
   * - Footnotes
     - ✓
     - ✓
     - ✓
     - ✓
     - ✗
     - ✓
   * - Task lists
     - ✓
     - ✓
     - Partial
     - ✓
     - ✗
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

**EPUB:**
- Images must be accessible at render time
- Limited styling control (depends on ereader)
- Chapter splitting required for logical structure

**PPTX:**
- Images not yet fully supported
- Links rendered as plain text
- Limited layout customization without templates
- Font availability depends on system

**RST:**
- Some advanced Markdown extensions may not have RST equivalents
- Directive syntax may differ from original

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
      from all2md.exceptions import RenderingError

      try:
          from_markdown('document.md', target_format='pdf', output='output.pdf')
      except RenderingError as e:
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
      docx_bytes = from_ast(ast1, target_format='docx')
      ast2 = to_ast(docx_bytes, format='docx')
      roundtrip_md = from_ast(ast2, target_format='markdown')

      # Compare (note: formatting may differ)
      assert len(original_md) > 0
      assert len(roundtrip_md) > 0

Markdown to EPUB
-----------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.epub import EpubRendererOptions

   # Simple conversion
   from_markdown('book.md', target_format='epub', output='book.epub')

   # With metadata
   options = EpubRendererOptions(
       title="My Book",
       author="John Doe",
       language="en",
       generate_toc=True
   )
   from_markdown('book.md', target_format='epub', output='book.epub', renderer_options=options)

Chapter Splitting Strategies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

EPUB documents are organized into chapters. all2md supports three strategies for splitting content into chapters:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.epub import EpubRendererOptions

   # Strategy 1: Split by thematic breaks (---)
   # Best for: Markdown with explicit separators between chapters
   options = EpubRendererOptions(
       chapter_split_mode="separator",
       title="My Novel"
   )
   from_markdown('novel.md', target_format='epub', output='novel.epub', renderer_options=options)

   # Strategy 2: Split by heading level
   # Best for: Structured documents with H1 or H2 chapter markers
   options = EpubRendererOptions(
       chapter_split_mode="heading",
       chapter_split_heading_level=1,  # Split on H1 headings
       use_heading_as_chapter_title=True
   )
   from_markdown('book.md', target_format='epub', output='book.epub', renderer_options=options)

   # Strategy 3: Auto-detect (default)
   # Prefers separators if present, falls back to headings
   options = EpubRendererOptions(chapter_split_mode="auto")
   from_markdown('content.md', target_format='epub', output='content.epub', renderer_options=options)

Example with Multiple Chapters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.epub import EpubRendererOptions

   # Markdown with explicit chapter separators
   markdown_content = """
   # Chapter 1: The Beginning

   It was a dark and stormy night...

   ---

   # Chapter 2: The Journey

   The next morning, our hero set out on their quest...

   ---

   # Chapter 3: The End

   And they lived happily ever after.
   """

   options = EpubRendererOptions(
       title="My Short Story",
       author="Jane Author",
       chapter_split_mode="separator",  # Split on ---
       generate_toc=True
   )

   from_markdown(markdown_content, target_format='epub', output='story.epub', renderer_options=options)

Advanced EPUB Options
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_ast, from_ast
   from all2md.renderers.epub import EpubRendererOptions

   # Parse Markdown
   doc_ast = to_ast('manuscript.md')

   # Configure EPUB rendering
   options = EpubRendererOptions(
       title="Technical Manual",
       author="Expert Team",
       language="en",
       identifier="urn:isbn:978-0-123456-78-9",  # ISBN or unique ID
       chapter_split_mode="heading",
       chapter_split_heading_level=1,
       chapter_title_template="Chapter {num}",
       use_heading_as_chapter_title=True,
       generate_toc=True
   )

   # Render to EPUB
   from_ast(doc_ast, target_format='epub', output='manual.epub', renderer_options=options)

EPUB Features
~~~~~~~~~~~~~

The EPUB renderer supports:

- **Chapter Organization** - Automatic chapter splitting with configurable strategies
- **Table of Contents** - Auto-generated navigation (NCX and nav.xhtml)
- **Metadata** - Title, author, language, ISBN, and Dublin Core fields
- **Rich Content** - Tables, code blocks, lists, images, formatting
- **EPUB3 Standard** - Modern EPUB3 format with proper structure

Markdown to PowerPoint (PPTX)
-------------------------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.pptx import PptxRendererOptions

   # Simple conversion
   from_markdown('presentation.md', target_format='pptx', output='presentation.pptx')

   # With custom fonts
   options = PptxRendererOptions(
       default_font="Arial",
       default_font_size=20,
       title_font_size=36
   )
   from_markdown('slides.md', target_format='pptx', output='slides.pptx', renderer_options=options)

Slide Splitting Strategies
~~~~~~~~~~~~~~~~~~~~~~~~~~~

PowerPoint presentations are organized into slides. all2md supports three strategies for splitting content into slides:

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.pptx import PptxRendererOptions

   # Strategy 1: Split by thematic breaks (---)
   # Best for: Markdown with explicit separators between slides
   options = PptxRendererOptions(slide_split_mode="separator")
   from_markdown('deck.md', target_format='pptx', output='deck.pptx', renderer_options=options)

   # Strategy 2: Split by heading level
   # Best for: Structured presentations with H2 slide markers
   options = PptxRendererOptions(
       slide_split_mode="heading",
       slide_split_heading_level=2,  # Split on H2 headings (common pattern)
       use_heading_as_slide_title=True
   )
   from_markdown('presentation.md', target_format='pptx', output='presentation.pptx', renderer_options=options)

   # Strategy 3: Auto-detect (default)
   # Prefers separators if present, falls back to headings
   options = PptxRendererOptions(slide_split_mode="auto")
   from_markdown('slides.md', target_format='pptx', output='slides.pptx', renderer_options=options)

Example Presentation
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.pptx import PptxRendererOptions

   # Markdown for a presentation
   markdown_content = """
   # Welcome to Our Product

   A revolutionary new solution

   ---

   ## Key Features

   - Fast performance
   - Easy to use
   - Secure by default

   ---

   ## Technical Specs

   | Feature | Value |
   |---------|-------|
   | Speed   | 10x faster |
   | Memory  | 50% less |

   ---

   ## Get Started Today

   Visit our website for more information
   """

   options = PptxRendererOptions(
       slide_split_mode="separator",  # Split on ---
       use_heading_as_slide_title=True,
       default_font_size=24,
       title_font_size=44
   )

   from_markdown(markdown_content, target_format='pptx', output='product.pptx', renderer_options=options)

Advanced PPTX Options
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_ast, from_ast
   from all2md.renderers.pptx import PptxRendererOptions

   # Parse Markdown
   doc_ast = to_ast('quarterly_review.md')

   # Configure PPTX rendering
   options = PptxRendererOptions(
       slide_split_mode="heading",
       slide_split_heading_level=2,
       default_layout="Title and Content",
       title_slide_layout="Title Slide",
       use_heading_as_slide_title=True,
       template_path="corporate_template.pptx",  # Use custom template
       default_font="Calibri",
       default_font_size=18,
       title_font_size=36
   )

   # Render to PPTX
   from_ast(doc_ast, target_format='pptx', output='review.pptx', renderer_options=options)

PPTX Features
~~~~~~~~~~~~~

The PPTX renderer supports:

- **Slide Organization** - Automatic slide splitting with configurable strategies
- **Text Formatting** - Bold, italic, code, inline formatting
- **Lists** - Bullet points and numbered lists
- **Tables** - Data tables with headers
- **Code Blocks** - Syntax highlighting with monospace font
- **Custom Layouts** - Support for PowerPoint templates
- **Font Customization** - Configure fonts and sizes

Markdown to reStructuredText (RST)
-----------------------------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import from_markdown
   from all2md.renderers.rst import RestructuredTextRenderer, RstRendererOptions

   # Simple conversion
   from_markdown('document.md', target_format='rst', output='document.rst')

   # With options
   options = RstRendererOptions(
       heading_chars="=-~^*",           # Customize heading underlines
       table_style="grid",              # Use grid tables
       code_directive_style="directive" # Use .. code-block:: directives
   )
   from_markdown('document.md', target_format='rst', output='document.rst', renderer_options=options)

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
.. autoclass:: all2md.renderers.epub.EpubRenderer
   :members:
.. autoclass:: all2md.renderers.pptx.PptxRenderer
   :members:
.. autoclass:: all2md.renderers.rst.RestructuredTextRenderer
   :members:
