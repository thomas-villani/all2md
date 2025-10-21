"""MHTML test fixture generators for testing MHTML-to-Markdown conversion.

This module provides functions to programmatically create MHTML files
for testing various aspects of MHTML-to-Markdown conversion.
"""

import base64
import tempfile
from pathlib import Path
from typing import Optional


def create_simple_mhtml() -> bytes:
    """Create a simple MHTML file with basic HTML content for testing.

    Returns
    -------
    bytes
        MHTML file content as bytes.

    """
    mhtml_content = """MIME-Version: 1.0
Content-Type: multipart/related;
	boundary="----MultipartBoundary--001"

------MultipartBoundary--001
Content-Type: text/html; charset=utf-8
Content-Location: http://example.com/test.html

<!DOCTYPE html>
<html>
<head>
    <title>Test MHTML Document</title>
</head>
<body>
    <h1>Test MHTML Document</h1>
    <p>This is a simple MHTML document with <strong>bold</strong> and <em>italic</em> text.</p>
    <p>It also contains a <a href="https://example.com">link</a>.</p>
    <ul>
        <li>First item</li>
        <li>Second item</li>
        <li>Third item</li>
    </ul>
</body>
</html>

------MultipartBoundary--001--
"""
    return mhtml_content.encode("utf-8")


def create_mhtml_with_image() -> bytes:
    """Create MHTML file with embedded image for testing image handling.

    Returns
    -------
    bytes
        MHTML file content as bytes.

    """
    # Create a simple 1x1 PNG image
    test_image_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    # Base64 encode the image
    image_b64 = base64.b64encode(test_image_data).decode("ascii")

    mhtml_content = f"""MIME-Version: 1.0
Content-Type: multipart/related;
	boundary="----MultipartBoundary--002"

------MultipartBoundary--002
Content-Type: text/html; charset=utf-8
Content-Location: http://example.com/test.html

<!DOCTYPE html>
<html>
<head>
    <title>Test MHTML with Image</title>
</head>
<body>
    <h1>Test MHTML with Image</h1>
    <p>This document contains an embedded image:</p>
    <img src="cid:test_image.png" alt="Test image" width="100" height="100">
    <p>Text after the image.</p>
</body>
</html>

------MultipartBoundary--002
Content-Type: image/png
Content-ID: <test_image.png>
Content-Transfer-Encoding: base64

{image_b64}

------MultipartBoundary--002--
"""
    return mhtml_content.encode("utf-8")


def create_mhtml_with_ms_word_artifacts() -> bytes:
    """Create MHTML file with MS Word artifacts for testing cleanup.

    Returns
    -------
    bytes
        MHTML file content as bytes.

    """
    mhtml_content = """MIME-Version: 1.0
Content-Type: multipart/related;
	boundary="----MultipartBoundary--003"

------MultipartBoundary--003
Content-Type: text/html; charset=utf-8
Content-Location: http://example.com/word_doc.html

<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
    <title>MS Word MHTML Document</title>
</head>
<body>
    <h1>MS Word MHTML Document</h1>

    <p>Regular paragraph text.</p>

    <!--[if !supportLists]-->- <!--[endif]-->
    <p class="MsoListParagraph">First list item</p>

    <!--[if !supportLists]-->- <!--[endif]-->
    <p class="MsoListParagraph">Second list item</p>

    <p>Another paragraph with <o:p></o:p> Office artifacts.</p>

    <!--[if gte mso 9]><xml>
    <w:WordDocument>
        <w:View>Normal</w:View>
    </w:WordDocument>
    </xml><![endif]-->

    <p>Final paragraph.</p>
</body>
</html>

------MultipartBoundary--003--
"""
    return mhtml_content.encode("utf-8")


