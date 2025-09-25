"""ODF test fixture generators using odfpy library.

This module provides functions to programmatically create ODT and ODP documents
for testing various aspects of ODF-to-Markdown conversion.
"""

import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional

try:
    from odf.opendocument import OpenDocumentText, OpenDocumentPresentation
    from odf.style import Style, TextProperties, ParagraphProperties, ListLevelProperties
    from odf.text import (
        H, P, List, ListItem, Span, A, Tab, S as Space
    )
    from odf.table import Table, TableColumn, TableRow, TableCell
    from odf.draw import Frame, TextBox, Image
    from odf import teletype
    HAS_ODFPY = True
except ImportError:
    HAS_ODFPY = False


def create_odt_with_formatting() -> 'OpenDocumentText':
    """Create an ODT with various text formatting for testing emphasis detection.

    Returns
    -------
    OpenDocumentText
        Document with bold, italic, and combined formatting.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    doc = OpenDocumentText()

    # Define styles for formatting
    bold_style = Style(name="BoldStyle", family="text")
    bold_style.addElement(TextProperties(fontweight="bold"))
    doc.styles.addElement(bold_style)

    italic_style = Style(name="ItalicStyle", family="text")
    italic_style.addElement(TextProperties(fontstyle="italic"))
    doc.styles.addElement(italic_style)

    bold_italic_style = Style(name="BoldItalicStyle", family="text")
    bold_italic_style.addElement(TextProperties(fontweight="bold", fontstyle="italic"))
    doc.styles.addElement(bold_italic_style)

    # Title
    title = H(outlinelevel=1, text="Formatting Test Document")
    doc.text.addElement(title)

    # Paragraph with mixed formatting
    p1 = P()
    p1.addText("This paragraph contains ")
    bold_span = Span(stylename=bold_style, text="bold text")
    p1.addElement(bold_span)
    p1.addText(", ")
    italic_span = Span(stylename=italic_style, text="italic text")
    p1.addElement(italic_span)
    p1.addText(", and normal text.")
    doc.text.addElement(p1)

    # Paragraph with combined formatting
    p2 = P()
    p2.addText("This paragraph has ")
    combined_span = Span(stylename=bold_italic_style, text="bold and italic text")
    p2.addElement(combined_span)
    p2.addText(" together.")
    doc.text.addElement(p2)

    # Different heading levels
    h2 = H(outlinelevel=2, text="Level 2 Heading")
    doc.text.addElement(h2)

    p3 = P(text="Content under level 2 heading.")
    doc.text.addElement(p3)

    h3 = H(outlinelevel=3, text="Level 3 Heading")
    doc.text.addElement(h3)

    p4 = P(text="Content under level 3 heading.")
    doc.text.addElement(p4)

    # Hyperlink
    link_p = P()
    link_p.addText("Visit our ")
    link = A(href="https://example.com", text="website")
    link_p.addElement(link)
    link_p.addText(" for more information.")
    doc.text.addElement(link_p)

    return doc


def create_odt_with_lists() -> 'OpenDocumentText':
    """Create an ODT with various list types for testing list conversion.

    Returns
    -------
    OpenDocumentText
        Document with bullet lists, numbered lists, and nested lists.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    doc = OpenDocumentText()

    # Define list styles
    from odf.style import ListStyle, ListLevelStyleBullet, ListLevelStyleNumber

    # Bullet list style
    bullet_list_style = ListStyle(name="BulletListStyle")
    bullet_level = ListLevelStyleBullet(level=1, bulletchar="•")
    bullet_list_style.addElement(bullet_level)
    doc.automaticstyles.addElement(bullet_list_style)

    # Numbered list style
    number_list_style = ListStyle(name="NumberListStyle")
    number_level = ListLevelStyleNumber(level=1, numformat="1", numsuffix=".")
    number_list_style.addElement(number_level)
    doc.automaticstyles.addElement(number_list_style)

    # Nested bullet list style
    nested_bullet_style = ListStyle(name="NestedBulletStyle")
    nested_level1 = ListLevelStyleBullet(level=1, bulletchar="•")
    nested_level2 = ListLevelStyleBullet(level=2, bulletchar="◦")
    nested_bullet_style.addElement(nested_level1)
    nested_bullet_style.addElement(nested_level2)
    doc.automaticstyles.addElement(nested_bullet_style)

    # Title
    title = H(outlinelevel=1, text="List Test Document")
    doc.text.addElement(title)

    # Unordered list
    h2 = H(outlinelevel=2, text="Unordered List")
    doc.text.addElement(h2)

    bullet_list = List(stylename=bullet_list_style)

    item1 = ListItem()
    item1.addElement(P(text="First bullet item"))
    bullet_list.addElement(item1)

    item2 = ListItem()
    item2.addElement(P(text="Second bullet item"))
    bullet_list.addElement(item2)

    item3 = ListItem()
    item3.addElement(P(text="Third bullet item"))
    bullet_list.addElement(item3)

    doc.text.addElement(bullet_list)

    # Ordered list
    h2_ordered = H(outlinelevel=2, text="Ordered List")
    doc.text.addElement(h2_ordered)

    number_list = List(stylename=number_list_style)

    num_item1 = ListItem()
    num_item1.addElement(P(text="First numbered item"))
    number_list.addElement(num_item1)

    num_item2 = ListItem()
    num_item2.addElement(P(text="Second numbered item"))
    number_list.addElement(num_item2)

    num_item3 = ListItem()
    num_item3.addElement(P(text="Third numbered item"))
    number_list.addElement(num_item3)

    doc.text.addElement(number_list)

    # Nested list
    h2_nested = H(outlinelevel=2, text="Nested List")
    doc.text.addElement(h2_nested)

    nested_list = List(stylename=nested_bullet_style)

    parent_item1 = ListItem()
    parent_item1.addElement(P(text="Parent item 1"))

    # Add nested list to parent item
    child_list = List(stylename=nested_bullet_style)
    child_item1 = ListItem()
    child_item1.addElement(P(text="Child item 1.1"))
    child_list.addElement(child_item1)

    child_item2 = ListItem()
    child_item2.addElement(P(text="Child item 1.2"))
    child_list.addElement(child_item2)

    parent_item1.addElement(child_list)
    nested_list.addElement(parent_item1)

    parent_item2 = ListItem()
    parent_item2.addElement(P(text="Parent item 2"))
    nested_list.addElement(parent_item2)

    doc.text.addElement(nested_list)

    return doc


