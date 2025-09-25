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

    >>> from all2md import to_markdown
    >>> markdown_content = to_markdown('document.pdf')
    >>> print(markdown_content)

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
from pathlib import Path
from typing import Any, IO, Union

from .constants import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PLAINTEXT_EXTENSIONS

# Extensions lists moved to constants.py - keep references for backward compatibility
from .exceptions import MdparseConversionError, MdparseInputError
from .options import DocxOptions, EmlOptions, HtmlOptions, MarkdownOptions, PdfOptions, PptxOptions

# Re-export for backward compatibility - all extension lists are now in constants.py
ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS


# Options handling helpers

def _create_format_options(file_mimetype: str, **options) -> Union[PdfOptions, DocxOptions, HtmlOptions, PptxOptions, EmlOptions, None]:
    """Create format-specific options object from flat options."""
    # Extract common MarkdownOptions
    markdown_opts = {}
    if 'markdown_emphasis_symbol' in options:
        markdown_opts['emphasis_symbol'] = options.pop('markdown_emphasis_symbol')
    if 'markdown_bullet_symbols' in options:
        markdown_opts['bullet_symbols'] = options.pop('markdown_bullet_symbols')
    if 'markdown_page_separator' in options:
        markdown_opts['page_separator'] = options.pop('markdown_page_separator')
    if 'markdown_list_indent_width' in options:
        markdown_opts['list_indent_width'] = options.pop('markdown_list_indent_width')

    # Create MarkdownOptions instance if we have any options
    md_options_instance = MarkdownOptions(**markdown_opts) if markdown_opts else None

    # Common attachment options
    attachment_opts = {}
    if 'attachment_mode' in options:
        attachment_opts['attachment_mode'] = options.pop('attachment_mode')
    if 'attachment_output_dir' in options:
        attachment_opts['attachment_output_dir'] = options.pop('attachment_output_dir')
    if 'attachment_base_url' in options:
        attachment_opts['attachment_base_url'] = options.pop('attachment_base_url')

    # Add markdown_options to attachment opts if we have it
    if md_options_instance:
        attachment_opts['markdown_options'] = md_options_instance

    # Create format-specific options based on MIME type
    if file_mimetype == "application/pdf":
        # PDF-specific options
        pdf_opts = {k.replace('pdf_', ''): v for k, v in options.items() if k.startswith('pdf_')}
        return PdfOptions(**{**attachment_opts, **pdf_opts})
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        # DOCX-specific options
        docx_opts = {k.replace('docx_', ''): v for k, v in options.items() if k.startswith('docx_')}
        return DocxOptions(**{**attachment_opts, **docx_opts})
    elif file_mimetype == "text/html":
        # HTML-specific options
        html_opts = {k.replace('html_', ''): v for k, v in options.items() if k.startswith('html_')}
        return HtmlOptions(**{**attachment_opts, **html_opts})
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        # PPTX-specific options
        pptx_opts = {k.replace('pptx_', ''): v for k, v in options.items() if k.startswith('pptx_')}
        return PptxOptions(**{**attachment_opts, **pptx_opts})
    elif file_mimetype == "message/rfc822":
        # EML-specific options
        eml_opts = {k.replace('eml_', ''): v for k, v in options.items() if k.startswith('eml_')}
        return EmlOptions(**{**attachment_opts, **eml_opts})
    else:
        # Return None for formats that don't use options
        return None


# Main conversion function starts here


