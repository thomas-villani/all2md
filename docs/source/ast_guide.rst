Working with the AST
====================

all2md provides a powerful Abstract Syntax Tree (AST) API that enables advanced programmatic document manipulation. The AST separates document parsing from rendering, allowing you to analyze, transform, and render documents in different ways.

.. contents::
   :local:
   :depth: 2

Why Use the AST?
----------------

The AST API is useful when you need to:

* **Analyze document structure**: Extract headings, count tables, find all links
* **Transform documents**: Change heading levels, rewrite links, modify content
* **Custom rendering**: Generate different Markdown flavors from the same document
* **Programmatic manipulation**: Build, modify, and combine documents programmatically
* **Persistent storage**: Save/load document structure as JSON

The AST provides separation between:

1. **Parsing**: Converting source documents to AST
2. **Manipulation**: Working with structured document tree
3. **Rendering**: Converting AST to Markdown (or other formats)

Getting Started
---------------

Converting to AST
~~~~~~~~~~~~~~~~~

Use ``to_ast()`` to convert any supported document to an AST:

.. code-block:: python

   from all2md import to_ast

   # Convert PDF to AST
   ast_doc = to_ast("document.pdf")

   # Convert HTML to AST
   ast_doc = to_ast("webpage.html")

   # Convert DOCX to AST
   ast_doc = to_ast("report.docx")

   # With options (same as to_markdown)
   from all2md.options import PdfOptions
   ast_doc = to_ast("document.pdf", options=PdfOptions(pages=[1, 2, 3]))

The AST Document Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every AST starts with a ``Document`` node containing child nodes:

.. code-block:: python

   from all2md import to_ast

   doc = to_ast("simple.md")

   # Document properties
   print(type(doc))  # <class 'all2md.ast.nodes.Document'>
   print(doc.children)  # List of top-level nodes

   # Access child nodes
   for child in doc.children:
       print(type(child).__name__)  # Heading, Paragraph, etc.

Rendering AST to Markdown
~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``MarkdownRenderer`` to convert AST back to Markdown:

.. code-block:: python

   from all2md import to_ast
   from all2md.renderers.markdown import MarkdownRenderer

   # Convert document to AST
   doc = to_ast("document.pdf")

   # Render to Markdown
   renderer = MarkdownRenderer()
   markdown = renderer.render_to_string(doc)
   print(markdown)

   # Render with specific flavor
   from all2md.options import MarkdownRendererOptions

   options = MarkdownRendererOptions(flavor="gfm")
   renderer = MarkdownRenderer(options=options)
   gfm_markdown = renderer.render_to_string(doc)

AST Node Types
--------------

Block Nodes
~~~~~~~~~~~

Block nodes represent block-level elements:

.. code-block:: python

   from all2md.ast import (
       Document,      # Root container
       Heading,       # Headings (h1-h6)
       Paragraph,     # Text paragraphs
       CodeBlock,     # Fenced code blocks
       BlockQuote,    # Blockquotes
       List,          # Ordered/unordered lists
       ListItem,      # List items
       Table,         # Tables
       TableRow,      # Table rows
       TableCell,     # Table cells
       ThematicBreak, # Horizontal rules
       HTMLBlock      # Raw HTML blocks
   )

   # Example: Create heading programmatically
   from all2md.ast import Heading, Text

   heading = Heading(
       level=1,
       content=[Text(content="Chapter 1")]
   )

Inline Nodes
~~~~~~~~~~~~

Inline nodes represent inline formatting:

.. code-block:: python

   from all2md.ast import (
       Text,          # Plain text
       Emphasis,      # Italic/emphasis
       Strong,        # Bold/strong
       Code,          # Inline code
       Link,          # Hyperlinks
       Image,         # Images
       LineBreak,     # Line breaks
       Strikethrough, # Strikethrough text
       Underline,     # Underlined text
       Superscript,   # Superscript
       Subscript,     # Subscript
       HTMLInline     # Inline HTML
   )

   # Example: Create link programmatically
   from all2md.ast import Link, Text

   link = Link(
       url="https://example.com",
       title="Example Site",
       content=[Text(content="Click here")]
   )

Traversing the AST
------------------

Using NodeVisitor
~~~~~~~~~~~~~~~~~

