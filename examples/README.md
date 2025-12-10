# all2md Examples

Welcome to the all2md examples directory! This collection demonstrates the library's capabilities through practical, real-world applications ranging from simple demos to production-ready tools.

## Quick Start

If you're new to all2md, start with these examples:

1. **progress_callback_demo.py** - Learn how to track conversion progress
2. **jinja_template_demo.py** - See custom template rendering in action
3. **flask_markdown_site.py** - Build a markdown-powered website in minutes

## Table of Contents

- [Overview](#overview)
- [Examples by Category](#examples-by-category)
  - [Getting Started](#getting-started)
  - [Document Analysis](#document-analysis)
  - [AST Manipulation & Transforms](#ast-manipulation--transforms)
  - [Batch Processing & Automation](#batch-processing--automation)
  - [LLM Integration](#llm-integration)
  - [Web Applications](#web-applications)
  - [Plugin Development](#plugin-development)
- [Examples by Complexity](#examples-by-complexity)
- [Requirements](#requirements)
- [Contributing](#contributing)

## Overview

The examples demonstrate:

- **Core Features**: AST manipulation, format conversion, metadata extraction
- **Advanced Patterns**: Custom transforms, plugin architecture, parallel processing
- **Real-World Use Cases**: Documentation sites, translation, privacy compliance, version control
- **Integration**: LLMs, Git, Flask, Jinja2 templates

## Examples by Category

### Getting Started

Simple examples to learn core concepts.

#### progress_callback_demo.py

Track conversion progress with custom callbacks.

```bash
python progress_callback_demo.py
```

**Demonstrates:**
- Progress callback registration
- Simple vs. detailed event handlers
- Integration with UI frameworks

**Complexity:** Beginner

---

#### jinja_template_demo.py

Render documents using custom Jinja2 templates.

```bash
python jinja_template_demo.py
```

**Features:**
- DocBook XML output
- YAML metadata extraction
- Custom outline formats
- ANSI terminal rendering

**Templates:** See `jinja-templates/` directory

**Complexity:** Beginner

---

### Document Analysis

Extract and analyze document content.

#### link_checker.py

Extract and validate all links in documents.

```bash
python link_checker.py document.pdf --check-urls
```

**Features:**
- HTTP status checking (with rate limiting)
- Broken link detection
- Link categorization (internal/external)
- Suggested fixes for common errors

**Use Cases:**
- Documentation maintenance
- SEO audits
- Content migration validation
- Website quality assurance

**Complexity:** Intermediate

---

#### api_doc_extractor.py

Extract runnable code examples from documentation.

```bash
python api_doc_extractor.py api-docs.md --output examples/
```

**Features:**
- Language-specific code block extraction
- Python syntax validation
- Auto-generated test harness
- Batch processing

**Use Cases:**
- Documentation testing
- Example maintenance
- SDK development
- Tutorial generation

**Complexity:** Intermediate

---

#### study_guide_generator.py

Generate comprehensive study materials from documents.

```bash
python study_guide_generator.py textbook.pdf --llm openai
```

**Features:**
- Section-by-section summaries
- Code example extraction
- LLM-generated quizzes
- Practice problem generation

**Requirements:** OpenAI API key or Anthropic API key

**Use Cases:**
- Educational content creation
- Training materials
- Self-study resources
- Course development

**Complexity:** Intermediate

---

### AST Manipulation & Transforms

Learn to modify document structure programmatically.

#### document_sanitizer.py

Remove sensitive information for safe document sharing.

```bash
python document_sanitizer.py confidential.pdf --output sanitized.pdf
```

**Features:**
- PII redaction (emails, phones, URLs)
- Metadata stripping
- Custom pattern matching
- Domain whitelisting
- Preserve document formatting

**Use Cases:**
- GDPR/CCPA compliance
- Legal document preparation
- Freedom of Information requests
- Public data releases

**Complexity:** Intermediate

**Documentation:** Includes detailed docstrings with privacy compliance notes

---

#### llm_translation_demo.py

Translate documents while preserving structure and formatting.

```bash
python llm_translation_demo.py document.pdf french --llm anthropic
```

**Features:**
- Format-agnostic translation
- Structure preservation
- Multiple LLM provider support (OpenAI, Anthropic, mock)
- AST NodeTransformer pattern

**Requirements:** LLM API keys

**Use Cases:**
- Technical documentation translation
- Multilingual content creation
- Localization workflows

**Documentation:** See code comments and docstrings for comprehensive guide

**Complexity:** Intermediate-Advanced

---

#### code_example_generator.py

Automatically generate working code examples using LLMs.

```bash
python code_example_generator.py api-reference.md --llm openai --validate
```

**Features:**
- LLM-powered example generation
- Syntax validation
- Multiple provider support
- Example insertion into docs

**Requirements:** OpenAI, Anthropic, or mock LLM

**Use Cases:**
- API documentation enhancement
- Tutorial creation
- Developer onboarding
- SDK documentation

**Complexity:** Advanced

---

### Batch Processing & Automation

Handle large-scale document operations.

#### batch_converter.py

Bulk document conversion with parallel processing.

```bash
python batch_converter.py input_dir/ output_dir/ --format markdown --workers 4
```

**Features:**
- Recursive directory processing
- Parallel conversion (configurable workers)
- Checkpoint/resume support
- Comprehensive error handling
- Progress tracking
- Flexible output structure

**Use Cases:**
- Large-scale migrations
- Archive conversion
- Batch processing pipelines
- Format standardization

**Complexity:** Intermediate-Advanced

---

#### vcs-converter/ (Directory)

Git integration for version-controlling binary documents.

```bash
cd vcs-converter
./setup.sh
```

**Features:**
- Git pre-commit hook integration
- Bidirectional sync (binary ↔ markdown)
- Automatic conversion on commit
- Configuration management
- Batch conversion script

**Structure:**
- `vcs_converter.py` - Core conversion logic
- `pre-commit-hook.sh` - Git hook script
- `install_hook.py` - Hook installer
- `setup.sh` - One-command setup
- `vcs-converter.config.json` - Configuration

**Use Cases:**
- Document version control
- Collaborative editing of binary docs
- Change tracking for presentations
- Documentation workflows

**Documentation:** See `vcs-converter/README.md`

**Complexity:** Advanced

---

### LLM Integration

Examples integrating AI/language models.

Three examples demonstrate LLM integration with different patterns:

1. **llm_translation_demo.py** - Document translation with structure preservation
2. **code_example_generator.py** - Automated code example generation
3. **study_guide_generator.py** - Educational content creation

**Common Features:**
- Multi-provider support (OpenAI, Anthropic, mock)
- API key management
- Error handling
- Content validation

**Requirements:**
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` environment variables
- Or use `--llm mock` for testing without API keys

---

### Web Applications

Build web-based tools with all2md.

#### flask_markdown_site.py

Flask application for serving markdown files as a website.

```bash
pip install flask
python flask_markdown_site.py
```

Visit: http://localhost:5000

**Features:**
- YAML frontmatter parsing (title, date, author, tags)
- Automatic post listing sorted by date
- URL slug generation
- Responsive design with custom CSS
- Static asset serving

**Structure:**
- Sample content in `flask-site-content/`
- Custom CSS styling
- Embedded Jinja2 template

**Use Cases:**
- Markdown-powered blogs
- Documentation websites
- Content management
- Static site prototyping

**Documentation:** See code comments and `flask-site-content/` for examples

**Complexity:** Intermediate

---

### Plugin Development

Learn to extend all2md with custom formats and transforms.

#### simpledoc-plugin/ (Directory)

Complete bidirectional converter plugin for custom "SimpleDoc" format.

```bash
cd simpledoc-plugin
pip install -e .
python examples/demo.py
```

**Demonstrates:**
- Parser implementation (custom format → AST)
- Renderer implementation (AST → custom format)
- Options class for configuration
- Plugin registration with entry points
- Complete package structure
- Testing patterns

**Structure:**
- `src/all2md_simpledoc/parser.py` - Format parser
- `src/all2md_simpledoc/renderer.py` - Format renderer
- `src/all2md_simpledoc/options.py` - Configuration options
- `tests/` - Unit tests
- `pyproject.toml` - Package configuration

**Documentation:**
- `README.md` - Plugin overview
- `RENDERER_PATTERNS.md` - Renderer implementation guide

**Complexity:** Advanced

**Use Case:** Template for creating custom format plugins

---

#### watermark-plugin/ (Directory)

Transform plugin that adds watermarks to document images.

```bash
cd watermark-plugin
pip install -e .
```

**Demonstrates:**
- Transform plugin pattern
- Image manipulation in AST
- Transform registration
- Plugin metadata

**Structure:**
- `src/all2md_watermark/transforms.py` - Transform implementation
- `tests/` - Unit tests
- `pyproject.toml` - Package configuration

**Complexity:** Intermediate

**Use Case:** Template for creating transform plugins

---

## Examples by Complexity

### Beginner

Start here to learn basic concepts:

- **progress_callback_demo.py** - Progress tracking
- **jinja_template_demo.py** - Template rendering

### Intermediate

Build on fundamentals with practical applications:

- **flask_markdown_site.py** - Web application
- **link_checker.py** - Link validation
- **document_sanitizer.py** - Content sanitization
- **api_doc_extractor.py** - Code extraction
- **batch_converter.py** - Bulk processing
- **llm_translation_demo.py** - LLM integration
- **study_guide_generator.py** - Content generation
- **watermark-plugin/** - Transform plugin

### Advanced

Production-ready applications and complex integrations:

- **code_example_generator.py** - Advanced LLM usage
- **simpledoc-plugin/** - Complete format plugin
- **vcs-converter/** - Git workflow integration

## Requirements

### Core Requirements

All examples require:

```bash
pip install all2md
```

### Example-Specific Requirements

**Flask Web Application:**
```bash
pip install flask
```

**LLM Integration Examples:**
```bash
pip install openai  # For OpenAI
# OR
pip install anthropic  # For Anthropic

# Set environment variables
export OPENAI_API_KEY="your-key"
# OR
export ANTHROPIC_API_KEY="your-key"
```

**Link Checker:**
```bash
pip install httpx  # For URL checking
```

**Plugin Development:**
```bash
cd simpledoc-plugin  # or watermark-plugin
pip install -e .
```

### Optional Dependencies

Some examples work better with optional all2md features:

```bash
pip install all2md[pdf]     # PDF support
pip install all2md[docx]    # Word document support
pip install all2md[all]     # All optional features
```

## Running Examples

### Standalone Scripts

Most examples are single Python files that can be run directly:

```bash
# With arguments
python example_name.py input.pdf --output output.md

# Without arguments (shows help/demo)
python example_name.py
```

All scripts include:
- Comprehensive help text (`--help`)
- Example usage in docstrings
- Demo mode when run without arguments

### Directory-Based Examples

Examples in subdirectories have their own README files:

```bash
# simpledoc-plugin
cd simpledoc-plugin
cat README.md

# watermark-plugin
cd watermark-plugin
cat README.md

# vcs-converter
cd vcs-converter
cat README.md
```

## Key Concepts Demonstrated

### AST Manipulation

Most examples work with all2md's AST (Abstract Syntax Tree):

```python
from all2md import to_ast, from_ast

# Parse to AST
doc = to_ast("input.pdf")

# Manipulate AST
# ... transform document ...

# Render to output
output = from_ast(doc, "markdown")
```

**Examples:** document_sanitizer.py, llm_translation_demo.py, code_example_generator.py

### NodeTransformer Pattern

Advanced AST manipulation using visitors:

```python
from all2md.ast.visitors import NodeTransformer

class CustomTransform(NodeTransformer):
    def visit_Link(self, node):
        # Transform links
        return modified_node
```

**Examples:** llm_translation_demo.py, document_sanitizer.py

### Batch Processing

Efficient processing of multiple files:

```python
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    results = executor.map(convert_file, file_list)
```

**Examples:** batch_converter.py, vcs-converter/

### Progress Callbacks

Track conversion progress:

```python
def progress_handler(event, data):
    print(f"Progress: {data.get('percent', 0)}%")

result = convert(path, progress_callback=progress_handler)
```

**Example:** progress_callback_demo.py

### Plugin Architecture

Extend all2md with custom formats:

**Parser Plugin:**
```python
from all2md.parsers.base import BaseParser

class CustomParser(BaseParser):
    def parse(self, input_source, options):
        # Parse custom format to AST
        return document
```

**Renderer Plugin:**
```python
from all2md.renderers.base import BaseRenderer

class CustomRenderer(BaseRenderer):
    def render(self, document, options):
        # Render AST to custom format
        return output
```

**Examples:** simpledoc-plugin/, watermark-plugin/

## Use Case Index

Find examples by your specific need:

**Documentation Management:**
- api_doc_extractor.py
- link_checker.py
- code_example_generator.py
- flask_markdown_site.py

**Privacy & Compliance:**
- document_sanitizer.py

**Education & Training:**
- study_guide_generator.py

**Translation & Localization:**
- llm_translation_demo.py

**Version Control:**
- vcs-converter/

**Bulk Operations:**
- batch_converter.py

**Custom Formats:**
- simpledoc-plugin/
- watermark-plugin/

**Web Publishing:**
- flask_markdown_site.py

## Contributing

Want to add your own example? We welcome contributions!

### Example Guidelines

Good examples should:

1. **Demonstrate a clear use case** - Solve a real-world problem
2. **Include documentation** - Comprehensive docstrings and help text
3. **Follow patterns** - Match existing example structure
4. **Be runnable** - Work out of the box or with clear setup instructions
5. **Show best practices** - Demonstrate proper all2md usage

### Example Template

```python
#!/usr/bin/env python3
"""Short description.

Longer description of what this example demonstrates and why it's useful.

Usage:
    python example.py input.pdf --option value

Example:
    python example.py document.pdf --output result.md

Requirements:
    pip install all2md optional-dependency

"""

import argparse
from all2md import to_ast, from_ast

def main():
    parser = argparse.ArgumentParser(description="...")
    # ... setup ...

if __name__ == "__main__":
    main()
```

### Submitting Examples

1. Create your example following the template
2. Test thoroughly
3. Add entry to this README.md
4. Submit a pull request

## Additional Resources

- **Main Documentation:** See `docs/` directory
- **API Reference:** See `docs/source/api/`
- **Python API Guide:** See `docs/source/python_api.rst`
- **Plugin Development:** See simpledoc-plugin/RENDERER_PATTERNS.md

## License

All examples are part of the all2md project. See the main LICENSE file for details.

---

**Questions or Issues?** Open an issue on the all2md repository or check the main documentation.
