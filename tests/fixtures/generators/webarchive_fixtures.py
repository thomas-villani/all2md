"""Safari WebArchive test fixture generators for testing WebArchive-to-Markdown conversion.

This module provides functions to programmatically create Safari WebArchive files
(.webarchive) for testing various aspects of WebArchive-to-Markdown conversion.
"""

import plistlib
import tempfile
from pathlib import Path
from typing import Optional


def create_simple_webarchive() -> bytes:
    """Create a simple WebArchive file with basic HTML content for testing.

    Returns
    -------
    bytes
        WebArchive file content as bytes (binary plist).

    """
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test WebArchive Document</title>
</head>
<body>
    <h1>Test WebArchive Document</h1>
    <p>This is a simple WebArchive document with <strong>bold</strong> and <em>italic</em> text.</p>
    <p>It also contains a <a href="https://example.com">link</a>.</p>
    <ul>
        <li>First item</li>
        <li>Second item</li>
        <li>Third item</li>
    </ul>
</body>
</html>"""

    archive_data = {
        "WebMainResource": {
            "WebResourceData": html_content.encode("utf-8"),
            "WebResourceMIMEType": "text/html",
            "WebResourceTextEncodingName": "UTF-8",
            "WebResourceURL": "http://example.com/test.html",
        }
    }

    return plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)


def create_webarchive_with_image() -> bytes:
    """Create WebArchive file with embedded image for testing image handling.

    Returns
    -------
    bytes
        WebArchive file content as bytes (binary plist).

    """
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test WebArchive with Image</title>
</head>
<body>
    <h1>Test WebArchive with Image</h1>
    <p>This document contains an embedded image:</p>
    <img src="test_image.png" alt="Test image" width="100" height="100">
    <p>Text after the image.</p>
</body>
</html>"""

    # Create a simple 1x1 PNG image
    test_image_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    archive_data = {
        "WebMainResource": {
            "WebResourceData": html_content.encode("utf-8"),
            "WebResourceMIMEType": "text/html",
            "WebResourceTextEncodingName": "UTF-8",
            "WebResourceURL": "http://example.com/test.html",
        },
        "WebSubresources": [
            {
                "WebResourceData": test_image_data,
                "WebResourceMIMEType": "image/png",
                "WebResourceURL": "http://example.com/test_image.png",
            }
        ],
    }

    return plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)


def create_webarchive_with_subframes() -> bytes:
    """Create WebArchive file with nested iframe content for testing.

    Returns
    -------
    bytes
        WebArchive file content as bytes (binary plist).

    """
    main_html = """<!DOCTYPE html>
<html>
<head>
    <title>Main WebArchive with Frames</title>
</head>
<body>
    <h1>Main Document</h1>
    <p>This is the main document content.</p>
    <iframe src="frame.html" name="TestFrame"></iframe>
    <p>Content after the frame.</p>
</body>
</html>"""

    frame_html = """<!DOCTYPE html>
<html>
<head>
    <title>Nested Frame</title>
</head>
<body>
    <h2>Frame Content</h2>
    <p>This content is inside the nested frame.</p>
    <ul>
        <li>Frame item 1</li>
        <li>Frame item 2</li>
    </ul>
</body>
</html>"""

    archive_data = {
        "WebMainResource": {
            "WebResourceData": main_html.encode("utf-8"),
            "WebResourceMIMEType": "text/html",
            "WebResourceTextEncodingName": "UTF-8",
            "WebResourceURL": "http://example.com/main.html",
        },
        "WebSubframeArchives": [
            {
                "WebMainResource": {
                    "WebResourceData": frame_html.encode("utf-8"),
                    "WebResourceMIMEType": "text/html",
                    "WebResourceTextEncodingName": "UTF-8",
                    "WebResourceURL": "http://example.com/frame.html",
                    "WebResourceFrameName": "TestFrame",
                }
            }
        ],
    }

    return plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)


