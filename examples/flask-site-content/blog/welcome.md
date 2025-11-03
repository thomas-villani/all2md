---
title: "Welcome to the all2md Blog"
date: 2025-01-15
author: "all2md Team"
slug: "welcome"
description: "Introducing our markdown-powered blog built with all2md and Flask"
tags: ["announcement", "getting-started"]
---

# Welcome to the all2md Blog

Welcome to our new blog powered by **all2md** and Flask! This is the first post to demonstrate how easy it is to create a markdown-powered website.

## Why Markdown?

Markdown is the perfect format for content creation because:

- **Simple syntax** - Easy to read and write
- **Version control friendly** - Plain text files work great with git
- **Portable** - Can be converted to any format
- **Developer friendly** - Code blocks and syntax highlighting built-in

## Why all2md?

The all2md library takes markdown further by:

1. Supporting bidirectional conversion to 200+ formats
2. Providing an AST-based processing system
3. Handling complex documents with tables, images, and more
4. Offering extensive customization options

## What's Next?

Stay tuned for more posts about:

- Getting started with all2md
- Advanced features and customization
- Building your own markdown-powered applications

```python
# Quick example of using all2md
from all2md import to_ast, from_ast

# Parse markdown
doc = to_ast("content.md")

# Convert to HTML
html = from_ast(doc, "html")
```

---

*This post demonstrates basic markdown features including headings, lists, code blocks, and emphasis.*