def to_markdown(
    input: Union[str, Path, IO[bytes]],
    **options
) -> str:
    """Convert document to Markdown format with automatic format detection.

    This is the main entry point for the all2md library. It automatically
    detects file type based on file path extension and MIME type, then routes
    to the appropriate specialized converter for processing.

    Parameters
    ----------
    input : str, Path, or IO[bytes]
        Input can be:
        - File path (str or Path): Opens and processes the file
        - File-like object (IO[bytes]): Processes the data directly
    **options : keyword arguments
        Conversion options passed to format-specific converters:
        - attachment_mode : {"skip", "alt_text", "download", "base64"}
        - attachment_output_dir : str
        - attachment_base_url : str
        - markdown_emphasis_symbol : {"*", "_"}
        - And format-specific options (see individual converter docs)

    Returns
    -------
    str
        Document content converted to Markdown format

    Raises
    ------
    ImportError
        If required dependencies for specific file formats are not installed
    MdparseConversionError
        If file processing fails due to corruption, format issues, etc.
    MdparseInputError
        If input parameters are invalid or file cannot be accessed

    Examples
    --------
    Convert from file path:

        >>> content = to_markdown('document.pdf')
        >>> print(type(content))
        <class 'str'>

    Convert with options:

        >>> content = to_markdown('document.docx',
        ...                       attachment_mode='download',
        ...                       attachment_output_dir='./attachments',
        ...                       markdown_emphasis_symbol='_')

    Convert from file object:

        >>> with open('document.pdf', 'rb') as f:
        ...     content = to_markdown(f)

    Notes
    -----
    Supported formats include PDF, Word (DOCX), PowerPoint (PPTX), HTML,
    email (EML), Excel (XLSX), images, and 200+ text file formats.
    """

    # Handle input parameter - convert to file object and filename
    if isinstance(input, (str, Path)):
        filename = str(input)
        with open(input, 'rb') as file:
            return to_markdown(file, **options, _filename=filename)
    else:
        # File-like object case
        file: IO[bytes] = input  # type: ignore
        filename = getattr(file, 'name', options.pop('_filename', 'unknown'))

    # Extract file extension and detect type
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

    # Create format-specific options
    format_options = _create_format_options(file_mimetype or "unknown", **options)

    # HTML file
    if file_mimetype == "text/html" or extension in (".html", ".htm"):
        from .html2markdown import html_to_markdown

        file.seek(0)
        html_content = file.read().decode("utf-8", errors="replace")
        content = html_to_markdown(html_content, options=format_options)
    # Plain text
    elif (file_mimetype and file_mimetype.startswith("text/")) or extension in PLAINTEXT_EXTENSIONS:
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
            content = pptx_to_markdown(file, options=format_options)
        except ImportError as e:
            raise ImportError(
                "`python-pptx` is required to read powerpoint files. Install with `pip install python-pptx`."
            ) from e
    # Docx file
    elif file_mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from .docx2markdown import docx_to_markdown

        file.seek(0)
        try:
            content = docx_to_markdown(file, options=format_options)
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
            content = pdf_to_markdown(filestream, options=format_options)
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
        # Handle encoding issues gracefully
        try:
            raw_data = file.read()
            decoded_data = raw_data.decode("utf-8")
        except UnicodeDecodeError:
            # Try with error handling for mixed encodings
            decoded_data = raw_data.decode("utf-8", errors="replace")

        eml_stream: StringIO = StringIO(decoded_data)
        result = parse_email_chain(eml_stream, options=format_options)
        # parse_email_chain can return str or list, ensure we get a string
        content = result if isinstance(result, str) else str(result)
    # Others
    else:  # elif file.content_type == "application/octet-stream":
        # guess = mimetypes.guess_type(file.filename)[0]
        # Try to just load it as text.
        file.seek(0)
        try:
            content = file.read().decode("utf-8")
        except UnicodeDecodeError as e:
            raise MdparseConversionError(f"Could not decode file as UTF-8: {filename}") from e

    # Fix windows newlines and return
    return content.replace("\r\n", "\n")


__all__ = [
    "ALL_ALLOWED_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "PLAINTEXT_EXTENSIONS",
    "to_markdown",
    # Re-exported classes and exceptions for public API
    "DocxOptions",
    "EmlOptions",
    "HtmlOptions",
    "MarkdownOptions",
    "PdfOptions",
    "PptxOptions",
    "MdparseConversionError",
    "MdparseInputError",
]
