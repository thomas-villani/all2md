"""Integration tests for Markdown to AST conversion."""

from pathlib import Path

import pytest

from all2md import to_ast, to_markdown
from all2md.ast.nodes import Document


@pytest.mark.integration
def test_markdown_to_ast_basic(tmp_path):
    """Test basic Markdown to AST conversion."""
    md_content = """# Main Heading

This is a paragraph with **bold** and *italic* text.

## Subheading

Another paragraph.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)
    assert len(doc.children) > 0

    # Convert back to markdown to verify roundtrip
    result = to_markdown(md_file)
    assert "# Main Heading" in result
    assert "## Subheading" in result
    assert "**bold**" in result or "bold" in result


@pytest.mark.integration
def test_markdown_to_ast_lists(tmp_path):
    """Test Markdown lists to AST conversion."""
    md_content = """# Lists Example

## Unordered List

- Item 1
- Item 2
- Item 3

## Ordered List

1. First item
2. Second item
3. Third item
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify content in roundtrip
    result = to_markdown(md_file)
    assert "Item 1" in result
    assert "First item" in result


@pytest.mark.integration
def test_markdown_to_ast_code_blocks(tmp_path):
    """Test Markdown code blocks to AST conversion."""
    md_content = """# Code Examples

Inline `code` example.

```python
def hello():
    return "Hello, World!"
```

Regular text after code.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify code block content
    result = to_markdown(md_file)
    assert "`code`" in result
    assert "def hello():" in result
    assert "Hello, World!" in result


@pytest.mark.integration
def test_markdown_to_ast_links(tmp_path):
    """Test Markdown links to AST conversion."""
    md_content = """# Links Example

