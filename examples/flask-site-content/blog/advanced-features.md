---
title: "Advanced Features: Custom Transforms and Plugins"
date: 2025-01-29
author: "all2md Team"
slug: "advanced-features"
description: "Explore advanced all2md features including custom transforms, plugins, and AST manipulation"
tags: ["advanced", "python", "customization"]
---

# Advanced Features: Custom Transforms and Plugins

Once you're comfortable with basic all2md usage, it's time to explore the advanced features that make it truly powerful.

## AST Transforms

all2md's AST-based architecture allows you to manipulate documents programmatically:

```python
from all2md import to_ast, from_ast
from all2md.ast.visitors import NodeVisitor

class LinkCollector(NodeVisitor):
    """Collect all links in a document."""

    def __init__(self):
        self.links = []

    def visit_Link(self, node):
        self.links.append(node.url)
        self.generic_visit(node)

# Parse document and collect links
doc = to_ast("document.md")
collector = LinkCollector()
collector.visit(doc)
print(f"Found {len(collector.links)} links")
```

## Custom Renderers

Create custom output formats by implementing a renderer:

```python
from all2md.renderers.base import BaseRenderer

class CustomRenderer(BaseRenderer):
    """Custom format renderer."""

    def render_heading(self, node, level):
        return f"{'#' * level} {self.render_children(node)}\n\n"

    def render_paragraph(self, node):
        return f"{self.render_children(node)}\n\n"
```

## Plugin System

all2md supports plugins for custom formats. The repository includes example plugins:

- **simpledoc-plugin** - Custom format parser and renderer
- **watermark-plugin** - AST transform for adding watermarks

### Creating a Plugin

A plugin typically includes:

1. **Parser** - Convert format to AST
2. **Renderer** - Convert AST to format
3. **Options** - Configuration for conversion

Check the `examples/` directory for complete plugin examples.

## Options and Configuration

Fine-tune conversion with options:

```python
from all2md.options.html import HtmlRendererOptions

options = HtmlRendererOptions(
    include_toc=True,
    toc_mode="inject",
    template_file="custom.html",
    standalone=True,
    include_css=True
)

html = from_ast(doc, "html", renderer_options=options)
```

## Batch Processing

Process multiple files efficiently:

```python
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def convert_file(path):
    return convert(path, target_format="markdown")

# Parallel conversion
with ThreadPoolExecutor() as executor:
    paths = Path("docs").glob("**/*.pdf")
    results = list(executor.map(convert_file, paths))
```

## Real-World Applications

The Flask app serving this blog is itself an example of a real-world all2md application:

- Parses markdown files with frontmatter
- Renders to HTML dynamically
- Generates post listings automatically
- Serves a complete website

## More Resources

For more examples and documentation:

- Browse the `examples/` directory in the repository
- Read the API documentation
- Join the community discussions

---

*This advanced post demonstrates complex code examples and formatting.*