The ``NodeVisitor`` pattern allows you to traverse and analyze the AST:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import NodeVisitor, Heading, Link, Image

   class DocumentAnalyzer(NodeVisitor):
       def __init__(self):
           self.headings = []
           self.links = []
           self.images = []

       def visit_heading(self, node: Heading):
           # Extract heading text
           text = ''.join(
               child.content for child in node.content
               if hasattr(child, 'content')
           )
           self.headings.append({
               'level': node.level,
               'text': text
           })
           # Continue visiting children
           self.generic_visit(node)

       def visit_link(self, node: Link):
           self.links.append({
               'url': node.url,
               'title': node.title
           })
           self.generic_visit(node)

       def visit_image(self, node: Image):
           self.images.append({
               'url': node.url,
               'alt': node.alt_text
           })
           self.generic_visit(node)

   # Analyze document
   doc = to_ast("document.pdf")
   analyzer = DocumentAnalyzer()
   doc.accept(analyzer)

   # Print results
   print(f"Found {len(analyzer.headings)} headings:")
   for h in analyzer.headings:
       print(f"  {'#' * h['level']} {h['text']}")

   print(f"\nFound {len(analyzer.links)} links:")
   for link in analyzer.links:
       print(f"  {link['url']}")

Built-in Visitors
~~~~~~~~~~~~~~~~~

all2md includes useful pre-built visitors:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import ValidationVisitor

   # Validate AST structure
   doc = to_ast("document.pdf")
   validator = ValidationVisitor()

   try:
       doc.accept(validator)
       print("AST is valid")
   except ValueError as e:
       print(f"AST validation error: {e}")

Transforming the AST
--------------------

Using NodeTransformer
~~~~~~~~~~~~~~~~~~~~~

Transform AST nodes by subclassing ``NodeTransformer``:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import NodeTransformer, Heading, MarkdownRenderer

   class IncreaseHeadingLevel(NodeTransformer):
       """Increase all heading levels by 1 (H1 -> H2, etc.)."""

       def visit_heading(self, node: Heading):
           # Don't exceed H6
           new_level = min(node.level + 1, 6)
           return Heading(
               level=new_level,
               content=self._transform_children(node.content)
           )

   # Apply transformation
   doc = to_ast("document.md")
   transformer = IncreaseHeadingLevel()
   transformed_doc = transformer.transform(doc)

   # Render transformed document
   renderer = MarkdownRenderer()
   markdown = renderer.render(transformed_doc)

Built-in Transformers
~~~~~~~~~~~~~~~~~~~~~

all2md provides commonly-used transformers:

**Heading Level Transformer:**

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import HeadingLevelTransformer, MarkdownRenderer

   doc = to_ast("document.md")

   # Increase all headings by 1 level
   transformer = HeadingLevelTransformer(offset=1)
   new_doc = transformer.transform(doc)

   # Decrease all headings by 1 level
   transformer = HeadingLevelTransformer(offset=-1)
   new_doc = transformer.transform(doc)

**Link Rewriter:**

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import LinkRewriter, MarkdownRenderer

   doc = to_ast("document.md")

   # Rewrite all links matching a pattern
   transformer = LinkRewriter(
       pattern=r'^/old-docs/',
       replacement='/new-docs/'
   )
   new_doc = transformer.transform(doc)

   # Or use a custom function
   def rewrite_link(url: str) -> str:
       if url.startswith('http://'):
           return url.replace('http://', 'https://')
       return url

   transformer = LinkRewriter(url_mapper=rewrite_link)
   new_doc = transformer.transform(doc)

**Text Replacer:**

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import TextReplacer

   doc = to_ast("document.md")

   # Replace text across all text nodes
   transformer = TextReplacer(
       pattern=r'\bcompany_name\b',
       replacement='Acme Corporation'
   )
   new_doc = transformer.transform(doc)

Filtering Nodes
~~~~~~~~~~~~~~~

Extract or remove specific node types:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import filter_nodes, extract_nodes, Heading, Image

   doc = to_ast("document.pdf")

   # Remove all images
   doc_without_images = filter_nodes(
       doc,
       lambda node: not isinstance(node, Image)
   )

   # Extract all headings
   headings = extract_nodes(doc, Heading)
   for heading in headings:
       print(f"Level {heading.level}: {heading.content}")

   # Extract multiple types
   from all2md.ast import Link
   links_and_images = extract_nodes(doc, (Link, Image))

Collecting Nodes
~~~~~~~~~~~~~~~~

Use ``extract_nodes()`` to gather specific node types:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import extract_nodes, Heading, Table

   doc = to_ast("report.pdf")

   # Extract all headings
   headings = extract_nodes(doc, Heading)
   print(f"Found {len(headings)} headings")

   # Extract all tables
   tables = extract_nodes(doc, Table)
   print(f"Found {len(tables)} tables")