Visit [Example Site](https://example.com) for more info.

Also check [GitHub](https://github.com).
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify links in roundtrip
    result = to_markdown(md_file)
    assert "[Example Site]" in result
    assert "https://example.com" in result
    assert "[GitHub]" in result


@pytest.mark.integration
def test_markdown_to_ast_images(tmp_path):
    """Test Markdown images to AST conversion."""
    md_content = """# Image Example

![Alt text](https://example.com/image.jpg)

![Another image](image.png "Image title")
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify images in roundtrip
    result = to_markdown(md_file)
    assert "![Alt text]" in result
    assert "https://example.com/image.jpg" in result


@pytest.mark.integration
def test_markdown_to_ast_blockquotes(tmp_path):
    """Test Markdown blockquotes to AST conversion."""
    md_content = """# Blockquote Example

> This is a quoted text.
> It spans multiple lines.

Regular text.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify blockquote in roundtrip
    result = to_markdown(md_file)
    assert "> " in result or ">" in result
    assert "This is a quoted text" in result


@pytest.mark.integration
def test_markdown_to_ast_tables(tmp_path):
    """Test Markdown tables to AST conversion."""
    md_content = """# Table Example

| Name | Age | City |
|------|-----|------|
| Alice | 30 | NYC |
| Bob | 25 | LA |
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify table in roundtrip
    result = to_markdown(md_file)
    assert "| Name" in result or "|Name" in result
    assert "Alice" in result
    assert "Bob" in result


@pytest.mark.integration
def test_markdown_to_ast_nested_lists(tmp_path):
    """Test Markdown nested lists to AST conversion."""
    md_content = """# Nested Lists

- Item 1
  - Nested 1.1
  - Nested 1.2
- Item 2
  - Nested 2.1
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify nested structure in roundtrip
    result = to_markdown(md_file)
    assert "Item 1" in result
    assert "Nested 1.1" in result


@pytest.mark.integration
def test_markdown_to_ast_horizontal_rules(tmp_path):
    """Test Markdown horizontal rules to AST conversion."""
    md_content = """# Section 1

Content 1

---

# Section 2

Content 2
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify horizontal rule in roundtrip
    result = to_markdown(md_file)
    assert "Section 1" in result
    assert "Section 2" in result


@pytest.mark.integration
def test_markdown_to_ast_headings_hierarchy(tmp_path):
    """Test Markdown heading hierarchy to AST conversion."""
    md_content = """# Level 1

## Level 2

### Level 3

#### Level 4

##### Level 5

###### Level 6
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify heading hierarchy in roundtrip
    result = to_markdown(md_file)
    assert "# Level 1" in result
    assert "## Level 2" in result
    assert "### Level 3" in result


@pytest.mark.integration
def test_markdown_to_ast_task_lists(tmp_path):
    """Test Markdown task lists to AST conversion (GitHub Flavored Markdown)."""
    md_content = """# Task List

- [x] Completed task
- [ ] Incomplete task
- [x] Another completed task
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify task list in roundtrip
    result = to_markdown(md_file)
    assert "task" in result.lower()


@pytest.mark.integration
def test_markdown_to_ast_strikethrough(tmp_path):
    """Test Markdown strikethrough to AST conversion."""
    md_content = """# Strikethrough Example

This text has ~~strikethrough~~ formatting.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify strikethrough in roundtrip
    result = to_markdown(md_file)
    assert "strikethrough" in result


@pytest.mark.integration
def test_markdown_to_ast_autolinks(tmp_path):
    """Test Markdown autolinks to AST conversion."""
    md_content = """# Autolinks

<https://example.com>

<email@example.com>
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify autolinks in roundtrip
    result = to_markdown(md_file)
    assert "https://example.com" in result


@pytest.mark.integration
def test_markdown_to_ast_emphasis_combinations(tmp_path):
    """Test Markdown emphasis combinations to AST conversion."""
    md_content = """# Emphasis Examples

**Bold text**

*Italic text*

***Bold and italic***

**Bold with *nested italic***
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify emphasis in roundtrip
    result = to_markdown(md_file)
    assert "Bold text" in result
    assert "Italic text" in result


@pytest.mark.integration
def test_markdown_to_ast_reference_links(tmp_path):
    """Test Markdown reference-style links to AST conversion."""
    md_content = """# Reference Links

Visit [Example Site][1] for more info.

[1]: https://example.com
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify link is resolved in roundtrip
    result = to_markdown(md_file)
    assert "Example Site" in result


@pytest.mark.integration
def test_markdown_to_ast_escaped_characters(tmp_path):
    """Test Markdown escaped characters to AST conversion."""
    md_content = r"""# Escaped Characters

This has \*escaped asterisks\* and \[escaped brackets\].

Regular *emphasis* still works.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify escaped characters are handled
    result = to_markdown(md_file)
    assert "Escaped Characters" in result


@pytest.mark.integration
def test_markdown_to_ast_html_passthrough(tmp_path):
    """Test Markdown with inline HTML to AST conversion."""
    md_content = """# HTML in Markdown

<div>This is raw HTML</div>

Regular **markdown** continues.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify HTML handling in roundtrip
    result = to_markdown(md_file)
    assert "markdown" in result.lower()


@pytest.mark.integration
def test_markdown_to_ast_footnotes(tmp_path):
    """Test Markdown footnotes to AST conversion."""
    md_content = """# Footnotes

This text has a footnote[^1].

[^1]: This is the footnote text.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify footnote handling in roundtrip
    result = to_markdown(md_file)
    assert "footnote" in result.lower()


@pytest.mark.integration
def test_markdown_to_ast_definition_lists(tmp_path):
    """Test Markdown definition lists to AST conversion."""
    md_content = """# Definition Lists

Term 1
: Definition 1

Term 2
: Definition 2a
: Definition 2b
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify definition list handling in roundtrip
    result = to_markdown(md_file)
    assert "Term 1" in result


@pytest.mark.integration
def test_markdown_to_ast_from_existing_fixture():
    """Test Markdown conversion using existing test fixture."""
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "documents"
    md_file = fixtures_dir / "basic.md"

    if not md_file.exists():
        pytest.skip("Test fixture not found")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)
    assert len(doc.children) > 0


@pytest.mark.integration
def test_markdown_to_ast_roundtrip_preservation(tmp_path):
    """Test that Markdown -> AST -> Markdown preserves content."""
    original_content = """# Test Document

This is a **test document** with *various* formatting.

## Features

- Lists
- **Bold** and *italic*
- `Code`

```python
def test():
    pass
```

[Link](https://example.com)
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(original_content, encoding="utf-8")

    # Convert to AST and back to Markdown
    doc = to_ast(md_file)
    result = to_markdown(md_file)

    # Verify key content is preserved
    assert isinstance(doc, Document)
    assert "Test Document" in result
    assert "test document" in result
    assert "Features" in result
    assert "Lists" in result
    assert "def test():" in result
    assert "https://example.com" in result


@pytest.mark.integration
def test_markdown_to_ast_with_frontmatter(tmp_path):
    """Test Markdown with YAML frontmatter to AST conversion."""
    md_content = """---
title: Test Document
author: Test Author
date: 2025-01-01
---

# Content

Document content here.
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Check if frontmatter is captured in metadata
    # (behavior depends on parser implementation)
    result = to_markdown(md_file)
    assert "Content" in result
    assert "Document content here" in result


@pytest.mark.integration
def test_markdown_to_ast_unicode_content(tmp_path):
    """Test Markdown with Unicode characters to AST conversion."""
    md_content = """# Unicode Test

Emoji: \uf600 \U00002764 \U00002b50

International: \U00004e2d\U00006587 \U00000391\U000003b1 \U00000420\U0000043e\U00000441\U00000441\U00000438\U00000439
\U00000441\U0000043a\U00000438\U00000439

Math: \U0000221e \U000000b1 \U00002260
"""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)

    # Verify Unicode is preserved
    result = to_markdown(md_file)
    assert "Unicode Test" in result


@pytest.mark.integration
def test_markdown_to_ast_empty_document(tmp_path):
    """Test empty Markdown document to AST conversion."""
    md_content = ""

    md_file = tmp_path / "empty.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)


@pytest.mark.integration
def test_markdown_to_ast_whitespace_only(tmp_path):
    """Test Markdown with only whitespace to AST conversion."""
    md_content = """




"""

    md_file = tmp_path / "whitespace.md"
    md_file.write_text(md_content, encoding="utf-8")

    doc = to_ast(md_file)

    assert isinstance(doc, Document)
