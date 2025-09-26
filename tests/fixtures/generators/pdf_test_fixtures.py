"""PDF test fixture generators using PyMuPDF.

This module provides functions to programmatically create PDF documents
for testing various aspects of PDF-to-Markdown conversion.
"""

import tempfile
from pathlib import Path

import fitz


def create_pdf_with_figures() -> fitz.Document:
    """Create a PDF with figure placeholders (shapes) for testing image-like content."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size

    # Add title
    page.insert_text((50, 50), "Test Document with Figures", fontsize=16, color=(0, 0, 0))

    # Create first "figure" using drawn shapes
    fig1_rect = fitz.Rect(100, 100, 200, 150)
    page.draw_rect(fig1_rect, color=(0, 0, 1), fill=(0.8, 0.8, 1.0), width=2)
    page.draw_circle(fitz.Point(150, 125), 15, color=(1, 0, 0), fill=(1, 0.8, 0.8))

    # Add image caption
    page.insert_text((100, 160), "Figure 1: Sample chart showing data trends", fontsize=10)

    # Create second "figure"
    fig2_rect = fitz.Rect(300, 200, 400, 250)
    page.draw_rect(fig2_rect, color=(0, 1, 0), fill=(0.8, 1.0, 0.8), width=2)
    # Draw a simple bar chart-like shape
    page.draw_rect(fitz.Rect(310, 230, 320, 240), fill=(0, 0.5, 0))
    page.draw_rect(fitz.Rect(325, 220, 335, 240), fill=(0, 0.5, 0))
    page.draw_rect(fitz.Rect(340, 210, 350, 240), fill=(0, 0.5, 0))

    # Add second caption
    page.insert_text((300, 260), "Figure 2: Additional visualization", fontsize=10)

    # Add some text after figures
    page.insert_text((50, 320), "This document contains multiple figures for testing", fontsize=12)
    page.insert_text((50, 340), "figure detection and caption recognition functionality.", fontsize=12)

    return doc


def create_pdf_with_tables() -> fitz.Document:
    """Create a PDF with tables for testing table detection."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Add title
    page.insert_text((50, 50), "Test Document with Tables", fontsize=16, color=(0, 0, 0))

    # First table - simple 3x3 table
    table1_start = (100, 100)
    cell_width = 80
    cell_height = 25

    # Table 1 headers
    headers1 = ["Name", "Age", "City"]
    for i, header in enumerate(headers1):
        x = table1_start[0] + i * cell_width
        y = table1_start[1]
        # Draw cell border
        rect = fitz.Rect(x, y, x + cell_width, y + cell_height)
        page.draw_rect(rect, color=(0, 0, 0), width=1)
        # Add text
        page.insert_text((x + 5, y + 15), header, fontsize=10, color=(0, 0, 0))

    # Table 1 data rows
    data1 = [
        ["Alice", "25", "NYC"],
        ["Bob", "30", "SF"],
        ["Carol", "28", "LA"]
    ]

    for row_idx, row in enumerate(data1):
        for col_idx, cell in enumerate(row):
            x = table1_start[0] + col_idx * cell_width
            y = table1_start[1] + (row_idx + 1) * cell_height
            # Draw cell border
            rect = fitz.Rect(x, y, x + cell_width, y + cell_height)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            # Add text
            page.insert_text((x + 5, y + 15), cell, fontsize=10, color=(0, 0, 0))

    # Add text between tables
    page.insert_text((50, 250), "Here is some text between the two tables.", fontsize=12)

    # Second table - different structure (2x4)
    table2_start = (150, 300)
    cell_width2 = 120

    # Table 2 headers
    headers2 = ["Product", "Price"]
    for i, header in enumerate(headers2):
        x = table2_start[0] + i * cell_width2
        y = table2_start[1]
        rect = fitz.Rect(x, y, x + cell_width2, y + cell_height)
        page.draw_rect(rect, color=(0, 0, 0), width=1)
        page.insert_text((x + 5, y + 15), header, fontsize=10, color=(0, 0, 0))

    # Table 2 data
    data2 = [
        ["Widget A", "$10.99"],
        ["Widget B", "$15.50"],
        ["Widget C", "$8.25"]
    ]

    for row_idx, row in enumerate(data2):
        for col_idx, cell in enumerate(row):
            x = table2_start[0] + col_idx * cell_width2
            y = table2_start[1] + (row_idx + 1) * cell_height
            rect = fitz.Rect(x, y, x + cell_width2, y + cell_height)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((x + 5, y + 15), cell, fontsize=10, color=(0, 0, 0))

    return doc