For advanced filtering, use ``NodeCollector`` with a custom predicate:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import NodeCollector, Heading

   doc = to_ast("report.pdf")

   # Collect headings with custom predicate
   collector = NodeCollector(predicate=lambda n: isinstance(n, Heading) and n.level <= 2)
   doc.accept(collector)
   print(f"Found {len(collector.collected)} top-level headings")

Building AST Programmatically
------------------------------

Creating Documents from Scratch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build documents programmatically using AST nodes:

.. code-block:: python

   from all2md.ast import (
       Document, Heading, Paragraph, Text,
       Strong, Emphasis, Link, CodeBlock,
       MarkdownRenderer
   )

   # Build document structure
   doc = Document(children=[
       Heading(level=1, content=[Text(content="User Guide")]),

       Paragraph(content=[
           Text(content="Welcome to "),
           Strong(content=[Text(content="all2md")]),
           Text(content=", a powerful document converter.")
       ]),

       Heading(level=2, content=[Text(content="Installation")]),

       CodeBlock(
           language="bash",
           content="pip install all2md[pdf]"
       ),

       Paragraph(content=[
           Text(content="For more information, visit "),
           Link(
               url="https://all2md.readthedocs.io",
               content=[Text(content="the documentation")]
           ),
           Text(content=".")
       ])
   ])

   # Render to Markdown
   renderer = MarkdownRenderer()
   markdown = renderer.render(doc)
   print(markdown)

Using Document Builders
~~~~~~~~~~~~~~~~~~~~~~~

all2md provides builders for complex structures:

**TableBuilder:**

.. code-block:: python

   from all2md.ast import TableBuilder, Text, MarkdownRenderer

   # Build table programmatically
   builder = TableBuilder()

   # Add header row
   builder.add_row(
       [Text(content="Name"), Text(content="Age"), Text(content="City")],
       is_header=True,
       alignments=[None, 'right', 'left']
   )

   # Add data rows
   builder.add_row([
       Text(content="Alice"),
       Text(content="30"),
       Text(content="New York")
   ])
   builder.add_row([
       Text(content="Bob"),
       Text(content="25"),
       Text(content="San Francisco")
   ])

   # Get table
   table = builder.get_table()

   # Render
   renderer = MarkdownRenderer()
   markdown = renderer.render(table)

**ListBuilder:**

.. code-block:: python

   from all2md.ast import ListBuilder, Text

   # Build nested list
   builder = ListBuilder()

   builder.add_item(level=1, ordered=False, content=[Text(content="Python")])
   builder.add_item(level=1, ordered=False, content=[Text(content="JavaScript")])

   # Add nested items (level 2)
   builder.add_item(level=2, ordered=True, content=[Text(content="ES6")])
   builder.add_item(level=2, ordered=True, content=[Text(content="TypeScript")])

   # Back to top level
   builder.add_item(level=1, ordered=False, content=[Text(content="Rust")])

   doc = builder.get_document()
   list_node = doc.children[0]

**DocumentBuilder:**

.. code-block:: python

   from all2md.ast import DocumentBuilder, Text

   # Fluent API for building documents
   builder = DocumentBuilder()

   (builder
       .add_heading(1, [Text(content="Title")])
       .add_paragraph([Text(content="Introduction paragraph.")])
       .add_heading(2, [Text(content="Section 1")])
       .add_paragraph([Text(content="Content here.")])
   )

   doc = builder.get_document()

Merging Documents
~~~~~~~~~~~~~~~~~

Combine multiple documents into one:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import merge_documents, MarkdownRenderer

   # Convert multiple documents
   doc1 = to_ast("chapter1.md")
   doc2 = to_ast("chapter2.md")
   doc3 = to_ast("chapter3.md")

   # Merge into single document
   combined = merge_documents([doc1, doc2, doc3])

   # Render combined document
   renderer = MarkdownRenderer()
   markdown = renderer.render(combined)

AST Serialization
-----------------

Saving AST as JSON
~~~~~~~~~~~~~~~~~~

Persist AST structure for later use:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import ast_to_json, json_to_ast
   from pathlib import Path

   # Convert document to AST
   doc = to_ast("document.pdf")

   # Save as JSON
   json_str = ast_to_json(doc)
   Path("document.ast.json").write_text(json_str)

   # Later: load from JSON
   loaded_json = Path("document.ast.json").read_text()
   restored_doc = json_to_ast(loaded_json)

   # Render restored document
   from all2md.ast import MarkdownRenderer
   renderer = MarkdownRenderer()
   markdown = renderer.render(restored_doc)

