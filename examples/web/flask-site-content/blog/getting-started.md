---
title: "Getting Started with all2md"
date: 2025-01-22
author: "Documentation Team"
slug: "getting-started"
description: "Learn how to install and use all2md for document conversion"
tags: ["tutorial", "python", "documentation"]
---

# Getting Started with all2md

Ready to start converting documents with all2md? This guide will walk you through installation and basic usage.

## Installation

Install all2md using pip:

```bash
pip install all2md
```

For optional dependencies (PDF support, etc.):

```bash
pip install all2md[pdf]
```

## Basic Usage

### Converting Documents

The simplest way to convert a document:

```python
from all2md import convert

# Convert any document to markdown
markdown = convert("document.pdf", target_format="markdown")

# Convert markdown to HTML
html = convert("content.md", target_format="html")
```

### Working with the AST

For more control, use the AST API:

```python
from all2md import to_ast, from_ast

# Parse to AST
doc = to_ast("input.pdf")

# Access metadata
title = doc.metadata.get("title")
author = doc.metadata.get("author")

# Transform the document
# ... apply custom transformations ...

# Render to output format
output = from_ast(doc, "markdown")
```

### Command Line Interface

all2md also provides a powerful CLI:

```bash
# Convert to markdown (stdout)
all2md document.pdf

# Save to file
all2md document.docx --out output.md

# Convert to HTML
all2md content.md --to html --out page.html
```

## YAML Frontmatter

all2md automatically extracts YAML frontmatter from markdown files:

```markdown
---
title: "My Document"
date: 2025-01-22
author: "Your Name"
tags: ["example", "demo"]
---

# Content starts here
```

The frontmatter is parsed and available in `doc.metadata`.

## Next Steps

- Explore the [API documentation](https://github.com/thomas-villani/all2md)
- Check out more examples in the repository
- Read about advanced features in our next post

---

*This post demonstrates code blocks, formatted text, and links.*
