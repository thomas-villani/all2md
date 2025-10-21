"""Golden tests for HTML to Markdown conversion.

These tests use syrupy for snapshot testing to ensure HTML conversion
output remains consistent across code changes.
"""

from io import BytesIO

import pytest

from all2md import HtmlOptions, to_markdown


@pytest.mark.golden
@pytest.mark.html
@pytest.mark.unit
class TestHTMLGolden:
    """Golden/snapshot tests for HTML converter."""

    def test_basic_html_conversion(self, snapshot):
        """Test basic HTML conversion matches snapshot."""
        html = """
        <html>
        <head><title>Test Document</title></head>
        <body>
            <h1>Main Heading</h1>
            <p>This is a paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
            <p>Another paragraph with a <a href="https://example.com">link</a>.</p>
        </body>
        </html>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert result == snapshot

    def test_html_with_lists(self, snapshot):
        """Test HTML lists conversion matches snapshot."""
        html = """
        <h2>Lists</h2>
        <ul>
            <li>Unordered item 1</li>
            <li>Unordered item 2</li>
            <li>Unordered item 3</li>
        </ul>
        <ol>
            <li>Ordered item 1</li>
            <li>Ordered item 2</li>
            <li>Ordered item 3</li>
        </ol>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert result == snapshot

    def test_html_with_table(self, snapshot):
        """Test HTML table conversion matches snapshot."""
        html = """
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
                    <td>New York</td>
                </tr>
                <tr>
                    <td>Bob</td>
                    <td>25</td>
                    <td>San Francisco</td>
                </tr>
            </tbody>
        </table>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert result == snapshot

    def test_html_with_code_blocks(self, snapshot):
        """Test HTML code blocks conversion matches snapshot."""
        html = """
        <h2>Code Example</h2>
        <p>Inline <code>code</code> example.</p>
        <pre><code class="language-python">
def hello_world():
    print("Hello, World!")
        </code></pre>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert result == snapshot

    def test_html_with_nested_elements(self, snapshot):
        """Test HTML with nested elements matches snapshot."""
        html = """
        <div>
            <h1>Main Title</h1>
            <div>
                <h2>Subsection</h2>
                <p>Paragraph in subsection with <strong>nested <em>formatting</em></strong>.</p>
                <blockquote>
                    <p>A quote within the subsection.</p>
                </blockquote>
            </div>
        </div>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert result == snapshot

    def test_html_with_images_alt_text_mode(self, snapshot):
        """Test HTML images in alt-text mode matches snapshot."""
        html = """
        <h2>Images</h2>
        <img src="https://example.com/image1.png" alt="First image">
        <img src="https://example.com/image2.jpg" alt="Second image">
        """

        options = HtmlOptions(attachment_mode="alt_text")
        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html", parser_options=options)
        assert result == snapshot

    def test_html_with_dangerous_content_stripped(self, snapshot):
        """Test HTML with dangerous content stripped matches snapshot."""
        html = """
        <h1>Safe Content</h1>
        <p>This is safe.</p>
        <script>alert('XSS')</script>
        <iframe src="evil.com"></iframe>
        <p>More safe content.</p>
        """

        options = HtmlOptions(strip_dangerous_elements=True)
        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html", parser_options=options)
        assert result == snapshot

    def test_html_with_metadata_extraction(self, snapshot):
        """Test HTML with metadata extraction matches snapshot."""
        html = """
        <html>
        <head>
            <title>Document Title</title>
            <meta name="author" content="John Doe">
            <meta name="description" content="Test document">
        </head>
        <body>
            <h1>Content</h1>
            <p>Body text.</p>
        </body>
        </html>
        """

        options = HtmlOptions(extract_title=True, extract_metadata=True)
        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html", parser_options=options)
        assert result == snapshot

    def test_html_with_complex_formatting(self, snapshot):
        """Test HTML with complex formatting matches snapshot."""
        html = """
        <h1>Complex Formatting</h1>
        <p>Text with <strong>bold</strong>, <em>italic</em>, <code>code</code>,
        <del>strikethrough</del>, and <mark>highlighted</mark> text.</p>
        <p>Text with <sub>subscript</sub> and <sup>superscript</sup>.</p>
        <p>A paragraph with<br>line<br>breaks.</p>
        <hr>
        <p>After horizontal rule.</p>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert result == snapshot

    def test_html_empty_document(self, snapshot):
        """Test empty HTML document matches snapshot."""
        html = "<html><body></body></html>"

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert result == snapshot
