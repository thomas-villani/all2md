AST Transforms and Hooks
========================

The **all2md** transform system provides a powerful plugin architecture for manipulating document ASTs (Abstract Syntax Trees) with hooks. Transforms enable custom document processing workflows without forking the library.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

Transforms allow you to:

- **Filter content**: Remove images, tables, or other elements
- **Modify structure**: Adjust heading levels, rewrite links
- **Add metadata**: Inject timestamps, word counts, IDs
- **Clean up**: Remove boilerplate text, deduplicate content
- **Enrich**: Generate table of contents, add watermarks

The transform system uses Python entry points for plugin discovery, making it easy to create and distribute third-party transforms.

Quick Start
-----------

Using Transforms
~~~~~~~~~~~~~~~~

Apply transforms during document conversion:

.. code-block:: python

   from all2md import to_markdown
   from all2md.transforms import RemoveImagesTransform, HeadingOffsetTransform

   markdown = to_markdown(
       'document.pdf',
       transforms=[
           RemoveImagesTransform(),
           HeadingOffsetTransform(offset=1)
       ]
   )

Or use transform names (requires entry point registration):

.. code-block:: python

   from all2md import to_ast
   from all2md.transforms import render

   doc = to_ast('document.pdf')
   markdown = render(doc, transforms=['remove-images', 'heading-offset'])

From the CLI:

.. code-block:: bash

   # Single transform
   all2md document.pdf --transform remove-images

   # Multiple transforms with parameters
   all2md document.pdf \
       --transform heading-offset --heading-offset 1 \
       --transform remove-images

   # List available transforms
   all2md list-transforms

Creating a Transform
~~~~~~~~~~~~~~~~~~~~

Create a simple transform by inheriting from ``NodeTransformer``:

.. code-block:: python

   from all2md.ast.transforms import NodeTransformer
   from all2md.ast import Image

   class RemoveImagesTransform(NodeTransformer):
       """Remove all images from the document."""

       def visit_image(self, node: Image) -> None:
           # Return None to remove the node
           return None

Built-in Transforms
-------------------

remove-images
~~~~~~~~~~~~~

Remove all Image nodes from the document.

.. code-block:: python

   from all2md.transforms import RemoveImagesTransform

   transform = RemoveImagesTransform()

CLI usage:

.. code-block:: bash

   all2md document.pdf --transform remove-images

remove-nodes
~~~~~~~~~~~~

Remove nodes of specified types.

.. code-block:: python

   from all2md.transforms import RemoveNodesTransform

   transform = RemoveNodesTransform(node_types=['image', 'table', 'code_block'])

CLI usage:

.. code-block:: bash

   all2md document.pdf --transform remove-nodes --node-types image table

heading-offset
~~~~~~~~~~~~~~

Shift heading levels by a specified offset. Levels are clamped to 1-6.

.. code-block:: python

   from all2md.transforms import HeadingOffsetTransform

   # H1 becomes H2, H2 becomes H3, etc.
   transform = HeadingOffsetTransform(offset=1)

   # H2 becomes H1, H3 becomes H2, etc.
   transform = HeadingOffsetTransform(offset=-1)

CLI usage:

.. code-block:: bash

   all2md document.pdf --transform heading-offset --heading-offset 1

link-rewriter
~~~~~~~~~~~~~

Rewrite link URLs using regex patterns with capture group support.

.. code-block:: python

   from all2md.transforms import LinkRewriterTransform

   # Rewrite relative links to absolute
   transform = LinkRewriterTransform(
       pattern=r'^/docs/',
       replacement='https://example.com/docs/'
   )

   # Use capture groups
   transform = LinkRewriterTransform(
       pattern=r'^/docs/(.+)$',
       replacement=r'https://example.com/documentation/\1'
   )

CLI usage:

.. code-block:: bash

   all2md document.pdf \
       --transform link-rewriter \
       --link-pattern "^/docs/" \
       --link-replacement "https://example.com/docs/"

