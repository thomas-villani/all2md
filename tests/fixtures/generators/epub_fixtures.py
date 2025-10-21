"""EPUB test fixture generators for testing EPUB-to-Markdown conversion.

This module provides functions to programmatically create EPUB files
for testing various aspects of EPUB-to-Markdown conversion.
"""

import tempfile
from pathlib import Path
from typing import Optional

try:
    import ebooklib
    from ebooklib import epub
except ImportError:
    ebooklib = None
    epub = None


def create_simple_epub() -> bytes:
    """Create a simple EPUB with basic structure for testing.

    Returns
    -------
    bytes
        EPUB file content as bytes.

    Raises
    ------
    ImportError
        If ebooklib is not installed.

    """
    if not ebooklib:
        raise ImportError("ebooklib is required for EPUB fixture generation")

    book = epub.EpubBook()
    book.set_identifier("test-epub-001")
    book.set_title("Test EPUB Document")
    book.set_language("en")
    book.add_author("Test Author")

    # Create chapters
    chapter1 = epub.EpubHtml(title="Chapter 1", file_name="chapter1.xhtml", lang="en")
    chapter1.content = """
    <html>
        <body>
            <h1>Chapter 1: Introduction</h1>
            <p>This is the first chapter with <strong>bold text</strong> and <em>italic text</em>.</p>
            <p>This paragraph contains a <a href="https://example.com">link</a>.</p>
        </body>
    </html>
    """

    chapter2 = epub.EpubHtml(title="Chapter 2", file_name="chapter2.xhtml", lang="en")
    chapter2.content = """
    <html>
        <body>
            <h1>Chapter 2: Content</h1>
            <p>This chapter has a list:</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
                <li>Item 3</li>
            </ul>
            <p>And a table:</p>
            <table>
                <tr><th>Header 1</th><th>Header 2</th></tr>
                <tr><td>Cell 1</td><td>Cell 2</td></tr>
            </table>
        </body>
    </html>
    """

    # Add chapters to book
    book.add_item(chapter1)
    book.add_item(chapter2)

    # Create table of contents
    book.toc = (
        epub.Link("chapter1.xhtml", "Chapter 1", "chapter1"),
        epub.Link("chapter2.xhtml", "Chapter 2", "chapter2"),
    )

    # Create spine
    book.spine = ["nav", chapter1, chapter2]

    # Add default navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Generate EPUB content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
        epub.write_epub(tmp_file.name, book, {})
        tmp_file.flush()

    # Read the file back
    with open(tmp_file.name, "rb") as f:
        content = f.read()

    # Clean up
    import os

    os.unlink(tmp_file.name)

    return content


def create_epub_with_images() -> bytes:
    """Create EPUB with embedded images for testing image handling.

    Returns
    -------
    bytes
        EPUB file content as bytes.

    Raises
    ------
    ImportError
        If ebooklib is not installed.

    """
    if not ebooklib:
        raise ImportError("ebooklib is required for EPUB fixture generation")

    book = epub.EpubBook()
    book.set_identifier("test-epub-images-001")
    book.set_title("Test EPUB with Images")
    book.set_language("en")
    book.add_author("Test Author")

    # Create a simple test image (1x1 PNG)
    test_image_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    # Create image item
    image_item = epub.EpubImage()
    image_item.file_name = "images/test_image.png"
    image_item.media_type = "image/png"
    image_item.content = test_image_data

    book.add_item(image_item)

    # Create chapter with image
    chapter = epub.EpubHtml(title="Chapter with Image", file_name="chapter_image.xhtml", lang="en")
    chapter.content = """
    <html>
        <body>
            <h1>Chapter with Image</h1>
            <p>This chapter contains an image:</p>
            <img src="images/test_image.png" alt="Test image" />
            <p>Text after the image.</p>
        </body>
    </html>
    """

    book.add_item(chapter)

    # Create table of contents
    book.toc = (epub.Link("chapter_image.xhtml", "Chapter with Image", "chapter_image"),)

    # Create spine
    book.spine = ["nav", chapter]

    # Add default navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Generate EPUB content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
        epub.write_epub(tmp_file.name, book, {})
        tmp_file.flush()

    # Read the file back
    with open(tmp_file.name, "rb") as f:
        content = f.read()

    # Clean up
    import os

    os.unlink(tmp_file.name)

    return content


