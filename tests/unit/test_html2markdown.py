import pytest

from all2md.converters.html2markdown import HTMLToMarkdown, html_to_markdown
from all2md.options import HtmlOptions, MarkdownOptions


@pytest.mark.unit
def test_heading_hash_true():
    html = "<h1>Title</h1><h2>Sub</h2>"
    converter = HTMLToMarkdown(hash_headings=True)
    md = converter.convert(html)
    assert md == "# Title\n\n## Sub"


@pytest.mark.unit
def test_heading_hash_false():
    html = "<h1>Title</h1><h2>Sub</h2>"
    converter = HTMLToMarkdown(hash_headings=False)
    md = converter.convert(html)
    assert md == "Title\n=====\n\nSub\n---"


@pytest.mark.unit
def test_paragraph_and_inline_formatting():
    html = "<p>This is <strong>bold</strong>, <em>italic</em>, and <code>code</code>.</p>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "This is **bold**, *italic*, and `code`."


@pytest.mark.unit
def test_line_break_and_horizontal_rule():
    html = "Line1<br>Line2<hr>Line3"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "Line1\nLine2\n\n---\n\nLine3"


@pytest.mark.unit
def test_unordered_list_simple():
    html = "<ul><li>One</li><li>Two</li></ul>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "* One\n* Two"


@pytest.mark.unit
def test_ordered_list_simple():
    html = "<ol><li>First</li><li>Second</li></ol>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "1. First\n2. Second"


@pytest.mark.unit
def test_unordered_list_nested():
    html = "<ul><li>Parent<ul><li>Child</li></ul></li></ul>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "* Parent\n  - Child"


@pytest.mark.unit
def test_ordered_list_nested():
    html = "<ol><li>Parent<ol><li>Child</li></ol></li></ol>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "1. Parent\n   1. Child"


@pytest.mark.unit
def test_mixed_list_symbols_and_depth():
    html = "<ul><li>A<ul><li>B<ol><li>C</li></ol></li></ul></li></ul>"
    converter = HTMLToMarkdown(bullet_symbols="*+")
    md = converter.convert(html)
    expected = "* A\n  + B\n     1. C"
    assert md == expected


@pytest.mark.unit
def test_link_with_and_without_title():
    html_title = '<a href="http://example.com" title="T">link</a>'
    html_no_title = '<a href="http://example.com">link</a>'
    converter = HTMLToMarkdown()
    md1 = converter.convert(html_title)
    md2 = converter.convert(html_no_title)
    assert md1 == '[link](http://example.com "T")'
    assert md2 == "[link](http://example.com)"


@pytest.mark.unit
def test_image_and_removal():
    html = '<img src="img.png" alt="Alt" title="T">'
    conv_keep = HTMLToMarkdown(attachment_mode="alt_text")
    conv_remove = HTMLToMarkdown(attachment_mode="skip")
    assert conv_keep.convert(html) == "![Alt]"
    assert conv_remove.convert(html) == ""


@pytest.mark.unit
def test_code_block_language_class():
    html = '<pre class="python"><code>print("hi")</code></pre>'
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == '```python\nprint("hi")\n```'


@pytest.mark.unit
def test_inline_code_and_special_characters():
    html = "<p>* _ ` # + - . ! [ ] ( ) { } \\</p>"
    # Default behavior now escapes special characters
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert "\\*" in md and "\\_" in md and "\\#" in md  # Should be escaped by default

    # Test with escaping disabled
    from all2md.options import MarkdownOptions

    converter_no_escape = HTMLToMarkdown(markdown_options=MarkdownOptions(escape_special=False))
    md_no_escape = converter_no_escape.convert(html)
    assert md_no_escape == "* _ ` # + - . ! [ ] ( ) { } \\"


@pytest.mark.unit
def test_blockquote_simple():
    html = "<blockquote>Quote</blockquote>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "> Quote"


@pytest.mark.unit
def test_table_with_header_and_rows():
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    expected = "| A | B |\n|:---:|:---:|\n| 1 | 2 |"
    assert md == expected


@pytest.mark.unit
def test_mixed_content_div():
    html = "<div><p>X</p><ul><li><em>I</em></li></ul></div>"
    converter = HTMLToMarkdown()
    md = converter.convert(html)
    assert md == "X\n\n* *I*"


@pytest.mark.unit
def test_empty_elements():
    conv = HTMLToMarkdown()
    assert conv.convert("<p></p>") == ""
    assert conv.convert("<ul><li></li></ul>") == ""


@pytest.mark.unit
def test_custom_emphasis_symbol_and_bullets():
    html = "<p><em>italic</em> <strong>bold</strong></p><ul><li>One</li></ul>"
    converter = HTMLToMarkdown(emphasis_symbol="_", bullet_symbols="x")
    md = converter.convert(html)
    assert md == "_italic_ __bold__\n\nx One"


