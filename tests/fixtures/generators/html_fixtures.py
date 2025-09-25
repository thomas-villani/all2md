"""HTML test fixture generators for testing HTML-to-Markdown conversion.

This module provides functions to programmatically create HTML documents
for testing various aspects of HTML-to-Markdown conversion.
"""

import tempfile
from pathlib import Path
from io import StringIO
from typing import Optional, List, Dict


def create_html_with_formatting() -> str:
    """Create HTML with various text formatting for testing emphasis detection.

    Returns
    -------
    str
        HTML string with bold, italic, code, and other formatting.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Formatting Test Document</title>
</head>
<body>
    <h1>Formatting Test Document</h1>

    <p>This paragraph contains <strong>bold text</strong>, <em>italic text</em>,
    and <code>inline code</code>.</p>

    <p>This paragraph has <strong><em>bold and italic text</em></strong> combined.</p>

    <h2>Level 2 Heading</h2>
    <p>Content under level 2 heading.</p>

    <h3>Level 3 Heading</h3>
    <p>Content under level 3 heading.</p>

    <h4>Level 4 Heading</h4>
    <p>Content under level 4 heading.</p>

    <h5>Level 5 Heading</h5>
    <p>Content under level 5 heading.</p>

    <h6>Level 6 Heading</h6>
    <p>Content under level 6 heading.</p>

    <p>Alternative emphasis: <b>bold with b tag</b> and <i>italic with i tag</i>.</p>

    <p>Text with <span style="text-decoration: underline;">underlined content</span>.</p>

    <p>Text with <del>strikethrough</del> content.</p>

    <blockquote>
        <p>This is a blockquote with some important information.</p>
    </blockquote>
</body>
</html>"""
    return html


def create_html_with_tables() -> str:
    """Create HTML with tables for testing table conversion.

    Returns
    -------
    str
        HTML string with various table structures.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Table Test Document</title>
</head>
<body>
    <h1>Table Test Document</h1>

    <p>Here is a simple table:</p>

    <table border="1">
        <thead>
            <tr>
                <th>Name</th>
                <th>Age</th>
                <th>City</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Alice Johnson</td>
                <td>25</td>
                <td>New York</td>
            </tr>
            <tr>
                <td>Bob Smith</td>
                <td>30</td>
                <td>San Francisco</td>
            </tr>
            <tr>
                <td>Carol Davis</td>
                <td>28</td>
                <td>Los Angeles</td>
            </tr>
        </tbody>
    </table>

    <p>Here is a table with complex formatting:</p>

    <table border="1">
        <thead>
            <tr>
                <th>Product</th>
                <th>Q1</th>
                <th>Q2</th>
                <th>Total</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Product A</strong></td>
                <td>100</td>
                <td>150</td>
                <td>250</td>
            </tr>
            <tr>
                <td><strong>Product B</strong></td>
                <td>200</td>
                <td>180</td>
                <td>380</td>
            </tr>
            <tr style="font-weight: bold;">
                <td>Total</td>
                <td>300</td>
                <td>330</td>
                <td>630</td>
            </tr>
        </tbody>
    </table>

    <p>Table with merged cells (using colspan and rowspan):</p>

    <table border="1">
        <tr>
            <th colspan="2">Header spanning two columns</th>
            <th>Single Header</th>
        </tr>
        <tr>
            <td>Data 1</td>
            <td>Data 2</td>
            <td rowspan="2">Spanning two rows</td>
        </tr>
        <tr>
            <td>Data 3</td>
            <td>Data 4</td>
        </tr>
    </table>
</body>
</html>"""
    return html


def create_html_with_lists() -> str:
    """Create HTML with various list types for testing list conversion.

    Returns
    -------
    str
        HTML string with bullet lists, numbered lists, and nested lists.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>List Test Document</title>
</head>
<body>
    <h1>List Test Document</h1>

    <p>Simple bullet list:</p>
    <ul>
        <li>First bullet item</li>
        <li>Second bullet item</li>
        <li>Third bullet item</li>
    </ul>

    <p>Numbered list:</p>
    <ol>
        <li>First numbered item</li>
        <li>Second numbered item</li>
        <li>Third numbered item</li>
    </ol>

    <p>Nested list example:</p>
    <ul>
        <li>Main item 1
            <ul>
                <li>Sub-item 1.1</li>
                <li>Sub-item 1.2</li>
            </ul>
        </li>
        <li>Main item 2
            <ol>
                <li>Sub-item 2.1</li>
                <li>Sub-item 2.2</li>
            </ol>
        </li>
        <li>Main item 3</li>
    </ul>

    <p>List with formatted text:</p>
    <ul>
        <li>Item with <strong>bold text</strong> in it</li>
        <li>Item with <em>italic text</em> in it</li>
        <li>Item with <code>inline code</code> in it</li>
        <li>Item with <a href="https://example.com">a link</a> in it</li>
    </ul>

    <p>Definition list:</p>
    <dl>
        <dt>Term 1</dt>
        <dd>Definition of term 1</dd>
        <dt>Term 2</dt>
        <dd>Definition of term 2 with <em>formatting</em></dd>
    </dl>
</body>
</html>"""
    return html


def create_html_with_code_blocks() -> str:
    """Create HTML with code blocks for testing code conversion.

    Returns
    -------
    str
        HTML string with various code block formats.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Code Block Test Document</title>
</head>
<body>
    <h1>Code Block Test Document</h1>

    <p>This document contains various code formats.</p>

    <p>Inline code: <code>print("Hello, World!")</code></p>

    <p>Pre-formatted text block:</p>
    <pre>function hello() {
    console.log("Hello, World!");
    return true;
}</pre>

    <p>Code block with code tag:</p>
    <pre><code>def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)</code></pre>

    <p>Code block with language specification:</p>
    <pre><code class="language-python">class TestClass:
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value</code></pre>

    <p>Code block with syntax highlighting class:</p>
    <pre><code class="python">import os
import sys

def main():
    print("Starting application...")
    return 0

if __name__ == "__main__":
    main()</code></pre>

    <p>Multiple inline code elements: <code>var x = 1;</code> and <code>var y = 2;</code></p>
</body>
</html>"""
    return html


