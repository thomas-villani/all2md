#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/pdf.py
"""PDF to AST converter.

This module provides conversion from PDF documents to AST representation.
It replaces direct markdown string generation with structured AST building,
enabling multiple rendering strategies and improved testability.

"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Callable, Optional, Union

from all2md.options.pdf import PdfOptions
from all2md.utils.attachments import create_attachment_sequencer
from all2md.utils.parser_helpers import attachment_result_to_image_node

if TYPE_CHECKING:
    import fitz

from dataclasses import dataclass, field

from all2md.ast import (
    Code,
    CodeBlock,
    Comment,
    Document,
    Emphasis,
    Heading,
    Link,
    List,
    ListItem,
    Node,
    SourceLocation,
    Strong,
    TableCell,
    TableRow,
    Text,
)
from all2md.ast import (
    Paragraph as AstParagraph,
)
from all2md.ast import (
    Table as AstTable,
)
from all2md.ast import (
    extract_text as extract_node_text,
)
from all2md.ast.transforms import InlineFormattingConsolidator, extract_nodes
from all2md.constants import (
    DEFAULT_OVERLAP_THRESHOLD_PX,
    DEPS_PDF,
    DEPS_PDF_LAYOUT,
    PDF_MIN_PYMUPDF_VERSION,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, MalformedFileError, PasswordProtectedError, ValidationError

# Import from private submodules
from all2md.parsers._pdf_columns import detect_columns
from all2md.parsers._pdf_headers import IdentifyHeaders, compute_line_style
from all2md.parsers._pdf_images import extract_page_images
from all2md.parsers._pdf_layout import (
    PageLayoutPredictions,
    annotate_blocks_with_layout,
    is_layout_available,
    match_predictions_to_blocks,
    native_find_tables,
    predict_page_layout,
)
from all2md.parsers._pdf_numbering import parse_numbering_prefix
from all2md.parsers._pdf_ocr import (
    dehyphenate_blocks,
    dehyphenate_text,
)
from all2md.parsers._pdf_ocr import (
    should_use_ocr as _should_use_ocr,
)
from all2md.parsers._pdf_tables import (
    MAX_DOT_LEADER_CELL_RATIO,
    MAX_TABLE_COLS,
    MAX_TABLE_EMPTY_RATIO,
    MAX_TABLE_ROWS,
    MIN_FILLED_FOR_UNIFORMITY_CHECK,
    MIN_TABLE_COLS,
    MIN_TABLE_ROWS,
    detect_tables_by_ruling_lines,
    is_dot_leader_cell,
    page_has_table_signals,
)
from all2md.parsers._pdf_text import (
    classify_line_rotation,
    collapse_whitespace_runs,
    extract_rotated_text,
    format_rotation_note,
    inline_has_text,
)
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.encoding import normalize_stream_to_bytes
from all2md.utils.inputs import validate_and_convert_input, validate_page_range
from all2md.utils.metadata import (
    PDF_FIELD_MAPPING,
    DocumentMetadata,
    extract_dict_metadata,
)

logger = logging.getLogger(__name__)

#: Fractions of the page height treated as the header and footer zones when
#: auto-detecting running furniture.
HEADER_ZONE_FRACTION = 0.2
FOOTER_ZONE_FRACTION = 0.8

#: Fewest pages that can show repetition. Two pages are enough: a block in the same
#: place on both has repeated. (Three used to be required, which silently disabled
#: ``auto_trim_headers_footers`` on every two-page document.)
MIN_PAGES_FOR_RUNNING_DETECTION = 2

#: How far, in points, a running header/footer may drift between pages and still count
#: as the same one. Real furniture is anchored to the page; body text that happens to
#: recur is anchored to the text flow and moves. The zone boundary is taken from the
#: innermost matching block, so a false positive trims everything outside it on every
#: page -- this tolerance is what keeps that aimed at furniture.
RUNNING_POSITION_TOLERANCE = 5.0

#: Runs of digits in a running header/footer, which differ from page to page precisely
#: because it is running furniture.
_RUNNING_DIGITS = re.compile(r"\d+")


def _running_text_key(text: str) -> str:
    """Key a header/footer candidate by what stays the same from page to page.

    ``Page 1 of 12`` and ``Page 2 of 12`` are the same running footer, but keying on
    raw text makes each of them unique, so neither ever reaches ``min_occurrences``
    and the footer is never detected. Collapsing digit runs is what lets the most
    common footer in existence -- one with a page number in it -- be recognized at all.
    """
    return _RUNNING_DIGITS.sub("#", text).strip()


def _collapse_text_whitespace_in_place(node: Node) -> None:
    """Collapse 2+ horizontal-whitespace runs in every Text descendant.

    Skips ``Code`` and ``CodeBlock`` content (whitespace-significant) and
    table cells (table layout uses its own spacing). Walks all other
    container nodes recursively, mutating Text.content in place.
    """
    if isinstance(node, (Code, CodeBlock)):
        return
    if isinstance(node, Text):
        node.content = collapse_whitespace_runs(node.content)
        return
    if isinstance(node, AstTable):
        # Tables are rendered with their own pipe-aligned spacing — leave
        # cell content alone so we don't collapse intentional padding.
        return
    children = getattr(node, "content", None)
    if isinstance(children, list):
        for child in children:
            _collapse_text_whitespace_in_place(child)
    block_children = getattr(node, "children", None)
    if isinstance(block_children, list):
        for child in block_children:
            _collapse_text_whitespace_in_place(child)


def _heading_text(heading: Heading) -> str:
    """Recursively extract plain text from a Heading's inline content."""
    parts: list[str] = []

    def _walk(nodes: list[Node]) -> None:
        for node in nodes:
            if isinstance(node, Text):
                parts.append(node.content)
            elif isinstance(node, Code):
                parts.append(node.content)
            elif isinstance(node, (Strong, Emphasis, Link)):
                _walk(node.content)

    _walk(heading.content)
    return "".join(parts).strip()


def _normalize_heading_for_dedup(text: str) -> str:
    """Normalize heading text for running-title comparison.

    Lowercases and collapses internal whitespace runs to single spaces so
    cosmetic differences (extra spaces from layout, capitalization changes
    between page templates) don't prevent matching.
    """
    return " ".join(text.lower().split())


