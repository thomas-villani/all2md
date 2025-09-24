"""all2md - A Python document conversion library for bidirectional transformation.

all2md provides a comprehensive solution for converting between various file formats
and Markdown. It supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML),
Excel (XLSX), images, and 200+ text file formats with intelligent content extraction
and formatting preservation.

The library uses a modular architecture where the main `parse_file()` function
automatically detects file types and routes to appropriate specialized converters.
Each converter module handles specific format requirements while maintaining
consistent Markdown output with support for tables, images, and complex formatting.

Key Features
------------
- Bidirectional conversion (format-to-Markdown and Markdown-to-format)
- Advanced PDF parsing with table detection using PyMuPDF
- Word document processing with formatting preservation
- PowerPoint slide-by-slide extraction
- HTML processing with configurable conversion options
- Email chain parsing with attachment handling
- Base64 image embedding support
- Support for 200+ plaintext file formats

Supported Formats
-----------------
- **Documents**: PDF, DOCX, PPTX, HTML, EML
- **Spreadsheets**: XLSX, CSV, TSV
- **Images**: PNG, JPEG, GIF (embedded as base64)
- **Text**: 200+ formats including code files, configs, markup

Requirements
------------
- Python 3.12+
- Optional dependencies loaded per format (PyMuPDF, python-docx, etc.)

Examples
--------
Basic usage for file conversion:

    >>> from all2md import parse_file
    >>> with open('document.pdf', 'rb') as f:
    ...     markdown_content = parse_file(f, 'document.pdf')
    >>> print(markdown_content)

With MIME type detection:

    >>> content, mimetype = parse_file(file_obj, filename, return_mimetype=True)
    >>> print(f"Detected type: {mimetype}")
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
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

#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#
import base64
import mimetypes
import os
from io import BytesIO, StringIO
from typing import IO, Union

from .constants import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PLAINTEXT_EXTENSIONS

# Extensions lists moved to constants.py - keep references for backward compatibility
from .exceptions import MdparseConversionError, MdparseInputError
from .options import DocxOptions, EmlOptions, HtmlOptions, PdfOptions, PptxOptions

# Re-export for backward compatibility - all extension lists are now in constants.py
ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS


# Main parse function starts here


def parse_file(
    file: IO,
    filename: str,
    return_mimetype: bool = False,
    options: dict | None = None,  # Reserved for future per-format options
) -> Union[str, None, tuple[Union[str, None], Union[str, None]]]:
    """Parse file and return content as Markdown format.

    This is the main entry point for the all2md library. It automatically
    detects file type based on filename and MIME type, then routes to the
    appropriate specialized converter for processing.

    Parameters
    ----------
    file : IO
        A file-like object containing the document data
    filename : str
        Filename used for MIME type detection and format determination
    return_mimetype : bool, default False
        If True, returns tuple of (content, mimetype) instead of just content
    options : dict or None, optional
        Reserved for future per-format conversion options

    Returns
    -------
    str or None or tuple
        - If return_mimetype=False: Markdown content as string, or None if unsupported
        - If return_mimetype=True: tuple of (content, mimetype) where either may be None

    Raises
    ------
    ImportError
        If required dependencies for specific file formats are not installed
    MdparseConversionError
        If file processing fails due to corruption, format issues, etc.
    MdparseInputError
        If file or filename parameters are invalid

    Examples
    --------
    Basic usage:

        >>> with open('document.pdf', 'rb') as f:
        ...     content = parse_file(f, 'document.pdf')
        >>> print(type(content))
        <class 'str'>

    With MIME type detection:

        >>> with open('document.docx', 'rb') as f:
        ...     content, mimetype = parse_file(f, 'document.docx', return_mimetype=True)
        >>> print(mimetype)
        application/vnd.openxmlformats-officedocument.wordprocessingml.document

    Notes
    -----
    Supported formats include PDF, Word (DOCX), PowerPoint (PPTX), HTML,
    email (EML), Excel (XLSX), images, and 200+ text file formats.
    """

    _, extension = os.path.splitext(filename)
    is_dot_file = False
    # For dot-files
    if not extension and os.path.basename(filename).startswith("."):
        extension = os.path.basename(filename)
        is_dot_file = True

    extension = extension.lower()
    file_mimetype = mimetypes.guess_type(filename)[0]
    if file_mimetype is None:
        if extension in PLAINTEXT_EXTENSIONS:
            file_mimetype = "text/plain"
        if is_dot_file:
            file_mimetype = "text/plain"

    # Plain text
    if (file_mimetype and file_mimetype.startswith("text/")) or extension in PLAINTEXT_EXTENSIONS:
        file.seek(0)
        if extension in (".csv", ".tsv"):
            try:
                import pandas as pd

                df = pd.read_csv(file, delimiter="\t" if extension == "tsv" else ",", encoding="utf-8")
                content = df.to_markdown()
            except ImportError:
                content = file.read().decode("utf-8")

        else:
            content = file.read().decode("utf-8")
    # Excel file
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError("`pandas` is required to read xlsx files. Install with `pip install pandas`.") from e

        excel_file = pd.ExcelFile(file)
        content = ""
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            content += "## " + sheet_name + "\n"
            content += df.to_markdown()
            content += "\n\n---\n\n"
    # Powerpoint file
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        from .pptx2markdown import pptx_to_markdown

        file.seek(0)
        try:
            content = pptx_to_markdown(file)
        except ImportError as e:
            raise ImportError(
                "`python-pptx` is required to read powerpoint files. Install with `pip install python-pptx`."
            ) from e
    # Docx file
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from .docx2markdown import docx_to_markdown

        file.seek(0)
        try:
            content = docx_to_markdown(file)
        except ImportError as e:
            raise ImportError(
                "`python-docx` is required to read Word docx files. Install with `pip install python-docx`."
            ) from e
    # PDF
    elif file_mimetype == "application/pdf":
        from .pdf2markdown import pdf_to_markdown

        file.seek(0)
        filestream = BytesIO(file.read())
        try:
            content = pdf_to_markdown(filestream)
        except ImportError as e:
            raise ImportError(
                "`pymupdf` version >1.24.0 is required to read PDF files. Install with `pip install pymupdf`"
            ) from e
    # Image
    elif file_mimetype and file_mimetype in ("image/png", "image/jpeg", "image/gif"):
        file.seek(0)
        b64_data = base64.b64encode(file.read()).decode("utf-8")
        content = f"data:{file_mimetype};base64,{b64_data}"
    # EML file (emails)
    elif file_mimetype == "message/rfc822":
        from .emlfile import parse_email_chain

        file.seek(0)
        eml_stream: StringIO = StringIO(file.read().decode("utf-8"))
        content = parse_email_chain(eml_stream)
    # Others
    else:  # elif file.content_type == "application/octet-stream":
        # guess = mimetypes.guess_type(file.filename)[0]
        # Try to just load it as text.
        file.seek(0)
        try:
            content = file.read().decode("utf-8")
        except UnicodeDecodeError:
            if return_mimetype:
                return (None, None)
            return None

    content = content.replace("\r\n", "\n")  # Fix windows newlines
    if return_mimetype:
        return content, file_mimetype
    return content


__all__ = [
    "ALL_ALLOWED_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "PLAINTEXT_EXTENSIONS",
    "parse_file",
    # Re-exported classes and exceptions for public API
    "DocxOptions",
    "EmlOptions",
    "HtmlOptions",
    "PdfOptions",
    "PptxOptions",
    "MdparseConversionError",
    "MdparseInputError",
]