def create_html_with_links() -> str:
    """Create HTML with various link types for testing link conversion.

    Returns
    -------
    str
        HTML string with different types of hyperlinks.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Link Test Document</title>
</head>
<body>
    <h1>Link Test Document</h1>

    <p>This document contains various types of links:</p>

    <p>Simple external link: <a href="https://www.example.com">Example.com</a></p>

    <p>Link with title: <a href="https://www.google.com" title="Search Engine">Google</a></p>

    <p>Email link: <a href="mailto:contact@example.com">Contact us</a></p>

    <p>Phone link: <a href="tel:+1234567890">Call us</a></p>

    <p>Internal anchor link: <a href="#section2">Go to Section 2</a></p>

    <p>Link with formatting: <a href="https://example.com"><strong>Bold link text</strong></a></p>

    <p>Multiple links in one paragraph: Visit <a href="https://github.com">GitHub</a> or
    <a href="https://stackoverflow.com">Stack Overflow</a> for help.</p>

    <p>Link that opens in new window: <a href="https://example.com" target="_blank">Open in new tab</a></p>

    <h2 id="section2">Section 2</h2>
    <p>This is the section referenced by the internal link above.</p>

    <p>Relative link: <a href="../other-page.html">Other page</a></p>

    <p>Link with complex content: <a href="https://example.com">
        <span>Complex</span> <em>formatted</em> <strong>link</strong> text
    </a></p>
</body>
</html>"""
    return html


def create_html_with_nested_elements() -> str:
    """Create HTML with deeply nested elements for testing complex parsing.

    Returns
    -------
    str
        HTML string with nested elements and complex structure.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nested Elements Test</title>
</head>
<body>
    <h1>Nested Elements Test Document</h1>

    <div class="content">
        <p>This paragraph contains <strong>bold text with <em>nested italic</em> inside</strong>.</p>

        <blockquote>
            <p>This blockquote contains <code>inline code</code> and a
            <a href="https://example.com">link with <strong>bold text</strong></a>.</p>

            <ul>
                <li>List item in blockquote</li>
                <li>Another list item with <em>emphasis</em></li>
            </ul>
        </blockquote>

        <div class="section">
            <h2>Section with nested content</h2>
            <p>Paragraph with <span class="highlight">highlighted <strong>bold</strong> text</span>.</p>

            <table border="1">
                <tr>
                    <th>Header with <em>italic</em></th>
                    <th>Another Header</th>
                </tr>
                <tr>
                    <td>Cell with <a href="#">link</a></td>
                    <td>Cell with <code>code</code></td>
                </tr>
            </table>
        </div>

        <p>Complex nesting: <strong>Bold <em>italic <code>code</code> text</em> end bold</strong></p>

        <ul>
            <li>Item with <blockquote><p>nested blockquote</p></blockquote></li>
            <li>Item with nested list:
                <ol>
                    <li>Nested <strong>bold</strong> item</li>
                    <li>Another nested item with <a href="#">link</a></li>
                </ol>
            </li>
        </ul>
    </div>
</body>
</html>"""
    return html


def create_html_with_entities() -> str:
    """Create HTML with HTML entities for testing entity conversion.

    Returns
    -------
    str
        HTML string with various HTML entities.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>HTML Entities Test</title>
</head>
<body>
    <h1>HTML Entities Test Document</h1>

    <p>Common entities: &amp; (ampersand), &lt; (less than), &gt; (greater than)</p>

    <p>Quotes: &quot;double quotes&quot; and &apos;single quotes&apos;</p>

    <p>Spaces: regular&nbsp;non-breaking&nbsp;spaces</p>

    <p>Copyright &copy; 2023 and trademark &trade; symbols</p>

    <p>Mathematical: 2 &times; 3 = 6, 8 &divide; 2 = 4, x &plusmn; y</p>

    <p>Arrows: &larr; left, &rarr; right, &uarr; up, &darr; down</p>

    <p>Currency: &dollar;100, &euro;50, &pound;25, &yen;1000</p>

    <p>Accented characters: caf&eacute;, na&iuml;ve, pi&ntilde;a</p>

    <p>Greek letters: &alpha;, &beta;, &gamma;, &delta;, &pi;, &omega;</p>

    <p>Numeric entities: &#8220;left double quote&#8221; and &#8216;right single quote&#8217;</p>

    <p>Unicode: &#x2665; (heart), &#x2600; (sun), &#x2603; (snowman)</p>
</body>
</html>"""
    return html


def create_minimal_html(title: str = "Test Document", content: str = "Test content") -> str:
    """Create a minimal HTML document for basic testing.

    Parameters
    ----------
    title : str, optional
        Document title, by default "Test Document"
    content : str, optional
        Document content, by default "Test content"

    Returns
    -------
    str
        Simple HTML document with title and content.
    """
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
    <h1>{title}</h1>
    <p>{content}</p>
</body>
</html>"""
    return html


def create_html_file(html_content: str, file_path: Optional[Path] = None) -> Path:
    """Save HTML content to a file.

    Parameters
    ----------
    html_content : str
        HTML content to save
    file_path : Path, optional
        File path to save to, by default creates temporary file

    Returns
    -------
    Path
        Path to the saved file
    """
    if file_path is None:
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
        file_path = Path(temp_file.name)
        temp_file.write(html_content)
        temp_file.close()
    else:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    return file_path