def _demote_running_headings(doc: "Document", total_pages: int) -> int:
    """Convert headings that recur on >50% of pages into paragraphs.

    A real document section usually appears once. Headings that recur on
    page after page are almost always running titles, form-label headers,
    or per-page footers misclassified by the layout model. Convert them
    to paragraphs in place so downstream readers don't see fake section
    breaks.

    Returns
    -------
    int
        The number of heading nodes demoted (a structural-confidence signal).

    """
    if total_pages < 3:
        return 0

    # First pass: count distinct pages each normalized heading appears on.
    pages_per_heading: dict[str, set[int]] = {}
    for child in doc.children:
        if not isinstance(child, Heading):
            continue
        norm = _normalize_heading_for_dedup(_heading_text(child))
        if not norm:
            continue
        page = child.source_location.page if child.source_location else None
        pages_per_heading.setdefault(norm, set()).add(page if page is not None else 0)

    threshold = max(2, total_pages // 2 + 1)
    running_headings = {norm for norm, pages in pages_per_heading.items() if len(pages) >= threshold}
    if not running_headings:
        return 0

    # Second pass: rebuild children, demoting matched headings.
    demoted = 0
    new_children: list[Node] = []
    for child in doc.children:
        if isinstance(child, Heading):
            norm = _normalize_heading_for_dedup(_heading_text(child))
            if norm in running_headings:
                new_children.append(
                    AstParagraph(
                        content=child.content,
                        metadata=child.metadata.copy(),
                        source_location=child.source_location,
                    )
                )
                demoted += 1
                continue
        new_children.append(child)
    doc.children = new_children
    return demoted


def _strip_leading_whitespace_in_place(nodes: list[Node]) -> None:
    """Trim leading whitespace from the first Text-bearing leaf in ``nodes``.

    Walks through Strong/Emphasis/Link wrappers (since heading content is
    often a wrapped Text node like ``Strong([Text(' I.')])``). Leaves the
    rest of the content alone — only the very first Text leaf is touched,
    so a heading like ``" **I.** **Background**"`` becomes
    ``"**I.** **Background**"`` without disturbing internal spacing.
    """
    for node in nodes:
        if isinstance(node, Text):
            node.content = node.content.lstrip()
            if node.content:
                return
            # Empty after strip — keep walking to the next leaf.
            continue
        if isinstance(node, (Strong, Emphasis, Link)):
            if node.content:
                _strip_leading_whitespace_in_place(node.content)
                # Only stop walking if the wrapper now carries text.
                first_text = next(
                    (c for c in node.content if isinstance(c, Text) and c.content),
                    None,
                )
                if first_text is not None:
                    return
            continue
        if isinstance(node, Code):
            return  # Code preserves whitespace; don't trim.


def _trailing_text_is_whitespace(nodes: list[Node]) -> bool:
    """Return True if the last Text-bearing leaf in ``nodes`` ends with whitespace.

    Walks Strong/Emphasis/Link wrappers to find the actual Text content.
    Used to decide whether an inter-line separator space would create a
    redundant whitespace run.
    """
    for node in reversed(nodes):
        if isinstance(node, Text):
            return bool(node.content) and node.content[-1] in (" ", "\t")
        if isinstance(node, (Strong, Emphasis, Link)):
            if node.content and _trailing_text_is_whitespace(node.content):
                return True
            # Wrapper had no Text leaves — keep walking outward.
            continue
        if isinstance(node, Code):
            return False
    return False


@dataclass
class _BlockProcessingState:
    """State tracking for block-to-AST processing.

    This class encapsulates the mutable state used during block processing,
    reducing parameter passing and simplifying helper method signatures.

    """

    nodes: list[Node] = field(default_factory=list)
    in_code_block: bool = False
    code_block_lines: list[str] = field(default_factory=list)
    paragraph_content: list[Node] = field(default_factory=list)
    paragraph_bbox: tuple[float, float, float, float] | None = None
    paragraph_is_list: bool = False
    paragraph_list_type: str | None = None
    previous_y: float = 0.0
    pending_rotated_text: list[str] = field(default_factory=list)
    pending_rotated_key: str | None = None
    # A heading whose entire text is a numbering prefix (e.g. "I.", "1.1")
    # is buffered here rather than emitted immediately, so it can be merged
    # with the next heading line on the same block. Flushed as its own
    # heading on block end if no follow-up appears.
    pending_heading_prefix_content: list[Node] | None = None
    pending_heading_prefix_level: int = 0
    pending_heading_prefix_page: int = 0

    def reset_paragraph(self) -> None:
        """Reset paragraph accumulation state."""
        self.paragraph_content = []
        self.paragraph_bbox = None
        self.paragraph_is_list = False
        self.paragraph_list_type = None

    def reset_code_block(self) -> None:
        """Reset code block state."""
        self.in_code_block = False
        self.code_block_lines = []

    def reset_rotated(self) -> None:
        """Reset accumulated rotated-text run."""
        self.pending_rotated_text = []
        self.pending_rotated_key = None


def _check_pymupdf_version() -> None:
    """Check that PyMuPDF version meets minimum requirements.

    Raises
    ------
    DependencyError
        If PyMuPDF version is too old

    Notes
    -----
    This function assumes fitz is already imported. It should be called
    after dependency checking via the @requires_dependencies decorator.

    """
    import fitz

    min_version = tuple(map(int, PDF_MIN_PYMUPDF_VERSION.split(".")))
    if fitz.pymupdf_version_tuple < min_version:
        raise DependencyError(
            converter_name="pdf",
            missing_packages=[],
            version_mismatches=[("pymupdf", PDF_MIN_PYMUPDF_VERSION, ".".join(fitz.pymupdf_version_tuple))],
        )


# Note: Column detection, table detection, image extraction, header identification,
# OCR utilities, and text processing functions have been moved to private submodules:
# - _pdf_columns.py: detect_columns and helpers
# - _pdf_tables.py: detect_tables_by_ruling_lines and helpers
# - _pdf_images.py: extract_page_images, detect_image_caption
# - _pdf_headers.py: IdentifyHeaders class
# - _pdf_ocr.py: OCR decision logic and language detection
# - _pdf_text.py: handle_rotated_text, resolve_links


class PdfToAstConverter(BaseParser):
    """Convert PDF to AST representation.

    This converter parses PDF documents using PyMuPDF and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : PdfOptions or None, default = None
        Conversion options

    """

    def __init__(self, options: PdfOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the PDF parser with options and progress callback."""
        BaseParser._validate_options_type(options, PdfOptions, "pdf")
        options = options or PdfOptions()
        super().__init__(options, progress_callback)
        self.options: PdfOptions = options
        self._hdr_identifier: Optional[IdentifyHeaders] = None
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions
        self._ocr_pages_applied: int = 0  # pages OCR was applied to in the current parse
        self._use_layout: bool = False
        # Most recent heading level emitted (any path). Used by
        # `_handle_header_line_with_layout` to pick a sibling-or-deeper level
        # when the layout model says section-header but the font heuristic
        # has nothing to anchor against.
        self._last_heading_level: int = 0

    @requires_dependencies("pdf", DEPS_PDF)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse PDF document into AST.

        This method handles loading the PDF file and converting it to AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            PDF file to parse

        Returns
        -------
        Document
            AST document node

        """
        import fitz

        _check_pymupdf_version()

        # Determine if layout analysis should be used
        if self.options.layout_analysis_mode == "enabled":
            if not is_layout_available():
                raise DependencyError(
                    converter_name="pdf",
                    missing_packages=[(pkg, ver) for pkg, _, ver in DEPS_PDF_LAYOUT],
                )
            self._use_layout = True
        elif self.options.layout_analysis_mode == "auto":
            self._use_layout = is_layout_available()
            if self._use_layout:
                logger.debug("Layout analysis available, enabling automatic block classification")
        else:
            self._use_layout = False

        # Validate and convert input
        doc_input, input_type = validate_and_convert_input(
            input_data, supported_types=["path-like", "file-like (BytesIO)", "fitz.Document objects"]
        )

        # Open document based on input type
        try:
            if input_type == "path":
                doc = fitz.open(filename=str(doc_input))
            elif input_type in ("file", "bytes"):
                # PyMuPDF expects bytes, not file-like objects
                stream_bytes = normalize_stream_to_bytes(doc_input)
                doc = fitz.open(stream=stream_bytes, filetype="pdf")
            elif input_type == "object":
                if isinstance(doc_input, fitz.Document) or (
                    hasattr(doc_input, "page_count") and hasattr(doc_input, "__getitem__")
                ):
                    doc = doc_input
                else:
                    raise ValidationError(
                        f"Expected fitz.Document object, got {type(doc_input).__name__}",
                        parameter_name="input_data",
                        parameter_value=doc_input,
                    )
            else:
                raise ValidationError(
                    f"Unsupported input type: {input_type}", parameter_name="input_data", parameter_value=doc_input
                )
        except Exception as e:
            raise MalformedFileError(
                f"Failed to open PDF document: {e!r}",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=e,
            ) from e

        # Handle password-protected PDFs using PyMuPDF's authentication API
        if doc.is_encrypted:
            filename = str(input_data) if isinstance(input_data, (str, Path)) else None
            if self.options.password:
                # Attempt authentication with provided password
                auth_result = doc.authenticate(self.options.password)
                if auth_result == 0:
                    # Authentication failed (return code 0)
                    raise PasswordProtectedError(
                        message=(
                            "Failed to authenticate PDF with provided password. Please check the password is correct."
                        ),
                        filename=filename,
                    )
                # auth_result > 0 indicates successful authentication
                # (1=no passwords, 2=user password, 4=owner password, 6=both equal)
            else:
                # Document is encrypted but no password provided
                raise PasswordProtectedError(
                    message=(
                        "PDF document is password-protected. Please provide a password using the 'password' option."
                    ),
                    filename=filename,
                )

        # Validate page range
        try:
            validated_pages = validate_page_range(self.options.pages, doc.page_count)
            pages_to_use: range | list[int] = validated_pages if validated_pages else range(doc.page_count)
        except Exception as e:
            raise ValidationError(
                f"Invalid page range: {str(e)}", parameter_name="pdf.pages", parameter_value=self.options.pages
            ) from e

        # Extract base filename for standardized attachment naming
        if input_type == "path" and isinstance(doc_input, (str, Path)):
            base_filename = Path(doc_input).stem
        else:
            # For non-file inputs, use a default name
            base_filename = "document"

        self._hdr_identifier = IdentifyHeaders(
            doc, pages=pages_to_use if isinstance(pages_to_use, list) else None, options=self.options
        )
        self._last_heading_level = 0

        # Auto-detect header/footer zones if requested
        if self.options.auto_trim_headers_footers:
            self._auto_detect_header_footer_zones(doc, pages_to_use)

        return self.convert_to_ast(doc, pages_to_use, base_filename)

    def _get_sample_pages(self, pages_to_use: range | list[int]) -> list[int] | None:
        """Get evenly distributed sample pages for header/footer detection.

        Two pages are enough. Repetition is the entire signal, and a block that appears
        at the same position on both pages of a two-page document has already repeated;
        ``min_occurrences`` still requires it on every sampled page. The previous floor
        of three made ``auto_trim_headers_footers`` a silent no-op on two-page documents.
        """
        total_pages = len(list(pages_to_use))
        if total_pages < MIN_PAGES_FOR_RUNNING_DETECTION:
            return None  # A single page cannot show repetition.

        sample_size = min(10, total_pages)
        if isinstance(pages_to_use, range):
            step = max(1, total_pages // sample_size)
            return [pages_to_use.start + i * step for i in range(sample_size)]
        step = max(1, len(pages_to_use) // sample_size)
        return [pages_to_use[i * step] for i in range(sample_size)]

    def _extract_block_text(self, block: dict) -> str | None:
        """Extract text from a block dictionary. Returns None if no valid text."""
        if block.get("type") != 0:
            return None
        if not block.get("bbox"):
            return None

        text_lines = []
        for line in block.get("lines", []):
            line_text = " ".join(span["text"] for span in line.get("spans", []))
            text_lines.append(line_text.strip())

        block_text = " ".join(text_lines).strip()
        return block_text if block_text else None

    def _collect_page_blocks(
        self, doc: "fitz.Document", sample_pages: list[int]
    ) -> dict[int, list[tuple[str, float, float]]]:
        """Collect text blocks with positions from sampled pages."""
        import fitz

        page_blocks: dict[int, list[tuple[str, float, float]]] = {}

        for page_num in sample_pages:
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            page_blocks[page_num] = []

            for block in blocks:
                block_text = self._extract_block_text(block)
                if block_text:
                    bbox = block["bbox"]
                    page_blocks[page_num].append((block_text, bbox[1], bbox[3]))

        return page_blocks

    def _classify_header_footer_candidates(
        self, page_blocks: dict[int, list[tuple[str, float, float]]], page_height: float
    ) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
        """Classify blocks into header/footer candidates based on position.

        Candidates are keyed on their text with digit runs collapsed (see
        :func:`_running_text_key`), so ``Page 1 of 12`` and ``Page 2 of 12`` are
        recognized as the same running footer rather than as two unrelated blocks.
        """
        header_candidates: dict[str, list[float]] = {}
        footer_candidates: dict[str, list[float]] = {}

        header_zone_threshold = page_height * HEADER_ZONE_FRACTION
        footer_zone_threshold = page_height * FOOTER_ZONE_FRACTION

        for blocks in page_blocks.values():
            for text, y_top, y_bottom in blocks:
                key = _running_text_key(text)
                if y_bottom < header_zone_threshold:
                    header_candidates.setdefault(key, []).append(y_bottom)
                if y_top > footer_zone_threshold:
                    footer_candidates.setdefault(key, []).append(y_top)

        return header_candidates, footer_candidates

    def _find_repeating_zone_boundaries(
        self,
        header_candidates: dict[str, list[float]],
        footer_candidates: dict[str, list[float]],
        page_height: float,
        min_occurrences: int,
    ) -> tuple[float, float]:
        """Find boundaries of repeating header/footer zones.

        A candidate must repeat *and hold still*. The zone boundary is taken from the
        innermost matching block, so a single false positive does not just drop its own
        line -- it drops everything outside it, on every page. Requiring the block to
        occupy the same vertical position on each page (within
        :data:`RUNNING_POSITION_TOLERANCE`) is what keeps that blast radius aimed at
        real furniture: a running head is anchored to the page, whereas a heading that
        merely recurs sits wherever the text flow leaves it.
        """
        max_header_y = 0.0
        max_footer_y = page_height

        def anchored(y_values: list[float]) -> bool:
            return len(y_values) >= min_occurrences and max(y_values) - min(y_values) <= RUNNING_POSITION_TOLERANCE

        for y_values in header_candidates.values():
            if anchored(y_values):
                max_header_y = max(max_header_y, max(y_values))

        for y_values in footer_candidates.values():
            if anchored(y_values):
                max_footer_y = min(max_footer_y, min(y_values))

        return max_header_y, max_footer_y

    def _auto_detect_header_footer_zones(self, doc: "fitz.Document", pages_to_use: range | list[int]) -> None:
        """Automatically detect and set header/footer zones by analyzing repeating text patterns.

        This method analyzes text blocks across multiple pages to identify repeating
        headers and footers. It looks for text that appears in similar vertical positions
        across multiple pages and calculates appropriate header_height and footer_height
        values to exclude them from conversion.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to analyze
        pages_to_use : range or list[int]
            Pages to process (used to determine sample range)

        """
        sample_pages = self._get_sample_pages(pages_to_use)
        if not sample_pages:
            return

        page_blocks = self._collect_page_blocks(doc, sample_pages)
        if not page_blocks:
            return

        page_height = doc[sample_pages[0]].rect.height
        header_candidates, footer_candidates = self._classify_header_footer_candidates(page_blocks, page_height)

        min_occurrences = max(2, len(sample_pages) // 2)
        max_header_y, max_footer_y = self._find_repeating_zone_boundaries(
            header_candidates, footer_candidates, page_height, min_occurrences
        )

        # Set header_height and footer_height if we found repeating patterns
        if max_header_y > 0:
            self.options = self.options.create_updated(header_height=int(max_header_y + 5), trim_headers_footers=True)

        if max_footer_y < page_height:
            footer_height_value = int(page_height - max_footer_y + 5)
            self.options = self.options.create_updated(footer_height=footer_height_value, trim_headers_footers=True)

    def extract_metadata(self, document: "fitz.Document") -> DocumentMetadata:
        """Extract metadata from PDF document.

        Extracts standard metadata fields from a PDF document including title,
        author, subject, keywords, creation date, modification date, and creator
        application information. Also preserves any custom metadata fields that
        are not part of the standard set.

        Parameters
        ----------
        document : fitz.Document
            PyMuPDF document object to extract metadata from

        Returns
        -------
        DocumentMetadata
            Extracted metadata including standard fields (title, author, dates, etc.)
            and any custom fields found in the PDF. Returns empty DocumentMetadata
            if no metadata is available.

        Notes
        -----
        - PDF date strings in format 'D:YYYYMMDDHHmmSS' are parsed into datetime objects
        - Empty or whitespace-only metadata values are ignored
        - Internal PDF fields (format, trapped, encryption) are excluded
        - Unknown metadata fields are stored in the custom dictionary

        """
        # PyMuPDF provides metadata as a dictionary
        pdf_meta = document.metadata if hasattr(document, "metadata") else {}

        if not pdf_meta:
            return DocumentMetadata()

        # Create custom handlers for PDF-specific field processing
        def handle_pdf_dates(meta_dict: dict[str, Any], field_names: list[str]) -> Any:
            """Handle PDF date fields with special parsing."""
            for field_name in field_names:
                if field_name in meta_dict:
                    date_val = meta_dict[field_name]
                    if date_val and str(date_val).strip():
                        return self._parse_pdf_date(str(date_val).strip())
            return None

        # Custom field mapping for PDF dates
        pdf_mapping = PDF_FIELD_MAPPING.copy()
        pdf_mapping.update(
            {
                "creation_date": ["creationDate", "CreationDate"],
                "modification_date": ["modDate", "ModDate"],
            }
        )

        # Custom handlers for special fields
        custom_handlers = {
            "creation_date": handle_pdf_dates,
            "modification_date": handle_pdf_dates,
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
                processed_keys.add(field_names)  # type: ignore[unreachable]

        # Skip internal PDF fields
        internal_fields = {"format", "trapped", "encryption"}

        for key, value in pdf_meta.items():
            if key not in processed_keys and key not in internal_fields:
                if value and str(value).strip():
                    metadata.custom[key] = value

        return metadata

    def _parse_pdf_date(self, date_str: str) -> str:
        """Parse PDF date format into a readable string.

        Converts PDF date strings from the internal format 'D:YYYYMMDDHHmmSS'
        into datetime objects for standardized date handling.

        Parameters
        ----------
        date_str : str
            PDF date string in format 'D:YYYYMMDDHHmmSS' with optional timezone

        Returns
        -------
        str
            Parsed datetime object or original string if parsing fails

        Notes
        -----
        Handles both UTC (Z suffix) and timezone offset formats.
        Returns original string if format is unrecognized.

        """
        if not date_str or not date_str.startswith("D:"):
            return date_str

        try:
            # Remove D: prefix and parse
            clean_date = date_str[2:]
            if "Z" in clean_date:
                clean_date = clean_date.replace("Z", "+0000")
            # Basic parsing - format is YYYYMMDDHHmmSS
            if len(clean_date) >= 8:
                year = int(clean_date[0:4])
                month = int(clean_date[4:6])
                day = int(clean_date[6:8])

                # Validate date ranges before passing to datetime
                if not (1000 <= year <= 9999):
                    logger.debug(f"Invalid year in PDF date: {year}")
                    return date_str
                if not (1 <= month <= 12):
                    logger.debug(f"Invalid month in PDF date: {month}")
                    return date_str
                if not (1 <= day <= 31):
                    logger.debug(f"Invalid day in PDF date: {day}")
                    return date_str

                return datetime(year, month, day).isoformat()
        except (ValueError, IndexError):
            pass
        return date_str

    def convert_to_ast(self, doc: "fitz.Document", pages_to_use: range | list[int], base_filename: str) -> Document:
        """Convert PDF document to AST Document.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to convert
        pages_to_use : range or list of int
            Pages to process
        base_filename : str
            Base filename for attachments

        Returns
        -------
        Document
            AST document node

        """
        # Reset footnote collection for this conversion
        self._attachment_footnotes = {}
        # Count pages OCR was applied to this conversion (drives the doc-level
        # OCR safety net below).
        self._ocr_pages_applied = 0
        # Reset per-conversion confidence collectors (degraded events accumulate
        # via _record_degraded; _tables_rejected feeds the quality-card signals).
        self._degraded_events: list[Any] = []
        self._quality_signals: dict[str, Any] = {}
        self._tables_rejected = 0

        total_pages = len(list(pages_to_use))

        # Emit started event
        self._emit_progress(
            "started",
            f"Converting PDF with {total_pages} page{'s' if total_pages != 1 else ''}",
            current=0,
            total=total_pages,
        )

        attachment_sequencer = create_attachment_sequencer()

        pages_list = list(pages_to_use)
        children = self._render_pages(doc, pages_list, base_filename, attachment_sequencer, total_pages)

        # Document-level OCR safety net: when nothing triggered OCR in auto mode
        # yet the rendered document is essentially empty, the per-page heuristic
        # likely missed a scanned/image-only PDF — retry once with OCR forced.
        children = self._maybe_retry_with_ocr(doc, pages_list, base_filename, total_pages, children)

        # Extract and attach metadata
        metadata = self.extract_metadata(doc)

        # Attach header detection debug info if enabled
        if self.options.header_debug_output and self._hdr_identifier:
            debug_info = self._hdr_identifier.get_debug_info()
            if debug_info:
                metadata.custom["pdf_header_debug"] = debug_info
                logger.debug("Attached PDF header detection debug info to document metadata")

        # Append footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        # Emit finished event
        self._emit_progress(
            "finished",
            f"PDF conversion completed ({total_pages} page{'s' if total_pages != 1 else ''})",
            current=total_pages,
            total=total_pages,
        )

        # Build the document
        ast_doc = Document(children=children, metadata=metadata.to_dict())

        # Apply inline formatting consolidation if enabled
        if self.options.consolidate_inline_formatting:
            consolidator = InlineFormattingConsolidator()
            consolidated = consolidator.transform(ast_doc)
            if isinstance(consolidated, Document):
                ast_doc = consolidated

        # Collapse whitespace runs that the consolidator may have produced when
        # it merged adjacent Text nodes carrying span-boundary spaces. Runs at
        # span level were already collapsed in `_process_text_spans_to_inline`,
        # but text-merging during consolidation can re-introduce them.
        if self.options.collapse_excess_whitespace:
            _collapse_text_whitespace_in_place(ast_doc)

        # Demote headings that recur on more than half the document pages —
        # those are running titles or per-page form labels masquerading as
        # section headings, not real document structure.
        headings_demoted = 0
        if self.options.dedup_running_headings and total_pages >= 3:
            headings_demoted = _demote_running_headings(ast_doc, total_pages)

        self._record_pdf_quality_signals(ast_doc, total_pages, headings_demoted)

        return ast_doc

    def _record_pdf_quality_signals(self, ast_doc: Document, total_pages: int, headings_demoted: int) -> None:
        """Populate the confidence-report signals from the finished PDF conversion.

        Derives the reference-free quality metrics — meaningful-text density,
        OCR reliance, and detected/rejected table counts — that feed the
        conversion :class:`~all2md.confidence.ConfidenceReport` assembled in
        ``to_ast``. ``chars_per_page`` is the primary text-density signal (a
        near-empty scanned page yields a low value); ``ocr_page_fraction``
        captures how much of the document leaned on OCR.
        """
        meaningful_chars = self._count_meaningful_chars(ast_doc.children)
        pages = max(1, total_pages)
        tables_emitted = sum(1 for _ in extract_nodes(ast_doc, AstTable))
        tables_rejected = getattr(self, "_tables_rejected", 0)

        self._set_quality_signal("page_count", total_pages)
        self._set_quality_signal("meaningful_chars", meaningful_chars)
        self._set_quality_signal("chars_per_page", round(meaningful_chars / pages, 1))
        self._set_quality_signal("ocr_page_fraction", round(self._ocr_pages_applied / pages, 3))
        self._set_quality_signal("tables_detected", tables_emitted + tables_rejected)
        self._set_quality_signal("tables_emitted", tables_emitted)
        self._set_quality_signal("tables_rejected", tables_rejected)
        self._set_quality_signal("running_headings_demoted", headings_demoted)

    def _render_pages(
        self,
        doc: "fitz.Document",
        pages_list: list[int],
        base_filename: str,
        attachment_sequencer: Any,
        total_pages: int,
    ) -> list[Node]:
        """Process each page to AST nodes, inserting page separators between pages.

        Extracted from ``parse`` so the document-level OCR safety net can re-run
        the whole page loop with OCR forced.
        """
        children: list[Node] = []
        # Suppress pymupdf-layout's global find_tables() hook for the whole
        # page loop. We call predict_page_layout() explicitly inside
        # _process_page_to_ast and merge its predictions ourselves; the
        # implicit hook would additionally reroute find_tables()/Table.extract()
        # through the layout model, overdetecting tables and garbling cell text.
        # See native_find_tables() for the full rationale.
        with native_find_tables():
            for idx, pno in enumerate(pages_list):
                try:
                    page = doc[pno]
                    page_nodes = self._process_page_to_ast(page, pno, base_filename, attachment_sequencer, total_pages)
                    if page_nodes:
                        children.extend(page_nodes)

                    # Add page separator between pages (but not after the last page)
                    if idx < len(pages_list) - 1 and self.options.include_page_numbers:
                        # Add page separator as Comment node - renderers decide whether to display it
                        # Format using page_separator_template with placeholders
                        separator_text = self.options.page_separator_template.format(
                            page_num=pno + 1, total_pages=total_pages
                        )
                        children.append(Comment(content=separator_text, metadata={"comment_type": "page_separator"}))

                    # Emit page done event
                    self._emit_progress(
                        "item_done",
                        f"Page {pno + 1} of {total_pages} processed",
                        current=idx + 1,
                        total=total_pages,
                        item_type="page",
                        page=pno + 1,
                    )
                except Exception as e:
                    # Emit error event but continue processing
                    self._emit_progress(
                        "error",
                        f"Error processing page {pno + 1}: {str(e)}",
                        current=idx + 1,
                        total=total_pages,
                        error=str(e),
                        stage="page_processing",
                        page=pno + 1,
                    )
                    # Re-raise to maintain existing error handling
                    raise
        return children

    @staticmethod
    def _count_meaningful_chars(children: list[Node]) -> int:
        """Count alphanumeric characters across content nodes (ignoring separators)."""
        content_nodes = [n for n in children if not isinstance(n, Comment)]
        text = extract_node_text(content_nodes, joiner="")
        return sum(1 for char in text if char.isalnum())

    def _record_table_rejection(self, reason: str) -> None:
        """Note a detected "table" discarded as non-tabular (empty frame, TOC, ...).

        Bumps the rejection counter used for the ``tables_rejected`` confidence
        signal and records a degraded-content event carrying the reason, so the
        quality card reflects structure the converter chose to drop.
        """
        self._tables_rejected = getattr(self, "_tables_rejected", 0) + 1
        self._record_degraded("table_rejected", detail=reason, severity="warn")

    def _maybe_retry_with_ocr(
        self,
        doc: "fitz.Document",
        pages_list: list[int],
        base_filename: str,
        total_pages: int,
        children: list[Node],
    ) -> list[Node]:
        """Re-run page rendering with OCR forced if an auto-mode doc came out empty.

        Returns the original ``children`` unless a forced-OCR retry produced
        strictly more text. When OCR is unavailable/disabled, emits a one-line
        hint instead of retrying.
        """
        ocr_opts = self.options.ocr
        meaningful = self._count_meaningful_chars(children)
        if meaningful >= ocr_opts.doc_text_threshold:
            return children

        # Already near-empty. Can we recover with OCR?
        can_auto_ocr = ocr_opts.enabled and ocr_opts.mode == "auto" and self._ocr_pages_applied == 0
        if not can_auto_ocr:
            if not ocr_opts.enabled or ocr_opts.mode == "off":
                logger.warning(
                    "PDF produced almost no text (%d meaningful chars) and OCR is disabled. "
                    "Re-run with --pdf-ocr-enabled --pdf-ocr-mode force (and install OCR extras, "
                    "e.g. `pip install all2md[ocr]`) to extract scanned content.",
                    meaningful,
                )
            return children

        logger.info(
            "Document produced almost no text (%d meaningful chars) under auto OCR; retrying with OCR forced.",
            meaningful,
        )
        forced_options = self.options.create_updated(ocr=ocr_opts.create_updated(mode="force"))
        original_options = self.options
        self.options = forced_options
        try:
            retry_children = self._render_pages(
                doc, pages_list, base_filename, create_attachment_sequencer(), total_pages
            )
        except Exception as e:  # noqa: BLE001 - retry is best-effort; keep the original result
            logger.warning("Forced-OCR retry failed: %s. Keeping original extraction.", e)
            return children
        finally:
            self.options = original_options

        if self._count_meaningful_chars(retry_children) > meaningful:
            return retry_children
        return children

    @staticmethod
    def _ocr_page_to_text(page: "fitz.Page", options: PdfOptions) -> str:
        """Extract text from a PDF page using OCR (Optical Character Recognition).

        Renders the page to an image at the configured DPI and hands it to the
        OCR backend selected by ``options.ocr.engine`` ("tesseract" or
        "easyocr"). Rendering needs only PyMuPDF; the per-engine Python
        dependencies are checked inside the engine adapters.

        Parameters
        ----------
        page : fitz.Page
            PDF page to extract text from
        options : PdfOptions
            PDF conversion options containing OCR settings

        Returns
        -------
        str
            Text extracted via OCR (empty string on failure)

        Raises
        ------
        DependencyError
            If the selected engine's Python packages are not installed
        RuntimeError
            If the Tesseract binary is missing, or EasyOCR cannot initialize

        """
        import fitz

        from all2md.parsers._ocr import ocr_pixmap

        # Render page to image (pixmap) at the configured DPI. DPI is applied via
        # the zoom matrix (DPI/72 = zoom factor).
        zoom = options.ocr.dpi / 72.0

        # Initialize pixmap reference for proper cleanup in finally block
        pix = None
        try:
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            return ocr_pixmap(pix, page, options)
        finally:
            # Clean up pixmap resources to prevent memory leaks
            # This is critical for long-running OCR operations
            if pix is not None:
                pix = None

    def _detect_page_tables(
        self, page: "fitz.Page", page_num: int, total_pages: int
    ) -> tuple[list[dict], list[Any], list[Any]]:
        """Detect tables on a PDF page.

        Parameters
        ----------
        page : fitz.Page
            PDF page to analyze
        page_num : int
            Page number (0-based)
        total_pages : int
            Total number of pages

        Returns
        -------
        tuple
            (table_info, fallback_table_rects, fallback_table_lines)

        """
        import fitz

        mode = self.options.table_detection_mode.lower()

        class EmptyTables:
            tables: list[Any] = []

            def __getitem__(self, index: int) -> Any:
                return self.tables[index]

        fallback_table_rects: list[Any] = []
        fallback_table_lines: list[Any] = []
        tabs = None

        if mode == "none":
            tabs = EmptyTables()
        elif mode == "pymupdf":
            tabs = page.find_tables()
        elif mode == "ruling":
            fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                page, self.options.table_ruling_line_threshold
            )
            tabs = EmptyTables()
        else:
            # Default ("both"): gate ``find_tables()`` behind a cheap drawings
            # scan. On prose-only pages ``find_tables()`` does ~1s of wasted
            # work per page and either returns nothing useful or fires on
            # decorative frames that our guards then have to reject. Skip it
            # when there's no ruling-line evidence; the ruling-line fallback
            # would also find nothing on those pages.
            if page_has_table_signals(page):
                tabs = page.find_tables()
                if self.options.enable_table_fallback_detection and not tabs.tables:
                    fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                        page, self.options.table_ruling_line_threshold
                    )
            else:
                tabs = EmptyTables()

        # Build table info list
        table_info = []
        for i, t in enumerate(tabs.tables):
            try:
                bbox = fitz.Rect(t.bbox) | fitz.Rect(t.header.bbox)
            except ValueError:
                # PyMuPDF may detect a table structure with no cells,
                # causing t.bbox to fail with "min() iterable argument is empty".
                # Skip these empty tables.
                continue
            table_info.append({"bbox": bbox, "idx": i, "type": "pymupdf", "table_obj": t})
        for i, rect in enumerate(fallback_table_rects):
            table_info.append({"bbox": rect, "idx": i, "type": "fallback", "lines": fallback_table_lines[i]})

        # Emit progress event if tables found
        total_table_count = len(table_info)
        if total_table_count > 0:
            self._emit_progress(
                "detected",
                f"Found {total_table_count} table{'s' if total_table_count != 1 else ''} on page {page_num + 1}",
                current=page_num + 1,
                total=total_pages,
                detected_type="table",
                table_count=total_table_count,
                page=page_num + 1,
            )

        return table_info, fallback_table_rects, fallback_table_lines

    def _apply_ocr_if_needed(
        self, page: "fitz.Page", all_blocks: list[dict], extracted_text: str
    ) -> tuple[list[dict], bool]:
        """Apply OCR to page if needed based on options and content.

        Parameters
        ----------
        page : fitz.Page
            PDF page
        all_blocks : list of dict
            Extracted text blocks
        extracted_text : str
            Extracted plain text from blocks

        Returns
        -------
        tuple of (list of dict, bool)
            Updated blocks (may include OCR-generated blocks) and whether OCR was applied.

        """
        use_ocr = _should_use_ocr(page, extracted_text, self.options)

        if not use_ocr:
            return all_blocks, False

        try:
            ocr_text = self._ocr_page_to_text(page, self.options)

            if not ocr_text.strip():
                logger.warning("OCR returned empty text, keeping original extraction")
                return all_blocks, False

            # OCR returns a flat string rather than the span structure
            # dehyphenate_blocks() walks, so line-break hyphenation ("be-\nwusst")
            # is merged here on the text instead. Same rules, same option.
            if self.options.merge_hyphenated_words:
                ocr_text = dehyphenate_text(ocr_text)

            # Handle preserve_existing_text option
            if self.options.ocr.preserve_existing_text and extracted_text.strip():
                logger.debug(
                    f"Supplementing existing text ({len(extracted_text)} chars) with OCR ({len(ocr_text)} chars)"
                )
                # Add OCR as additional block
                ocr_block = {
                    "type": 0,
                    "bbox": page.rect,
                    "lines": [
                        {
                            "spans": [{"text": ocr_text, "font": "OCR", "size": 11, "flags": 0, "color": 0}],
                            "bbox": page.rect,
                            "dir": (1, 0),  # Horizontal text direction
                        }
                    ],
                }
                all_blocks.append(ocr_block)
                self._ocr_pages_applied += 1
                return all_blocks, True
            else:
                logger.debug(f"Replacing PyMuPDF text ({len(extracted_text)} chars) with OCR ({len(ocr_text)} chars)")
                # Replace with OCR block
                self._ocr_pages_applied += 1
                return [
                    {
                        "type": 0,
                        "bbox": page.rect,
                        "lines": [
                            {
                                "spans": [{"text": ocr_text, "font": "OCR", "size": 11, "flags": 0, "color": 0}],
                                "bbox": page.rect,
                                "dir": (1, 0),  # Horizontal text direction
                            }
                        ],
                    }
                ], True

        except Exception as e:
            logger.warning(f"OCR processing failed: {e}. Falling back to standard text extraction.")
            return all_blocks, False

    def _assign_tables_to_columns(self, table_info: list[dict], columns: list[list[dict]]) -> None:
        """Assign each table to a column based on x-coordinate.

        Parameters
        ----------
        table_info : list of dict
            Table information with bbox
        columns : list of list of dict
            Column blocks

        """
        for table in table_info:
            table_center_x = (table["bbox"].x0 + table["bbox"].x1) / 2
            table["column"] = 0  # Default to first column

            for col_idx, column in enumerate(columns):
                if column:
                    col_x_values = [b["bbox"][0] for b in column if "bbox" in b]
                    if col_x_values:
                        col_min_x = min(col_x_values)
                        col_max_x = max(b["bbox"][2] for b in column if "bbox" in b)
                        if col_min_x <= table_center_x <= col_max_x:
                            table["column"] = col_idx
                            break

    def _calculate_average_line_height(self, columns: list[list[dict]]) -> float | None:
        """Calculate average line height across all columns.

        Parameters
        ----------
        columns : list of list of dict
            Text block columns

        Returns
        -------
        float or None
            Average line height, or None if no valid lines found

        """
        line_heights = []
        for column in columns:
            for block in column:
                for line in block.get("lines", []):
                    if "bbox" in line:
                        line_height = line["bbox"][3] - line["bbox"][1]
                        if line_height > 0:
                            line_heights.append(line_height)
        return sum(line_heights) / len(line_heights) if line_heights else None

    def _build_sorted_column_items(self, column: list[dict], col_tables: list[dict]) -> list[tuple[str, float, Any]]:
        """Build a sorted list of blocks and tables for a column.

        Parameters
        ----------
        column : list of dict
            Text blocks in the column
        col_tables : list of dict
            Tables assigned to this column

        Returns
        -------
        list of tuple
            Sorted list of (item_type, y_coord, item_data) tuples

        """
        items: list[tuple[str, float, Any]] = []
        for block in column:
            if "bbox" in block:
                items.append(("block", block["bbox"][1], block))
        for table in col_tables:
            items.append(("table", table["bbox"].y0, table))
        items.sort(key=lambda x: x[1])
        return items

    def _process_table_item(self, item_data: dict, page: "fitz.Page", page_num: int) -> Node | None:
        """Process a single table item and return its AST node.

        Parameters
        ----------
        item_data : dict
            Table information dictionary
        page : fitz.Page
            PDF page
        page_num : int
            Page number

        Returns
        -------
        Node or None
            Table AST node, or None if processing failed

        """
        if item_data["type"] == "pymupdf":
            return self._process_table_to_ast(item_data["table_obj"], page, page_num)
        elif item_data["type"] == "fallback":
            h_lines, v_lines = item_data["lines"]
            return self._extract_table_from_ruling_rect(page, item_data["bbox"], h_lines, v_lines, page_num)
        elif item_data["type"] == "layout":
            # Layout-detected table: extract text from the predicted region
            return self._extract_table_from_layout_region(page, item_data["bbox"], page_num)
        return None

    def _get_page_links(self, page: "fitz.Page") -> list:
        """Extract URI links from a page.

        Parameters
        ----------
        page : fitz.Page
            PDF page

        Returns
        -------
        list
            List of URI link dictionaries

        """
        try:
            return [link for link in page.get_links() if link["kind"] == 2]
        except (AttributeError, Exception):
            return []

    def _process_columns_and_tables(
        self,
        columns: list[list[dict]],
        table_info: list[dict],
        page: "fitz.Page",
        page_num: int,
        page_images: list[Any],
    ) -> list[Node]:
        """Process columns with tables inserted at correct positions.

        Parameters
        ----------
        columns : list of list of dict
            Text block columns
        table_info : list of dict
            Table information
        page : fitz.Page
            PDF page
        page_num : int
            Page number
        page_images : list
            Extracted images for the page

        Returns
        -------
        list of Node
            Processed AST nodes

        """
        nodes: list[Node] = []
        average_line_height = self._calculate_average_line_height(columns)
        links = self._get_page_links(page)

        # Process each column
        for col_idx, column in enumerate(columns):
            col_tables = [t for t in table_info if t["column"] == col_idx]
            items = self._build_sorted_column_items(column, col_tables)

            for item_type, _y, item_data in items:
                if item_type == "block":
                    block_nodes = self._process_single_block_to_ast(item_data, links, page_num, average_line_height)
                    nodes.extend(block_nodes)
                elif item_type == "table":
                    table_node = self._process_table_item(item_data, page, page_num)
                    if table_node:
                        nodes.append(table_node)

        # Post-processing
        nodes = self._merge_rotated_paragraphs(nodes)
        nodes = self._merge_adjacent_paragraphs(nodes)
        nodes = self._convert_paragraphs_to_lists(nodes)

        # Add images if placement markers enabled
        if page_images and self.options.image_placement_markers:
            for img in page_images:
                img_node = self._create_image_node(img, page_num)
                if img_node:
                    nodes.append(img_node)

        return nodes

    def _process_page_to_ast(
        self,
        page: "fitz.Page",
        page_num: int,
        base_filename: str,
        attachment_sequencer: Callable[[str, str], tuple[str, int]],
        total_pages: int = 0,
    ) -> list[Node]:
        """Process a PDF page to AST nodes.

        Parameters
        ----------
        page : fitz.Page
            PDF page to process
        page_num : int
            Page number (0-based)
        base_filename : str
            Base filename for attachments
        attachment_sequencer : Callable
            Sequencer for generating unique attachment names
        total_pages : int, default=0
            Total number of pages being processed

        Returns
        -------
        list of Node
            List of AST nodes representing the page

        """
        import fitz

        # Detect tables on the page
        table_info, _, _ = self._detect_page_tables(page, page_num, total_pages)

        # Extract all text blocks from the page
        try:
            all_blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT, sort=False)["blocks"]
            if self.options.merge_hyphenated_words:
                dehyphenate_blocks(all_blocks)
        except (AttributeError, KeyError, Exception):
            return []

        # Run layout analysis if enabled (before any filtering so indices match).
        # Done before image extraction so that page-header / page-footer regions
        # can be used to filter out repeating decorative images.
        layout: PageLayoutPredictions | None = None
        if self._use_layout:
            try:
                raw_predictions = predict_page_layout(page)
                layout = match_predictions_to_blocks(raw_predictions, all_blocks, self.options.layout_iou_threshold)
                annotate_blocks_with_layout(all_blocks, layout)
            except Exception as e:
                logger.warning("Layout analysis failed for page %d: %s", page_num + 1, e)
                layout = None

        # Extract images if needed. Pass page-header/footer regions so we don't
        # emit placeholders for the recurring decorations / signature artifacts
        # those zones tend to contain.
        page_images: list[Any] = []
        if self.options.attachment_mode != "skip":
            excluded_regions = self._collect_image_exclusion_regions(layout)
            page_images, page_footnotes = extract_page_images(
                page,
                page_num,
                self.options,
                base_filename,
                attachment_sequencer,
                excluded_regions=excluded_regions,
            )
            self._attachment_footnotes.update(page_footnotes)

        # Extract plain text for OCR detection
        extracted_text = "".join(
            span.get("text", "")
            for block in all_blocks
            if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )

        # Apply OCR if needed
        all_blocks, ocr_applied = self._apply_ocr_if_needed(page, all_blocks, extracted_text)

        # Filter headers/footers when enabled - layout labels provide more accurate detection
        if self.options.trim_headers_footers or self.options.auto_trim_headers_footers:
            if layout and (layout.has_label("page-header") or layout.has_label("page-footer")):
                all_blocks = [b for b in all_blocks if b.get("_layout_label") not in ("page-header", "page-footer")]
            else:
                all_blocks = self._filter_headers_footers(all_blocks, page)

        # Supplement table detection with layout-predicted tables
        if layout:
            for pred in layout.get_predictions_by_label("table"):
                pred_rect = fitz.Rect(pred.x0, pred.y0, pred.x1, pred.y1)
                # Check both directions: layout region covered by existing table,
                # OR existing table covered by layout region
                already_covered = any(
                    abs(pred_rect & t["bbox"]) > 0.3 * max(abs(pred_rect), abs(t["bbox"])) for t in table_info
                )
                if not already_covered:
                    table_info.append(
                        {
                            "bbox": pred_rect,
                            "idx": len(table_info),
                            "type": "layout",
                            "lines": ([], []),
                        }
                    )
                    logger.debug("Layout analysis detected additional table at %s on page %d", pred_rect, page_num + 1)

        # Filter out blocks inside table regions
        text_blocks = []
        for block in all_blocks:
            if "bbox" not in block:
                text_blocks.append(block)
                continue

            block_rect = fitz.Rect(block["bbox"])
            is_in_table = any(abs(block_rect & table["bbox"]) > 0.5 * abs(block_rect) for table in table_info)
            if not is_in_table:
                text_blocks.append(block)

        # Apply column detection if enabled
        if self.options.detect_columns and self.options.column_detection_mode not in ("disabled", "force_single"):
            force_multi = self.options.column_detection_mode == "force_multi"
            columns = detect_columns(
                text_blocks,
                self.options.column_gap_threshold,
                use_clustering=self.options.use_column_clustering,
                force_multi_column=force_multi,
            )
        else:
            columns = [text_blocks]

        # Assign tables to columns
        self._assign_tables_to_columns(table_info, columns)

        # Process columns and tables (suppress image placeholders when OCR replaced page content)
        nodes = self._process_columns_and_tables(
            columns, table_info, page, page_num, page_images=[] if ocr_applied else page_images
        )

        return nodes

    def _apply_column_detection(self, blocks: list[dict]) -> list[dict]:
        """Apply column detection to text blocks based on options.

        Parameters
        ----------
        blocks : list[dict]
            List of text blocks from PyMuPDF

        Returns
        -------
        list[dict]
            Processed blocks in reading order

        """
        if not self.options.detect_columns:
            return blocks

        # Check column_detection_mode option
        if self.options.column_detection_mode in ("disabled", "force_single"):
            # Force single column (no detection)
            return blocks

        # Apply column detection for force_multi or auto modes
        if self.options.column_detection_mode == "force_multi":
            columns: list[list[dict]] = detect_columns(
                blocks,
                self.options.column_gap_threshold,
                use_clustering=self.options.use_column_clustering,
                force_multi_column=True,
            )
        else:  # "auto" mode (default)
            columns = detect_columns(
                blocks,
                self.options.column_gap_threshold,
                use_clustering=self.options.use_column_clustering,
                force_multi_column=False,
            )

        # Process blocks in proper reading order: top-to-bottom, left-to-right
        return self._merge_columns_for_reading_order(columns)

    def _calculate_blocks_average_line_height(self, blocks: list[dict]) -> float | None:
        """Calculate average line height across multiple blocks."""
        line_heights = []
        for block in blocks:
            for line in block.get("lines", []):
                if "bbox" in line:
                    line_height = line["bbox"][3] - line["bbox"][1]
                    if line_height > 0:
                        line_heights.append(line_height)

        if line_heights:
            avg = sum(line_heights) / len(line_heights)
            logger.debug(f"Calculated average line height for page: {avg:.2f} points")
            return avg
        return None

    def _process_blocks_line_monospace(self, spans: list, text: str, block: dict, state: _BlockProcessingState) -> bool:
        """Handle monospace line in blocks processing. Returns True if handled."""
        all_mono = all(s["flags"] & 8 for s in spans)
        if not all_mono:
            return False

        state.in_code_block = True
        span_size = spans[0]["size"]
        delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (span_size * 0.5)) if span_size > 0 else 0
        state.code_block_lines.append(" " * delta + text)
        return True

    def _process_blocks_line_text(
        self,
        spans: list,
        links: list[dict],
        page_num: int,
        average_line_height: float | None,
        state: _BlockProcessingState,
    ) -> None:
        """Process text line (heading or paragraph) in blocks processing."""
        header_level = 0
        if self._hdr_identifier:
            line_style = compute_line_style(spans)
            if line_style is not None:
                header_level = self._hdr_identifier.classify_line_style(
                    size=line_style.size,
                    text=line_style.text,
                    is_bold=line_style.is_bold,
                    is_allcaps=line_style.is_allcaps,
                )
        inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)

        if not inline_content or not inline_has_text(inline_content):
            return

        if header_level > 0:
            line_text = "".join(s.get("text", "") for s in spans).strip()
            self._emit_heading(state, header_level, line_text, inline_content, page_num)
        else:
            # Paragraph emission orphans any buffered numbering prefix —
            # flush it as its own heading so the marker isn't lost.
            self._flush_pending_heading_prefix(state)
            state.nodes.append(
                AstParagraph(content=inline_content, source_location=SourceLocation(format="pdf", page=page_num + 1))
            )

    def _process_text_blocks_to_nodes(
        self, blocks_to_process: list[dict], links: list[dict], page_num: int
    ) -> list[Node]:
        """Process text blocks into AST nodes.

        Parameters
        ----------
        blocks_to_process : list[dict]
            Text blocks to process
        links : list[dict]
            Links on the page
        page_num : int
            Page number for source tracking

        Returns
        -------
        list[Node]
            List of AST nodes

        """
        average_line_height = self._calculate_blocks_average_line_height(blocks_to_process)
        state = _BlockProcessingState()

        for block in blocks_to_process:
            previous_y = 0.0

            for line in block["lines"]:
                # Handle rotated text — group consecutive same-direction lines
                if line.get("dir", (0, 0))[1] != 0:
                    if self.options.handle_rotated_text:
                        self._accumulate_rotated_line(line, state, page_num)
                    continue
                # Horizontal line: flush any pending rotated run before continuing
                self._flush_rotated_text(state, page_num)

                spans = list(line["spans"])
                if not spans:
                    continue

                this_y = line["bbox"][3]
                same_line = abs(this_y - previous_y) <= DEFAULT_OVERLAP_THRESHOLD_PX and previous_y > 0
                text = "".join([s["text"] for s in spans])

                if not same_line:
                    previous_y = this_y

                # Handle monospace text (code blocks)
                if self._process_blocks_line_monospace(spans, text, block, state):
                    continue

                # Finalize code block if we were in one
                if state.in_code_block:
                    self._finalize_code_block(state, page_num)

                # Process text line (heading or paragraph)
                self._process_blocks_line_text(spans, links, page_num, average_line_height, state)

        # Finalize any remaining code block
        if state.in_code_block:
            self._finalize_code_block(state, page_num)

        # Flush any trailing rotated-text run
        self._flush_rotated_text(state, page_num)

        # Drop any unmerged numbering prefix as a standalone heading rather
        # than silently swallowing it.
        self._flush_pending_heading_prefix(state)

        return state.nodes

    def _process_text_region_to_ast(self, page: "fitz.Page", clip: "fitz.Rect", page_num: int) -> list[Node]:
        """Process a text region to AST nodes.

        Parameters
        ----------
        page : fitz.Page
            PDF page
        clip : fitz.Rect
            Clipping rectangle for text extraction
        page_num : int
            Page number for source tracking

        Returns
        -------
        list of Node
            List of AST nodes (paragraphs, headings, code blocks)

        """
        import fitz

        # Extract URL type links on page
        try:
            links = [line for line in page.get_links() if line["kind"] == 2]
        except (AttributeError, Exception):
            links = []

        # Extract text blocks
        try:
            blocks = page.get_text(
                "dict",
                clip=clip,
                flags=fitz.TEXTFLAGS_TEXT,
                sort=False,
            )["blocks"]
            if self.options.merge_hyphenated_words:
                dehyphenate_blocks(blocks)
        except (AttributeError, KeyError, Exception):
            # If extraction fails (e.g., in tests), return empty
            return []

        # Filter out headers/footers if trim_headers_footers is enabled
        if self.options.trim_headers_footers:
            blocks = self._filter_headers_footers(blocks, page)

        # Apply column detection
        blocks_to_process = self._apply_column_detection(blocks)

        # Process blocks to create AST nodes
        return self._process_text_blocks_to_nodes(blocks_to_process, links, page_num)

    def _process_text_spans_to_inline(
        self, spans: list[dict], links: list[dict], page_num: int, average_line_height: float | None = None
    ) -> list[Node]:
        """Process text spans to inline AST nodes.

        Parameters
        ----------
        spans : list of dict
            Text spans from PyMuPDF
        links : list of dict
            Links on the page
        page_num : int
            Page number for source tracking
        average_line_height : float or None, optional
            Average line height for the page, used for link threshold auto-calibration

        Returns
        -------
        list of Node
            List of inline AST nodes

        """
        result: list[Node] = []
        # Tracks whether the most recently emitted Text-bearing span ended
        # with whitespace, so we can avoid creating multi-space runs at span
        # boundaries when collapse_excess_whitespace is enabled.
        prev_text_ends_ws = False

        for span in spans:
            span_text = span["text"]
            # Skip completely empty spans, but preserve single spaces
            if not span_text:
                continue

            # Check for list bullets before treating as monospace
            is_list_bullet = span_text in ["-", "o", "•", "◦", "▪"] and len(span_text) == 1

            # Decode font properties
            mono = span["flags"] & 8
            bold = span["flags"] & 16
            italic = span["flags"] & 2

            # Check for links with auto-calibrated threshold
            link_url = self._resolve_link_for_span(links, span, average_line_height)

            # Build the inline node
            if mono and not is_list_bullet:
                # Inline code — preserve whitespace as-is, don't update the
                # running whitespace state.
                inline_node: Node = Code(content=span_text)
            else:
                # Regular text with optional formatting
                # Replace special characters
                span_text = (
                    span_text.replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace(chr(0xF0B7), "-")
                    .replace(chr(0xB7), "-")
                    .replace(chr(8226), "-")
                    .replace(chr(9679), "-")
                )

                # Collapse layout-padded whitespace runs in non-mono spans.
                # PDF spans frequently encode visual spacing as long runs of
                # ascii spaces (e.g. "Policy Title:                  ") that
                # do not carry meaning in markdown.
                if self.options.collapse_excess_whitespace:
                    span_text = collapse_whitespace_runs(span_text)
                    if prev_text_ends_ws and span_text.startswith((" ", "\t")):
                        span_text = span_text.lstrip(" \t")
                    if not span_text:
                        # Span was nothing but redundant whitespace — drop it.
                        continue
                    prev_text_ends_ws = span_text[-1] in (" ", "\t")

                inline_node = Text(content=span_text)

                # Apply formatting layers — but skip bold/italic wrapping
                # for whitespace-only spans, since "**  **" or "* *" carries
                # no meaning and tends to confuse the inline-formatting
                # consolidator into emitting redundant marker pairs.
                if span_text.strip():
                    if bold:
                        inline_node = Strong(content=[inline_node])
                    if italic:
                        inline_node = Emphasis(content=[inline_node])

            # Wrap in link if URL present
            if link_url:
                inline_node = Link(url=link_url, content=[inline_node])

            result.append(inline_node)

        return result

    def _calculate_paragraph_break_threshold(self, block: dict) -> float:
        """Calculate adaptive paragraph break threshold based on line heights.

        Parameters
        ----------
        block : dict
            Text block from PyMuPDF

        Returns
        -------
        float
            Paragraph break threshold in points

        """
        line_heights_in_block = []
        for line in block["lines"]:
            if "bbox" in line and "dir" in line and line["dir"][1] == 0:  # Only horizontal lines
                line_height = line["bbox"][3] - line["bbox"][1]
                if line_height > 0:
                    line_heights_in_block.append(line_height)

        # Use median line height for robustness (less affected by outliers)
        if line_heights_in_block:
            sorted_heights = sorted(line_heights_in_block)
            median_height = sorted_heights[len(sorted_heights) // 2]
            # Paragraph break threshold: 50% of typical line height
            return median_height * 0.5
        else:
            # Fallback to fixed threshold if we can't calculate
            return 5.0

    def _build_paragraph_metadata(
        self,
        paragraph_bbox: tuple[float, float, float, float] | None,
        paragraph_is_list: bool,
        paragraph_list_type: str | None,
    ) -> dict:
        """Build metadata dict including bbox and list marker info.

        Parameters
        ----------
        paragraph_bbox : tuple or None
            Bounding box of paragraph
        paragraph_is_list : bool
            Whether paragraph is a list item
        paragraph_list_type : str or None
            Type of list marker

        Returns
        -------
        dict
            Metadata dictionary

        """
        metadata: dict[str, Any] = {"bbox": paragraph_bbox} if paragraph_bbox else {}
        if paragraph_is_list:
            metadata["is_list_item"] = True
            metadata["list_type"] = paragraph_list_type
            if paragraph_bbox:
                metadata["marker_x"] = paragraph_bbox[0]
        return metadata

    def _flush_paragraph(
        self,
        paragraph_content: list[Node],
        paragraph_bbox: tuple[float, float, float, float] | None,
        paragraph_is_list: bool,
        paragraph_list_type: str | None,
        page_num: int,
        nodes: list[Node],
    ) -> None:
        """Flush accumulated paragraph content to nodes list.

        Parameters
        ----------
        paragraph_content : list of Node
            Accumulated inline nodes for paragraph
        paragraph_bbox : tuple or None
            Bounding box of paragraph
        paragraph_is_list : bool
            Whether paragraph is a list item
        paragraph_list_type : str or None
            Type of list marker
        page_num : int
            Page number for source tracking
        nodes : list of Node
            Output nodes list to append to

        """
        if paragraph_content:
            metadata = self._build_paragraph_metadata(paragraph_bbox, paragraph_is_list, paragraph_list_type)
            source_loc = SourceLocation(format="pdf", page=page_num + 1, metadata=metadata)
            nodes.append(AstParagraph(content=paragraph_content, source_location=source_loc))

    def _flush_state_paragraph(self, state: _BlockProcessingState, page_num: int) -> None:
        """Flush paragraph from state to nodes and reset paragraph state.

        If the state has accumulated paragraph content, also drain any
        buffered numbering-prefix heading first so the prefix is emitted
        as its own heading rather than disappearing behind the paragraph.
        Empty-paragraph flushes leave the buffer alone — heading lines may
        still arrive on the same block and want to absorb the prefix.
        """
        if state.paragraph_content:
            self._flush_pending_heading_prefix(state)
        self._flush_paragraph(
            state.paragraph_content,
            state.paragraph_bbox,
            state.paragraph_is_list,
            state.paragraph_list_type,
            page_num,
            state.nodes,
        )
        state.reset_paragraph()

    def _emit_heading(
        self,
        state: _BlockProcessingState,
        level: int,
        line_text: str,
        inline_content: list[Node],
        page_num: int,
    ) -> None:
        """Emit a heading or buffer a numbering-only prefix for merging.

        Lines whose entire text is a numbering prefix (``"I."``, ``"1.1"``,
        ``"(a)"``) are deferred — the next heading line on the same block
        will absorb them and emit a single ``"I. Background"``-style
        heading. PDFs often visually break Roman-numeral section markers
        onto their own line above the actual heading text, and emitting
        them as separate headings produced obviously-wrong output before.
        """
        if parse_numbering_prefix(line_text) is not None:
            # If we *already* have a buffered prefix and this is also one,
            # flush the older one first so neither gets lost (rare in real
            # documents but cheap to handle).
            if state.pending_heading_prefix_content is not None:
                self._flush_pending_heading_prefix(state)
            state.pending_heading_prefix_content = inline_content
            state.pending_heading_prefix_level = level
            state.pending_heading_prefix_page = page_num
            return

        if state.pending_heading_prefix_content is not None:
            # Merge: prepend pending prefix content with a single space,
            # using the prefix's level (which represented the section depth).
            merged = state.pending_heading_prefix_content + [Text(content=" ")] + inline_content
            merged_level = state.pending_heading_prefix_level
            page = state.pending_heading_prefix_page
            state.pending_heading_prefix_content = None
            state.pending_heading_prefix_level = 0
            _strip_leading_whitespace_in_place(merged)
            state.nodes.append(
                Heading(
                    level=merged_level,
                    content=merged,
                    source_location=SourceLocation(format="pdf", page=page + 1),
                )
            )
            self._last_heading_level = merged_level
            return

        _strip_leading_whitespace_in_place(inline_content)
        state.nodes.append(
            Heading(
                level=level,
                content=inline_content,
                source_location=SourceLocation(format="pdf", page=page_num + 1),
            )
        )
        self._last_heading_level = level

    def _flush_pending_heading_prefix(self, state: _BlockProcessingState) -> None:
        """Emit any buffered numbering-prefix heading as a standalone heading."""
        if state.pending_heading_prefix_content is None:
            return
        _strip_leading_whitespace_in_place(state.pending_heading_prefix_content)
        state.nodes.append(
            Heading(
                level=state.pending_heading_prefix_level,
                content=state.pending_heading_prefix_content,
                source_location=SourceLocation(format="pdf", page=state.pending_heading_prefix_page + 1),
            )
        )
        self._last_heading_level = state.pending_heading_prefix_level
        state.pending_heading_prefix_content = None
        state.pending_heading_prefix_level = 0

    def _finalize_code_block(self, state: _BlockProcessingState, page_num: int) -> None:
        """Finalize code block from state and reset code block state."""
        if state.code_block_lines:
            code_content = "\n".join(state.code_block_lines)
            state.nodes.append(
                CodeBlock(content=code_content, source_location=SourceLocation(format="pdf", page=page_num + 1))
            )
        state.reset_code_block()

    def _flush_rotated_text(self, state: _BlockProcessingState, page_num: int) -> None:
        """Emit accumulated rotated-text run as a single paragraph and reset.

        Same-direction rotated lines within one block are joined with spaces.
        The paragraph is tagged with the rotation key in source-location metadata
        so :meth:`_merge_rotated_paragraphs` can join runs that span multiple
        blocks (common when PyMuPDF puts each rotated label in its own block).
        """
        if not state.pending_rotated_text:
            return
        combined = " ".join(state.pending_rotated_text)
        source_loc = SourceLocation(
            format="pdf",
            page=page_num + 1,
            metadata={"rotated": state.pending_rotated_key or ""},
        )
        state.nodes.append(AstParagraph(content=[Text(content=combined)], source_location=source_loc))
        state.reset_rotated()

    def _accumulate_rotated_line(self, line: dict, state: _BlockProcessingState, page_num: int) -> None:
        """Append a rotated line to the in-progress run, flushing on direction change."""
        text = extract_rotated_text(line, None)
        if not text.strip():
            return
        key = classify_line_rotation(line)
        if state.pending_rotated_key is not None and state.pending_rotated_key != key:
            self._flush_rotated_text(state, page_num)
        if state.pending_rotated_key is None:
            self._flush_state_paragraph(state, page_num)
            state.pending_rotated_key = key
        state.pending_rotated_text.append(text)

    def _handle_rotated_line(self, line: dict, state: _BlockProcessingState, page_num: int) -> bool:
        """Handle rotated text line. Returns True if line was processed (should skip further processing)."""
        if line["dir"][1] == 0:  # Horizontal line
            self._flush_rotated_text(state, page_num)
            return False

        if self.options.handle_rotated_text:
            self._accumulate_rotated_line(line, state, page_num)
        return True  # Skip non-horizontal lines

    def _handle_monospace_line(
        self, line: dict, spans: list, text: str, block: dict, state: _BlockProcessingState, page_num: int
    ) -> bool:
        """Handle monospace line (code block). Returns True if line was processed as code."""
        all_mono = all(s["flags"] & 8 for s in spans)
        if not all_mono:
            return False

        # Flush accumulated paragraph before starting code block
        self._flush_state_paragraph(state, page_num)
        state.in_code_block = True

        # Compute approximate indentation
        span_size = spans[0]["size"]
        delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (span_size * 0.5)) if span_size > 0 else 0
        state.code_block_lines.append(" " * delta + text)
        return True

    def _handle_header_line(
        self,
        spans: list,
        links: list[dict],
        state: _BlockProcessingState,
        page_num: int,
        average_line_height: float | None,
    ) -> bool:
        """Handle header line. Returns True if line was processed as header."""
        header_level = 0
        if self._hdr_identifier:
            line_style = compute_line_style(spans)
            if line_style is not None:
                header_level = self._hdr_identifier.classify_line_style(
                    size=line_style.size,
                    text=line_style.text,
                    is_bold=line_style.is_bold,
                    is_allcaps=line_style.is_allcaps,
                )

        if header_level <= 0:
            return False

        inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
        if not inline_content or not inline_has_text(inline_content):
            # Whitespace-only line at header-sized font: drop it, don't promote
            # to a heading and don't fall through to paragraph treatment.
            return True

        self._flush_state_paragraph(state, page_num)
        line_text = "".join(s.get("text", "") for s in spans).strip()
        self._emit_heading(state, header_level, line_text, inline_content, page_num)
        return True

    def _handle_header_line_with_layout(
        self,
        spans: list,
        links: list[dict],
        state: _BlockProcessingState,
        page_num: int,
        average_line_height: float | None,
        layout_label: str,
    ) -> bool:
        """Handle header line using layout analysis classification.

        The layout model classifies the block as ``title`` or ``section-header``.
        For ``title``, always use heading level 1. For ``section-header``,
        prefer the font-size heuristic if available. When the heuristic
        disagrees with the layout model, only promote to heading if the text
        looks plausibly like a header (short text without trailing punctuation).

        Parameters
        ----------
        spans : list
            Text spans from the line.
        links : list[dict]
            Links on the page.
        state : _BlockProcessingState
            Current processing state.
        page_num : int
            Page number for source tracking.
        average_line_height : float or None
            Average line height for the page.
        layout_label : str
            Layout label (``"title"`` or ``"section-header"``).

        Returns
        -------
        bool
            True if the line was emitted as a heading.

        """
        # The layout model labels whole blocks as section-header / title, which
        # means every line in the block (including blank/whitespace lines) hits
        # this path. Reject whitespace-only lines up front so we don't emit
        # empty `## ` headings; return True so the caller doesn't fall through
        # to paragraph treatment.
        line_style = compute_line_style(spans)
        if line_style is None:
            return True

        # Ask the font heuristic at line level — used to corroborate or
        # override the layout label.
        font_level = 0
        if self._hdr_identifier:
            font_level = self._hdr_identifier.classify_line_style(
                size=line_style.size,
                text=line_style.text,
                is_bold=line_style.is_bold,
                is_allcaps=line_style.is_allcaps,
            )

        if layout_label == "title":
            # Layout's "title" is often noisy: it fires for the first
            # heading-styled line on each page even when the document has
            # only one heading style and the line is really a section
            # heading. Defer to the font heuristic when it has an opinion.
            level = font_level if font_level > 0 else 1
        else:
            # section-header: trust the font heuristic when it speaks; cap
            # at h2 so a doc with a single heading size doesn't promote
            # every section-header to h1 against the structural signal.
            if font_level > 0:
                level = max(font_level, 2)
            else:
                # Font heuristic has nothing to say. Trust the layout label
                # only if the text plausibly looks like a header.
                text = line_style.text
                if text.endswith((".", ",", ";", ":", "!", "?")):
                    return False  # Trailing punctuation: usually a sentence, not a heading
                if len(text) > self.options.header_max_line_length:
                    return False  # Too long for a header
                # Pick a level from context rather than the old hard-coded 2:
                # sibling of the most recent emitted heading; fall back to h2
                # when nothing has been emitted yet.
                level = self._last_heading_level if self._last_heading_level > 0 else 2

        inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
        if not inline_content or not inline_has_text(inline_content):
            return True

        self._flush_state_paragraph(state, page_num)
        self._emit_heading(state, level, line_style.text, inline_content, page_num)
        return True

    def _accumulate_paragraph_line(
        self,
        line: dict,
        spans: list,
        links: list[dict],
        vertical_gap: float,
        paragraph_break_threshold: float,
        state: _BlockProcessingState,
        page_num: int,
        average_line_height: float | None,
    ) -> None:
        """Accumulate regular text line into paragraph state."""
        # Check if we should start a new paragraph (don't break list items)
        if vertical_gap > paragraph_break_threshold and state.paragraph_content and not state.paragraph_is_list:
            self._flush_state_paragraph(state, page_num)

        inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
        if not inline_content:
            return

        if state.paragraph_content:
            # Add an inter-line separator unless the previous line already
            # ended with whitespace (collapse_excess_whitespace would
            # otherwise leave us with a 2-space run at the line boundary).
            if not (self.options.collapse_excess_whitespace and _trailing_text_is_whitespace(state.paragraph_content)):
                state.paragraph_content.append(Text(content=" "))
        else:
            # Starting new paragraph
            state.paragraph_bbox = line["bbox"]
            first_text = next((n.content for n in inline_content if isinstance(n, Text)), "")
            state.paragraph_is_list, state.paragraph_list_type = self._is_valid_list_marker(first_text)

        state.paragraph_content.extend(inline_content)

        # Expand bbox to include this line
        if state.paragraph_bbox:
            line_bbox = line["bbox"]
            state.paragraph_bbox = (
                min(state.paragraph_bbox[0], line_bbox[0]),
                min(state.paragraph_bbox[1], line_bbox[1]),
                max(state.paragraph_bbox[2], line_bbox[2]),
                max(state.paragraph_bbox[3], line_bbox[3]),
            )

    def _process_single_block_to_ast(
        self, block: dict, links: list[dict], page_num: int, average_line_height: float | None = None
    ) -> list[Node]:
        """Process a single text block to AST nodes.

        Parameters
        ----------
        block : dict
            Single text block from PyMuPDF
        links : list of dict
            Links on the page
        page_num : int
            Page number for source tracking
        average_line_height : float or None, optional
            Average line height for the page, used for link threshold auto-calibration

        Returns
        -------
        list of Node
            List of AST nodes (paragraphs, headings, code blocks)

        """
        if "lines" not in block:
            return []

        layout_label = block.get("_layout_label")
        state = _BlockProcessingState()
        paragraph_break_threshold = self._calculate_paragraph_break_threshold(block)

        # Layout hint: if model says list-item, pre-set list state
        if layout_label == "list-item":
            state.paragraph_is_list = True
            state.paragraph_list_type = "unordered"

        for line in block["lines"]:
            # Handle rotated text (skip further processing if rotated)
            if self._handle_rotated_line(line, state, page_num):
                continue

            spans = list(line.get("spans", []))
            if not spans:
                continue

            this_y = line["bbox"][3]
            vertical_gap = abs(this_y - state.previous_y) if state.previous_y > 0 else 0
            text = "".join([s["text"] for s in spans])
            state.previous_y = this_y

            # Handle monospace text (code blocks)
            if self._handle_monospace_line(line, spans, text, block, state, page_num):
                continue

            # Finalize code block if we were in one
            if state.in_code_block:
                self._finalize_code_block(state, page_num)

            # Handle headers - layout label overrides font-size heuristics
            if layout_label in ("title", "section-header"):
                if self._handle_header_line_with_layout(
                    spans, links, state, page_num, average_line_height, layout_label
                ):
                    continue
            elif self._handle_header_line(spans, links, state, page_num, average_line_height):
                continue

            # Regular paragraph text
            self._accumulate_paragraph_line(
                line, spans, links, vertical_gap, paragraph_break_threshold, state, page_num, average_line_height
            )

        # Finalize remaining content
        self._flush_rotated_text(state, page_num)
        self._flush_state_paragraph(state, page_num)
        if state.in_code_block:
            self._finalize_code_block(state, page_num)
        # Flush any unmerged numbering prefix at block end so it surfaces
        # as a standalone heading rather than vanishing.
        self._flush_pending_heading_prefix(state)

        return state.nodes

    def _resolve_link_for_span(
        self, links: list[dict], span: dict, average_line_height: float | None = None
    ) -> str | None:
        """Resolve link URL for a text span with auto-calibrated overlap threshold.

        Parameters
        ----------
        links : list of dict
            Links on the page
        span : dict
            Text span
        average_line_height : float or None, optional
            Average line height for the page, used for auto-calibration of threshold
            for spans with unusual heights (e.g., large fonts)

        Returns
        -------
        str or None
            Link URL if span is part of a link

        Notes
        -----
        Uses the link_overlap_threshold option from self.options to determine
        the minimum overlap required for link detection. When average_line_height
        is provided, automatically adjusts the threshold for spans that are
        significantly taller than average (common in documents with font scaling).

        """
        if not links or not span.get("text"):
            return None

        import fitz

        bbox = fitz.Rect(span["bbox"])

        # Calculate span height
        span_height = bbox.height

        # Use threshold from options
        threshold_percent = self.options.link_overlap_threshold

        # Auto-calibrate threshold for tall spans if average line height is available
        if average_line_height and average_line_height > 0 and span_height > average_line_height * 1.5:
            # Span is significantly taller than average (>1.5x), likely due to font scaling
            # Relax the threshold to compensate for the increased bbox area
            # Scale down threshold proportionally to the height ratio
            height_ratio = span_height / average_line_height
            adjusted_threshold = threshold_percent / (height_ratio**0.5)  # Square root dampening
            adjusted_threshold = max(adjusted_threshold, 30.0)  # Don't go below 30%
            threshold_percent = adjusted_threshold
            logger.debug(
                f"Auto-calibrated link threshold for tall span: "
                f"{self.options.link_overlap_threshold:.1f}% -> {threshold_percent:.1f}% "
                f"(span height: {span_height:.1f}, avg: {average_line_height:.1f})"
            )

        # Find all links that overlap with this span
        for link in links:
            hot = link["from"]  # The hot area of the link
            overlap = hot & bbox
            bbox_area = (threshold_percent / 100.0) * abs(bbox)
            if abs(overlap) >= bbox_area:
                return link.get("uri")

        return None

    @classmethod
    def _extract_cell_text(cls, cell_text: Any) -> str:
        """Normalize a table cell value to a stripped string.

        Parameters
        ----------
        cell_text : Any
            Cell text value which may be None, string, or other type

        Returns
        -------
        str
            Stripped cell text, empty string if None

        """
        if cell_text is None:
            return ""
        return str(cell_text).strip()

    def _process_table_to_ast(self, table: Any, page: "fitz.Page", page_num: int) -> Node | None:
        """Process a PyMuPDF table to AST Table node.

        Directly accesses table cell data from PyMuPDF table object instead of
        converting to markdown and re-parsing, which is more efficient and robust.

        Parameters
        ----------
        table : PyMuPDF Table
            Table object from find_tables()
        page : fitz.Page
            Page containing the table. Used to recover the region's text when the
            detection is rejected as a degenerate grid.
        page_num : int
            Page number for source tracking

        Returns
        -------
        Node or None
            A table when the detection is a real grid; a paragraph carrying the
            region's text when it is a degenerate (1xN / Nx1) grid; ``None`` when
            the region has no usable content.

        """
        import fitz

        try:
            # Try to extract cells directly from PyMuPDF table object
            # PyMuPDF tables have a `extract()` method that returns cell data
            table_data = table.extract()

            if not table_data or len(table_data) == 0:
                logger.debug("Table has no data")
                return None

            # Reject pathological detections (PyMuPDF's find_tables() can fire on
            # decorative frames / TOC dot-leader regions / non-tabular content,
            # the same way our ruling-line fallback can). Same caps as ruling.
            n_rows = len(table_data)
            n_cols = max((len(r) for r in table_data), default=0)
            n_cells = sum(len(r) for r in table_data)
            if n_cells == 0:
                return None
            # A grid needs two dimensions to be a table. One column is prose wrapped in
            # pipes; one row is a single line of text chopped at its word boundaries --
            # find_tables() emits both, and on an academic paper it turned the sentence
            # "What is the capital of this country?" into an eight-column table. Neither
            # shape can carry tabular meaning, and rendering them as tables is strictly
            # worse than leaving the text alone.
            #
            # Return the region's text as a paragraph rather than None: the text inside a
            # table bbox has already been excluded from the ordinary text blocks, so
            # returning None here would delete it, not demote it.
            if n_rows < MIN_TABLE_ROWS or n_cols < MIN_TABLE_COLS:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"{n_rows}x{n_cols} is not a grid (needs at least "
                    f"{MIN_TABLE_ROWS}x{MIN_TABLE_COLS})"
                )
                self._record_table_rejection("degenerate_grid")
                return self._region_text_as_paragraph(page, fitz.Rect(table.bbox), page_num)
            if n_cols > MAX_TABLE_COLS or n_rows > MAX_TABLE_ROWS:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: {n_rows}x{n_cols} grid exceeds size caps"
                )
                self._record_table_rejection("oversized_grid")
                return self._region_text_as_paragraph(page, fitz.Rect(table.bbox), page_num)
            n_empty = sum(1 for r in table_data for c in r if c is None or not str(c).strip())
            if n_empty / n_cells > MAX_TABLE_EMPTY_RATIO:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"{n_empty}/{n_cells} ({n_empty / n_cells:.0%}) cells empty"
                )
                self._record_table_rejection("mostly_empty")
                return self._region_text_as_paragraph(page, fitz.Rect(table.bbox), page_num)
            unique_texts = {str(c).strip() for r in table_data for c in r if c is not None and str(c).strip()}
            n_filled = n_cells - n_empty
            if len(unique_texts) == 1 and n_filled >= MIN_FILLED_FOR_UNIFORMITY_CHECK:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"all {n_filled} non-empty cells have identical content"
                )
                self._record_table_rejection("uniform_cells")
                return self._region_text_as_paragraph(page, fitz.Rect(table.bbox), page_num)
            n_dot_leader = sum(1 for r in table_data for c in r if c is not None and is_dot_leader_cell(str(c)))
            if n_filled and n_dot_leader / n_filled > MAX_DOT_LEADER_CELL_RATIO:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"{n_dot_leader}/{n_filled} ({n_dot_leader / n_filled:.0%}) cells are "
                    f"dot-leader noise (looks like TOC region)"
                )
                self._record_table_rejection("dot_leader_toc")
                return self._region_text_as_paragraph(page, fitz.Rect(table.bbox), page_num)

            # Separate header row (first row) from data rows
            header_row_data = table_data[0] if table_data else []
            data_rows_data = table_data[1:] if len(table_data) > 1 else []

            header_cells = [TableCell(content=[Text(content=self._extract_cell_text(c))]) for c in header_row_data]
            header_row = TableRow(cells=header_cells, is_header=True)

            data_rows = []
            for row_data in data_rows_data:
                row_cells = [TableCell(content=[Text(content=self._extract_cell_text(c))]) for c in row_data]
                data_rows.append(TableRow(cells=row_cells))

            return AstTable(
                header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

        except (AttributeError, Exception) as e:
            # Fallback to markdown conversion if direct extraction fails
            logger.debug(f"Direct table extraction failed ({e}), falling back to markdown parsing")
            return self._process_table_to_ast_fallback(table, page_num)

    def _process_table_to_ast_fallback(self, table: Any, page_num: int) -> AstTable | None:
        """Fallback method using markdown conversion when direct extraction fails.

        Parameters
        ----------
        table : PyMuPDF Table
            Table object from find_tables()
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstTable or None
            Table node if table has content

        """
        try:
            # Get table as markdown
            table_md = table.to_markdown(clean=False)
            if not table_md:
                return None

            # Parse the markdown table to extract structure
            lines = table_md.strip().split("\n")
            if len(lines) < 2:  # Need at least header and separator
                return None

            # Parse header row (first line)
            header_line = lines[0]
            header_cells_text = self._parse_markdown_table_row(header_line)

            # Skip separator line (second line)
            # Parse data rows (remaining lines)
            data_rows_text = []
            for line in lines[2:]:
                if line.strip():
                    row_cells = self._parse_markdown_table_row(line)
                    if row_cells:
                        data_rows_text.append(row_cells)

            # Build AST table
            header_cells = [TableCell(content=[Text(content=cell)]) for cell in header_cells_text]
            header_row = TableRow(cells=header_cells, is_header=True)

            data_rows = []
            for row_cells in data_rows_text:
                cells = [TableCell(content=[Text(content=cell)]) for cell in row_cells]
                data_rows.append(TableRow(cells=cells))

            return AstTable(
                header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

        except Exception as e:
            logger.debug(f"Fallback table processing failed: {e}")
            return None

    def _extract_table_from_ruling_rect(
        self, page: "fitz.Page", table_rect: "fitz.Rect", h_lines: list[tuple], v_lines: list[tuple], page_num: int
    ) -> AstTable | None:
        """Extract table content from a bounding box using ruling lines.

        Implements basic grid-based cell segmentation using detected horizontal
        and vertical lines to extract text from each cell.

        Parameters
        ----------
        page : fitz.Page
            PDF page containing the table
        table_rect : fitz.Rect
            Bounding box of the table
        h_lines : list of tuple
            Horizontal ruling lines as (x0, y0, x1, y1) tuples
        v_lines : list of tuple
            Vertical ruling lines as (x0, y0, x1, y1) tuples
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstTable or None
            Table node if extraction successful

        Notes
        -----
        This method uses grid-based cell segmentation. It may not work well
        for tables without clear ruling lines or with merged cells.

        """
        if self.options.table_fallback_extraction_mode == "none":
            return None

        # Sort lines for grid creation
        h_lines_sorted = sorted(h_lines, key=lambda line: line[1])  # Sort by y-coordinate
        v_lines_sorted = sorted(v_lines, key=lambda line: line[0])  # Sort by x-coordinate

        if len(h_lines_sorted) < 2 or len(v_lines_sorted) < 2:
            # Need at least 2 horizontal and 2 vertical lines to form cells
            return None

        # Create grid cells from line intersections
        rows: list[TableRow] = []

        # Extract y-coordinates for rows (between consecutive h_lines)
        row_y_coords = [(h_lines_sorted[i][1], h_lines_sorted[i + 1][1]) for i in range(len(h_lines_sorted) - 1)]

        # Extract x-coordinates for columns (between consecutive v_lines)
        col_x_coords = [(v_lines_sorted[i][0], v_lines_sorted[i + 1][0]) for i in range(len(v_lines_sorted) - 1)]

        n_rows = len(row_y_coords)
        n_cols = len(col_x_coords)
        n_cells = n_rows * n_cols

        import fitz

        n_empty = 0
        n_dot_leader = 0
        unique_texts: set[str] = set()

        for row_idx, (y0, y1) in enumerate(row_y_coords):
            cells: list[TableCell] = []

            for _col_idx, (x0, x1) in enumerate(col_x_coords):
                cell_rect = fitz.Rect(x0, y0, x1, y1)
                cell_text = page.get_textbox(cell_rect).strip()

                if cell_text:
                    unique_texts.add(cell_text)
                    if is_dot_leader_cell(cell_text):
                        n_dot_leader += 1
                else:
                    n_empty += 1

                cells.append(TableCell(content=[Text(content=cell_text)]))

            # First row is typically the header
            is_header = row_idx == 0
            rows.append(TableRow(cells=cells, is_header=is_header))

        if not rows:
            return None

        # Sparsity guard: real tables are not mostly empty. A "table" with
        # >70% empty cells is almost always a misfire on a bordered region.
        if n_cells > 0 and n_empty / n_cells > 0.70:
            logger.debug(
                f"Rejecting ruling-line table on page {page_num + 1}: "
                f"{n_empty}/{n_cells} ({n_empty / n_cells:.0%}) cells empty"
            )
            self._record_table_rejection("mostly_empty")
            return None

        # Uniformity guard: a "table" where every non-empty cell has the same
        # content is the prompt-callout pattern (decorative box with a
        # repeated title fragment scattered across cells).
        n_filled = n_cells - n_empty
        if len(unique_texts) == 1 and n_filled >= 5:
            logger.debug(
                f"Rejecting ruling-line table on page {page_num + 1}: "
                f"all {n_filled} non-empty cells have identical content"
            )
            self._record_table_rejection("uniform_cells")
            return None

        if n_filled and n_dot_leader / n_filled > MAX_DOT_LEADER_CELL_RATIO:
            logger.debug(
                f"Rejecting ruling-line table on page {page_num + 1}: "
                f"{n_dot_leader}/{n_filled} ({n_dot_leader / n_filled:.0%}) cells are "
                f"dot-leader noise (looks like TOC region)"
            )
            self._record_table_rejection("dot_leader_toc")
            return None

        # Separate header and data rows
        header_row = rows[0] if rows else TableRow(cells=[])
        data_rows = rows[1:] if len(rows) > 1 else []

        return AstTable(
            header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
        )

    def _extract_table_from_layout_region(
        self, page: "fitz.Page", table_rect: "fitz.Rect", page_num: int
    ) -> Node | None:
        """Extract the content of a region the layout model predicted to be a table.

        Uses ``page.find_tables()`` scoped to the predicted region. When no structured
        table can be recovered there, the region's text is returned as a **paragraph**.

        It used to be returned as a single-column table -- one row per line of text --
        and that was wrong twice over. A one-column table is not a table: it is prose
        wrapped in pipes, so the output was *worse* than plain text, not better. And
        because these tables are the only copy of the region's text (it is excluded
        from the ordinary text blocks to avoid duplication), the mangling could not
        simply be dropped either: suppressing them on a real arXiv paper removed 144
        junk table rows and 530 words of body text along with them.

        The layout model over-fires on academic PDFs -- on one paper it predicted six
        "table" regions and none of them held a table -- so this path is common, and
        every one of those six became a fake table. No converter option changed that;
        the same six appeared under every ``table_detection_mode``, because they never
        came from the table detector at all.

        Parameters
        ----------
        page : fitz.Page
            PDF page containing the region.
        table_rect : fitz.Rect
            Bounding box predicted by the layout model.
        page_num : int
            Page number for source tracking.

        Returns
        -------
        Node or None
            A table when the region really holds one, otherwise a paragraph carrying
            its text. ``None`` only when the region is empty.

        """
        # Try PyMuPDF's find_tables within the predicted region. Only a real table is
        # accepted here: a rejected detection may hand back a paragraph covering just
        # the grid's bbox, which can be narrower than the region the layout model
        # predicted. Falling through instead keeps the whole region's text.
        try:
            tabs = page.find_tables(clip=table_rect)
            if tabs.tables:
                table = self._process_table_to_ast(tabs.tables[0], page, page_num)
                if isinstance(table, AstTable):
                    return table
        except Exception:
            # PyMuPDF table detection is best-effort; fall through to the text path.
            pass

        # No table here -- the layout model was wrong. Keep the text, drop the pipes.
        paragraph = self._region_text_as_paragraph(page, table_rect, page_num)
        if paragraph is not None:
            self._record_table_rejection("layout_region_not_tabular")
        return paragraph

    def _region_text_as_paragraph(self, page: "fitz.Page", region: "fitz.Rect", page_num: int) -> AstParagraph | None:
        """Return a region's text as a paragraph, for regions rejected as tables.

        Text inside a detected table's bbox is removed from the ordinary text blocks so
        it is not emitted twice, and that removal happens *before* the table is validated.
        So a rejection path that simply returns ``None`` does not fall back to prose --
        it deletes the region's text outright. Rejecting degenerate grids this way cost
        256 words of real body text across the corpus.

        Returns
        -------
        AstParagraph or None
            The region's text as a paragraph, or ``None`` if the region holds no text.

        """
        text = page.get_textbox(region)
        if not text or not text.strip():
            return None

        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if not lines:
            return None

        return AstParagraph(
            content=[Text(content=" ".join(lines))],
            source_location=SourceLocation(format="pdf", page=page_num + 1),
        )

    def _parse_markdown_table_row(self, row_line: str) -> list[str]:
        """Parse a markdown table row into cell contents.

        Parameters
        ----------
        row_line : str
            Markdown table row (e.g., "| cell1 | cell2 |")

        Returns
        -------
        list of str
            Cell contents

        """
        # Remove leading/trailing pipes and split
        row_line = row_line.strip()
        if row_line.startswith("|"):
            row_line = row_line[1:]
        if row_line.endswith("|"):
            row_line = row_line[:-1]

        cells = [cell.strip() for cell in row_line.split("|")]
        return cells

    def _collect_image_exclusion_regions(self, layout: "PageLayoutPredictions | None") -> list[Any]:
        """Return regions where images should be skipped during extraction.

        Currently only the layout model's ``page-header`` and ``page-footer``
        predictions are used. Returns an empty list when layout analysis is
        unavailable or the option is disabled, leaving image extraction
        unchanged.
        """
        if layout is None or not self.options.filter_header_footer_images:
            return []
        import fitz

        regions: list[Any] = []
        for label in ("page-header", "page-footer"):
            for pred in layout.get_predictions_by_label(label):
                regions.append(fitz.Rect(pred.x0, pred.y0, pred.x1, pred.y1))
        return regions

    def _create_image_node(self, img_info: dict, page_num: int) -> AstParagraph | None:
        """Create an image node from image info.

        Parameters
        ----------
        img_info : dict
            Image information dict with 'result' (process_attachment result) and 'caption' keys
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstParagraph or None
            Paragraph containing the image node

        """
        try:
            # Get the process_attachment result
            result = img_info.get("result", {})
            caption = img_info.get("caption") or "Image"

            # Convert result to Image node using helper
            img_node = attachment_result_to_image_node(result, fallback_alt_text=caption)

            if img_node:
                # Add source location
                img_node.source_location = SourceLocation(format="pdf", page=page_num + 1)

                # Wrap in paragraph
                return AstParagraph(content=[img_node], source_location=SourceLocation(format="pdf", page=page_num + 1))

            return None

        except Exception as e:
            logger.debug(f"Failed to create image node: {e}")
            return None

    def _filter_headers_footers(self, blocks: list[dict], page: "fitz.Page") -> list[dict]:
        """Filter out text blocks in header/footer zones.

        Parameters
        ----------
        blocks : list of dict
            Text blocks from PyMuPDF
        page : fitz.Page
            PDF page

        Returns
        -------
        list of dict
            Filtered blocks excluding headers and footers

        """
        if not self.options.trim_headers_footers:
            return blocks

        page_height = page.rect.height
        header_zone = self.options.header_height
        footer_zone = self.options.footer_height

        filtered_blocks = []
        for block in blocks:
            bbox = block.get("bbox")
            if not bbox:
                filtered_blocks.append(block)
                continue

            # A block must lie ENTIRELY inside the zone to be furniture. Testing only the
            # near edge -- does the block *start* above header_height -- deletes any body
            # paragraph that happens to begin near the top margin, and takes the rest of
            # the page with it: on an FCC filing whose body opened 4pt below the running
            # head, the whole opening paragraph of every page was dropped. Real furniture
            # is always fully contained, because the zone is derived from its own far edge.
            if header_zone > 0 and bbox[3] <= header_zone:
                continue  # Skip this block

            if footer_zone > 0 and bbox[1] >= (page_height - footer_zone):
                continue  # Skip this block

            filtered_blocks.append(block)

        return filtered_blocks

    def _merge_columns_for_reading_order(self, columns: list[list[dict]]) -> list[dict]:
        """Merge multiple columns into proper reading order.

        For multi-column layouts, the standard reading order is column-by-column:
        read the entire left column top-to-bottom, then move to the right column
        and read it top-to-bottom. This matches how PyMuPDF naturally orders blocks
        and is the expected behavior for most multi-column documents.

        Parameters
        ----------
        columns : list[list[dict]]
            List of columns, where each column is a list of blocks

        Returns
        -------
        list[dict]
            Merged list of blocks in proper reading order

        """
        if len(columns) <= 1:
            # Single column or empty, just return flattened
            return [block for col in columns for block in col]

        # Sort each column by y-coordinate (top to bottom)
        # Then concatenate: all of column 0, then all of column 1, etc.
        result = []
        for column in columns:
            sorted_column = sorted(column, key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
            result.extend(sorted_column)

        return result

    def _is_list_item_paragraph(self, paragraph: AstParagraph) -> bool:
        """Check if paragraph starts with a list marker.

        Parameters
        ----------
        paragraph : AstParagraph
            Paragraph to check

        Returns
        -------
        bool
            True if paragraph starts with list marker

        """
        if not paragraph.content:
            return False

        def extract_text(nodes: list[Node]) -> str:
            """Recursively extract text from nodes."""
            text_parts = []
            for node in nodes:
                if isinstance(node, Text):
                    text_parts.append(node.content)
                elif hasattr(node, "content") and isinstance(node.content, list):
                    text_parts.append(extract_text(node.content))
            return "".join(text_parts)

        full_text = extract_text(paragraph.content)
        is_list, _ = self._is_valid_list_marker(full_text)
        return is_list

    def _determine_list_level_from_x(self, x_coord: float, x_levels: dict[int, float]) -> int:
        """Determine the nesting level of a list item based on its x-coordinate.

        Parameters
        ----------
        x_coord : float
            The x-coordinate of the list item
        x_levels : dict
            Dictionary mapping level numbers to representative x-coordinates

        Returns
        -------
        int
            The nesting level (0-based)

        Notes
        -----
        X-coordinates within 5 points of each other are considered the same level.

        """
        LEVEL_THRESHOLD = 5.0

        # Check if x_coord matches an existing level
        for level, level_x in x_levels.items():
            if abs(x_coord - level_x) < LEVEL_THRESHOLD:
                return level

        # New level - assign it the next available level number
        new_level = len(x_levels)
        x_levels[new_level] = x_coord
        return new_level

    def _apply_list_indentation(
        self, paragraph: AstParagraph, current_bbox: tuple[float, float, float, float], first_list_item_x: float
    ) -> None:
        """Store bbox information for later use in nested list detection.

        Parameters
        ----------
        paragraph : AstParagraph
            Paragraph to process
        current_bbox : tuple
            Current bounding box
        first_list_item_x : float
            X-coordinate of first list item (unused, kept for API compatibility)

        Notes
        -----
        This method no longer adds manual spacing. List nesting is now handled
        structurally in _convert_paragraphs_to_lists using x-coordinate data.

        """
        # No-op: nesting is now handled structurally, not via spacing
        pass

    def _should_merge_with_accumulated(
        self,
        current_bbox: tuple[float, float, float, float] | None,
        last_bbox_bottom: float | None,
        accumulated_content: list[Node],
        is_list_item: bool,
        last_was_list_item: bool,
        merge_threshold: float,
        current_metadata: dict | None = None,
        last_metadata: dict | None = None,
    ) -> bool:
        """Determine if current paragraph should merge with accumulated content.

        Parameters
        ----------
        current_bbox : tuple or None
            Current paragraph bounding box
        last_bbox_bottom : float or None
            Bottom y-coordinate of last paragraph
        accumulated_content : list of Node
            Accumulated content so far
        is_list_item : bool
            Whether current paragraph is a list item
        last_was_list_item : bool
            Whether last paragraph was a list item
        merge_threshold : float
            Threshold for vertical gap merging
        current_metadata : dict or None, optional
            Metadata from current paragraph's source location
        last_metadata : dict or None, optional
            Metadata from last paragraph's source location

        Returns
        -------
        bool
            True if should merge

        """
        # Check metadata for list markers first (more reliable than text-based detection)
        current_is_list = (current_metadata and current_metadata.get("is_list_item", False)) or is_list_item
        last_is_list = (last_metadata and last_metadata.get("is_list_item", False)) or last_was_list_item

        # Don't merge list items with anything
        if current_is_list or last_is_list:
            return False

        # If bbox information is missing, don't merge to be safe
        if not current_bbox or last_bbox_bottom is None:
            return not accumulated_content

        # Must have accumulated content and valid bbox info
        if not accumulated_content:
            return True

        # Calculate vertical gap
        current_bbox_top = current_bbox[1]
        vertical_gap = current_bbox_top - last_bbox_bottom

        # Only merge if gap is small
        return vertical_gap < merge_threshold

    def _merge_rotated_paragraphs(self, nodes: list[Node]) -> list[Node]:
        """Merge consecutive paragraphs that came from same-direction rotated runs.

        Each rotated paragraph is tagged with its rotation key in
        ``source_location.metadata['rotated']`` by :meth:`_flush_rotated_text`.
        This pass joins adjacent paragraphs with the same key (which can be
        produced by separate PyMuPDF blocks within a column) and appends the
        rotation marker once per merged run when ``annotate_rotated_text`` is on.
        """
        if not nodes:
            return nodes

        merged: list[Node] = []
        pending_text: list[str] = []
        pending_key: str | None = None
        pending_loc: SourceLocation | None = None

        def flush() -> None:
            nonlocal pending_text, pending_key, pending_loc
            if pending_text:
                combined = " ".join(pending_text)
                if self.options.annotate_rotated_text and pending_key:
                    combined += format_rotation_note(pending_key)
                merged.append(AstParagraph(content=[Text(content=combined)], source_location=pending_loc))
            pending_text = []
            pending_key = None
            pending_loc = None

        for node in nodes:
            rot_key: str | None = None
            if isinstance(node, AstParagraph) and node.source_location and node.source_location.metadata:
                rot_key = node.source_location.metadata.get("rotated") or None

            if rot_key and isinstance(node, AstParagraph):
                text = "".join(c.content for c in node.content if isinstance(c, Text))
                if pending_key is not None and pending_key != rot_key:
                    flush()
                if pending_key is None:
                    pending_key = rot_key
                    pending_loc = node.source_location
                pending_text.append(text)
            else:
                flush()
                merged.append(node)
        flush()
        return merged

    def _merge_adjacent_paragraphs(self, nodes: list[Node]) -> list[Node]:
        """Merge consecutive paragraph nodes that should be combined.

        In multi-column layouts, PyMuPDF often creates separate blocks for each
        line of text. This results in many small paragraph nodes that should be
        merged into cohesive paragraphs. This method combines consecutive
        Paragraph nodes that have small vertical gaps (< 10 points), indicating
        they're part of the same logical paragraph.

        Parameters
        ----------
        nodes : list of Node
            List of AST nodes (paragraphs, headings, tables, etc.)

        Returns
        -------
        list of Node
            List of nodes with consecutive paragraphs merged

        Notes
        -----
        Only Paragraph nodes with small vertical gaps are merged. Paragraphs
        with larger gaps (>= 10 points) are kept separate. Headings, code blocks,
        tables, and other block-level elements act as natural paragraph boundaries.

        This method requires bbox information to be stored in SourceLocation.metadata['bbox'].
        If bbox information is not available, paragraphs without bbox are not merged.

        """
        if not nodes:
            return nodes

        MERGE_THRESHOLD = 5.0

        merged: list[Node] = []
        accumulated_content: list[Node] = []
        last_source_location: SourceLocation | None = None
        last_bbox_bottom: float | None = None
        last_was_list_item: bool = False
        last_metadata: dict | None = None
        first_list_item_x: float | None = None

        for node in nodes:
            if isinstance(node, AstParagraph):
                current_bbox = None
                current_metadata = None
                if node.source_location and node.source_location.metadata:
                    current_bbox = node.source_location.metadata.get("bbox")
                    current_metadata = node.source_location.metadata

                is_list_item = self._is_list_item_paragraph(node)

                # Handle list item indentation
                if is_list_item and current_bbox:
                    if first_list_item_x is None:
                        first_list_item_x = current_bbox[0]
                    self._apply_list_indentation(node, current_bbox, first_list_item_x)

                # Determine if we should merge
                should_merge = self._should_merge_with_accumulated(
                    current_bbox,
                    last_bbox_bottom,
                    accumulated_content,
                    is_list_item,
                    last_was_list_item,
                    MERGE_THRESHOLD,
                    current_metadata,
                    last_metadata,
                )

                if should_merge:
                    # Merge: accumulate content
                    if accumulated_content and node.content:
                        accumulated_content.append(Text(content=" "))
                    accumulated_content.extend(node.content)
                    if last_source_location is None:
                        last_source_location = node.source_location
                    if current_bbox:
                        last_bbox_bottom = current_bbox[3]
                    last_was_list_item = is_list_item
                    last_metadata = current_metadata
                else:
                    # Don't merge: flush accumulated content
                    if accumulated_content:
                        merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))
                    accumulated_content = list(node.content)
                    last_source_location = node.source_location
                    last_bbox_bottom = current_bbox[3] if current_bbox else None
                    last_was_list_item = is_list_item
                    last_metadata = current_metadata
                    if not is_list_item:
                        first_list_item_x = None
            else:
                # Non-paragraph node: flush and reset
                if accumulated_content:
                    merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))
                    accumulated_content = []
                    last_source_location = None
                    last_bbox_bottom = None
                    last_was_list_item = False
                    last_metadata = None
                    first_list_item_x = None
                merged.append(node)

        # Flush remaining content
        if accumulated_content:
            merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))

        return merged

    @staticmethod
    def _is_valid_list_marker(text: str) -> tuple[bool, str | None]:
        """Check if text starts with a valid list marker.

        Parameters
        ----------
        text : str
            Text to check for list markers

        Returns
        -------
        tuple[bool, str | None]
            (is_list_item, list_type) where list_type is "ordered", "unordered", or None

        Notes
        -----
        This function is more conservative about detecting list markers to avoid false positives:
        - Letter "o" must be followed by a space to be treated as a marker (avoids "office", "online", etc.)
        - Numbered markers must be followed by space (avoids dates like "2024")

        """
        if not text:
            return False, None

        stripped = text.lstrip()
        if not stripped:
            return False, None

        first_char = stripped[0]

        # Check for bullet markers - but be careful with "o"
        # Include EN DASH (–, U+2013) and EM DASH (—, U+2014) which are commonly used in PDFs
        if first_char in ("-", "\u2013", "\u2014", "*", "+", "•", "◦", "▪", "▫"):
            return True, "unordered"

        # Special handling for lowercase "o" - only treat as marker if followed by space
        if first_char == "o":
            # Must have at least 2 characters and second must be space
            if len(stripped) >= 2 and stripped[1] == " ":
                return True, "unordered"
            else:
                return False, None

        # Check for numbered list markers (1. or 1) followed by space)
        # More robust: require space after marker to avoid matching dates/numbers
        match = re.match(r"^\s*(\d+)[\.\)]\s", text)
        if match:
            return True, "ordered"

        return False, None

    def _detect_list_marker(self, para: AstParagraph) -> tuple[bool, str | None]:
        """Detect if a paragraph is a list item and return its type.

        Parameters
        ----------
        para : AstParagraph
            The paragraph to check

        Returns
        -------
        tuple[bool, str | None]
            A tuple of (is_list_item, list_type) where list_type is
            "ordered", "unordered", or None

        """
        full_text = ""
        for node in para.content:
            if isinstance(node, Text):
                full_text = node.content
                break

        return self._is_valid_list_marker(full_text)

    def _extract_list_item_x_coord(self, node: AstParagraph) -> float | None:
        """Extract x-coordinate from a paragraph's bbox metadata.

        Parameters
        ----------
        node : AstParagraph
            The paragraph node

        Returns
        -------
        float | None
            The x-coordinate if available, None otherwise

        """
        if node.source_location and node.source_location.metadata:
            bbox = node.source_location.metadata.get("bbox")
            if bbox and len(bbox) >= 1:
                return bbox[0]
        return None

    def _strip_list_marker(self, para: AstParagraph) -> list[Node]:
        """Remove list marker from paragraph content and return cleaned content.

        Parameters
        ----------
        para : AstParagraph
            The paragraph containing a list marker

        Returns
        -------
        list[Node]
            Content nodes with the list marker removed

        """
        full_text = ""
        for node in para.content:
            if isinstance(node, Text):
                full_text = node.content
                break

        # Use the robust marker detection to validate this is actually a list item
        is_list, list_type = self._is_valid_list_marker(full_text)
        if not is_list:
            # Not a valid list marker, return content as-is
            return list(para.content)

        # Determine marker and strip it
        stripped = full_text.lstrip()
        marker_end = 0

        if list_type == "unordered":
            # Bullet marker - find where it ends (marker + space)
            marker_char = stripped[0]
            marker_end = full_text.index(marker_char) + 1
            # Skip following space if present
            if marker_end < len(full_text) and full_text[marker_end] == " ":
                marker_end += 1
        elif list_type == "ordered":
            # Numbered marker - use regex to find end
            match = re.match(r"^(\s*)(\d+[\.\)])\s", full_text)
            if match:
                marker_end = match.end()

        # Create new content without the marker
        new_content: list[Node] = []
        if marker_end > 0:
            # Remove marker from first text node
            for i, node in enumerate(para.content):
                if i == 0 and isinstance(node, Text):
                    remaining_text = node.content[marker_end:]
                    if remaining_text:
                        new_content.append(Text(content=remaining_text))
                else:
                    new_content.append(node)
        else:
            new_content = list(para.content)

        return new_content

    def _finalize_pending_lists(self, list_stack: list[tuple[str, int, list[ListItem]]], result: list[Node]) -> None:
        """Finalize all lists in the stack, nesting them properly.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of (list_type, level, items) tuples
        result : list[Node]
            Result list to append finalized top-level list to

        """
        while len(list_stack) > 1:
            # Pop deeper list
            deeper_type, deeper_level, deeper_items = list_stack.pop()
            nested_list = List(ordered=(deeper_type == "ordered"), items=deeper_items, tight=True)

            # Add to parent's last item
            parent_items = list_stack[-1][2]
            if parent_items:
                parent_items[-1].children.append(nested_list)

        # Add the top-level list to results
        if list_stack:
            list_type, level, items = list_stack.pop()
            result.append(List(ordered=(list_type == "ordered"), items=items, tight=True))

    def _handle_empty_stack(
        self, list_stack: list[tuple[str, int, list[ListItem]]], list_type: str, level: int, item_node: ListItem
    ) -> None:
        """Handle adding a list item when stack is empty.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples (will be empty when called)
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level
        item_node : ListItem
            The list item to add

        """
        list_stack.append((list_type, level, [item_node]))

    def _handle_deeper_nesting(
        self, list_stack: list[tuple[str, int, list[ListItem]]], list_type: str, level: int, item_node: ListItem
    ) -> None:
        """Handle adding a list item at a deeper nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level (greater than current stack top level)
        item_node : ListItem
            The list item to add

        """
        list_stack.append((list_type, level, [item_node]))

    def _handle_shallower_level(
        self,
        list_stack: list[tuple[str, int, list[ListItem]]],
        list_type: str,
        level: int,
        item_node: ListItem,
        result: list[Node],
    ) -> None:
        """Handle adding a list item at a shallower nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level (less than current stack top level)
        item_node : ListItem
            The list item to add
        result : list[Node]
            Result list for finalized lists

        """
        # Going back to shallower level - finalize deeper lists
        while list_stack and list_stack[-1][1] > level:
            popped_type, popped_level, popped_items = list_stack.pop()
            nested_list = List(ordered=(popped_type == "ordered"), items=popped_items, tight=True)

            # Add nested list to parent's last item
            if list_stack:
                parent_items = list_stack[-1][2]
                if parent_items:
                    parent_items[-1].children.append(nested_list)

        # Check if we're at the same level and type
        if list_stack and list_stack[-1][1] == level:
            if list_stack[-1][0] == list_type:
                # Same level and type - add item
                list_stack[-1][2].append(item_node)
            else:
                # Different type at same level - finalize old, start new
                old_type, old_level, old_items = list_stack.pop()
                result.append(List(ordered=(old_type == "ordered"), items=old_items, tight=True))
                list_stack.append((list_type, level, [item_node]))
        else:
            # Start new list at this level
            list_stack.append((list_type, level, [item_node]))

    def _handle_same_level(
        self,
        list_stack: list[tuple[str, int, list[ListItem]]],
        list_type: str,
        item_node: ListItem,
        result: list[Node],
        current_type: str,
        current_level: int,
    ) -> None:
        """Handle adding a list item at the same nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        item_node : ListItem
            The list item to add
        result : list[Node]
            Result list for finalized lists
        current_type : str
            Current list type from stack top
        current_level : int
            Current nesting level from stack top

        """
        if current_type == list_type:
            # Same type - add to current list
            list_stack[-1][2].append(item_node)
        else:
            # Different type at same level - finalize old, start new
            old_type, old_level, old_items = list_stack.pop()
            result.append(List(ordered=(old_type == "ordered"), items=old_items, tight=True))
            list_stack.append((list_type, current_level, [item_node]))

    def _convert_paragraphs_to_lists(self, nodes: list[Node]) -> list[Node]:
        """Convert paragraphs with list markers into List/ListItem structures with proper nesting.

        Parameters
        ----------
        nodes : list of Node
            AST nodes that may contain list marker paragraphs

        Returns
        -------
        list of Node
            Nodes with list paragraphs converted to nested List structures

        Notes
        -----
        Uses x-coordinate information from bbox metadata to determine nesting levels.
        Implements a stack-based algorithm to build properly nested list structures.

        """
        result: list[Node] = []
        list_stack: list[tuple[str, int, list[ListItem]]] = []
        x_levels: dict[int, float] = {}

        for node in nodes:
            if isinstance(node, AstParagraph):
                # Check if this is a list item
                is_list_item, list_type = self._detect_list_marker(node)

                if is_list_item and list_type:
                    # Extract x-coordinate and determine nesting level
                    x_coord = self._extract_list_item_x_coord(node)
                    level = 0
                    if x_coord is not None:
                        level = self._determine_list_level_from_x(x_coord, x_levels)

                    # Create list item with cleaned content
                    cleaned_content = self._strip_list_marker(node)
                    item_node = ListItem(children=[AstParagraph(content=cleaned_content)])

                    # Handle list stack based on level
                    if not list_stack:
                        self._handle_empty_stack(list_stack, list_type, level, item_node)
                    else:
                        current_type, current_level, current_items = list_stack[-1]

                        if level > current_level:
                            self._handle_deeper_nesting(list_stack, list_type, level, item_node)
                        elif level < current_level:
                            self._handle_shallower_level(list_stack, list_type, level, item_node, result)
                        else:
                            self._handle_same_level(
                                list_stack, list_type, item_node, result, current_type, current_level
                            )
                else:
                    # Not a list item - finalize any pending lists
                    self._finalize_pending_lists(list_stack, result)
                    x_levels.clear()
                    result.append(node)
            else:
                # Non-paragraph - finalize any pending lists
                self._finalize_pending_lists(list_stack, result)
                x_levels.clear()
                result.append(node)

        # Finalize any remaining lists
        self._finalize_pending_lists(list_stack, result)

        return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pdf",
    extensions=[".pdf"],
    mime_types=["application/pdf"],
    magic_bytes=[
        (b"%PDF", 0),
    ],
    parser_class=PdfToAstConverter,
    renderer_class="all2md.renderers.pdf.PdfRenderer",
    renders_as_string=False,
    parser_required_packages=[("pymupdf", "fitz", ">=1.26.4")],
    renderer_required_packages=[("reportlab", "reportlab", ">=4.0.0")],
    optional_packages=[
        ("pytesseract", "pytesseract"),
        ("easyocr", "easyocr"),
        ("Pillow", "PIL"),
    ],
    import_error_message=("PDF conversion requires 'PyMuPDF'. Install with: pip install pymupdf"),
    parser_options_class=PdfOptions,
    renderer_options_class="all2md.options.pdf.PdfRendererOptions",
    description="Convert PDF documents to/from AST with table detection and optional OCR support",
    priority=10,
)
