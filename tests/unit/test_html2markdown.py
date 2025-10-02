import pytest

from all2md.parsers.html2markdown import html_to_markdown
from all2md.options import HtmlOptions, MarkdownOptions



@pytest.mark.unit
def test_title_extraction_default_and_no_hash():
    html = "<html><head><title>My Title</title></head><body><p>Para</p></body></html>"
    md_opts_hash = MarkdownOptions(use_hash_headings=True)
    md_default = html_to_markdown(html, options=HtmlOptions(extract_title=True, markdown_options=md_opts_hash))
    assert md_default == "# My Title\n\nPara"
    md_opts_underline = MarkdownOptions(use_hash_headings=False)
    md_no_hash = html_to_markdown(html, options=HtmlOptions(extract_title=True, markdown_options=md_opts_underline))
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
        detect_table_alignment=True,
        convert_nbsp=True,
        markdown_options=MarkdownOptions(escape_special=True),
    )

    result = html_to_markdown(html, options=options)

    assert "\\*" in result  # Escaped special chars
    assert "&" in result  # Decoded entities
    assert "*Data Table*" in result  # Caption
    assert ":---:" in result  # Center alignment
    assert "alert" not in result  # Sanitized dangerous content
