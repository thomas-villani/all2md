#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/pdf2markdown.py
"""PDF to Markdown conversion module.

This module provides advanced PDF parsing with table detection using PyMuPDF.
It extracts text content, handles complex layouts, and converts them to
well-formatted Markdown with support for headers, tables, links, and code blocks.

The conversion process identifies document structure including headers based on
font sizes, preserves table layouts using PyMuPDF's table detection, and
maintains formatting for code blocks, emphasis, and links.

Key Features
------------
- Advanced table detection and Markdown formatting
- Header identification based on font size analysis
- Link extraction and Markdown link formatting
- Code block detection for monospace fonts
- Page-by-page processing with customizable page ranges
- Password-protected PDF support
- Image embedding as base64 data URLs

Dependencies
------------
- PyMuPDF (fitz) v1.24.0 or later for PDF processing
- Required for all PDF operations including text extraction and table detection

Examples
--------
Basic PDF conversion:

    >>> from all2md.parsers.pdf2markdown import pdf_to_markdown
    >>> markdown_content = pdf_to_markdown("document.pdf")

Convert specific pages with options:

    >>> from all2md.options import PdfOptions
    >>> options = PdfOptions(pages=[0, 1, 2])
    >>> content = pdf_to_markdown("document.pdf", options=options)

Convert from file-like object:

    >>> from io import BytesIO
    >>> with open("document.pdf", "rb") as f:
    ...     content = pdf_to_markdown(BytesIO(f.read()))

Original from pdf4llm package, modified by Tom Villani to improve table processing.
"""

import string
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    import fitz

from all2md.constants import (
    PDF_MIN_PYMUPDF_VERSION,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import InputError, MarkdownConversionError, PasswordProtectedError
from all2md.options import MarkdownOptions, PdfOptions
from all2md.utils.attachments import create_attachment_sequencer
from all2md.utils.inputs import (
    validate_and_convert_input,
    validate_page_range,
)
from all2md.utils.metadata import (
    PDF_FIELD_MAPPING,
    DocumentMetadata,
    extract_dict_metadata,
    prepend_metadata_if_enabled,
)

# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pdf",
    extensions=[".pdf"],
    mime_types=["application/pdf", "application/x-pdf"],
    magic_bytes=[
        (b"%PDF", 0),  # PDF signature
    ],
    converter_module="all2md.parsers.pdf2markdown",
    converter_function="pdf_to_markdown",
    required_packages=[("pymupdf", "fitz", ">=1.26.4")],
    optional_packages=[],
    import_error_message=(
        "PDF conversion requires 'pymupdf' version 1.26.4 or later. "
        "Install with: pip install 'pymupdf>=1.26.4'"
    ),
    options_class="PdfOptions",
    description="Convert PDF documents to Markdown with advanced table detection",
    priority=10
)


def _check_pymupdf_version() -> None:
    """Check that PyMuPDF version meets minimum requirements.

    Raises
    ------
    MarkdownConversionError
        If PyMuPDF version is too old
    """
    try:
        import fitz
        min_version = tuple(map(int, PDF_MIN_PYMUPDF_VERSION.split(".")))
        if fitz.pymupdf_version_tuple < min_version:
            raise ImportError(
                f"PyMuPDF version {PDF_MIN_PYMUPDF_VERSION} or later is required, "
                f"but {'.'.join(map(str, fitz.pymupdf_version_tuple))} is installed."
            )
    except ImportError as e:
        if "fitz" in str(e) or "No module" in str(e):
            from all2md.exceptions import DependencyError
            raise DependencyError(
                converter_name="pdf",
                missing_packages=[("pymupdf", f">={PDF_MIN_PYMUPDF_VERSION}")],
            ) from e
        raise


SPACES = set(string.whitespace)  # used to check relevance of text pieces