@pytest.mark.unit
def test_title_extraction_default_and_no_hash():
    html = "<html><head><title>My Title</title></head><body><p>Para</p></body></html>"
    md_default = html_to_markdown(html, options=HtmlOptions(extract_title=True, use_hash_headings=True))
    assert md_default == "# My Title\n\nPara"
    md_no_hash = html_to_markdown(html, options=HtmlOptions(extract_title=True, use_hash_headings=False))
    assert md_no_hash == "My Title\n========\n\nPara"


@pytest.mark.unit
def test_html_to_markdown_alias():
    assert html_to_markdown("<p>Hi</p>") == "Hi"


# New tests for enhanced features


@pytest.mark.unit
def test_markdown_escaping_enabled():
    """Test that special Markdown characters are escaped when escape_special is True."""
    html = "<p>Text with * and _ and # characters</p>"
    options = HtmlOptions(markdown_options=MarkdownOptions(escape_special=True))
    result = html_to_markdown(html, options=options)
    assert "\\*" in result and "\\_" in result and "\\#" in result


@pytest.mark.unit
def test_markdown_escaping_disabled():
    """Test that special characters are not escaped when escape_special is False."""
    html = "<p>Text with * and _ and # characters</p>"
    options = HtmlOptions(markdown_options=MarkdownOptions(escape_special=False))
    result = html_to_markdown(html, options=options)
    assert "\\*" not in result and "\\_" not in result and "\\#" not in result


@pytest.mark.unit
def test_dynamic_code_fencing():
    """Test that code blocks use appropriate fence lengths based on content."""
    html_simple = "<pre><code>print('hello')</code></pre>"
    html_with_backticks = "<pre><code>Use ```markdown``` syntax</code></pre>"

    converter = HTMLToMarkdown()
    result_simple = converter.convert(html_simple)
    result_backticks = converter.convert(html_with_backticks)

    assert result_simple.startswith("```")
    assert "````" in result_backticks or "`````" in result_backticks


@pytest.mark.unit
def test_table_with_caption():
    """Test table processing with caption support."""
    html = """
    <table>
        <caption>Table Caption</caption>
        <tr><th>A</th><th>B</th></tr>
        <tr><td>1</td><td>2</td></tr>
    </table>
    """
    converter = HTMLToMarkdown()
    result = converter.convert(html)
    assert "*Table Caption*" in result


@pytest.mark.unit
def test_table_alignment_detection():
    """Test table alignment detection from HTML attributes."""
    html = """
    <table>
        <tr>
            <th align="left">Left</th>
            <th align="center">Center</th>
            <th align="right">Right</th>
        </tr>
        <tr><td>1</td><td>2</td><td>3</td></tr>
    </table>
    """
    converter = HTMLToMarkdown(table_alignment_auto_detect=True)
    result = converter.convert(html)
    assert ":---" in result
    assert ":---:" in result
    assert "---:" in result


@pytest.mark.unit
def test_html_entity_decoding():
    """Test HTML entity decoding functionality."""
    html = "<p>Text with &amp; and &lt; and &gt; entities</p>"
    converter = HTMLToMarkdown()
    result = converter.convert(html)
    assert "&" in result and "<" in result and ">" in result


@pytest.mark.unit
def test_convert_nbsp():
    """Test non-breaking space preservation."""
    html = "<p>Text&nbsp;with&nbsp;nbsp</p>"
    converter_preserve = HTMLToMarkdown(convert_nbsp=True)
    converter_no_preserve = HTMLToMarkdown(convert_nbsp=False)

    result_preserve = converter_preserve.convert(html)
    result_no_preserve = converter_no_preserve.convert(html)

    # Both should handle nbsp, but preserve option affects internal handling
    assert "Text" in result_preserve and "with" in result_preserve
    assert "Text" in result_no_preserve and "with" in result_no_preserve


@pytest.mark.unit
def test_content_sanitization():
    """Test removal of dangerous HTML elements."""
    dangerous_html = """
    <p>Safe content</p>
    <script>alert('dangerous')</script>
    <style>body { display: none; }</style>
    <p>More safe content</p>
    """
    converter_sanitize = HTMLToMarkdown(strip_dangerous_elements=True)
    converter_no_sanitize = HTMLToMarkdown(strip_dangerous_elements=False)

    result_sanitize = converter_sanitize.convert(dangerous_html)
    result_no_sanitize = converter_no_sanitize.convert(dangerous_html)

    assert "Safe content" in result_sanitize and "More safe content" in result_sanitize
    assert "alert" not in result_sanitize and "display: none" not in result_sanitize
    # Default behavior should also remove script/style
    assert "alert" not in result_no_sanitize and "display: none" not in result_no_sanitize


