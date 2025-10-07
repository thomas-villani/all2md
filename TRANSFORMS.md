# AST Transforms Guide

This guide explains how to create custom AST transforms for `all2md`, either as built-in transforms or as third-party plugins.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Transform Basics](#transform-basics)
- [Creating a Transform](#creating-a-transform)
- [Transform Metadata](#transform-metadata)
- [Publishing a Plugin](#publishing-a-plugin)
- [Built-in Transforms](#built-in-transforms)
- [Advanced Topics](#advanced-topics)
- [Best Practices](#best-practices)

## Overview

The `all2md` transform system allows you to manipulate document ASTs (Abstract Syntax Trees) before rendering them to Markdown. Transforms can:

- Remove or filter nodes (e.g., remove all images)
- Modify node properties (e.g., offset heading levels)
- Add metadata to nodes
- Rewrite content (e.g., fix links)
- Generate new content

Transforms are discovered via Python entry points, making it easy to create and distribute third-party plugins.

## Quick Start

### Using Existing Transforms

```python
from all2md import to_markdown
from all2md.transforms import RemoveImagesTransform, HeadingOffsetTransform

# Apply transforms during conversion
markdown = to_markdown(
    'document.pdf',
    transforms=[
        RemoveImagesTransform(),
        HeadingOffsetTransform(offset=1)
    ]
)
```

### Creating a Simple Transform

```python
from all2md.ast.transforms import NodeTransformer
from all2md.ast import Image

class RemoveImagesTransform(NodeTransformer):
    """Remove all images from the document."""

    def visit_image(self, node: Image) -> None:
        # Return None to remove the node
        return None
```

## Transform Basics

### The NodeTransformer Base Class

All transforms inherit from `NodeTransformer`, which provides the visitor pattern for traversing the AST:

```python
from all2md.ast.transforms import NodeTransformer
from all2md.ast import Heading, Paragraph, Text, Image, Link

class MyTransform(NodeTransformer):
    """Example transform demonstrating visitor methods."""

    def visit_heading(self, node: Heading) -> Heading:
        # Called for each Heading node
        # Must return a node or None
        return super().visit_heading(node)  # Continue traversal

    def visit_paragraph(self, node: Paragraph) -> Paragraph:
        # Called for each Paragraph node
        return super().visit_paragraph(node)

    def visit_text(self, node: Text) -> Text:
        # Called for each Text node
        return super().visit_text(node)

    def visit_image(self, node: Image) -> Image | None:
        # Return None to remove the node
        return super().visit_image(node)

    def visit_link(self, node: Link) -> Link:
        # Called for each Link node
        return super().visit_link(node)
```

### Visitor Method Naming

Visitor methods follow the pattern `visit_<node_type_lowercase>`:

- `Heading` → `visit_heading()`
- `Paragraph` → `visit_paragraph()`
- `CodeBlock` → `visit_code_block()`
- `TableCell` → `visit_table_cell()`

### Return Values

- **Return the node** (possibly modified) to keep it
- **Return None** to remove the node
- **Return a different node** to replace it

## Creating a Transform

### Example: Custom Watermark Transform

```python
from all2md.ast.transforms import NodeTransformer
from all2md.ast import Image

class WatermarkTransform(NodeTransformer):
    """Add watermark metadata to all images.

    Parameters
    ----------
    text : str
        Watermark text to add (default: "CONFIDENTIAL")
    """

    def __init__(self, text: str = "CONFIDENTIAL"):
        super().__init__()
        self.watermark_text = text

    def visit_image(self, node: Image) -> Image:
        # First, traverse children (if any)
        node = super().visit_image(node)

        # Add watermark to metadata
        new_metadata = node.metadata.copy()
        new_metadata['watermark'] = self.watermark_text

        # Return new node with updated metadata
        return Image(
            url=node.url,
            alt_text=node.alt_text,
            title=node.title,
            metadata=new_metadata
        )
```

### Example: Link Rewriter

```python
import re
from all2md.ast.transforms import NodeTransformer
from all2md.ast import Link

class LinkRewriterTransform(NodeTransformer):
    """Rewrite link URLs using regex patterns.

    Parameters
    ----------
    pattern : str
        Regex pattern to match in URLs
    replacement : str
        Replacement string (can use capture groups like \\1)
    """

    def __init__(self, pattern: str, replacement: str):
        super().__init__()
        self.pattern = re.compile(pattern)
        self.replacement = replacement

    def visit_link(self, node: Link) -> Link:
        # Traverse children first
        node = super().visit_link(node)

        # Rewrite URL if it matches pattern
        new_url = self.pattern.sub(self.replacement, node.url)

        if new_url != node.url:
            return Link(
                url=new_url,
                content=node.content,
                title=node.title,
                metadata=node.metadata
            )

        return node
```

## Transform Metadata

To make your transform discoverable via entry points and usable from the CLI, you need to define metadata:

```python
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
    priority=100,  # Execution order (lower = earlier)
    tags=["images", "metadata"],
    version="1.0.0",
    author="Your Name"
)
```

### ParameterSpec Fields

- **type**: Python type (str, int, bool, list)
- **default**: Default value if not specified
- **help**: Help text for CLI
- **cli_flag**: Command-line flag (e.g., `--watermark-text`)
- **required**: Whether parameter is required (default: False)
- **choices**: List of allowed values
- **validator**: Custom validation function

### TransformMetadata Fields

- **name**: Unique identifier (used with `--transform`)
- **description**: Short description
- **transformer_class**: Your transform class
- **parameters**: Dict of parameter specs
- **priority**: Execution order (default: 100)
- **dependencies**: List of transform names that must run first
- **tags**: Tags for categorization
- **version**: Version string
- **author**: Author name

## Publishing a Plugin

### 1. Create Your Package

```
my-transform-plugin/
├── pyproject.toml
├── README.md
└── src/
    └── all2md_myplugin/
        ├── __init__.py
        └── transforms.py
```

### 2. Define Your Transform

**src/all2md_myplugin/transforms.py**:

```python
from all2md.ast.transforms import NodeTransformer
from all2md.ast import Image
from all2md.transforms import TransformMetadata, ParameterSpec

class WatermarkTransform(NodeTransformer):
    """Add watermark to images."""

    def __init__(self, text: str = "CONFIDENTIAL"):
        super().__init__()
        self.watermark_text = text

    def visit_image(self, node: Image) -> Image:
        node = super().visit_image(node)
        new_metadata = node.metadata.copy()
        new_metadata['watermark'] = self.watermark_text
        return Image(
            url=node.url,
            alt_text=node.alt_text,
            title=node.title,
            metadata=new_metadata
        )

# Metadata for registry
METADATA = TransformMetadata(
    name="watermark",
    description="Add watermark metadata to images",
    transformer_class=WatermarkTransform,
    parameters={
        'text': ParameterSpec(
            type=str,
            default="CONFIDENTIAL",
            help="Watermark text",
            cli_flag='--watermark-text'
        )
    }
)
```

### 3. Configure Entry Point

**pyproject.toml**:

```toml
[project]
name = "all2md-watermark"
version = "1.0.0"
dependencies = ["all2md>=0.1.0"]

[project.entry-points."all2md.transforms"]
watermark = "all2md_myplugin.transforms:METADATA"
```

### 4. Install and Use

```bash
# Install your plugin
pip install all2md-watermark

# Use from Python
from all2md import to_markdown
markdown = to_markdown('doc.pdf', transforms=['watermark'])

# Use from CLI
all2md document.pdf --transform watermark --watermark-text "DRAFT"
```

## Built-in Transforms

### remove-images
Remove all Image nodes from the document.

```python
from all2md.transforms import RemoveImagesTransform
transform = RemoveImagesTransform()
```

### remove-nodes
Remove nodes of specified types.

```python
from all2md.transforms import RemoveNodesTransform
transform = RemoveNodesTransform(node_types=['image', 'table'])
```

### heading-offset
Shift heading levels by an offset.

```python
from all2md.transforms import HeadingOffsetTransform
transform = HeadingOffsetTransform(offset=1)  # H1→H2, H2→H3, etc.
```

### link-rewriter
Rewrite URLs using regex patterns.

```python
from all2md.transforms import LinkRewriterTransform
transform = LinkRewriterTransform(
    pattern=r'^/docs/',
    replacement='https://example.com/docs/'
)
```

### text-replacer
Find and replace text in Text nodes.

```python
from all2md.transforms import TextReplacerTransform
transform = TextReplacerTransform(find="TODO", replace="DONE")
```

### add-heading-ids
Generate unique IDs for headings.

```python
from all2md.transforms import AddHeadingIdsTransform
transform = AddHeadingIdsTransform(id_prefix="doc-", separator="-")
```

### remove-boilerplate
Remove paragraphs matching boilerplate patterns.

```python
from all2md.transforms import RemoveBoilerplateTextTransform
transform = RemoveBoilerplateTextTransform(
    patterns=[r'^CONFIDENTIAL$', r'^Page \d+ of \d+$']
)
```

### add-timestamp
Add conversion timestamp to metadata.

```python
from all2md.transforms import AddConversionTimestampTransform
transform = AddConversionTimestampTransform(
    field_name="converted_at",
    format="iso"  # or "unix" or strftime format
)
```

### word-count
Calculate word and character counts.

```python
from all2md.transforms import CalculateWordCountTransform
transform = CalculateWordCountTransform(
    word_field="words",
    char_field="chars"
)
```

## Advanced Topics

### Using Hooks

Hooks allow you to intercept the rendering pipeline at specific points:

```python
from all2md.transforms import render, HookContext

def log_images(node, context: HookContext):
    """Log image URLs."""
    print(f"Image: {node.url}")
    return node  # Return node to keep it

def add_footer(markdown: str, context: HookContext) -> str:
    """Add footer to rendered markdown."""
    return markdown + "\n\n---\nGenerated by all2md"

markdown = render(
    doc,
    transforms=['remove-images'],
    hooks={
        'image': [log_images],  # Called for each Image node
        'post_render': [add_footer]  # Called after rendering
    }
)
```

### Available Hook Points

- **post_ast**: After AST creation, before transforms
- **pre_transform**: Before each transform
- **post_transform**: After each transform
- **pre_render**: Before rendering to markdown
- **Element hooks**: Per node type (heading, image, link, etc.)
- **post_render**: After rendering to markdown

### Transform Dependencies

Specify transforms that must run before yours:

```python
METADATA = TransformMetadata(
    name="table-of-contents",
    dependencies=["add-heading-ids"],  # Must run after add-heading-ids
    ...
)
```

### State Management

Use the transform instance to maintain state:

```python
class DeduplicateImagesTransform(NodeTransformer):
    """Remove duplicate images."""

    def __init__(self):
        super().__init__()
        self.seen_urls = set()

    def visit_image(self, node: Image) -> Image | None:
        if node.url in self.seen_urls:
            return None  # Remove duplicate
        self.seen_urls.add(node.url)
        return node
```

## Best Practices

### 1. Always Call super()

```python
def visit_heading(self, node: Heading) -> Heading:
    # Process children first
    node = super().visit_heading(node)

    # Then modify this node
    # ...

    return node
```

### 2. Create New Nodes (Immutability)

```python
# Good: Create new node
return Heading(
    level=node.level + 1,
    content=node.content,
    metadata=node.metadata
)

# Bad: Mutate existing node
node.level += 1  # Don't do this!
return node
```

### 3. Copy Metadata

```python
new_metadata = node.metadata.copy()
new_metadata['custom_field'] = value
```

### 4. Handle None Returns

```python
def visit_paragraph(self, node: Paragraph) -> Paragraph | None:
    node = super().visit_paragraph(node)

    # May be None if child was removed
    if node is None:
        return None

    # Filter empty paragraphs
    if not node.content:
        return None

    return node
```

### 5. Document Your Transform

```python
class MyTransform(NodeTransformer):
    """One-line summary.

    Detailed description of what this transform does,
    when to use it, and any side effects.

    Parameters
    ----------
    param1 : str
        Description of param1
    param2 : int, optional
        Description of param2 (default: 42)

    Examples
    --------
    >>> transform = MyTransform(param1="value")
    >>> markdown = render(doc, transforms=[transform])
    """
```

### 6. Test Thoroughly

```python
import pytest
from all2md.ast import Document, Paragraph, Text

def test_my_transform():
    doc = Document(children=[
        Paragraph(content=[Text(content="Test")])
    ])

    transform = MyTransform()
    result = transform.transform(doc)

    assert isinstance(result, Document)
    assert len(result.children) == 1
```

### 7. Version Your Plugin

```toml
[project]
version = "1.0.0"

[project.entry-points."all2md.transforms"]
my-transform = "my_package.transforms:METADATA"
```

### 8. Provide Good Error Messages

```python
class MyTransform(NodeTransformer):
    def __init__(self, required_param: str):
        if not required_param:
            raise ValueError("required_param cannot be empty")
        super().__init__()
        self.required_param = required_param
```

## Examples

See the `examples/` directory for complete plugin examples:

- `examples/watermark-plugin/` - Simple image watermarking
- `examples/toc-plugin/` - Table of contents generation
- `examples/redact-plugin/` - Sensitive information redaction

## Getting Help

- **Documentation**: https://all2md.readthedocs.io
- **Issues**: https://github.com/your-org/all2md/issues
- **Discussions**: https://github.com/your-org/all2md/discussions

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.
