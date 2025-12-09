# SimpleDoc Format Plugin for all2md

An example plugin demonstrating how to build a complete bidirectional converter (parser + renderer) for the `all2md` library.

## Overview

This plugin adds support for the **SimpleDoc** format - a lightweight, invented markup language designed for structured documents. SimpleDoc demonstrates how to create a plugin that both reads from and writes to a custom format.

## What is SimpleDoc?

SimpleDoc (.sdoc, .simpledoc) is a minimal markup language with the following features:

- **Frontmatter metadata** block using `---` delimiters
- **Headings** using `@@` marker
- **Paragraphs** separated by blank lines
- **Lists** using `-` prefix
- **Code blocks** using triple backticks
- Clean, readable syntax

### Example SimpleDoc Document

```
---
title: Getting Started with Python
author: Jane Smith
date: 2025-01-15
tags: python, tutorial, beginner
---

@@ Introduction

Python is a high-level programming language designed for
readability and simplicity. It's widely used in data science,
web development, automation, and more.

@@ Key Features

- Easy to learn syntax
- Versatile applications
- Large standard library
- Active community support

@@ Example Code

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
```

@@ Conclusion

Python is an excellent choice for both beginners and experienced
developers looking for a productive language.
```

## Installation

```bash
pip install all2md-simpledoc
```

Or for development:

```bash
git clone https://github.com/thomas-villani/all2md.git
cd all2md/examples/simpledoc-plugin
pip install -e .
```

## Usage

### Convert SimpleDoc to Markdown

```bash
all2md document.sdoc --out output.md
```

### Convert Markdown to SimpleDoc

```bash
all2md document.md --out output.sdoc
```

### Using in Python

```python
from all2md import to_markdown, from_markdown
from all2md_simpledoc.options import SimpleDocOptions

# Parse SimpleDoc to Markdown
markdown_output = to_markdown("document.sdoc")

# Parse with custom options
options = SimpleDocOptions(include_frontmatter=True)
markdown_output = to_markdown("document.sdoc", parser_options=options)

# Convert Markdown to SimpleDoc
from all2md.converter_registry import get_registry
registry = get_registry()

# Parse markdown to AST
parser = registry.get_parser("markdown")()
ast_doc = parser.parse("document.md")

# Render AST as SimpleDoc
renderer_class = registry.get_renderer("simpledoc")
renderer = renderer_class()
renderer.render(ast_doc, "output.sdoc")
```

## Plugin Architecture

This plugin demonstrates key concepts for building `all2md` plugins:

### 1. Parser (parser.py)

- Inherits from `BaseParser`
- Implements `parse()` method to convert SimpleDoc text to AST
- Implements `extract_metadata()` to parse frontmatter
- Handles all input types: str, Path, IO[bytes], bytes
- Proper error handling with `ParsingError`

### 2. Renderer (renderer.py)

- Inherits from `BaseRenderer` and `NodeVisitor`
- Uses visitor pattern to traverse AST
- Implements `visit_*()` methods for each node type
- Produces valid SimpleDoc output from AST

### 3. Options (options.py)

- `SimpleDocOptions` for parser configuration
- `SimpleDocRendererOptions` for renderer configuration
- Frozen dataclass pattern for immutability
- CLI integration via field metadata

### 4. Metadata Registration

The `CONVERTER_METADATA` object in `__init__.py` registers the plugin:

- Format name: "simpledoc"
- File extensions: [".sdoc", ".simpledoc"]
- MIME type: "text/x-simpledoc"
- Magic bytes: `(b"---\n", 0)` for frontmatter detection
- Links to parser and renderer classes
- Links to options classes

## Format Specification

### Frontmatter Block

Optional metadata block at the start of the document:

```
---
title: Document Title
author: Author Name
date: YYYY-MM-DD
tags: tag1, tag2, tag3
---
```

Supported fields:
- `title`: Document title
- `author`: Author name
- `date`: Publication date (ISO format recommended)
- `tags`: Comma-separated tags
- Any custom key-value pairs

### Headings

```
@@ First Level Heading
```

All headings use `@@` regardless of level. The parser assigns heading levels based on document structure.

### Paragraphs

Regular text separated by blank lines:

```
This is a paragraph.
It can span multiple lines.

This is another paragraph.
```

### Lists

Unordered lists using `-` prefix:

```
- First item
- Second item
- Third item
```

### Code Blocks

Fenced code blocks with optional language:

````
```python
def hello():
    print("Hello!")
```
````

## Development

### Running Tests

```bash
pytest tests/
```

### Building the Package

```bash
python -m build
```

## How This Plugin Works

1. **Plugin Discovery**: The entry point in `pyproject.toml` registers the converter with all2md
2. **Format Detection**: When all2md encounters a `.sdoc` file or detects `---\n` at the start, it uses this plugin
3. **Parsing**: `SimpleDocParser.parse()` converts SimpleDoc text to AST nodes
4. **Rendering**: `SimpleDocRenderer.render()` converts AST back to SimpleDoc format

## Why This Example?

This plugin serves as a comprehensive example because it demonstrates:

- Full bidirectional conversion (read and write)
- Parser implementation following all2md patterns
- Renderer implementation using visitor pattern
- Custom options classes for both parser and renderer
- Metadata extraction from structured frontmatter
- Format detection via file extensions and magic bytes
- Comprehensive test coverage
- Production-ready error handling
- Documentation and packaging

## Learning from This Example

To create your own plugin:

1. Copy this plugin as a template
2. Define your format's structure
3. Implement the parser to convert your format to AST
4. Implement the renderer to convert AST to your format
5. Create custom options if needed
6. Register with proper metadata
7. Write comprehensive tests
8. Package and distribute

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## Related Projects

- [all2md](https://github.com/thomas-villani/all2md) - Universal document converter
- [all2md-watermark](https://github.com/thomas-villani/all2md/tree/main/examples/watermark-plugin) - Transform plugin example