def create_odt_with_tables() -> 'OpenDocumentText':
    """Create an ODT with tables for testing table conversion.

    Returns
    -------
    OpenDocumentText
        Document with various table structures.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    doc = OpenDocumentText()

    # Title
    title = H(outlinelevel=1, text="Table Test Document")
    doc.text.addElement(title)

    # Simple table
    p1 = P(text="Here is a simple table:")
    doc.text.addElement(p1)

    # Create table
    table = Table(name="TestTable")

    # Add columns
    for i in range(3):
        column = TableColumn()
        table.addElement(column)

    # Header row
    header_row = TableRow()

    header_cell1 = TableCell()
    header_cell1.addElement(P(text="Name"))
    header_row.addElement(header_cell1)

    header_cell2 = TableCell()
    header_cell2.addElement(P(text="Age"))
    header_row.addElement(header_cell2)

    header_cell3 = TableCell()
    header_cell3.addElement(P(text="City"))
    header_row.addElement(header_cell3)

    table.addElement(header_row)

    # Data rows
    data_rows = [
        ["Alice Johnson", "25", "New York"],
        ["Bob Smith", "30", "San Francisco"],
        ["Charlie Brown", "22", "Seattle"]
    ]

    for row_data in data_rows:
        data_row = TableRow()
        for cell_text in row_data:
            cell = TableCell()
            cell.addElement(P(text=cell_text))
            data_row.addElement(cell)
        table.addElement(data_row)

    doc.text.addElement(table)

    # Table with formatting
    p2 = P(text="Table with some formatting:")
    doc.text.addElement(p2)

    # Define bold style for table headers
    bold_style = Style(name="TableBoldStyle", family="text")
    bold_style.addElement(TextProperties(fontweight="bold"))
    doc.styles.addElement(bold_style)

    formatted_table = Table(name="FormattedTable")

    # Add columns
    for i in range(2):
        column = TableColumn()
        formatted_table.addElement(column)

    # Formatted header
    fmt_header_row = TableRow()

    fmt_header_cell1 = TableCell()
    fmt_header_p1 = P()
    fmt_header_span1 = Span(stylename=bold_style, text="Product")
    fmt_header_p1.addElement(fmt_header_span1)
    fmt_header_cell1.addElement(fmt_header_p1)
    fmt_header_row.addElement(fmt_header_cell1)

    fmt_header_cell2 = TableCell()
    fmt_header_p2 = P()
    fmt_header_span2 = Span(stylename=bold_style, text="Price")
    fmt_header_p2.addElement(fmt_header_span2)
    fmt_header_cell2.addElement(fmt_header_p2)
    fmt_header_row.addElement(fmt_header_cell2)

    formatted_table.addElement(fmt_header_row)

    # Data with some formatting
    fmt_data = [
        ["Widget A", "$10.00"],
        ["Widget B", "$15.00"]
    ]

    for row_data in fmt_data:
        fmt_data_row = TableRow()
        for cell_text in row_data:
            cell = TableCell()
            cell.addElement(P(text=cell_text))
            fmt_data_row.addElement(cell)
        formatted_table.addElement(fmt_data_row)

    doc.text.addElement(formatted_table)

    return doc


def create_odt_with_spaces_and_formatting() -> 'OpenDocumentText':
    """Create an ODT with various spacing and text formatting scenarios.

    Returns
    -------
    OpenDocumentText
        Document testing space handling and complex text formatting.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    doc = OpenDocumentText()

    # Define styles
    bold_style = Style(name="BoldStyle", family="text")
    bold_style.addElement(TextProperties(fontweight="bold"))
    doc.styles.addElement(bold_style)

    # Title
    title = H(outlinelevel=1, text="Spacing and Formatting Test")
    doc.text.addElement(title)

    # Text with multiple spaces
    p1 = P()
    p1.addText("This text has")
    p1.addElement(Space(c=3))  # 3 spaces
    p1.addText("multiple spaces")
    p1.addElement(Space(c=2))  # 2 spaces
    p1.addText("in between.")
    doc.text.addElement(p1)

    # Text with tabs
    p2 = P()
    p2.addText("This text")
    p2.addElement(Tab())
    p2.addText("has tabs")
    p2.addElement(Tab())
    p2.addText("separating words.")
    doc.text.addElement(p2)

    # Mixed formatting with spaces
    p3 = P()
    p3.addText("Here is ")
    bold_span = Span(stylename=bold_style)
    bold_span.addText("bold text")
    bold_span.addElement(Space(c=2))
    bold_span.addText("with spaces")
    p3.addElement(bold_span)
    p3.addText(" and normal text.")
    doc.text.addElement(p3)

    # Unicode text
    p4 = P(text="Unicode test: Café, naïve, résumé, 中文, العربية")
    doc.text.addElement(p4)

    # Smart quotes and special characters
    p5 = P(text="Smart quotes: "Hello" and 'world'. En dash – and em dash —.")
    doc.text.addElement(p5)

    return doc


