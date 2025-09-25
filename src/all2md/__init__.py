"""all2md - A Python document conversion library for bidirectional transformation.

all2md provides a comprehensive solution for converting between various file formats
and Markdown. It supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML),
Excel (XLSX), Jupyter Notebooks (IPYNB), EPUB e-books, images, and 200+ text file formats with
intelligent content extraction and formatting preservation.

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
- **Documents**: PDF, DOCX, PPTX, HTML, EML, EPUB
- **Notebooks**: IPYNB (Jupyter Notebooks)
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
import logging
import mimetypes
import os
from dataclasses import fields
from io import BytesIO, StringIO
from pathlib import Path
from typing import IO, Literal, Optional, Union

from .constants import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PLAINTEXT_EXTENSIONS

# Extensions lists moved to constants.py - keep references for backward compatibility
from .exceptions import FormatError, InputError, MarkdownConversionError
from .options import (
    BaseOptions,
    DocxOptions,
    EmlOptions,
    EpubOptions,
    HtmlOptions,
    IpynbOptions,
    MarkdownOptions,
    MhtmlOptions,
    OdfOptions,
    PdfOptions,
    PptxOptions,
    RtfOptions,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility - all extension lists are now in constants.py
ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS

# Type definitions
DocumentFormat = Literal[
    "auto",      # Auto-detect from filename/content
    "pdf",       # PDF documents
    "docx",      # Word documents
    "pptx",      # PowerPoint presentations
    "html",      # HTML documents
    "mhtml",     # MHTML single-file web archives
    "rtf",       # Rich Text Format
    "xlsx",      # Excel spreadsheets
    "csv",       # CSV files
    "tsv",       # TSV files
    "txt",       # Plain text
    "eml",       # Email messages
    "image",     # Image files (PNG, JPEG, GIF)
    "ipynb",     # Jupyter Notebooks
    "odt",       # OpenDocument Text
    "odp",       # OpenDocument Presentation
    "epub"       # EPUB e-books
]


# Content-based format detection

def _detect_format_from_content(file_obj: IO[bytes]) -> DocumentFormat:
    """Detect document format from file content using magic bytes.

    Parameters
    ----------
    file_obj : IO[bytes]
        File object positioned at the beginning of content.

    Returns
    -------
    DocumentFormat
        Detected format or "txt" if unable to determine.
    """
    # Save current position and read magic bytes
    original_pos = file_obj.tell()
    file_obj.seek(0)
    magic_bytes = file_obj.read(512)  # Read first 512 bytes for detection
    file_obj.seek(original_pos)  # Restore original position

    if len(magic_bytes) == 0:
        return "txt"

    # PDF files start with %PDF
    if magic_bytes.startswith(b'%PDF'):
        return "pdf"

    # ZIP-based files (DOCX, PPTX, XLSX, EPUB) start with ZIP signature
    if magic_bytes.startswith(b'PK\x03\x04'):
        # Read more content to distinguish between ZIP-based formats
        file_obj.seek(0)
        zip_content = file_obj.read(1024)
        file_obj.seek(original_pos)

        if b'word/' in zip_content:
            return "docx"
        elif b'ppt/' in zip_content:
            return "pptx"
        elif b'xl/' in zip_content:
            return "xlsx"
        elif b'META-INF/container.xml' in zip_content or b'mimetype' in zip_content:
            # EPUB files contain META-INF/container.xml and/or mimetype file
            return "epub"
        else:
            logger.debug("Could not determine specific ZIP format, defaulting to txt")
            # Generic ZIP file, can't determine specific format
            return "txt"

    # RTF files start with {\rtf
    if magic_bytes.startswith(b'{\\rtf'):
        return "rtf"

    # HTML files often start with <!DOCTYPE html> or <html
    if (magic_bytes.lstrip().startswith(b'<!DOCTYPE html') or
        magic_bytes.lstrip().startswith(b'<html') or
        magic_bytes.lstrip().startswith(b'<HTML')):
        return "html"

    # EML files typically start with header fields
    if (b'Return-Path:' in magic_bytes[:100] or
        b'Received:' in magic_bytes[:100] or
        b'From:' in magic_bytes[:100] or
        b'To:' in magic_bytes[:100] or
        b'Subject:' in magic_bytes[:100]):
        return "eml"

    # MHTML files start with MIME-Version and have multipart/related Content-Type
    if (b'MIME-Version:' in magic_bytes[:50] and
        b'multipart/related' in magic_bytes[:512]):
        return "mhtml"

    # Image formats
    if magic_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image"
    elif magic_bytes.startswith(b'\xff\xd8\xff'):
        return "image"
    elif magic_bytes.startswith(b'GIF87a') or magic_bytes.startswith(b'GIF89a'):
        return "image"

    # Check for Jupyter Notebook JSON structure
    try:
        text_content = magic_bytes.decode('utf-8', errors='ignore')
        if text_content.strip().startswith('{'):
            # Try to parse as JSON to check for notebook structure
            import json
            try:
                data = json.loads(text_content[:1024])  # Parse first 1KB as JSON sample
                if isinstance(data, dict) and 'cells' in data and isinstance(data.get('cells'), list):
                    # Has the basic structure of a Jupyter notebook
                    logger.debug("Jupyter notebook structure detected in JSON content")
                    return "ipynb"
            except (json.JSONDecodeError, ValueError):
                pass  # Not valid JSON or not a notebook structure
    except UnicodeDecodeError:
        pass

    # Check if content looks like CSV/TSV (tabular data patterns)
    try:
        text_content = magic_bytes.decode('utf-8', errors='ignore')
        lines = text_content.split('\n')[:5]  # Check first 5 lines
        non_empty_lines = [line for line in lines if line.strip()]

        if len(non_empty_lines) >= 2:  # Need at least 2 lines (header + data)
            comma_count = sum(line.count(',') for line in non_empty_lines)
            tab_count = sum(line.count('\t') for line in non_empty_lines)

            # More relaxed CSV detection
            if comma_count >= len(non_empty_lines):  # At least one comma per line
                logger.debug(f"CSV pattern detected: {comma_count} commas in {len(non_empty_lines)} lines")
                return "csv"
            elif tab_count >= len(non_empty_lines):  # At least one tab per line
                logger.debug(f"TSV pattern detected: {tab_count} tabs in {len(non_empty_lines)} lines")
                return "tsv"
    except UnicodeDecodeError:
        pass

    # Default to plain text if no specific format detected
    return "txt"


def _get_format_from_filename(filename: str) -> DocumentFormat:
    """Extract format from filename extension with fallback to MIME type detection.

    Parameters
    ----------
    filename : str
        Filename to analyze.

    Returns
    -------
    DocumentFormat
        Format based on file extension, MIME type, or "txt" if unknown.
    """
    _, extension = os.path.splitext(filename.lower())

    # First try our explicit mapping (most reliable for our supported formats)
    format_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.pptx': 'pptx',
        '.xlsx': 'xlsx',
        '.html': 'html',
        '.htm': 'html',
        '.mhtml': 'mhtml',
        '.mht': 'mhtml',
        '.rtf': 'rtf',
        '.csv': 'csv',
        '.tsv': 'tsv',
        '.eml': 'eml',
        '.ipynb': 'ipynb',
        '.odt': 'odt',
        '.odp': 'odp',
        '.epub': 'epub',
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.gif': 'image',
    }

    explicit_format = format_map.get(extension)
    if explicit_format:
        logger.debug(f"Format detected from extension {extension}: {explicit_format}")
        return explicit_format  # type: ignore[return-value]

    # Fall back to MIME type detection
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        mime_to_format = {
            'application/pdf': 'pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
            'text/html': 'html',
            'application/rtf': 'rtf',
            'text/rtf': 'rtf',
            'text/csv': 'csv',
            'text/tab-separated-values': 'tsv',
            'message/rfc822': 'eml',
            'image/png': 'image',
            'image/jpeg': 'image',
            'image/gif': 'image',
        }

        detected_format = mime_to_format.get(mime_type)
        if detected_format:
            logger.debug(f"Format detected from MIME type {mime_type}: {detected_format}")
            return detected_format  # type: ignore[return-value]

        # Check for generic text types
        if mime_type.startswith('text/'):
            logger.debug(f"Generic text MIME type detected: {mime_type}")
            return "txt"

    logger.debug(f"No format detected from filename {filename}, defaulting to txt")
    return "txt"


def _dataframe_to_simple_markdown(df) -> str:
    """Convert pandas DataFrame to simple markdown table when tabulate is not available.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame to convert.

    Returns
    -------
    str
        Simple markdown table representation.
    """
    if df.empty:
        return ""

    lines = []

    # Header row
    headers = [str(col) for col in df.columns]
    lines.append("| " + " | ".join(headers) + " |")

    # Separator row
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    # Data rows
    for _, row in df.iterrows():
        values = [str(val) for val in row]
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def _detect_format_comprehensive(file_obj: IO[bytes], filename: str) -> DocumentFormat:
    """Comprehensive format detection using multiple strategies.

    Uses a multi-layered approach with the following priority:
    1. Explicit filename/extension mapping (if filename available)
    2. MIME type detection (if filename available)
    3. Content-based magic byte detection
    4. Fallback to text format

    Parameters
    ----------
    file_obj : IO[bytes]
        File object for content analysis if needed.
    filename : str
        Filename for extension/MIME type analysis. Can be 'unknown'.

    Returns
    -------
    DocumentFormat
        Best-guess format based on available information.
    """
    logger.debug(f"Starting comprehensive format detection for file: {filename}")

    # Strategy 1: If we have a filename, try filename-based detection first
    if filename != 'unknown':
        filename_format = _get_format_from_filename(filename)
        if filename_format != "txt":
            logger.debug(f"Format successfully detected from filename: {filename_format}")
            return filename_format

    # Strategy 2: If filename detection failed or unavailable, try content analysis
    logger.debug("Filename detection failed or unavailable, trying content analysis")
    content_format = _detect_format_from_content(file_obj)
    if content_format != "txt":
        logger.debug(f"Format successfully detected from content: {content_format}")
        return content_format

    # Strategy 3: Final fallback
    logger.debug("All detection methods failed, defaulting to txt format")
    return "txt"


# Options handling helpers

def _get_options_class_for_format(format: DocumentFormat) -> type[BaseOptions] | None:
    """Get the appropriate Options class for a given document format.

    Parameters
    ----------
    format : DocumentFormat
        The document format.

    Returns
    -------
    type[BaseOptions] | None
        Options class or None for formats that don't use options.
    """
    format_to_class = {
        "pdf": PdfOptions,
        "docx": DocxOptions,
        "pptx": PptxOptions,
        "html": HtmlOptions,
        "mhtml": MhtmlOptions,
        "eml": EmlOptions,
        "ipynb": IpynbOptions,
        "rtf": RtfOptions,
        "odt": OdfOptions,
        "odp": OdfOptions,
        "epub": EpubOptions
    }
    return format_to_class.get(format)


def _create_options_from_kwargs(format: DocumentFormat, **kwargs) -> BaseOptions | None:
    """Create format-specific options object from keyword arguments.

    Parameters
    ----------
    format : DocumentFormat
        The document format to create options for.
    **kwargs
        Keyword arguments to use for options creation.

    Returns
    -------
    BaseOptions | None
        Options instance or None for formats that don't use options.
    """
    options_class = _get_options_class_for_format(format)
    if not options_class:
        return None

    # Extract MarkdownOptions fields
    markdown_fields = {field.name for field in fields(MarkdownOptions)}
    markdown_opts = {k: v for k, v in kwargs.items() if k in markdown_fields}

    # Remove markdown fields from main kwargs
    remaining_kwargs = {k: v for k, v in kwargs.items() if k not in markdown_fields}

    # Create MarkdownOptions if we have any markdown-specific options
    markdown_options = MarkdownOptions(**markdown_opts) if markdown_opts else None

    # Add markdown_options to remaining kwargs if created
    if markdown_options:
        remaining_kwargs['markdown_options'] = markdown_options

    option_names = [field.name for field in fields(options_class)]
    valid_kwargs = {k: v for k, v in remaining_kwargs.items() if k in option_names}
    missing = [k for k in remaining_kwargs if k not in valid_kwargs]
    if missing:
        logger.debug(f"Skipping unknown options: {missing}")
    return options_class(**valid_kwargs)


def _merge_options(base_options: BaseOptions | MarkdownOptions | None, format: DocumentFormat, **kwargs) -> BaseOptions | None:
    """Merge base options with additional kwargs.

    Parameters
    ----------
    base_options : BaseOptions | None
        Existing options object to use as base.
    format : DocumentFormat
        Document format for creating new options if base_options is None.
    **kwargs
        Additional keyword arguments to merge/override.

    Returns
    -------
    BaseOptions | None
        Merged options object or None for formats that don't use options.
    """
    if base_options is None:
        return _create_options_from_kwargs(format, **kwargs)
    elif isinstance(base_options, MarkdownOptions):
        options_instance = _create_options_from_kwargs(format, **kwargs)

        if options_instance.markdown_options is None:
            options_instance.markdown_options = base_options
        else:
            # Update existing MarkdownOptions
            for field in fields(base_options):
                setattr(options_instance.markdown_options, field.name, getattr(base_options, field.name))
        return options_instance

    # Create a copy of the base options
    import copy
    merged_options = copy.deepcopy(base_options)

    # Extract MarkdownOptions fields from kwargs
    markdown_fields = {field.name for field in fields(MarkdownOptions)}
    markdown_kwargs = {k: v for k, v in kwargs.items() if k in markdown_fields}
    other_kwargs = {k: v for k, v in kwargs.items() if k not in markdown_fields}

    # Handle MarkdownOptions merging
    if markdown_kwargs:

        if merged_options.markdown_options is None:
            merged_options.markdown_options = MarkdownOptions(**markdown_kwargs)
        else:
            # Update existing MarkdownOptions
            for k, v in markdown_kwargs.items():
                setattr(merged_options.markdown_options, k, v)

    # Update other options directly
    for k, v in other_kwargs.items():
        if hasattr(merged_options, k):
            setattr(merged_options, k, v)

    return merged_options


# Main conversion function starts here


def to_markdown(
    input: Union[str, Path, IO[bytes], bytes],
    *,
    options: Optional[BaseOptions | MarkdownOptions] = None,
    format: DocumentFormat = "auto",
    **kwargs
) -> str:
    """Convert document to Markdown format with enhanced format detection.

    This is the main entry point for the all2md library. It can detect file
    formats from filenames, content analysis, or explicit format specification,
    then routes to the appropriate specialized converter for processing.

    Parameters
    ----------
    input : str, Path, or IO[bytes]
        Input can be:
        - File path (str or Path): Opens and processes the file
        - File-like object (IO[bytes]): Processes the data directly
    options : BaseOptions, optional
        Pre-configured options object for format-specific settings.
        If provided, individual kwargs will override these settings.
    format : {"auto", "pdf", "docx", "pptx", "html", "rtf", "xlsx", "csv", "tsv", "txt", "eml", "ipynb", "epub"}, default "auto"
        Document format specification:
        - "auto": Detect format automatically from filename and content
        - Other values: Force processing as the specified format
    **kwargs : keyword arguments
        Individual conversion options that override or supplement the options parameter:
        - attachment_mode : {"skip", "alt_text", "download", "base64"}
        - attachment_output_dir : str
        - attachment_base_url : str
        - Common MarkdownOptions fields (emphasis_symbol, bullet_symbols, etc.)
        - Format-specific options (see individual converter documentation)

    Returns
    -------
    str
        Document content converted to Markdown format

    Raises
    ------
    ImportError
        If required dependencies for specific file formats are not installed
    MarkdownConversionError
        If file processing fails due to corruption, format issues, etc.
    InputError
        If input parameters are invalid or file cannot be accessed

    Examples
    --------
    Convert from file path with automatic detection:

        >>> content = to_markdown('document.pdf')
        >>> print(type(content))
        <class 'str'>

    Convert with explicit format and options:

        >>> content = to_markdown('document.docx',
        ...                       format='docx',
        ...                       attachment_mode='download',
        ...                       attachment_output_dir='./attachments',
        ...                       emphasis_symbol='_')

    Convert from file object with pre-configured options:

        >>> pdf_options = PdfOptions(pages=[0, 1, 2], attachment_mode='base64')
        >>> with open('document.pdf', 'rb') as f:
        ...     content = to_markdown(f, options=pdf_options)

    Override specific settings in existing options:

        >>> content = to_markdown('document.pdf',
        ...                       options=pdf_options,
        ...                       attachment_mode='download')  # Override base64 with download

    Notes
    -----
    Supported formats include PDF, Word (DOCX), PowerPoint (PPTX), HTML,
    email (EML), Excel (XLSX), Jupyter Notebooks (IPYNB), EPUB e-books, RTF, images,
    CSV/TSV, and 200+ text file formats.

    The function provides intelligent format detection using filename extensions,
    MIME types, and content analysis (magic bytes) for file objects without names.
    """

    # Handle input parameter - convert to file object and get filename
    if isinstance(input, (str, Path)):
        filename = str(input)
        with open(input, 'rb') as file:
            return to_markdown(file, options=options, format=format, _filename=filename, **kwargs)
    elif isinstance(input, bytes):
        file: IO[bytes] = BytesIO(input)
        filename = "unknown"
    else:
        # File-like object case
        file: IO[bytes] = input  # type: ignore
        filename = getattr(file, 'name', kwargs.pop('_filename', 'unknown'))

    # Determine the actual format to use
    if format == "auto":
        # Use comprehensive detection strategy
        actual_format = _detect_format_comprehensive(file, filename)
    else:
        # Use explicitly specified format
        actual_format = format
        logger.debug(f"Using explicitly specified format: {actual_format}")

    # Create or merge options based on parameters
    if options is not None and kwargs:
        # Merge provided options with kwargs (kwargs override)
        final_options = _merge_options(options, actual_format, **kwargs)
    elif options is not None:
        # Use provided options as-is
        final_options = options
    elif kwargs:
        # Create options from kwargs only
        final_options = _create_options_from_kwargs(actual_format, **kwargs)
    else:
        # No options provided
        final_options = None

    # Process file based on detected/specified format
    if actual_format == "html":
        from all2md.converters.html2markdown import html_to_markdown

        file.seek(0)
        html_content = file.read().decode("utf-8", errors="replace")
        content = html_to_markdown(html_content, options=final_options)

    elif actual_format == "mhtml":
        from all2md.converters.mhtml2markdown import mhtml_to_markdown

        file.seek(0)
        content = mhtml_to_markdown(file, options=final_options)

    elif actual_format == "rtf":
        from all2md.converters.rtf2markdown import rtf_to_markdown

        file.seek(0)
        try:
            content = rtf_to_markdown(file, options=final_options)
        except ImportError as e:
            raise ImportError(
                "`pyth` is required to read RTF files. Install with `pip install pyth`."
            ) from e

    elif actual_format == "csv":
        file.seek(0)
        try:
            import pandas as pd
            df = pd.read_csv(file, delimiter=",", encoding="utf-8")
            try:
                content = df.to_markdown()
            except ImportError:
                # tabulate not available, create simple markdown table
                logger.debug("tabulate not available, creating simple markdown table")
                content = _dataframe_to_simple_markdown(df)
        except ImportError:
            content = file.read().decode("utf-8", errors="replace")

    elif actual_format == "tsv":
        file.seek(0)
        try:
            import pandas as pd
            df = pd.read_csv(file, delimiter="\t", encoding="utf-8")
            try:
                content = df.to_markdown()
            except ImportError:
                # tabulate not available, create simple markdown table
                logger.debug("tabulate not available, creating simple markdown table")
                content = _dataframe_to_simple_markdown(df)
        except ImportError:
            content = file.read().decode("utf-8", errors="replace")

    elif actual_format == "xlsx":
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

    elif actual_format == "pptx":
        from all2md.converters.pptx2markdown import pptx_to_markdown

        file.seek(0)
        try:
            content = pptx_to_markdown(file, options=final_options)
        except ImportError as e:
            raise ImportError(
                "`python-pptx` is required to read powerpoint files. Install with `pip install python-pptx`."
            ) from e

    elif actual_format == "docx":
        from all2md.converters.docx2markdown import docx_to_markdown

        file.seek(0)
        try:
            content = docx_to_markdown(file, options=final_options)
        except ImportError as e:
            raise ImportError(
                "`python-docx` is required to read Word docx files. Install with `pip install python-docx`."
            ) from e

    elif actual_format == "pdf":
        from all2md.converters.pdf2markdown import pdf_to_markdown

        file.seek(0)
        filestream = BytesIO(file.read())
        try:
            content = pdf_to_markdown(filestream, options=final_options)
        except ImportError as e:
            raise ImportError(
                "`pymupdf` version >1.24.0 is required to read PDF files. Install with `pip install pymupdf`"
            ) from e

    elif actual_format == "eml":
        from all2md.converters.eml2markdown import eml_to_markdown

        file.seek(0)
        raw_data = b""
        # Handle encoding issues gracefully
        try:
            raw_data = file.read()
            decoded_data = raw_data.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.debug(f"Unicode error decoding as UTF: {e!r}", exc_info=True)
            # Try with error handling for mixed encodings
            decoded_data = raw_data.decode("utf-8", errors="replace")

        eml_stream: StringIO = StringIO(decoded_data)
        content = eml_to_markdown(eml_stream, options=final_options)

    elif actual_format == "ipynb":
        from all2md.converters.ipynb2markdown import ipynb_to_markdown

        file.seek(0)
        content = ipynb_to_markdown(file, options=final_options)

    elif actual_format in ("odt", "odp"):
        from all2md.converters.odf2markdown import odf_to_markdown

        file.seek(0)
        try:
            content = odf_to_markdown(file, options=final_options)
        except ImportError as e:
            raise ImportError(
                "`odfpy` is required to read OpenDocument files. Install with `pip install odfpy`."
            ) from e

    elif actual_format == "epub":
        from all2md.converters.epub2markdown import epub_to_markdown

        try:
            # EPUB requires file path, not file object, due to ebooklib limitation
            if filename == "unknown":
                # For file objects without known path, we need to create a temporary file
                import tempfile
                file.seek(0)
                with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as temp_file:
                    temp_file.write(file.read())
                    temp_path = temp_file.name
                try:
                    content = epub_to_markdown(temp_path, options=final_options)
                finally:
                    # Clean up temporary file
                    import os
                    os.unlink(temp_path)
            else:
                # Use the original filename path
                content = epub_to_markdown(filename, options=final_options)
        except ImportError as e:
            raise ImportError(
                "`ebooklib` is required to read EPUB files. Install with `pip install ebooklib`."
            ) from e

    elif actual_format == "image":
        raise FormatError("Invalid input type: `image` not supported.")
    else:  # actual_format == "txt" or any other format
        # Plain text handling
        file.seek(0)
        try:
            content = file.read().decode("utf-8", errors="replace")
        except Exception as e:
            raise MarkdownConversionError(f"Could not decode file as UTF-8: {filename}") from e

    # Fix windows newlines and return
    return content.replace("\r\n", "\n")


__all__ = [
    "ALL_ALLOWED_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "PLAINTEXT_EXTENSIONS",
    "to_markdown",
    # Type definitions
    "DocumentFormat",
    # Re-exported classes and exceptions for public API
    "BaseOptions",
    "DocxOptions",
    "EmlOptions",
    "HtmlOptions",
    "IpynbOptions",
    "MarkdownOptions",
    "OdfOptions",
    "PdfOptions",
    "PptxOptions",
    "MarkdownConversionError",
    "InputError",
]