def create_mhtml_with_multiple_assets() -> bytes:
    """Create MHTML file with multiple embedded assets for testing.

    Returns
    -------
    bytes
        MHTML file content as bytes.

    """
    # Create test images
    test_image1_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    test_image2_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02"
        b"\x08\x06\x00\x00\x00r\xb5\xd1\xdd\x00\x00\x00\x0eIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x00\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    image1_b64 = base64.b64encode(test_image1_data).decode("ascii")
    image2_b64 = base64.b64encode(test_image2_data).decode("ascii")

    mhtml_content = f"""MIME-Version: 1.0
Content-Type: multipart/related;
	boundary="----MultipartBoundary--004"

------MultipartBoundary--004
Content-Type: text/html; charset=utf-8
Content-Location: http://example.com/multi_assets.html

<!DOCTYPE html>
<html>
<head>
    <title>MHTML with Multiple Assets</title>
</head>
<body>
    <h1>MHTML with Multiple Assets</h1>

    <p>First image (referenced by Content-ID):</p>
    <img src="cid:image1.png" alt="Image 1">

    <p>Second image (referenced by file:// location):</p>
    <img src="file://image2.png" alt="Image 2">

    <p>Text between images.</p>

    <table>
        <tr>
            <th>Column 1</th>
            <th>Column 2</th>
        </tr>
        <tr>
            <td>Cell 1</td>
            <td>Cell 2</td>
        </tr>
    </table>
</body>
</html>

------MultipartBoundary--004
Content-Type: image/png
Content-ID: <image1.png>
Content-Transfer-Encoding: base64

{image1_b64}

------MultipartBoundary--004
Content-Type: image/png
Content-Location: image2.png
Content-Transfer-Encoding: base64

{image2_b64}

------MultipartBoundary--004--
"""
    return mhtml_content.encode("utf-8")


def create_mhtml_with_complex_html() -> bytes:
    """Create MHTML file with complex HTML structure for testing.

    Returns
    -------
    bytes
        MHTML file content as bytes.

    """
    mhtml_content = """MIME-Version: 1.0
Content-Type: multipart/related;
	boundary="----MultipartBoundary--005"

------MultipartBoundary--005
Content-Type: text/html; charset=utf-8
Content-Location: http://example.com/complex.html

<!DOCTYPE html>
<html>
<head>
    <title>Complex MHTML Document</title>
    <style>
        .highlight { background-color: yellow; }
        .center { text-align: center; }
    </style>
</head>
<body>
    <h1>Complex MHTML Document</h1>

    <div class="center">
        <h2>Centered Section</h2>
    </div>

    <blockquote>
        <p>This is a blockquote with <span class="highlight">highlighted text</span>.</p>
        <p>Multiple paragraphs in the quote.</p>
    </blockquote>

    <h3>Code Examples</h3>
    <pre><code>
function example() {
    console.log("Hello, World!");
    return true;
}
    </code></pre>

    <h3>Nested Lists</h3>
    <ol>
        <li>First item
            <ul>
                <li>Nested item 1</li>
                <li>Nested item 2</li>
            </ul>
        </li>
        <li>Second item</li>
        <li>Third item</li>
    </ol>

    <h3>Complex Table</h3>
    <table border="1">
        <thead>
            <tr>
                <th rowspan="2">Header 1</th>
                <th colspan="2">Header Group</th>
            </tr>
            <tr>
                <th>Sub Header 1</th>
                <th>Sub Header 2</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Row 1 Cell 1</td>
                <td>Row 1 Cell 2</td>
                <td>Row 1 Cell 3</td>
            </tr>
            <tr>
                <td>Row 2 Cell 1</td>
                <td colspan="2">Merged cells content</td>
            </tr>
        </tbody>
    </table>

    <hr>

    <p>Final paragraph with <strong>bold</strong>, <em>italic</em>, and <code>code</code> formatting.</p>
</body>
</html>

------MultipartBoundary--005--
"""
    return mhtml_content.encode("utf-8")


def create_malformed_mhtml() -> bytes:
    """Create malformed MHTML file for testing error handling.

    Returns
    -------
    bytes
        Malformed MHTML file content as bytes.

    """
    # Missing proper MIME headers and boundary
    mhtml_content = """This is not a proper MHTML file.
It lacks MIME headers and structure.
<html><body><h1>Invalid</h1></body></html>
"""
    return mhtml_content.encode("utf-8")


def create_mhtml_file(content: bytes, temp_dir: Optional[Path] = None) -> Path:
    """Create a temporary MHTML file with the given content.

    Parameters
    ----------
    content : bytes
        MHTML file content as bytes.
    temp_dir : Path, optional
        Directory to create the file in. If None, uses system temp directory.

    Returns
    -------
    Path
        Path to the created MHTML file.

    """
    if temp_dir is None:
        temp_dir = Path(tempfile.gettempdir())

    mhtml_file = temp_dir / f"test_mhtml_{hash(content) % 10000}.mht"
    mhtml_file.write_bytes(content)
    return mhtml_file