Dictionary Format
~~~~~~~~~~~~~~~~~

Work with AST as dictionaries:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import ast_to_dict, dict_to_ast

   doc = to_ast("document.md")

   # Convert to dictionary
   doc_dict = ast_to_dict(doc)

   # Inspect structure
   print(doc_dict.keys())  # ['type', 'children', ...]

   # Modify dictionary
   doc_dict['metadata'] = {'author': 'Jane Doe'}

   # Restore to AST
   modified_doc = dict_to_ast(doc_dict)

Markdown Flavors
----------------

Rendering Different Flavors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Render the same AST in different Markdown dialects:

.. code-block:: python

   from all2md import to_ast
   from all2md.renderers.markdown import MarkdownRenderer
   from all2md.utils.flavors import (
       GFMFlavor,
       CommonMarkFlavor,
       MarkdownPlusFlavor
   )

   doc = to_ast("document.pdf")

   # GitHub Flavored Markdown
   gfm_renderer = MarkdownRenderer(flavor=GFMFlavor())
   gfm_md = gfm_renderer.render(doc)

   # CommonMark (strict)
   cm_renderer = MarkdownRenderer(flavor=CommonMarkFlavor())
   cm_md = cm_renderer.render(doc)

   # Markdown Plus (extended features)
   mdp_renderer = MarkdownRenderer(flavor=MarkdownPlusFlavor())
   mdp_md = mdp_renderer.render(doc)

Flavor Differences
~~~~~~~~~~~~~~~~~~

Different flavors support different features:

.. code-block:: python

   from all2md.utils.flavors import GFMFlavor, CommonMarkFlavor

   # GFM supports:
   # - Tables
   # - Strikethrough
   # - Task lists
   # - Automatic URL linking

   # CommonMark supports:
   # - Core Markdown only
   # - No tables (rendered as HTML)
   # - No strikethrough (rendered as HTML)
   # - Strict spec compliance

Practical Examples
------------------

Example 1: Generate Table of Contents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extract headings and build TOC:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import NodeVisitor, Heading
   from all2md.ast.utils import extract_text

   class TOCGenerator(NodeVisitor):
       def __init__(self):
           self.toc = []

       def visit_heading(self, node: Heading):
           # Extract text from heading using official utility
           text = extract_text(node.content)

           # Create anchor from text
           anchor = text.lower().replace(' ', '-')

           # Add to TOC with indentation
           indent = '  ' * (node.level - 1)
           self.toc.append(f"{indent}- [{text}](#{anchor})")

           self.generic_visit(node)

   # Generate TOC
   doc = to_ast("document.pdf")
   generator = TOCGenerator()
   doc.accept(generator)

   print("# Table of Contents\n")
   print('\n'.join(generator.toc))

Example 2: Document Statistics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyze document content:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import NodeVisitor, Heading, Paragraph, Table, Image, Link
   from all2md.ast.utils import extract_text

   class DocumentStats(NodeVisitor):
       def __init__(self):
           self.stats = {
               'headings': [],
               'paragraphs': 0,
               'tables': 0,
               'images': 0,
               'links': 0,
               'words': 0
           }

       def visit_heading(self, node: Heading):
           text = extract_text(node.content)
           self.stats['headings'].append({
               'level': node.level,
               'text': text
           })
           self.generic_visit(node)

       def visit_paragraph(self, node: Paragraph):
           self.stats['paragraphs'] += 1
           # Count words
           text = extract_text(node.content)
           self.stats['words'] += len(text.split())
           self.generic_visit(node)

       def visit_table(self, node: Table):
           self.stats['tables'] += 1
           self.generic_visit(node)

       def visit_image(self, node: Image):
           self.stats['images'] += 1
           self.generic_visit(node)

       def visit_link(self, node: Link):
           self.stats['links'] += 1
           self.generic_visit(node)

   # Analyze document
   doc = to_ast("report.pdf")
   stats = DocumentStats()
   doc.accept(stats)

   print(f"Document Statistics:")
   print(f"  Headings: {len(stats.stats['headings'])}")
   print(f"  Paragraphs: {stats.stats['paragraphs']}")
   print(f"  Tables: {stats.stats['tables']}")
   print(f"  Images: {stats.stats['images']}")
   print(f"  Links: {stats.stats['links']}")
   print(f"  Words: {stats.stats['words']}")

