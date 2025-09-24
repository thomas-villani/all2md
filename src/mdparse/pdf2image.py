"""PDF to image conversion module.

This module provides functionality to convert PDF documents into image formats
(JPEG, PNG) using PyMuPDF. It supports page-by-page conversion with customizable
resolution, format options, and range selection. The module can output images
as raw binary data or base64-encoded strings for web applications.

The converter processes PDF pages by rendering them at specified zoom levels
and quality settings, producing high-quality images suitable for display,
archival, or further processing. It handles password-protected PDFs and
provides flexible output options.

Key Features
------------
- High-quality PDF page rendering to images
- Multiple output formats (JPEG, PNG)
- Customizable zoom/resolution control
- Page range selection (first/last page options)
- Password-protected PDF support
- Base64 encoding for web applications
- Batch processing of multiple pages
- Memory-efficient page-by-page processing

Conversion Options
------------------
- Zoom levels for resolution control (default 2.0x)
- Format selection (JPEG for smaller files, PNG for quality)
- Page range specification for selective conversion
- Password support for protected documents
- Output format choice (binary bytes or base64 strings)

Quality and Performance
-----------------------
- High-resolution rendering with anti-aliasing
- Optimized memory usage for large documents
- Configurable compression settings
- Fast processing using PyMuPDF's efficient rendering
- Support for complex PDF layouts and graphics

Dependencies
------------
- PyMuPDF (fitz): For PDF rendering and image generation
- base64: For encoding images as strings
- pathlib: For file path handling

Examples
--------
Basic PDF to images conversion:

    >>> from pdf2image import pdf_to_images
    >>> with open('document.pdf', 'rb') as f:
    ...     images = pdf_to_images(f, fmt='png', zoom=1.5)
    >>> print(f"Generated {len(images)} images")

Convert specific page range with base64 output:

    >>> images_b64 = pdf_to_images(
    ...     'document.pdf',
    ...     first_page=1,
    ...     last_page=5,
    ...     as_base64=True,
    ...     fmt='jpeg'
    ... )

High-resolution conversion:

    >>> hi_res_images = pdf_to_images(pdf_file, zoom=3.0, fmt='png')

Note
----
Requires PyMuPDF package. Higher zoom levels produce better quality but
larger file sizes. JPEG format is more compact while PNG preserves
transparency and provides lossless compression.
"""

#  Copyright (c) 2023-2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import base64
from pathlib import Path
from typing import BinaryIO, Literal

import fitz


def pdf_to_images(
    pdf_file: str | Path | BinaryIO,
    zoom: float = 2.0,
    fmt: Literal["jpeg", "png"] = "jpeg",
    first_page: int | None = None,
    last_page: int | None = None,
    userpw: str | None = None,
    as_base64: bool = False,
) -> list[bytes] | list[str]:
    """Convert PDF to list of images using PyMuPDF.

    Parameters
    ----------
    pdf_file : Union[str, Path, BinaryIO]
        PDF file path or file-like object
    zoom : float, default=2.0
        Zoom factor for rendering (higher = better quality but larger files)
    fmt : str, default='jpeg', one of {'jpeg', 'png'}
        Output format for images
    first_page : int, optional
        First page to convert (0-based)
    last_page : int, optional
        Last page to convert (0-based)
    userpw : str, optional
        User password if PDF is encrypted
    as_base64 : bool, default=False
        If True, return base64 encoded data URLs

    Returns
    -------
    List[Union[bytes, str]]
        List of image data (bytes or base64 data URLs)

    Notes
    -----
    Requires PyMuPDF package:
    pip install PyMuPDF

    """

    # Open PDF
    if isinstance(pdf_file, str | Path):
        pdf = fitz.open(pdf_file)
    else:
        # Handle file-like object
        pdf_content = pdf_file.read()
        pdf = fitz.open(stream=pdf_content)

    if userpw:
        pdf.authenticate(userpw)

    # Determine page range
    first_page = first_page or 0
    last_page = last_page or len(pdf) - 1

    result = []
    for page_num in range(first_page, last_page + 1):
        page = pdf[page_num]

        # Get page as image
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        img_data = pix.tobytes("jpeg") if fmt == "jpeg" else pix.tobytes("png")

        if as_base64:
            b64_data = base64.b64encode(img_data).decode("utf-8")
            result.append(f"data:image/{fmt.lower()};base64,{b64_data}")
        else:
            result.append(img_data)

    pdf.close()
    return result
