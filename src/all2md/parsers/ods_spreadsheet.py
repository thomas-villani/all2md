#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/ods_spreadsheet.py
"""ODS spreadsheet to AST converter.

This module provides conversion from ODS (OpenDocument Spreadsheet) files
to AST representation. It replaces the combined spreadsheet parser with a
focused ODS parser.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, Any, Optional, Union, cast

from all2md.ast import (
    Alignment,
    Document,
    Heading,
    HTMLInline,
    Node,
    Paragraph,
    Text,
)
from all2md.constants import DEPS_ODF
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError
from all2md.options.ods import OdsSpreadsheetOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import create_attachment_sequencer, process_attachment
from all2md.utils.decorators import requires_dependencies
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.parser_helpers import attachment_result_to_image_node
from all2md.utils.spreadsheet import (
    build_table_ast,
    sanitize_cell_text,
    transform_header_case,
    trim_columns,
    trim_rows,
)

logger = logging.getLogger(__name__)


def _extract_ods_images(
    doc: Any, table: Any, base_filename: str, attachment_sequencer: Any, options: Any
) -> tuple[list[Node], dict[str, str]]:
    """Extract images from an ODS table and convert to Image AST nodes.

    Parameters
    ----------
    doc : Any
        ODS document object
    table : Any
        ODS table object
    base_filename : str
        Base filename for generating image filenames
    attachment_sequencer : callable
        Sequencer for generating unique attachment filenames
    options : OdsSpreadsheetOptions
        Conversion options

    Returns
    -------
    tuple[list[Node], dict[str, str]]
        Tuple of (list of Image AST nodes, footnotes dict)

    """
    from odf.draw import Frame
    from odf.draw import Image as OdfImage

    images: list[Node] = []
    collected_footnotes: dict[str, str] = {}

    try:
        # Find all image frames in the table
        frames = table.getElementsByType(Frame)

        for frame in frames:
            try:
                # Get the image element
                odf_images = frame.getElementsByType(OdfImage)
                if not odf_images:
                    continue

                for odf_img in odf_images:
                    # Get the image reference (href)
                    href = odf_img.getAttribute("href")
                    if not href:
                        continue

                    # Extract image data from document's Pictures directory
                    image_bytes = None
                    try:
                        # Images are stored as Pictures/imagename.ext in the ODF package
                        # The href is like Pictures/10000000000001F4000001F4ABC123.png
                        if hasattr(doc, "Pictures") and href in doc.Pictures:
                            image_bytes = doc.Pictures[href]
                        elif hasattr(doc, "getMediaByPath"):
                            image_bytes = doc.getMediaByPath(href)
                    except Exception:
                        logger.debug(f"Could not access image {href} from ODS document")

                    if not image_bytes:
                        continue

                    # Determine file extension from href
                    extension = "png"  # default
                    if "." in href:
                        extension = href.rsplit(".", 1)[-1].lower()

                    # Generate filename
                    image_filename, _ = attachment_sequencer(
                        base_stem=base_filename, format_type="general", extension=extension, attachment_type="img"
                    )

                    # Get alt text from frame or image
                    alt_text = frame.getAttribute("name") or "image"

                    # Process attachment
                    result = process_attachment(
                        attachment_data=image_bytes,
                        attachment_name=image_filename,
                        alt_text=alt_text,
                        attachment_mode=options.attachment_mode,
                        attachment_output_dir=options.attachment_output_dir,
                        attachment_base_url=options.attachment_base_url,
                        is_image=True,
                        alt_text_mode=options.alt_text_mode,
                    )

                    # Collect footnote info if present
                    if result.get("footnote_label") and result.get("footnote_content"):
                        collected_footnotes[result["footnote_label"]] = result["footnote_content"]

                    # Create Image AST node using helper
                    image_node = attachment_result_to_image_node(result, fallback_alt_text=alt_text)
                    if image_node:
                        images.append(image_node)

            except Exception as e:
                logger.debug(f"Failed to extract image from ODS: {e!r}")
                continue

    except Exception as e:
        logger.debug(f"Error accessing ODS images: {e!r}")

    return images, collected_footnotes


def _extract_ods_charts(table: Any, base_filename: str, options: Any) -> list[Node]:
    """Extract charts from an ODS table and convert to AST nodes.

    Parameters
    ----------
    table : Any
        ODS table object
    base_filename : str
        Base filename for context
    options : OdsSpreadsheetOptions
        Conversion options

    Returns
    -------
    list[Node]
        List of AST nodes (Tables or Paragraphs) representing charts

    """
    chart_nodes: list[Node] = []

    if options.chart_mode == "skip":
        return chart_nodes

    try:
        from odf.draw import Frame, Object

        # Find all object frames (charts are embedded as objects)
        frames = table.getElementsByType(Frame)

        for frame in frames:
            try:
                objects = frame.getElementsByType(Object)
                if not objects:
                    continue

                for obj in objects:
                    # Check if this is a chart object
                    href = obj.getAttribute("href")
                    if not href or "Object" not in str(href):
                        continue

                    if options.chart_mode == "data":
                        # For now, add a placeholder paragraph indicating a chart was found
                        # Full chart data extraction from ODS is complex as it requires
                        # parsing the embedded chart subdocument
                        chart_nodes.append(
                            Paragraph(
                                content=[
                                    Text(content=("[Chart detected - data extraction not yet " "implemented for ODS]"))
                                ]
                            )
                        )

            except Exception as e:
                logger.debug(f"Failed to extract chart from ODS: {e!r}")
                continue

    except Exception as e:
        logger.debug(f"Error accessing ODS charts: {e!r}")

    return chart_nodes


class OdsSpreadsheetToAstConverter(BaseParser):
    """Convert ODS spreadsheet files to AST representation.

    This converter handles ODS (OpenDocument Spreadsheet) format by building
    Table nodes from spreadsheet data.

    Parameters
    ----------
    options : OdsSpreadsheetOptions or None
        Conversion options

    """

    def __init__(
        self, options: Optional[OdsSpreadsheetOptions] = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the ODS spreadsheet parser with options and progress callback."""
        BaseParser._validate_options_type(options, OdsSpreadsheetOptions, "ods")
        options = options or OdsSpreadsheetOptions()
        super().__init__(options, progress_callback)
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

        # Type hint for IDE
        self.options: OdsSpreadsheetOptions = options

    @requires_dependencies("ods", DEPS_ODF)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse ODS spreadsheet into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input ODS file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed spreadsheet structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid format or corruption
        DependencyError
            If required dependencies are not installed
        ValidationError
            If input data is invalid or inaccessible

        """
        from odf import opendocument

        # Validate ZIP archive security for all input types
        self._validate_zip_security(input_data, suffix=".ods")

        # Load ODS document
        try:
            doc_input, input_type = validate_and_convert_input(
                input_data, supported_types=["path-like", "file-like", "bytes"], require_binary=True
            )
            doc = opendocument.load(doc_input)
        except Exception as e:
            raise MalformedFileError(f"Failed to parse ODS file: {e!r}", original_error=e) from e

        return self.ods_to_ast(doc)

    def _select_sheets(self, tables: list[Any], sheet_names: list[str]) -> tuple[list[Any], list[str]]:
        """Select sheets based on options.

        Parameters
        ----------
        tables : list of Any
            All ODF table objects
        sheet_names : list of str
            Names of all sheets

        Returns
        -------
        tuple[list[Any], list[str]]
            Tuple of (selected tables, selected names)

        """
        selected_tables = []
        selected_names = []

        if isinstance(self.options.sheets, list):
            for i, name in enumerate(sheet_names):
                if name in self.options.sheets:
                    selected_tables.append(tables[i])
                    selected_names.append(name)
        elif isinstance(self.options.sheets, str):
            pattern = re.compile(self.options.sheets)
            for i, name in enumerate(sheet_names):
                if pattern.search(name):
                    selected_tables.append(tables[i])
                    selected_names.append(name)
        else:
            selected_tables = tables
            selected_names = sheet_names

        return selected_tables, selected_names

    def _extract_rows_from_table(self, table: Any) -> list[list[str]]:
        """Extract raw row data from ODF table.

        Parameters
        ----------
        table : Any
            ODF table object

        Returns
        -------
        list[list[str]]
            Raw rows with cell data

        """
        from odf.table import TableCell, TableRow

        rows_elem = list(table.getElementsByType(TableRow))
        raw_rows = []

        for row in rows_elem:
            cells = list(row.getElementsByType(TableCell))
            row_data = []

            for cell in cells:
                cell_text = ""
                for node in cell.childNodes:
                    if hasattr(node, "data"):
                        cell_text += str(node.data)
                    elif hasattr(node, "childNodes"):
                        for subnode in node.childNodes:
                            if hasattr(subnode, "data"):
                                cell_text += str(subnode.data)

                # Handle cell repetition
                repeat_count = 1
                try:
                    repeat_attr = cell.getAttribute("numbercolumnsrepeated")
                    if repeat_attr:
                        repeat_count = int(repeat_attr)
                except (ValueError, TypeError):
                    pass

                for _ in range(repeat_count):
                    row_data.append(cell_text.strip() if cell_text else "")

            raw_rows.append(row_data)

        # Remove empty trailing rows
        while raw_rows and all(not cell for cell in raw_rows[-1]):
            raw_rows.pop()

        return raw_rows

    def _process_sheet_data(self, raw_rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
        """Process header and data rows with limits and trimming.

        Parameters
        ----------
        raw_rows : list[list[str]]
            Raw row data from table

        Returns
        -------
        tuple[list[str], list[list[str]]]
            Tuple of (header, data_rows)

        """
        if not raw_rows:
            return [], []

        # Apply row limits
        if self.options.max_rows is not None:
            total_available = len(raw_rows) - 1
            if total_available > self.options.max_rows:
                raw_rows = raw_rows[: self.options.max_rows + 1]

        # Extract header and data
        if self.options.has_header:
            header = raw_rows[0]
            data_rows = raw_rows[1:] if len(raw_rows) > 1 else []
        else:
            if raw_rows:
                max_cols = max(len(row) for row in raw_rows)
                if self.options.max_cols is not None:
                    max_cols = min(max_cols, self.options.max_cols)
                header = [f"Column {i + 1}" for i in range(max_cols)]
                data_rows = raw_rows
            else:
                header = []
                data_rows = []

        # Apply column limits
        if self.options.max_cols is not None:
            header = header[: self.options.max_cols]
            data_rows = [row[: self.options.max_cols] for row in data_rows]

        # Apply row/column trimming
        all_rows = [header] + data_rows if header else data_rows
        all_rows = trim_rows(all_rows, cast(Any, self.options.trim_empty))
        all_rows = trim_columns(all_rows, cast(Any, self.options.trim_empty))

        if not all_rows:
            return [], []

        # Sanitize all cell content
        header = [sanitize_cell_text(cell, self.options.preserve_newlines_in_cells) for cell in all_rows[0]]
        data_rows = [
            [sanitize_cell_text(cell, self.options.preserve_newlines_in_cells) for cell in row] for row in all_rows[1:]
        ]

        # Apply header case transformation
        header = transform_header_case(header, self.options.header_case)

        # Ensure all rows have same number of columns
        if header:
            max_cols = len(header)
            data_rows = [row + [""] * (max_cols - len(row)) for row in data_rows]

        return header, data_rows

    def ods_to_ast(self, doc: Any) -> Document:
        """Convert ODS document to AST Document.

        Parameters
        ----------
        doc : Any
            ODS document object

        Returns
        -------
        Document
            AST document with table nodes

        """
        from odf.table import Table as OdfTable

        children: list[Node] = []

        # Extract metadata
        metadata = self.extract_metadata(doc)

        # Determine base filename for attachments
        base_filename = "spreadsheet"
        try:
            if hasattr(doc, "meta"):
                from odf.dc import Title

                titles = doc.meta.getElementsByType(Title)
                if titles and len(titles) > 0:
                    title_text = str(titles[0]).strip()
                    if title_text:
                        base_filename = title_text.replace(" ", "_")
        except Exception:
            pass

        # Create attachment sequencer for unique filenames
        attachment_sequencer = create_attachment_sequencer()

        body = doc.body
        tables = list(body.getElementsByType(OdfTable)) if body else []

        if not tables:
            return Document(children=[], metadata=metadata.to_dict())

        # Filter sheets based on options
        sheet_names = [table.getAttribute("name") or f"Sheet{i + 1}" for i, table in enumerate(tables)]
        selected_tables, selected_names = self._select_sheets(tables, sheet_names)

        # Process each selected sheet
        for table, name in zip(selected_tables, selected_names, strict=False):
            # Add sheet title if requested
            if self.options.include_sheet_titles:
                children.append(Heading(level=2, content=[Text(content=name)]))

            # Extract rows
            raw_rows = self._extract_rows_from_table(table)
            if not raw_rows:
                continue

            # Process header and data
            header, data_rows = self._process_sheet_data(raw_rows)
            if not header:
                continue

            # Build table
            alignments: list[Alignment] = cast(list[Alignment], ["center"] * len(header))
            table_node = build_table_ast(header, data_rows, alignments)
            children.append(table_node)

            # Add truncation indicator if needed
            truncated = (self.options.max_rows is not None and len(raw_rows) - 1 > self.options.max_rows) or (
                self.options.max_cols is not None and any(len(row) > self.options.max_cols for row in raw_rows)
            )
            if truncated:
                children.append(Paragraph(content=[HTMLInline(content=f"*{self.options.truncation_indicator}*")]))

            # Extract images from table
            table_images, table_footnotes = _extract_ods_images(
                doc, table, base_filename, attachment_sequencer, self.options
            )
            self._attachment_footnotes.update(table_footnotes)
            children.extend(table_images)

            # Extract charts from table
            table_charts = _extract_ods_charts(table, base_filename, self.options)
            children.extend(table_charts)

        # Append attachment footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        return Document(children=children, metadata=metadata.to_dict())

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from ODS document.

        Parameters
        ----------
        document : Any
            ODS document object

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Try to extract metadata from document properties
        try:
            if hasattr(document, "meta"):
                from odf.dc import Creator, Description, Title
                from odf.meta import CreationDate

                meta = document.meta

                # Title
                titles = meta.getElementsByType(Title)
                if titles and len(titles) > 0:
                    metadata.title = str(titles[0]).strip()

                # Creator
                creators = meta.getElementsByType(Creator)
                if creators and len(creators) > 0:
                    metadata.author = str(creators[0]).strip()

                # Description
                descriptions = meta.getElementsByType(Description)
                if descriptions and len(descriptions) > 0:
                    metadata.subject = str(descriptions[0]).strip()

                # Creation date
                creation_dates = meta.getElementsByType(CreationDate)
                if creation_dates and len(creation_dates) > 0:
                    metadata.creation_date = str(creation_dates[0]).strip()
        except Exception:
            pass

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="ods",
    extensions=[".ods"],
    mime_types=["application/vnd.oasis.opendocument.spreadsheet"],
    magic_bytes=[
        (b"PK\x03\x04", 0),
    ],
    parser_class=OdsSpreadsheetToAstConverter,
    renderer_class=None,
    parser_required_packages=[("odfpy", "odf", "")],
    renderer_required_packages=[],
    import_error_message="ODS conversion requires 'odfpy'. Install with: pip install odfpy",
    parser_options_class=OdsSpreadsheetOptions,
    renderer_options_class=None,
    description="Convert OpenDocument Spreadsheet files to Markdown tables",
    priority=6,
)