text-replacer
~~~~~~~~~~~~~

Find and replace text in all Text nodes.

.. code-block:: python

   from all2md.transforms import TextReplacerTransform

   transform = TextReplacerTransform(find="TODO", replace="DONE")

CLI usage:

.. code-block:: bash

   all2md document.pdf \
       --transform text-replacer \
       --find-text "TODO" \
       --replace-text "DONE"

add-heading-ids
~~~~~~~~~~~~~~~

Generate unique IDs for all headings, useful for creating anchors and table of contents.

.. code-block:: python

   from all2md.transforms import AddHeadingIdsTransform

   # Basic usage
   transform = AddHeadingIdsTransform()

   # With prefix and custom separator
   transform = AddHeadingIdsTransform(
       id_prefix="doc-",
       separator="_"
   )

The transform:

- Converts heading text to slugs (lowercase, spaces to separator)
- Removes special characters
- Handles duplicates by appending numbers
- Adds IDs to node metadata

CLI usage:

.. code-block:: bash

   all2md document.pdf \
       --transform add-heading-ids \
       --heading-id-prefix "doc-"

remove-boilerplate
~~~~~~~~~~~~~~~~~~

Remove paragraphs matching common boilerplate patterns.

.. code-block:: python

   from all2md.transforms import RemoveBoilerplateTextTransform

   # Use default patterns
   transform = RemoveBoilerplateTextTransform()

   # Custom patterns
   transform = RemoveBoilerplateTextTransform(
       patterns=[
           r'^CONFIDENTIAL$',
           r'^Page \d+ of \d+$',
           r'^DRAFT$'
       ]
   )

Default patterns include:
- ``^CONFIDENTIAL$`` (case-insensitive)
- ``^Page \d+ of \d+$``
- ``^Internal Use Only$``
- ``^\[DRAFT\]$``

CLI usage:

.. code-block:: bash

   all2md document.pdf --transform remove-boilerplate

add-timestamp
~~~~~~~~~~~~~

Add conversion timestamp to document metadata.

.. code-block:: python

   from all2md.transforms import AddConversionTimestampTransform

   # ISO format (default)
   transform = AddConversionTimestampTransform()

   # Unix timestamp
   transform = AddConversionTimestampTransform(format="unix")

   # Custom strftime format
   transform = AddConversionTimestampTransform(
       format="%Y-%m-%d %H:%M:%S",
       field_name="converted_at"
   )

CLI usage:

.. code-block:: bash

   all2md document.pdf \
       --transform add-timestamp \
       --timestamp-format "iso"

word-count
~~~~~~~~~~

Calculate word and character counts and add to document metadata.

.. code-block:: python

   from all2md.transforms import CalculateWordCountTransform

   transform = CalculateWordCountTransform()

   # Custom field names
   transform = CalculateWordCountTransform(
       word_field="words",
       char_field="characters"
   )

CLI usage:

.. code-block:: bash

   all2md document.pdf --transform word-count

add-attachment-footnotes
~~~~~~~~~~~~~~~~~~~~~~~~

Convert attachment references (typically produced by ``attachment_mode=alt_text`` with ``alt_text_mode="footnote"``)
into numbered footnotes so readers can find the extracted assets.

.. code-block:: python

   from all2md.transforms import AddAttachmentFootnotesTransform

   transform = AddAttachmentFootnotesTransform(section_title="Referenced Assets")

CLI usage:

.. code-block:: bash

   all2md document.pdf \
     --attachment-mode alt_text \
     --alt-text-mode footnote \
     --transform add-attachment-footnotes \
     --attachment-section-title "Referenced Assets"

Use ``--add-image-footnotes`` or ``--add-link-footnotes`` to toggle which references receive footnote definitions.

generate-toc
~~~~~~~~~~~~

Generate a table of contents from document headings.