@pytest.mark.unit
def test_definition_lists():
    """Test definition list (dl/dt/dd) conversion."""
    html = """
    <dl>
        <dt>Term 1</dt>
        <dd>Definition 1</dd>
        <dt>Term 2</dt>
        <dd>Definition 2</dd>
    </dl>
    """
    converter = HTMLToMarkdown()
    result = converter.convert(html)
    assert "**Term 1**" in result and ": Definition 1" in result
    assert "**Term 2**" in result and ": Definition 2" in result


@pytest.mark.unit
def test_nested_blockquotes():
    """Test improved nested blockquote handling."""
    html = """
    <blockquote>
        <p>First level quote</p>
        <blockquote>
            <p>Second level quote</p>
        </blockquote>
    </blockquote>
    """
    converter = HTMLToMarkdown(preserve_nested_structure=True)
    result = converter.convert(html)
    assert "> First level quote" in result
    # Should have proper nested quoting
    lines = result.split("\n")
    nested_quotes = [line for line in lines if line.startswith("> >")]
    assert len(nested_quotes) > 0


@pytest.mark.unit
def test_base_url_resolution():
    """Test base URL resolution for relative links and images."""
    html = '<p><a href="/page">Link</a> <img src="/image.jpg" alt="Image"></p>'
    converter = HTMLToMarkdown(attachment_base_url="https://example.com")
    result = converter.convert(html)
    assert "https://example.com/page" in result
    assert "https://example.com/image.jpg" in result


@pytest.mark.unit
def test_image_removal():
    """Test image removal functionality."""
    html = '<p>Text <img src="image.jpg" alt="Image"> more text</p>'
    converter = HTMLToMarkdown(attachment_mode="skip")
    result = converter.convert(html)
    assert "![Image]" not in result
    assert "Text" in result and "more text" in result


@pytest.mark.unit
def test_multiple_header_rows():
    """Test table with multiple header rows."""
    html = """
    <table>
        <thead>
            <tr><th>Group A</th><th>Group B</th></tr>
            <tr><th>Sub 1</th><th>Sub 2</th></tr>
        </thead>
        <tbody>
            <tr><td>Data 1</td><td>Data 2</td></tr>
        </tbody>
    </table>
    """
    converter = HTMLToMarkdown()
    result = converter.convert(html)
    _lines = result.strip().split("\n")
    # Should have main header, separator, additional header row, then data
    assert "Group A" in result and "Group B" in result
    assert "Sub 1" in result and "Sub 2" in result
    assert "Data 1" in result and "Data 2" in result


@pytest.mark.unit
def test_empty_elements_handling():
    """Test handling of empty HTML elements."""
    html = """
    <p></p>
    <div></div>
    <ul><li></li></ul>
    <blockquote></blockquote>
    """
    converter = HTMLToMarkdown()
    result = converter.convert(html).strip()
    # Should not produce excessive whitespace or empty content
    assert len(result) == 0 or result.count("\n") < 5


@pytest.mark.unit
def test_options_object_usage():
    """Test using HtmlOptions object with all new features."""
    html = """
    <div>
        <h1>Title with * special chars</h1>
        <p>Text with &amp; entities</p>
        <table>
            <caption>Data Table</caption>
            <tr><th align="center">Centered</th></tr>
            <tr><td>Value</td></tr>
        </table>
        <script>alert('danger')</script>
    </div>
    """

    options = HtmlOptions(
        extract_title=False,
        strip_dangerous_elements=True,
        table_alignment_auto_detect=True,
        convert_nbsp=True,
        markdown_options=MarkdownOptions(escape_special=True),
    )

    result = html_to_markdown(html, options=options)

    assert "\\*" in result  # Escaped special chars
    assert "&" in result  # Decoded entities
    assert "*Data Table*" in result  # Caption
    assert ":---:" in result  # Center alignment
    assert "alert" not in result  # Sanitized dangerous content


@pytest.mark.unit
def test_code_fence_with_language():
    """Test code blocks with language specification."""
    html = '<pre class="python"><code>def hello():\n    print("world")</code></pre>'
    converter = HTMLToMarkdown()
    result = converter.convert(html)
    assert "```python" in result
    assert "def hello():" in result


@pytest.mark.unit
def test_inline_code_with_backticks():
    """Test inline code containing backticks."""
    html = "<p>Use <code>`markdown`</code> syntax</p>"
    converter = HTMLToMarkdown()
    result = converter.convert(html)
    # Should handle backticks within inline code appropriately
    assert "`" in result