def create_epub_with_footnotes() -> bytes:
    """Create EPUB with footnotes for testing footnote conversion.

    Returns
    -------
    bytes
        EPUB file content as bytes.

    Raises
    ------
    ImportError
        If ebooklib is not installed.

    """
    if not ebooklib:
        raise ImportError("ebooklib is required for EPUB fixture generation")

    book = epub.EpubBook()
    book.set_identifier("test-epub-footnotes-001")
    book.set_title("Test EPUB with Footnotes")
    book.set_language("en")
    book.add_author("Test Author")

    chapter = epub.EpubHtml(title="Chapter with Footnotes", file_name="chapter_footnotes.xhtml", lang="en")
    chapter.content = """
    <html>
        <body>
            <h1>Chapter with Footnotes</h1>
            <p>This is the main text with a footnote reference<a epub:type="noteref" href="#fn1">1</a>.</p>
            <p>Another paragraph with another footnote<a epub:type="noteref" href="#fn2">2</a>.</p>

            <div id="fn1">This is the first footnote content.</div>
            <div id="fn2">This is the second footnote with <strong>formatting</strong>.</div>
        </body>
    </html>
    """

    book.add_item(chapter)

    # Create table of contents
    book.toc = (epub.Link("chapter_footnotes.xhtml", "Chapter with Footnotes", "chapter_footnotes"),)

    # Create spine
    book.spine = ["nav", chapter]

    # Add default navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Generate EPUB content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
        epub.write_epub(tmp_file.name, book, {})
        tmp_file.flush()

    # Read the file back
    with open(tmp_file.name, "rb") as f:
        content = f.read()

    # Clean up
    import os

    os.unlink(tmp_file.name)

    return content


def create_epub_with_nested_toc() -> bytes:
    """Create EPUB with nested table of contents for testing TOC generation.

    Returns
    -------
    bytes
        EPUB file content as bytes.

    Raises
    ------
    ImportError
        If ebooklib is not installed.

    """
    if not ebooklib:
        raise ImportError("ebooklib is required for EPUB fixture generation")

    book = epub.EpubBook()
    book.set_identifier("test-epub-nested-toc-001")
    book.set_title("Test EPUB with Nested TOC")
    book.set_language("en")
    book.add_author("Test Author")

    # Create chapters
    part1_ch1 = epub.EpubHtml(title="Part 1 Chapter 1", file_name="part1_ch1.xhtml", lang="en")
    part1_ch1.content = "<html><body><h1>Part 1, Chapter 1</h1><p>Content here.</p></body></html>"

    part1_ch2 = epub.EpubHtml(title="Part 1 Chapter 2", file_name="part1_ch2.xhtml", lang="en")
    part1_ch2.content = "<html><body><h1>Part 1, Chapter 2</h1><p>More content.</p></body></html>"

    part2_ch1 = epub.EpubHtml(title="Part 2 Chapter 1", file_name="part2_ch1.xhtml", lang="en")
    part2_ch1.content = "<html><body><h1>Part 2, Chapter 1</h1><p>Different content.</p></body></html>"

    book.add_item(part1_ch1)
    book.add_item(part1_ch2)
    book.add_item(part2_ch1)

    # Create nested table of contents
    book.toc = (
        (
            epub.Section("Part 1"),
            (
                epub.Link("part1_ch1.xhtml", "Chapter 1", "part1_ch1"),
                epub.Link("part1_ch2.xhtml", "Chapter 2", "part1_ch2"),
            ),
        ),
        (epub.Section("Part 2"), (epub.Link("part2_ch1.xhtml", "Chapter 1", "part2_ch1"),)),
    )

    # Create spine
    book.spine = ["nav", part1_ch1, part1_ch2, part2_ch1]

    # Add default navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Generate EPUB content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
        epub.write_epub(tmp_file.name, book, {})
        tmp_file.flush()

    # Read the file back
    with open(tmp_file.name, "rb") as f:
        content = f.read()

    # Clean up
    import os

    os.unlink(tmp_file.name)

    return content


def create_epub_file(content: bytes, temp_dir: Optional[Path] = None) -> Path:
    """Create a temporary EPUB file with the given content.

    Parameters
    ----------
    content : bytes
        EPUB file content as bytes.
    temp_dir : Path, optional
        Directory to create the file in. If None, uses system temp directory.

    Returns
    -------
    Path
        Path to the created EPUB file.

    """
    if temp_dir is None:
        temp_dir = Path(tempfile.gettempdir())

    epub_file = temp_dir / f"test_epub_{hash(content) % 10000}.epub"
    epub_file.write_bytes(content)
    return epub_file