.. code-block:: python

   from all2md.transforms import GenerateTocTransform

   # Basic usage - adds TOC at top of document
   transform = GenerateTocTransform()

   # Custom configuration
   transform = GenerateTocTransform(
       title="Table of Contents",
       max_depth=3,
       position="top",
       add_links=True,
       separator="-"
   )

**Parameters:**

* ``title`` (str, default="Table of Contents") - Title for the TOC section
* ``max_depth`` (int, default=3) - Maximum heading level to include (1-6)
* ``position`` ("top" or "bottom", default="top") - Position to insert the TOC
* ``add_links`` (bool, default=True) - Whether to create links to headings (requires heading IDs)
* ``separator`` (str, default="-") - Separator for generating heading IDs when not present

CLI usage:

.. code-block:: bash

   # Generate TOC at top of document
   all2md document.pdf --transform generate-toc

   # Custom TOC configuration
   all2md document.pdf \
       --transform generate-toc \
       --toc-title "Contents" \
       --toc-max-depth 2 \
       --toc-position bottom

Creating Custom Transforms
---------------------------

The NodeTransformer Pattern
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All transforms inherit from ``NodeTransformer`` and use the visitor pattern:

.. code-block:: python

   from all2md.ast.transforms import NodeTransformer
   from all2md.ast import Heading, Paragraph, Text, Image

   class MyTransform(NodeTransformer):
       """Example transform."""

       def visit_heading(self, node: Heading) -> Heading:
           # Called for each Heading node
           # Process children first
           node = super().visit_heading(node)

           # Modify the node
           # ...

           return node

       def visit_paragraph(self, node: Paragraph) -> Paragraph | None:
           node = super().visit_paragraph(node)

           # Return None to remove the node
           if should_remove(node):
               return None

           return node

Visitor Method Naming
~~~~~~~~~~~~~~~~~~~~~

Visitor methods follow the pattern ``visit_<node_type_lowercase>``:

- ``Heading`` → ``visit_heading()``
- ``Paragraph`` → ``visit_paragraph()``
- ``CodeBlock`` → ``visit_code_block()``
- ``TableCell`` → ``visit_table_cell()``

Available node types include: Document, Heading, Paragraph, Text, Strong, Emphasis, Link, Image, CodeBlock, CodeSpan, BlockQuote, List, ListItem, Table, TableRow, TableCell, ThematicBreak, LineBreak, and more.

Example: Watermark Transform
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md.ast.transforms import NodeTransformer
   from all2md.ast import Image

   class WatermarkTransform(NodeTransformer):
       """Add watermark metadata to all images.

       Parameters
       ----------
       text : str
           Watermark text to add
       """

       def __init__(self, text: str = "CONFIDENTIAL"):
           super().__init__()
           self.watermark_text = text

       def visit_image(self, node: Image) -> Image:
           # Process children first (if any)
           node = super().visit_image(node)

           # Create new metadata dict
           new_metadata = node.metadata.copy()
           new_metadata['watermark'] = self.watermark_text

           # Return new node with updated metadata
           return Image(
               url=node.url,
               alt_text=node.alt_text,
               title=node.title,
               metadata=new_metadata
           )

Transform Metadata
------------------

To make your transform discoverable and usable from the CLI, define metadata:

.. code-block:: python

   from all2md.transforms import TransformMetadata, ParameterSpec

   WATERMARK_METADATA = TransformMetadata(
       name="watermark",
       description="Add watermark metadata to all images",
       transformer_class=WatermarkTransform,
       parameters={
           'text': ParameterSpec(
               type=str,
               default="CONFIDENTIAL",
               help="Watermark text to add",
               cli_flag='--watermark-text'
           )
       },
       priority=100,
       tags=["images", "metadata"],
       version="1.0.0",
       author="Your Name"
   )

ParameterSpec Options
~~~~~~~~~~~~~~~~~~~~~

- **type**: Python type (str, int, bool, list)
- **default**: Default value
- **help**: Help text for CLI
- **cli_flag**: Command-line flag
- **expose**: Set to ``True`` to expose the parameter on the CLI with an
  auto-generated flag (defaults to hidden unless ``cli_flag`` is provided)