def create_pdf_with_formatting() -> fitz.Document:
    """Create a PDF with various text formatting for testing emphasis detection."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Normal text
    page.insert_text((50, 50), "This is normal text.", fontsize=12, color=(0, 0, 0))

    # Bold text (simulated with thicker font)
    page.insert_text((50, 80), "This is bold text.", fontsize=12, color=(0, 0, 0))

    # Italic text (simulated with oblique font)
    page.insert_text((50, 110), "This is italic text.", fontsize=12, color=(0, 0, 0))

    # Bold italic text
    page.insert_text((50, 140), "This is bold italic text.", fontsize=12, color=(0, 0, 0))

    # Different font sizes for header detection
    page.insert_text((50, 200), "Large Header Text", fontsize=18, color=(0, 0, 0))

    page.insert_text((50, 230), "Medium Subheader", fontsize=14, color=(0, 0, 0))

    page.insert_text((50, 260), "Regular paragraph text continues here with normal formatting",
                     fontsize=12, color=(0, 0, 0))

    # Mixed formatting in same line (requires multiple text insertions)
    page.insert_text((50, 320), "This line has ", fontsize=12, color=(0, 0, 0))
    page.insert_text((130, 320), "bold", fontsize=12, color=(0, 0, 0))
    page.insert_text((160, 320), " and ", fontsize=12, color=(0, 0, 0))
    page.insert_text((190, 320), "italic", fontsize=12, color=(0, 0, 0))
    page.insert_text((220, 320), " text.", fontsize=12, color=(0, 0, 0))

    # Monospace text for code detection
    page.insert_text((50, 380), "def function():", fontsize=10, color=(0, 0, 0))
    page.insert_text((70, 400), "return 'code block'", fontsize=10, color=(0, 0, 0))

    return doc


def create_pdf_with_complex_layout() -> fitz.Document:
    """Create a PDF with complex layout including figures and text flow."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Title
    page.insert_text((50, 50), "Complex Layout Test", fontsize=16, color=(0, 0, 0))

    # First paragraph
    para1 = ("This document tests complex layouts with text flowing around "
             "figures and tables. The PDF parser should handle this gracefully.")
    page.insert_text((50, 100), para1, fontsize=12, color=(0, 0, 0))

    # Insert figure that text should flow around (using shapes instead of image)
    fig_rect = fitz.Rect(350, 150, 450, 200)
    page.draw_rect(fig_rect, color=(0.5, 0.5, 0.5), fill=(0.9, 0.9, 0.9), width=1)
    # Draw a simple chart-like visualization
    page.draw_line(fitz.Point(360, 190), fitz.Point(440, 190), color=(0, 0, 0))  # X-axis
    page.draw_line(fitz.Point(360, 190), fitz.Point(360, 160), color=(0, 0, 0))  # Y-axis
    page.draw_line(fitz.Point(370, 185), fitz.Point(430, 165), color=(1, 0, 0), width=2)  # Data line

    page.insert_text((350, 210), "Figure: Sample chart", fontsize=10, color=(0, 0, 0))

    # Text that should appear after figure
    para2 = ("This paragraph comes after the figure. It should be properly "
             "detected and positioned in the markdown output.")
    page.insert_text((50, 150), para2, fontsize=12, color=(0, 0, 0))

    # Small table
    table_start = (100, 250)
    headers = ["Item", "Value"]
    cell_w, cell_h = 60, 20

    for i, header in enumerate(headers):
        x, y = table_start[0] + i * cell_w, table_start[1]
        rect = fitz.Rect(x, y, x + cell_w, y + cell_h)
        page.draw_rect(rect, color=(0, 0, 0), width=1)
        page.insert_text((x + 5, y + 12), header, fontsize=10)

    data = [["A", "100"], ["B", "200"]]
    for row_i, row in enumerate(data):
        for col_i, cell in enumerate(row):
            x = table_start[0] + col_i * cell_w
            y = table_start[1] + (row_i + 1) * cell_h
            rect = fitz.Rect(x, y, x + cell_w, y + cell_h)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((x + 5, y + 12), cell, fontsize=10)

    # Final paragraph
    para3 = "This final paragraph tests that content after tables is properly extracted."
    page.insert_text((50, 350), para3, fontsize=12, color=(0, 0, 0))

    return doc


def create_test_pdf_bytes(pdf_type: str) -> bytes:
    """Create test PDF and return as bytes.

    Parameters
    ----------
    pdf_type : str
        Type of PDF to create: 'images', 'tables', 'formatting', 'complex'

    Returns
    -------
    bytes
        PDF document as bytes
    """
    if pdf_type == 'images' or pdf_type == 'figures':
        doc = create_pdf_with_figures()
    elif pdf_type == 'tables':
        doc = create_pdf_with_tables()
    elif pdf_type == 'formatting':
        doc = create_pdf_with_formatting()
    elif pdf_type == 'complex':
        doc = create_pdf_with_complex_layout()
    else:
        raise ValueError(f"Unknown PDF type: {pdf_type}")

    # Convert to bytes
    pdf_bytes = doc.write()
    doc.close()

    return pdf_bytes


def create_temp_pdf_file(pdf_type: str) -> Path:
    """Create temporary PDF file for testing.

    Parameters
    ----------
    pdf_type : str
        Type of PDF to create: 'images', 'tables', 'formatting', 'complex'

    Returns
    -------
    Path
        Path to temporary PDF file (caller should clean up)
    """
    pdf_bytes = create_test_pdf_bytes(pdf_type)

    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    temp_file.write(pdf_bytes)
    temp_file.close()

    return Path(temp_file.name)