def save_odt_to_file(doc: 'OpenDocumentText', filepath: Path) -> None:
    """Save an ODT document to a file.

    Parameters
    ----------
    doc : OpenDocumentText
        The document to save.
    filepath : Path
        Path where to save the document.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    doc.save(str(filepath))


def save_odt_to_bytes(doc: 'OpenDocumentText') -> bytes:
    """Save an ODT document to bytes.

    Parameters
    ----------
    doc : OpenDocumentText
        The document to save.

    Returns
    -------
    bytes
        The document as bytes.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    # Save to temporary file and read back as bytes
    with tempfile.NamedTemporaryFile() as tmp:
        doc.save(tmp.name)
        tmp.seek(0)
        return tmp.read()


def create_odp_with_slides() -> 'OpenDocumentPresentation':
    """Create an ODP presentation with multiple slides.

    Returns
    -------
    OpenDocumentPresentation
        Presentation with slides containing various content.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    from odf.draw import Page, Frame, TextBox
    from odf.style import MasterPage, PageLayout, PageLayoutProperties

    doc = OpenDocumentPresentation()

    # Define basic page layout
    page_layout = PageLayout(name="StandardLayout")
    page_layout.addElement(PageLayoutProperties(
        margintop="1in", marginbottom="1in",
        marginleft="1in", marginright="1in"
    ))
    doc.automaticstyles.addElement(page_layout)

    # Master page
    master_page = MasterPage(name="Standard", pagelayoutname=page_layout)
    doc.masterstyles.addElement(master_page)

    # Slide 1
    slide1 = Page(name="Slide1", masterpagename=master_page, stylename="StandardLayout")

    # Title frame
    title_frame = Frame(width="8in", height="2in", x="1in", y="1in")
    title_box = TextBox()
    title_p = P()
    title_p.addText("Welcome to Our Presentation")
    title_box.addElement(title_p)
    title_frame.addElement(title_box)
    slide1.addElement(title_frame)

    # Content frame
    content_frame = Frame(width="8in", height="4in", x="1in", y="3in")
    content_box = TextBox()
    content_p = P()
    content_p.addText("This is the first slide with introductory content.")
    content_box.addElement(content_p)
    content_frame.addElement(content_box)
    slide1.addElement(content_frame)

    doc.presentation.addElement(slide1)

    # Slide 2
    slide2 = Page(name="Slide2", masterpagename=master_page, stylename="StandardLayout")

    # Title frame
    title_frame2 = Frame(width="8in", height="2in", x="1in", y="1in")
    title_box2 = TextBox()
    title_p2 = P()
    title_p2.addText("Second Slide")
    title_box2.addElement(title_p2)
    title_frame2.addElement(title_box2)
    slide2.addElement(title_frame2)

    # Bullet points frame
    bullet_frame = Frame(width="8in", height="4in", x="1in", y="3in")
    bullet_box = TextBox()

    # Add some bullet points
    from odf.style import ListStyle, ListLevelStyleBullet

    bullet_style = ListStyle(name="SlideBulletStyle")
    bullet_level = ListLevelStyleBullet(level=1, bulletchar="•")
    bullet_style.addElement(bullet_level)
    doc.automaticstyles.addElement(bullet_style)

    bullet_list = List(stylename=bullet_style)

    item1 = ListItem()
    item1.addElement(P(text="First key point"))
    bullet_list.addElement(item1)

    item2 = ListItem()
    item2.addElement(P(text="Second key point"))
    bullet_list.addElement(item2)

    item3 = ListItem()
    item3.addElement(P(text="Third key point"))
    bullet_list.addElement(item3)

    bullet_box.addElement(bullet_list)
    bullet_frame.addElement(bullet_box)
    slide2.addElement(bullet_frame)

    doc.presentation.addElement(slide2)

    return doc


def create_comprehensive_odt_test_document() -> 'OpenDocumentText':
    """Create a comprehensive ODT document with all supported features.

    Returns
    -------
    OpenDocumentText
        Document with headings, formatting, lists, tables, links, and special characters.

    Raises
    ------
    ImportError
        If odfpy library is not available.
    """
    if not HAS_ODFPY:
        raise ImportError("odfpy library required for ODF fixture generation")

    doc = OpenDocumentText()

    # Define all styles
    bold_style = Style(name="BoldStyle", family="text")
    bold_style.addElement(TextProperties(fontweight="bold"))
    doc.styles.addElement(bold_style)

    italic_style = Style(name="ItalicStyle", family="text")
    italic_style.addElement(TextProperties(fontstyle="italic"))
    doc.styles.addElement(italic_style)

    bold_italic_style = Style(name="BoldItalicStyle", family="text")
    bold_italic_style.addElement(TextProperties(fontweight="bold", fontstyle="italic"))
    doc.styles.addElement(bold_italic_style)

    # List styles
    from odf.style import ListStyle, ListLevelStyleBullet, ListLevelStyleNumber

    bullet_list_style = ListStyle(name="BulletListStyle")
    bullet_level = ListLevelStyleBullet(level=1, bulletchar="•")
    bullet_list_style.addElement(bullet_level)
    doc.automaticstyles.addElement(bullet_list_style)

    number_list_style = ListStyle(name="NumberListStyle")
    number_level = ListLevelStyleNumber(level=1, numformat="1", numsuffix=".")
    number_list_style.addElement(number_level)
    doc.automaticstyles.addElement(number_list_style)

    # Title
    title = H(outlinelevel=1, text="Comprehensive ODF Test Document")
    doc.text.addElement(title)

    # Introduction
    intro_p = P(text="This document contains various elements to test ODF to Markdown conversion.")
    doc.text.addElement(intro_p)

    # Text formatting section
    format_h = H(outlinelevel=2, text="Text Formatting")
    doc.text.addElement(format_h)

    format_p = P()
    format_p.addText("This paragraph demonstrates ")
    format_p.addElement(Span(stylename=bold_style, text="bold"))
    format_p.addText(", ")
    format_p.addElement(Span(stylename=italic_style, text="italic"))
    format_p.addText(", and ")
    format_p.addElement(Span(stylename=bold_italic_style, text="bold italic"))
    format_p.addText(" formatting.")
    doc.text.addElement(format_p)

    # Lists section
    lists_h = H(outlinelevel=2, text="Lists")
    doc.text.addElement(lists_h)

    # Unordered list
    ul_h = H(outlinelevel=3, text="Unordered List")
    doc.text.addElement(ul_h)

    bullet_list = List(stylename=bullet_list_style)
    for i in range(1, 4):
        item = ListItem()
        item.addElement(P(text=f"Bullet item {i}"))
        bullet_list.addElement(item)
    doc.text.addElement(bullet_list)

    # Ordered list
    ol_h = H(outlinelevel=3, text="Ordered List")
    doc.text.addElement(ol_h)

    number_list = List(stylename=number_list_style)
    for i in range(1, 4):
        item = ListItem()
        item.addElement(P(text=f"Numbered item {i}"))
        number_list.addElement(item)
    doc.text.addElement(number_list)

    # Table section
    table_h = H(outlinelevel=2, text="Tables")
    doc.text.addElement(table_h)

    table = Table(name="ComprehensiveTable")

    # Add columns
    for i in range(3):
        column = TableColumn()
        table.addElement(column)

    # Header
    header_row = TableRow()
    headers = ["Feature", "Status", "Notes"]
    for header_text in headers:
        cell = TableCell()
        p = P()
        p.addElement(Span(stylename=bold_style, text=header_text))
        cell.addElement(p)
        header_row.addElement(cell)
    table.addElement(header_row)

    # Data rows
    data = [
        ["Headings", "Supported", "Multiple levels"],
        ["Formatting", "Supported", "Bold and italic"],
        ["Lists", "Supported", "Bullet and numbered"],
        ["Tables", "Supported", "Basic structure"]
    ]

    for row_data in data:
        row = TableRow()
        for cell_text in row_data:
            cell = TableCell()
            cell.addElement(P(text=cell_text))
            row.addElement(cell)
        table.addElement(row)

    doc.text.addElement(table)

    # Links section
    links_h = H(outlinelevel=2, text="Links")
    doc.text.addElement(links_h)

    link_p = P()
    link_p.addText("Here is a link to ")
    link_p.addElement(A(href="https://example.com", text="Example.com"))
    link_p.addText(" and another to ")
    link_p.addElement(A(href="https://github.com", text="GitHub"))
    link_p.addText(".")
    doc.text.addElement(link_p)

    # Special characters
    special_h = H(outlinelevel=2, text="Special Characters")
    doc.text.addElement(special_h)

    special_p = P(text="Unicode: café, naïve, résumé. Quotes: "Hello" and 'world'. Dashes: en–dash and em—dash.")
    doc.text.addElement(special_p)

    return doc