- **required**: Whether required (default: False)
- **choices**: List of allowed values
- **validator**: Custom validation function

Publishing Plugins
------------------

Entry Point Registration
~~~~~~~~~~~~~~~~~~~~~~~~~

Register your transform via entry points in ``pyproject.toml``:

.. code-block:: toml

   [project]
   name = "all2md-watermark"
   version = "1.0.0"
   dependencies = ["all2md>=0.1.0"]

   [project.entry-points."all2md.transforms"]
   watermark = "all2md_watermark:METADATA"

Package Structure
~~~~~~~~~~~~~~~~~

.. code-block:: text

   my-transform-plugin/
   ├── pyproject.toml
   ├── README.md
   └── src/
       └── all2md_myplugin/
           ├── __init__.py
           └── transforms.py

Installation and Usage
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install plugin
   pip install all2md-watermark

   # Use from Python
   from all2md import to_markdown
   markdown = to_markdown('doc.pdf', transforms=['watermark'])

   # Use from CLI
   all2md document.pdf --transform watermark --watermark-text "DRAFT"

Advanced Features
-----------------

Using Hooks
~~~~~~~~~~~

Hooks allow you to intercept the rendering pipeline:

.. code-block:: python

   from all2md.transforms import render, HookContext

   def log_images(node, context: HookContext):
       """Log each image URL."""
       print(f"Image: {node.url}")
       return node  # Keep the node

   def add_footer(markdown: str, context: HookContext) -> str:
       """Add footer after rendering."""
       return markdown + "\n\n---\nGenerated by all2md"

   markdown = render(
       doc,
       transforms=['remove-images'],
       hooks={
           'image': [log_images],
           'post_render': [add_footer]
       }
   )

Available Hook Points
~~~~~~~~~~~~~~~~~~~~~

- **post_ast**: After AST creation, before transforms
- **pre_transform**: Before each transform
- **post_transform**: After each transform
- **pre_render**: Before rendering to markdown
- **Element hooks**: Per node type (heading, image, link, etc.)
- **post_render**: After rendering to markdown

Transform Dependencies
~~~~~~~~~~~~~~~~~~~~~~

Specify transforms that must run before yours:

.. code-block:: python

   METADATA = TransformMetadata(
       name="table-of-contents",
       dependencies=["add-heading-ids"],  # Requires IDs on headings
       ...
   )

The registry will automatically resolve dependencies and execute transforms in the correct order.

Best Practices
--------------

1. **Always call super()** to ensure children are processed:

   .. code-block:: python

      def visit_heading(self, node: Heading) -> Heading:
          node = super().visit_heading(node)  # Process children first
          # Modify node...
          return node

2. **Create new nodes** (don't mutate):

   .. code-block:: python

      # Good
      return Heading(level=node.level + 1, content=node.content, ...)

      # Bad
      node.level += 1
      return node

3. **Copy metadata** before modifying:

   .. code-block:: python

      new_metadata = node.metadata.copy()
      new_metadata['custom_field'] = value

4. **Handle None returns** from child processing:

   .. code-block:: python

      def visit_paragraph(self, node: Paragraph) -> Paragraph | None:
          node = super().visit_paragraph(node)
          if node is None:
              return None
          # Process node...
          return node

5. **Document your transforms** with NumPy-style docstrings

6. **Test thoroughly** with various node types and edge cases

See Also
--------

- :doc:`ast_guide` - AST structure and node types
- :doc:`plugins` - General plugin development guide
- `TRANSFORMS.md <https://github.com/thomas.villani/all2md/blob/main/TRANSFORMS.md>`_ - Complete transform development guide

API Reference
-------------

.. autosummary::
   :toctree: api/

   all2md.transforms
   all2md.transforms.metadata
   all2md.transforms.registry
   all2md.transforms.hooks
   all2md.transforms.pipeline
   all2md.transforms.builtin
