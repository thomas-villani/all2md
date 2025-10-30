"""Integration tests for HTML to Markdown conversion."""

from pathlib import Path

import pytest

from all2md import to_ast, to_markdown
from all2md.options.html import HtmlOptions


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_basic(tmp_path):
    """Test basic HTML to Markdown conversion."""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test Document</title>
</head>
<body>
    <h1>Main Heading</h1>
    <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
    <h2>Subheading</h2>
    <p>Another paragraph.</p>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "# Main Heading" in result
    assert "## Subheading" in result
    assert "**bold**" in result
    assert "*italic*" in result
    assert "This is a paragraph" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_lists(tmp_path):
    """Test HTML lists conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Lists Example</h1>
    <ul>
        <li>Unordered item 1</li>
        <li>Unordered item 2</li>
        <li>Unordered item 3</li>
    </ul>
    <ol>
        <li>Ordered item 1</li>
        <li>Ordered item 2</li>
    </ol>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "# Lists Example" in result
    assert "Unordered item 1" in result
    assert "Unordered item 2" in result
    assert "Ordered item 1" in result
    assert "Ordered item 2" in result
    assert "- " in result or "* " in result  # Unordered list markers
    assert "1. " in result  # Ordered list markers


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_tables(tmp_path):
    """Test HTML tables conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Table Example</h1>
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>Age</th>
                <th>City</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Alice</td>
                <td>30</td>
                <td>NYC</td>
            </tr>
            <tr>
                <td>Bob</td>
                <td>25</td>
                <td>LA</td>
            </tr>
        </tbody>
    </table>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "| Name" in result or "|Name" in result
    assert "Alice" in result
    assert "Bob" in result
    assert "NYC" in result
    assert "|" in result  # Table markers


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_code_blocks(tmp_path):
    """Test HTML code blocks conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Code Example</h1>
    <p>Here is some <code>inline code</code>.</p>
    <pre><code>def hello():
    return "Hello, World!"</code></pre>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "# Code Example" in result
    assert "`inline code`" in result
    assert "def hello():" in result
    assert "Hello, World!" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_links(tmp_path):
    """Test HTML links conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Links Example</h1>
    <p>Visit <a href="https://example.com">Example Site</a> for more info.</p>
    <p>Also check <a href="https://github.com">GitHub</a>.</p>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "[Example Site]" in result
    assert "https://example.com" in result
    assert "[GitHub]" in result
    assert "https://github.com" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_blockquotes(tmp_path):
    """Test HTML blockquotes conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Blockquote Example</h1>
    <blockquote>
        <p>This is a quoted text.</p>
        <p>With multiple paragraphs.</p>
    </blockquote>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "> " in result
    assert "This is a quoted text" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_images(tmp_path):
    """Test HTML images conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Image Example</h1>
    <p>Here is an image:</p>
    <img src="https://example.com/image.jpg" alt="Example Image" />
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "![" in result
    assert "Example Image" in result
    assert "https://example.com/image.jpg" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_nested_lists(tmp_path):
    """Test HTML nested lists conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Nested Lists</h1>
    <ul>
        <li>Item 1
            <ul>
                <li>Nested item 1.1</li>
                <li>Nested item 1.2</li>
            </ul>
        </li>
        <li>Item 2</li>
    </ul>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "Item 1" in result
    assert "Nested item 1.1" in result
    assert "Nested item 1.2" in result
    assert "Item 2" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_with_parser_options(tmp_path):
    """Test HTML conversion with parser options."""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Document Title</title>
</head>
<body>
    <h1>Main Content</h1>
    <p>Body text.</p>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    # Test with extract_title option
    options = HtmlOptions(extract_title=True)
    doc = to_ast(html_file, parser_options=options)

    assert doc.metadata.get("title") == "Document Title"


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_horizontal_rules(tmp_path):
    """Test HTML horizontal rules conversion to Markdown."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Section 1</h1>
    <p>Content 1</p>
    <hr>
    <h1>Section 2</h1>
    <p>Content 2</p>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "---" in result or "***" in result or "- - -" in result
    assert "Section 1" in result
    assert "Section 2" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_complex_formatting(tmp_path):
    """Test HTML with complex formatting combinations."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Complex Formatting</h1>
    <p>Text with <strong><em>bold and italic</em></strong> combined.</p>
    <p>Text with <code><strong>bold code</strong></code>.</p>
    <p>Link with <a href="https://example.com"><strong>bold text</strong></a>.</p>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "# Complex Formatting" in result
    assert "bold and italic" in result
    assert "bold code" in result
    assert "https://example.com" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_headings_hierarchy(tmp_path):
    """Test HTML headings hierarchy conversion."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Level 1</h1>
    <h2>Level 2</h2>
    <h3>Level 3</h3>
    <h4>Level 4</h4>
    <h5>Level 5</h5>
    <h6>Level 6</h6>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "# Level 1" in result
    assert "## Level 2" in result
    assert "### Level 3" in result
    assert "#### Level 4" in result
    assert "##### Level 5" in result
    assert "###### Level 6" in result


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_from_existing_fixture():
    """Test HTML conversion using existing test fixture."""
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "documents"
    html_file = fixtures_dir / "basic.html"

    if not html_file.exists():
        pytest.skip("Test fixture not found")

    result = to_markdown(html_file)

    # Basic assertions that the conversion succeeded
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.integration
@pytest.mark.html
def test_html_to_markdown_readability_article():
    """Test HTML conversion with readability article fixture."""
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "documents"
    html_file = fixtures_dir / "html_readability_article.html"

    if not html_file.exists():
        pytest.skip("Test fixture not found")

    result = to_markdown(html_file)

    # Basic assertions that the conversion succeeded
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.integration
@pytest.mark.html
def test_html_to_ast_conversion(tmp_path):
    """Test HTML to AST conversion pipeline."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>AST Test</h1>
    <p>Testing AST conversion.</p>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    doc = to_ast(html_file)

    # Verify AST structure
    assert doc is not None
    assert doc.children is not None
    assert len(doc.children) > 0

    # Verify content in AST
    markdown_output = to_markdown(html_file)
    assert "AST Test" in markdown_output


@pytest.mark.integration
@pytest.mark.html
def test_html_with_meta_tags(tmp_path):
    """Test HTML with meta tags for metadata extraction."""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta name="author" content="Test Author" />
    <meta name="description" content="Test Description" />
    <meta name="keywords" content="test, html, conversion" />
    <title>Test Document</title>
</head>
<body>
    <h1>Content</h1>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    doc = to_ast(html_file, parser_options=HtmlOptions(extract_title=True))

    # Check metadata
    assert doc.metadata.get("title") == "Test Document"


@pytest.mark.integration
@pytest.mark.html
def test_html_with_inline_styles_removal(tmp_path):
    """Test that inline styles are removed from HTML."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1 style="color: red;">Styled Heading</h1>
    <p style="font-size: 16px;">Styled paragraph.</p>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "Styled Heading" in result
    assert "Styled paragraph" in result
    assert "color: red" not in result  # Style should be stripped
    assert "font-size" not in result  # Style should be stripped


@pytest.mark.integration
@pytest.mark.html
def test_html_with_script_and_style_tags(tmp_path):
    """Test that script and style tags are removed."""
    html_content = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { background-color: white; }
    </style>
    <script>
        console.log("Hello");
    </script>
</head>
<body>
    <h1>Main Content</h1>
    <p>Visible text.</p>
    <script>
        alert("Test");
    </script>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    result = to_markdown(html_file)

    assert "Main Content" in result
    assert "Visible text" in result
    assert "console.log" not in result  # Script should be removed
    assert "background-color" not in result  # Style should be removed
    assert "alert" not in result  # Script should be removed