def create_webarchive_with_multiple_assets() -> bytes:
    """Create WebArchive file with multiple embedded assets for testing.

    Returns
    -------
    bytes
        WebArchive file content as bytes (binary plist).

    """
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>WebArchive with Multiple Assets</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <h1>WebArchive with Multiple Assets</h1>

    <p>First image:</p>
    <img src="image1.png" alt="Image 1">

    <p>Second image:</p>
    <img src="image2.png" alt="Image 2">

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
</html>"""

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

    css_content = """
body {
    font-family: Arial, sans-serif;
    margin: 20px;
}
.highlight {
    background-color: yellow;
}
"""

    archive_data = {
        "WebMainResource": {
            "WebResourceData": html_content.encode("utf-8"),
            "WebResourceMIMEType": "text/html",
            "WebResourceTextEncodingName": "UTF-8",
            "WebResourceURL": "http://example.com/multi_assets.html",
        },
        "WebSubresources": [
            {
                "WebResourceData": test_image1_data,
                "WebResourceMIMEType": "image/png",
                "WebResourceURL": "http://example.com/image1.png",
            },
            {
                "WebResourceData": test_image2_data,
                "WebResourceMIMEType": "image/png",
                "WebResourceURL": "http://example.com/image2.png",
            },
            {
                "WebResourceData": css_content.encode("utf-8"),
                "WebResourceMIMEType": "text/css",
                "WebResourceTextEncodingName": "UTF-8",
                "WebResourceURL": "http://example.com/styles.css",
            },
        ],
    }

    return plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)


def create_webarchive_with_complex_html() -> bytes:
    """Create WebArchive file with complex HTML structure for testing.

    Returns
    -------
    bytes
        WebArchive file content as bytes (binary plist).

    """
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Complex WebArchive Document</title>
    <style>
        .highlight { background-color: yellow; }
        .center { text-align: center; }
    </style>
</head>
<body>
    <h1>Complex WebArchive Document</h1>

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
</html>"""

    archive_data = {
        "WebMainResource": {
            "WebResourceData": html_content.encode("utf-8"),
            "WebResourceMIMEType": "text/html",
            "WebResourceTextEncodingName": "UTF-8",
            "WebResourceURL": "http://example.com/complex.html",
        }
    }

    return plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)


def create_webarchive_with_different_encoding() -> bytes:
    """Create WebArchive file with non-UTF-8 encoding for testing.

    Returns
    -------
    bytes
        WebArchive file content as bytes (binary plist).

    """
    # HTML content with Latin-1 characters
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test Encoding</title>
</head>
<body>
    <h1>Test Encoding</h1>
    <p>This document tests Latin-1 encoding: cafe.</p>
    <p>Special characters: n.</p>
</body>
</html>"""

    archive_data = {
        "WebMainResource": {
            "WebResourceData": html_content.encode("latin-1"),
            "WebResourceMIMEType": "text/html",
            "WebResourceTextEncodingName": "ISO-8859-1",
            "WebResourceURL": "http://example.com/encoding_test.html",
        }
    }

    return plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)


def create_malformed_webarchive() -> bytes:
    """Create malformed WebArchive file for testing error handling.

    Returns
    -------
    bytes
        Malformed WebArchive file content as bytes.

    """
    # Create a plist without required WebMainResource
    archive_data = {
        "WebSubresources": [],
    }

    return plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)


def create_invalid_plist() -> bytes:
    """Create invalid plist file for testing error handling.

    Returns
    -------
    bytes
        Invalid plist content.

    """
    # Not a valid plist at all
    return b"This is not a valid plist file.\nJust random text."


def create_webarchive_file(content: bytes, temp_dir: Optional[Path] = None) -> Path:
    """Create a temporary WebArchive file with the given content.

    Parameters
    ----------
    content : bytes
        WebArchive file content as bytes (binary plist).
    temp_dir : Path, optional
        Directory to create the file in. If None, uses system temp directory.

    Returns
    -------
    Path
        Path to the created WebArchive file.

    """
    if temp_dir is None:
        temp_dir = Path(tempfile.gettempdir())

    webarchive_file = temp_dir / f"test_webarchive_{hash(content) % 10000}.webarchive"
    webarchive_file.write_bytes(content)
    return webarchive_file