class IdentifyHeaders:
    """Compute data for identifying header text based on font size analysis.

    This class analyzes font sizes across document pages to identify which
    font sizes should be treated as headers versus body text. It creates
    a mapping from font sizes to Markdown header levels (# ## ### etc.).

    Parameters
    ----------
    doc : fitz.Document
        PDF document to analyze
    pages : list[int], range, or None, optional
        Pages to analyze for font size distribution. If None, analyzes all pages.
    body_limit : float or None, optional
        Font size threshold below which text is considered body text.
        If None, uses the most frequent font size as body text baseline.
    options : PdfOptions or None, optional
        PDF conversion options containing header detection parameters.

    Attributes
    ----------
    header_id : dict[int, str]
        Mapping from font size to markdown header prefix string
    options : PdfOptions
        PDF conversion options used for header detection
    """

    def __init__(
            self,
            doc,  # PyMuPDF Document object
            pages: list[int] | range | None = None,
            body_limit: float | None = None,
            options: PdfOptions | None = None,
    ) -> None:
        """Initialize header identification by analyzing font sizes.

        Reads all text spans from specified pages and builds a frequency
        distribution of font sizes. Uses this to determine which font sizes
        should be treated as headers versus body text.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to analyze
        pages : list[int], range, or None, optional
            Pages to analyze for font size distribution. If None, analyzes all pages.
        body_limit : float or None, optional
            Font size threshold below which text is considered body text.
            If None, uses the most frequent font size as body text baseline.
        options : PdfOptions or None, optional
            PDF conversion options containing header detection parameters.
        """
        self.options = options or PdfOptions()

        # Determine pages to sample for header analysis
        if self.options.header_sample_pages is not None:
            if isinstance(self.options.header_sample_pages, int):
                # Sample first N pages
                pages_to_sample = list(range(min(self.options.header_sample_pages, doc.page_count)))
            else:
                # Use specific page list
                pages_to_sample = [p for p in self.options.header_sample_pages if p < doc.page_count]
        elif pages is not None:
            pages_to_sample = pages if isinstance(pages, list) else list(pages)
        else:
            pages_to_sample = list(range(doc.page_count))

        pages_to_use: list[int] = pages_to_sample
        fontsizes: dict[int, int] = {}
        fontweight_sizes: dict[int, int] = {}  # Track bold font sizes
        allcaps_sizes: dict[int, int] = {}  # Track all-caps text sizes
        import fitz
        for pno in pages_to_use:
            page = doc[pno]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            for span in [  # look at all non-empty horizontal spans
                s
                for b in blocks
                for line in b["lines"]
                for s in line["spans"]
                if not SPACES.issuperset(s["text"]) and line["dir"] == (1, 0)
            ]:
                fontsz = round(span["size"])
                text = span["text"].strip()
                text_len = len(text)

                # Track font size occurrences
                count = fontsizes.get(fontsz, 0) + text_len
                fontsizes[fontsz] = count

                # Track bold text if enabled
                if self.options.header_use_font_weight and (span["flags"] & 16):  # Bold flag
                    fontweight_sizes[fontsz] = fontweight_sizes.get(fontsz, 0) + text_len

                # Track all-caps text if enabled
                if self.options.header_use_all_caps and text.isupper() and text.isalpha():
                    allcaps_sizes[fontsz] = allcaps_sizes.get(fontsz, 0) + text_len

        # maps a fontsize to a string of multiple # header tag characters
        self.header_id = {}
        self.bold_header_sizes = set()  # Track which sizes are headers due to bold
        self.allcaps_header_sizes = set()  # Track which sizes are headers due to all-caps

        # Apply allowlist/denylist filters
        if self.options.header_size_denylist:
            for size in self.options.header_size_denylist:
                fontsizes.pop(round(size), None)

        # Filter by minimum occurrences
        if self.options.header_min_occurrences > 0:
            fontsizes = {k: v for k, v in fontsizes.items() if v >= self.options.header_min_occurrences}

        # If not provided, choose the most frequent font size as body text.
        # If no text at all on all pages, just use 12
        if body_limit is None:
            temp = sorted(
                fontsizes.items(),
                key=lambda i: i[1],
                reverse=True,
            )
            body_limit = temp[0][0] if temp else 12

        # Get header sizes based on percentile threshold and minimum font size ratio
        if self.options.header_percentile_threshold and fontsizes:
            sorted_sizes = sorted(fontsizes.keys(), reverse=True)
            percentile_idx = int(len(sorted_sizes) * (1 - self.options.header_percentile_threshold / 100))
            percentile_threshold = sorted_sizes[max(0, percentile_idx - 1)] if percentile_idx > 0 else sorted_sizes[0]
            # Apply both percentile and font size ratio filters
            min_header_size = body_limit * self.options.header_font_size_ratio
            sizes = [s for s in sorted_sizes if s >= percentile_threshold and s >= min_header_size]
        else:
            # Apply font size ratio filter even without percentile threshold
            min_header_size = body_limit * self.options.header_font_size_ratio
            sizes = sorted([f for f in fontsizes if f >= min_header_size], reverse=True)

        # Add sizes from allowlist
        if self.options.header_size_allowlist:
            for size in self.options.header_size_allowlist:
                rounded_size = round(size)
                if rounded_size not in sizes and rounded_size > body_limit:
                    sizes.append(rounded_size)
            sizes = sorted(sizes, reverse=True)

        # Add bold and all-caps sizes as potential headers (but still respect font size ratio)
        min_header_size = body_limit * self.options.header_font_size_ratio
        if self.options.header_use_font_weight:
            for size in fontweight_sizes:
                if size not in sizes and size >= min_header_size:
                    sizes.append(size)
                    self.bold_header_sizes.add(size)

        if self.options.header_use_all_caps:
            for size in allcaps_sizes:
                if size not in sizes and size >= min_header_size:
                    sizes.append(size)
                    self.allcaps_header_sizes.add(size)

        sizes = sorted(set(sizes), reverse=True)

        # make the header tag dictionary
        for i, size in enumerate(sizes):
            level = min(i + 1, 6)  # Limit to h6
            # Store level information for later formatting
            self.header_id[size] = level

    def get_header_level(self, span: dict) -> int:
        """Return header level for a text span, or 0 if not a header.

        Analyzes the font size of a text span and returns the corresponding
        header level (1-6) or 0 if the span should be treated as body text.
        Includes content-based validation to reduce false positives.

        Parameters
        ----------
        span : dict
            Text span dictionary from PyMuPDF extraction containing 'size' key

        Returns
        -------
        int
            Header level (1-6) or 0 if not a header
        """
        fontsize = round(span["size"])  # compute fontsize
        level = self.header_id.get(fontsize, 0)

        # Check for additional header indicators if no size-based header found
        if not level and self.options:
            text = span.get("text", "").strip()

            # Check for bold header
            if self.options.header_use_font_weight and (span.get("flags", 0) & 16):
                if fontsize in self.bold_header_sizes:
                    level = self.header_id.get(fontsize, 0)

            # Check for all-caps header
            if self.options.header_use_all_caps and text.isupper() and text.isalpha():
                if fontsize in self.allcaps_header_sizes:
                    level = self.header_id.get(fontsize, 0)

        # Apply content-based validation if we detected a potential header
        if level > 0:
            text = span.get("text", "").strip()

            # Skip if text is too long to be a realistic header
            if len(text) > self.options.header_max_line_length:
                return 0

            # Skip if text is mostly whitespace or empty
            if not text or len(text.strip()) == 0:
                return 0

            # Skip if text looks like a paragraph (ends with typical sentence punctuation and is long)
            if len(text) > 50 and text.endswith(('.', '!', '?')):
                return 0

        return level