Example 3: Batch Link Rewriting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Update links across multiple documents:

.. code-block:: python

   from pathlib import Path
   from all2md import to_ast
   from all2md.ast import LinkRewriter, MarkdownRenderer

   def migrate_documentation(source_dir: Path, output_dir: Path):
       """Migrate documentation with updated links."""

       # Define link rewriting rules
       def rewrite_docs_links(url: str) -> str:
           # Update old documentation links
           if url.startswith('/v1/docs/'):
               return url.replace('/v1/docs/', '/v2/docs/')
           # Update HTTP to HTTPS
           if url.startswith('http://'):
               return url.replace('http://', 'https://')
           return url

       transformer = LinkRewriter(url_mapper=rewrite_docs_links)
       renderer = MarkdownRenderer()

       # Process all markdown files
       for md_file in source_dir.glob('**/*.md'):
           # Convert to AST
           doc = to_ast(md_file)

           # Transform links
           updated_doc = transformer.transform(doc)

           # Render to Markdown
           markdown = renderer.render(updated_doc)

           # Save to output directory
           output_file = output_dir / md_file.relative_to(source_dir)
           output_file.parent.mkdir(parents=True, exist_ok=True)
           output_file.write_text(markdown)

           print(f"Migrated: {md_file}")

   # Run migration
   migrate_documentation(
       source_dir=Path('./old-docs'),
       output_dir=Path('./new-docs')
   )

Example 4: Custom Renderer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a custom renderer for specific output:

.. code-block:: python

   from all2md import to_ast
   from all2md.ast import NodeVisitor, Heading, Paragraph, Strong, Emphasis, Text

   class PlainTextRenderer(NodeVisitor):
       """Render AST as plain text (no formatting)."""

       def __init__(self):
           self.output = []

       def visit_heading(self, node: Heading):
           # Add heading text with level prefix
           text = self._extract_text(node.content)
           prefix = '#' * node.level
           self.output.append(f"{prefix} {text}\n")

       def visit_paragraph(self, node: Paragraph):
           text = self._extract_text(node.content)
           self.output.append(f"{text}\n\n")

       def visit_text(self, node: Text):
           # Plain text nodes handled in _extract_text
           pass

       def _extract_text(self, nodes):
           text = []
           for node in nodes:
               if isinstance(node, Text):
                   text.append(node.content)
               elif isinstance(node, (Strong, Emphasis)):
                   text.append(self._extract_text(node.content))
               elif hasattr(node, 'content') and isinstance(node.content, list):
                   text.append(self._extract_text(node.content))
           return ''.join(text)

       def render(self, doc):
           doc.accept(self)
           return ''.join(self.output)

   # Use custom renderer
   doc = to_ast("document.pdf")
   renderer = PlainTextRenderer()
   plain_text = renderer.render(doc)
   print(plain_text)

Best Practices
--------------

Performance Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **AST Conversion**: Converting to AST has overhead. Use ``to_markdown()`` directly if you don't need AST features.

2. **Transformation**: Clone nodes only when necessary. Transformers create new trees by default.

3. **Serialization**: JSON serialization is best for persistence, not real-time processing.

Error Handling
~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_ast, FormatError
   from all2md.ast import ValidationVisitor

   try:
       doc = to_ast("document.pdf")

       # Validate structure
       validator = ValidationVisitor()
       doc.accept(validator)

   except FormatError as e:
       print(f"Unsupported format: {e}")
   except ValueError as e:
       print(f"Invalid AST structure: {e}")

Thread Safety
~~~~~~~~~~~~~

AST nodes are immutable by default. Transformations create new trees. This makes the AST safe for concurrent processing:

.. code-block:: python

   from concurrent.futures import ThreadPoolExecutor
   from all2md import to_ast
   from all2md.ast import HeadingLevelTransformer, MarkdownRenderer

   def transform_document(file_path):
       doc = to_ast(file_path)
       transformer = HeadingLevelTransformer(offset=1)
       new_doc = transformer.transform(doc)
       renderer = MarkdownRenderer()
       return renderer.render(new_doc)

   # Safe concurrent processing
   files = ['doc1.pdf', 'doc2.pdf', 'doc3.pdf']
   with ThreadPoolExecutor() as executor:
       results = list(executor.map(transform_document, files))

For more examples, see the :doc:`recipes` cookbook. For API reference, see :doc:`api/all2md.ast`.