def _parse_pdf_date(date_str: str) -> str:
    """Parse PDF date format into a readable string.

    Parameters
    ----------
    date_str : str
        PDF date string (e.g., "D:20210315120000Z")

    Returns
    -------
    str
        Parsed date or original string if parsing fails
    """
    if not date_str or not date_str.startswith('D:'):
        return date_str

    try:
        from datetime import datetime
        # Remove D: prefix and parse
        clean_date = date_str[2:]
        if 'Z' in clean_date:
            clean_date = clean_date.replace('Z', '+0000')
        # Basic parsing - format is YYYYMMDDHHmmSS
        if len(clean_date) >= 8:
            year = int(clean_date[0:4])
            month = int(clean_date[4:6])
            day = int(clean_date[6:8])
            return datetime(year, month, day)
    except (ValueError, IndexError):
        pass
    return date_str


def extract_pdf_metadata(doc: "fitz.Document") -> DocumentMetadata:
    """Extract metadata from PDF document.

    Parameters
    ----------
    doc : fitz.Document
        PyMuPDF document object

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    # PyMuPDF provides metadata as a dictionary
    pdf_meta = doc.metadata if hasattr(doc, 'metadata') else {}

    if not pdf_meta:
        return DocumentMetadata()

    # Create custom handlers for PDF-specific field processing
    def handle_pdf_dates(meta_dict: dict[str, Any], field_names: list[str]) -> Any:
        """Handle PDF date fields with special parsing."""
        for field_name in field_names:
            if field_name in meta_dict:
                date_val = meta_dict[field_name]
                if date_val and str(date_val).strip():
                    return _parse_pdf_date(str(date_val).strip())
        return None

    # Custom field mapping for PDF dates
    pdf_mapping = PDF_FIELD_MAPPING.copy()
    pdf_mapping.update({
        'creation_date': ['creationDate', 'CreationDate'],
        'modification_date': ['modDate', 'ModDate'],
    })

    # Custom handlers for special fields
    custom_handlers = {
        'creation_date': handle_pdf_dates,
        'modification_date': handle_pdf_dates,
    }

    # Use the utility function for standard extraction
    metadata = extract_dict_metadata(pdf_meta, pdf_mapping)

    # Apply custom handlers for date fields
    for field_name, handler in custom_handlers.items():
        if field_name in pdf_mapping:
            value = handler(pdf_meta, pdf_mapping[field_name])
            if value:
                setattr(metadata, field_name, value)

    # Store any additional PDF-specific metadata in custom fields
    processed_keys = set()
    for field_names in pdf_mapping.values():
        if isinstance(field_names, list):
            processed_keys.update(field_names)
        else:
            processed_keys.add(field_names)

    # Skip internal PDF fields
    internal_fields = {'format', 'trapped', 'encryption'}

    for key, value in pdf_meta.items():
        if key not in processed_keys and key not in internal_fields:
            if value and str(value).strip():
                metadata.custom[key] = value

    return metadata


def _expand_page_separators(markdown: str, options: PdfOptions) -> str:
    """Expand PAGE_SEP markers with page separator template.

    Replaces HTML comment markers like <!-- PAGE_SEP:1/10 --> with the
    actual page separator template, expanding {page_num} and {total_pages} placeholders.

    Parameters
    ----------
    markdown : str
        Markdown text containing PAGE_SEP markers
    options : PdfOptions
        PDF options containing page_separator_template

    Returns
    -------
    str
        Markdown with expanded page separators

    """
    import re

    # Pattern to match <!-- PAGE_SEP:N/T -->
    pattern = r'<!-- PAGE_SEP:(\d+)/(\d+) -->'

    def replace_sep(match):
        page_num = match.group(1)
        total_pages = match.group(2)

        # Get template from options
        template = options.page_separator_template

        # Expand placeholders
        separator = template.replace("{page_num}", page_num)
        separator = separator.replace("{total_pages}", total_pages)

        # If include_page_numbers is True and template doesn't have placeholders,
        # append page numbers automatically
        if options.include_page_numbers and "{page_num}" not in template and "{total_pages}" not in template:
            separator = f"{separator}\nPage {page_num}/{total_pages}"

        return f"\n{separator}\n"

    return re.sub(pattern, replace_sep, markdown)


def pdf_to_markdown(input_data: Union[str, Path, IO[bytes], "fitz.Document"], options: PdfOptions | None = None) -> str:
    """Convert PDF document to Markdown format.

    This function processes PDF documents and converts them to well-formatted
    Markdown with support for headers, tables, links, and code blocks. It uses
    PyMuPDF's advanced table detection and preserves document structure.

    Parameters
    ----------
    input_data : str, Path, IO[bytes], or fitz.Document
        PDF document to convert. Can be:
        - String or Path to PDF file
        - Binary file object containing PDF data
        - Already opened PyMuPDF Document object
    options : PdfOptions or None, default None
        Configuration options for PDF conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown-formatted text content of the PDF document.

    Raises
    ------
    InputError
        If input type is not supported or page numbers are invalid
    PasswordProtectedError
        If PDF is password-protected and no/incorrect password provided
    MarkdownConversionError
        If document cannot be processed or PyMuPDF version is too old

    Notes
    -----
    - Tables may occasionally appear out of order compared to original layout
    - Complex tables can sometimes break into multiple separate tables
    - Headers are identified based on font size analysis
    - Code blocks are detected using monospace font analysis

    Examples
    --------
    Basic conversion:

        >>> markdown_text = pdf_to_markdown("document.pdf")

    Convert specific pages with base64 images:

        >>> from all2md.options import PdfOptions
        >>> options = PdfOptions(pages=[0, 1, 2])
        >>> content = pdf_to_markdown("document.pdf", options=options)

    Convert from file object with password:

        >>> from io import BytesIO
        >>> with open("encrypted.pdf", "rb") as f:
        ...     data = BytesIO(f.read())
        >>> options = PdfOptions(password="secret123")
        >>> content = pdf_to_markdown(data, options=options)
    """
    _check_pymupdf_version()

    import fitz

    # Handle backward compatibility and merge options
    if options is None:
        options = PdfOptions()

    # Validate and convert input
    doc_input, input_type = validate_and_convert_input(
        input_data, supported_types=["path-like", "file-like (BytesIO)", "fitz.Document objects"]
    )

    # Open document based on input type
    try:
        if input_type == "path":
            doc = fitz.open(filename=str(doc_input))
        elif input_type in ("file", "bytes"):
            # Handle different file-like object types
            if hasattr(doc_input, 'name') and hasattr(doc_input, 'read'):
                # For file objects that have a name attribute (like BufferedReader from open()),
                # use the filename approach which is more memory efficient
                doc = fitz.open(filename=doc_input.name)
            elif hasattr(doc_input, 'read'):
                # For file-like objects without name (like BytesIO), read the content
                doc = fitz.open(stream=doc_input.read(), filetype="pdf")
            else:
                # For bytes objects
                doc = fitz.open(stream=doc_input)
        elif input_type == "object":
            if isinstance(doc_input, fitz.Document) or (
                    hasattr(doc_input, "page_count") and hasattr(doc_input, "__getitem__")
            ):
                doc = doc_input
            else:
                raise InputError(
                    f"Expected fitz.Document object, got {type(doc_input).__name__}",
                    parameter_name="input_data",
                    parameter_value=doc_input,
                )
        else:
            raise InputError(
                f"Unsupported input type: {input_type}", parameter_name="input_data", parameter_value=doc_input
            )
    except Exception as e:
        if "password" in str(e).lower() or "encrypt" in str(e).lower():
            filename = str(input_data) if isinstance(input_data, (str, Path)) else None
            raise PasswordProtectedError(filename=filename) from e
        else:
            raise MarkdownConversionError(
                f"Failed to open PDF document: {str(e)}", conversion_stage="document_opening", original_error=e
            ) from e

    # Validate page range
    try:
        validated_pages = validate_page_range(options.pages, doc.page_count)
        pages_to_use: range | list[int] = validated_pages if validated_pages else range(doc.page_count)
    except Exception as e:
        raise InputError(
            f"Invalid page range: {str(e)}", parameter_name="pages", parameter_value=options.pages
        ) from e

    # Extract base filename for standardized attachment naming
    if input_type == "path" and isinstance(doc_input, (str, Path)):
        base_filename = Path(doc_input).stem
    else:
        # For non-file inputs, use a default name
        base_filename = "document"

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_pdf_metadata(doc)

    # Get Markdown options (create default if not provided)
    md_options = options.markdown_options or MarkdownOptions()

    # Create header identifier for font-based header detection
    hdr_identifier = IdentifyHeaders(doc, pages=pages_to_use if isinstance(pages_to_use, list) else None, options=options)

    # Create attachment sequencer for consistent filename generation
    attachment_sequencer = create_attachment_sequencer()

    # Use new AST-based conversion path
    from all2md.parsers.pdf import PdfToAstConverter
    from all2md.ast import MarkdownRenderer

    # Convert PDF to AST
    ast_converter = PdfToAstConverter(
        options=options,
        doc=doc,
        base_filename=base_filename,
        attachment_sequencer=attachment_sequencer,
        hdr_identifier=hdr_identifier,
    )
    ast_document = ast_converter.convert_to_ast(doc, pages_to_use)

    # Render AST to markdown using MarkdownOptions
    renderer = MarkdownRenderer(md_options)
    markdown = renderer.render(ast_document)

    # Post-process page separators: expand PAGE_SEP markers with template
    markdown = _expand_page_separators(markdown, options)

    # Prepend metadata if enabled
    markdown = prepend_metadata_if_enabled(markdown, metadata, options.extract_metadata)

    return markdown
