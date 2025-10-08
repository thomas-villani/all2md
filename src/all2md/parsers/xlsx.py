#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/xlsx.py
"""XLSX to AST converter.

This module provides conversion from Excel XLSX files to AST representation.
It replaces the combined spreadsheet parser with a focused Excel parser.

"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import IO, Any, Iterable, Optional, Union, cast

from all2md.ast import (
    Alignment,
    Document,
    Heading,
    HTMLInline,
    Image,
    Node,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import create_attachment_sequencer, process_attachment
from all2md.utils.decorators import requires_dependencies
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.security import validate_zip_archive

logger = logging.getLogger(__name__)


def _sanitize_cell_text(text: Any, preserve_newlines: bool = False) -> str:
    """Convert any cell value to a safe string for AST Text node.

    Note: Markdown escaping is handled by the renderer, not here.
    We only normalize whitespace and convert to string.

    Parameters
    ----------
    text : Any
        Cell value to sanitize
    preserve_newlines : bool
        If True, preserve newlines as <br> tags; if False, replace with spaces

    Returns
    -------
    str
        Sanitized cell text

    """
    if text is None:
        s = ""
    else:
        s = str(text)

    # Handle newlines based on preserve_newlines option
    if preserve_newlines:
        # Keep line breaks as <br> tags
        s = s.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
    else:
        # Normalize whitespace/newlines inside cells
        s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    return s


def _format_link_or_text(cell: Any, text: str, preserve_newlines: bool = False) -> str:
    """Get cell text, checking for hyperlinks.

    Parameters
    ----------
    cell : Any
        Cell object (openpyxl)
    text : str
        Cell text value
    preserve_newlines : bool
        Whether to preserve newlines in cells

    Returns
    -------
    str
        Cell text (hyperlinks not yet supported in AST path)

    """
    # TODO: Support hyperlinks in table cells via Link nodes
    # For now, just return sanitized text
    return _sanitize_cell_text(text, preserve_newlines)


def _alignment_for_cell(cell: Any) -> Alignment:
    """Map an openpyxl cell alignment to alignment string.

    Parameters
    ----------
    cell : Any
        Cell object

    Returns
    -------
    Alignment
        Alignment: 'left', 'center', 'right', or 'center' (default)

    """
    try:
        align = getattr(cell, "alignment", None)
        if align and getattr(align, "horizontal", None):
            horiz = align.horizontal.lower()
            # Map Excel alignment to our alignment values
            alignment_map: dict[str, Alignment] = {
                "left": "left",
                "center": "center",
                "centre": "center",
                "right": "right",
                "general": "left",
                "justify": "left",
            }
            return alignment_map.get(horiz, "center")
    except Exception:
        pass

    return "center"


def _build_table_ast(
    header: list[str], rows: list[list[str]], alignments: list[Alignment]
) -> Table:
    """Build an AST Table from header, rows, and alignments.

    Parameters
    ----------
    header : list[str]
        Header row cells
    rows : list[list[str]]
        Data rows
    alignments : list[Alignment]
        Column alignments ('left', 'center', 'right')

    Returns
    -------
    Table
        AST Table node

    """
    # Build header row
    header_cells = [
        TableCell(content=[Text(content=cell)], alignment=alignments[i] if i < len(alignments) else "center")
        for i, cell in enumerate(header)
    ]
    header_row = TableRow(cells=header_cells, is_header=True)

    # Build data rows
    data_rows = []
    for row in rows:
        row_cells = [
            TableCell(content=[Text(content=cell)], alignment=alignments[i] if i < len(alignments) else "center")
            for i, cell in enumerate(row)
        ]
        data_rows.append(TableRow(cells=row_cells, is_header=False))

    # Table alignments are already the correct type
    table_alignments: list[Alignment | None] = list(alignments)

    return Table(header=header_row, rows=data_rows, alignments=table_alignments)


def _xlsx_iter_rows(sheet: Any, max_rows: int | None, max_cols: int | None) -> Iterable[list[Any]]:
    """Iterate rows of an openpyxl worksheet with optional truncation.

    Parameters
    ----------
    sheet : Any
        Openpyxl worksheet
    max_rows : int | None
        Maximum rows to read
    max_cols : int | None
        Maximum columns to read

    Yields
    ------
    list[Any]
        Row cells

    """
    row_iter = sheet.iter_rows(values_only=False)
    for r_idx, row in enumerate(row_iter, start=1):
        if max_rows is not None and r_idx > max_rows:
            break
        out_row = []
        for c_idx, cell in enumerate(row, start=1):
            if max_cols is not None and c_idx > max_cols:
                break
            out_row.append(cell)
        yield out_row


def _map_merged_cells(sheet: Any) -> dict[str, str]:
    """Return a map of cell.coordinate -> master.coordinate for merged ranges.

    Parameters
    ----------
    sheet : Any
        Openpyxl worksheet

    Returns
    -------
    dict[str, str]
        Mapping of cell coordinates to master cell coordinates

    """
    merged_map: dict[str, str] = {}
    try:
        ranges = getattr(sheet, "merged_cells", None)
        if not ranges or not getattr(ranges, "ranges", None):
            return merged_map

        for mcr in ranges.ranges:
            min_r, min_c, max_r, max_c = mcr.min_row, mcr.min_col, mcr.max_row, mcr.max_col
            master = sheet.cell(row=min_r, column=min_c).coordinate
            for rr in range(min_r, max_r + 1):
                for cc in range(min_c, max_c + 1):
                    coord = sheet.cell(row=rr, column=cc).coordinate
                    merged_map[coord] = master
    except Exception as e:
        logger.debug(f"Unable to compute merged cell map: {e!r}")
    return merged_map


def _extract_sheet_images(sheet: Any, base_filename: str, attachment_sequencer: Any, options: Any) -> list[Image]:
    """Extract images from an XLSX sheet and convert to Image AST nodes.

    Parameters
    ----------
    sheet : Any
        Openpyxl worksheet
    base_filename : str
        Base filename for generating image filenames
    attachment_sequencer : callable
        Sequencer for generating unique attachment filenames
    options : XlsxOptions
        Conversion options

    Returns
    -------
    list[Image]
        List of Image AST nodes

    """
    images: list[Image] = []

    try:
        # Access images through the sheet's _images attribute
        if not hasattr(sheet, '_images') or not sheet._images:
            return images

        for img in sheet._images:
            try:
                # Get image data
                image_bytes = img._data() if hasattr(img, '_data') and callable(img._data) else None
                if not image_bytes and hasattr(img, 'ref'):
                    # Try alternative method via relationships
                    image_part = img.ref
                    if hasattr(image_part, 'blob'):
                        image_bytes = image_part.blob

                if not image_bytes:
                    logger.debug("Could not extract image data from XLSX sheet")
                    continue

                # Determine file extension
                extension = "png"  # default
                if hasattr(img, 'format'):
                    extension = img.format.lower()
                elif hasattr(img, 'ref') and hasattr(img.ref, 'content_type'):
                    content_type = img.ref.content_type.lower()
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        extension = "jpg"
                    elif 'png' in content_type:
                        extension = "png"
                    elif 'gif' in content_type:
                        extension = "gif"

                # Generate filename
                image_filename, _ = attachment_sequencer(
                    base_stem=base_filename,
                    format_type="general",
                    extension=extension,
                    attachment_type="img"
                )

                # Get alt text
                alt_text = getattr(img, 'name', '') or getattr(img, 'title', '') or "image"

                # Process attachment
                url = process_attachment(
                    attachment_data=image_bytes,
                    attachment_name=image_filename,
                    alt_text=alt_text,
                    attachment_mode=options.attachment_mode,
                    attachment_output_dir=options.attachment_output_dir,
                    attachment_base_url=options.attachment_base_url,
                    is_image=True,
                    alt_text_mode=options.alt_text_mode,
                )

                # Create Image AST node
                if url:
                    images.append(Image(url=url, alt_text=alt_text))

            except Exception as e:
                logger.debug(f"Failed to extract image from XLSX: {e!r}")
                continue

    except Exception as e:
        logger.debug(f"Error accessing sheet images: {e!r}")

    return images


def _extract_sheet_charts(sheet: Any, base_filename: str, options: Any) -> list[Node]:
    """Extract charts from an XLSX sheet and convert to AST nodes.

    Parameters
    ----------
    sheet : Any
        Openpyxl worksheet
    base_filename : str
        Base filename for context
    options : XlsxOptions
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
        # Access charts through the sheet's _charts attribute or ChartSpace objects
        charts = []
        if hasattr(sheet, '_charts') and sheet._charts:
            charts = sheet._charts
        elif hasattr(sheet, 'charts') and sheet.charts:
            charts = sheet.charts

        if not charts:
            return chart_nodes

        for chart in charts:
            try:
                if options.chart_mode == "data":
                    # Extract chart data and convert to table
                    table_node = _chart_to_table_ast(chart)
                    if table_node:
                        chart_nodes.append(table_node)

            except Exception as e:
                logger.debug(f"Failed to extract chart from XLSX: {e!r}")
                continue

    except Exception as e:
        logger.debug(f"Error accessing sheet charts: {e!r}")

    return chart_nodes


def _chart_to_table_ast(chart: Any) -> Table | None:
    """Convert an XLSX chart to a Table AST node.

    Parameters
    ----------
    chart : Any
        Openpyxl chart object

    Returns
    -------
    Table | None
        Table AST node representing chart data, or None if extraction fails

    """
    try:
        # Extract chart title (for potential future use)
        # title = ""
        # if hasattr(chart, 'title') and chart.title:
        #     title = str(chart.title)

        # Extract series data
        series_data: list[tuple[str, list[Any]]] = []
        categories: list[str] = []

        if hasattr(chart, 'series') and chart.series:
            for series in chart.series:
                series_name = getattr(series, 'title', '') or f"Series {len(series_data) + 1}"
                if hasattr(series_name, 'v'):
                    series_name = str(series_name.v)

                # Extract values
                values = []
                if hasattr(series, 'values') and series.values:
                    values_ref = series.values
                    if hasattr(values_ref, 'numRef') and values_ref.numRef:
                        num_cache = values_ref.numRef.numCache
                        if num_cache and hasattr(num_cache, 'pt'):
                            values = [pt.v for pt in num_cache.pt if hasattr(pt, 'v')]

                series_data.append((str(series_name), values))

                # Extract categories from first series
                if not categories and hasattr(series, 'cat') and series.cat:
                    cat_ref = series.cat
                    if hasattr(cat_ref, 'strRef') and cat_ref.strRef:
                        str_cache = cat_ref.strRef.strCache
                        if str_cache and hasattr(str_cache, 'pt'):
                            categories = [str(pt.v) for pt in str_cache.pt if hasattr(pt, 'v')]

        if not series_data:
            return None

        # Build table with categories as first column
        header_cells = [TableCell(content=[Text(content="Category")], alignment="left")]
        for series_name, _ in series_data:
            header_cells.append(TableCell(content=[Text(content=series_name)], alignment="center"))
        header_row = TableRow(cells=header_cells, is_header=True)

        # Build data rows
        data_rows = []
        max_rows = max(len(values) for _, values in series_data) if series_data else 0
        for i in range(max_rows):
            category = categories[i] if i < len(categories) else f"Row {i + 1}"
            row_cells = [TableCell(content=[Text(content=category)], alignment="left")]

            for _, values in series_data:
                value = values[i] if i < len(values) else ""
                row_cells.append(TableCell(content=[Text(content=str(value))], alignment="center"))

            data_rows.append(TableRow(cells=row_cells, is_header=False))

        # Build alignments list with proper typing
        alignments: list[Alignment | None] = [cast(Alignment | None, "left")]
        alignments.extend([cast(Alignment | None, "center")] * len(series_data))

        return Table(header=header_row, rows=data_rows, alignments=alignments)

    except Exception as e:
        logger.debug(f"Failed to convert chart to table: {e!r}")
        return None


class XlsxToAstConverter(BaseParser):
    """Convert XLSX Excel files to AST representation.

    This converter handles XLSX (Excel) format by building Table nodes
    from spreadsheet data.

    Parameters
    ----------
    options : XlsxOptions or None
        Conversion options

    """

    def __init__(self, options: Any = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the XLSX parser with options and progress callback."""
        # Import here to avoid circular dependency
        from all2md.options import XlsxOptions

        options = options or XlsxOptions()
        super().__init__(options, progress_callback)

        # Type hint for IDE
        from all2md.options import XlsxOptions
        self.options: XlsxOptions = options

    @requires_dependencies("xlsx", [("openpyxl", "openpyxl", "")])
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse the XLSX file into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input Excel file to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw document bytes

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
        import openpyxl

        # Validate ZIP archive security for all input types
        if isinstance(input_data, (str, Path)):
            # Path/str inputs - validate directly
            validate_zip_archive(input_data)
        elif isinstance(input_data, bytes):
            # Bytes inputs - create temp file, validate, cleanup
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                tmp.write(input_data)
                tmp_path = tmp.name
            try:
                validate_zip_archive(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        elif hasattr(input_data, 'read'):
            # File-like inputs - read, validate, reset position
            original_position = input_data.tell() if hasattr(input_data, 'tell') else 0
            input_data.seek(0)
            data = input_data.read()
            input_data.seek(original_position)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                validate_zip_archive(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        # Load workbook
        try:
            doc_input, input_type = validate_and_convert_input(
                input_data, supported_types=["path-like", "file-like", "bytes"], require_binary=True
            )
            wb = openpyxl.load_workbook(doc_input, data_only=self.options.render_formulas)
        except Exception as e:
            raise MalformedFileError(
                f"Failed to parse XLSX file: {e!r}",
                original_error=e
            ) from e

        return self.xlsx_to_ast(wb)

    def xlsx_to_ast(self, workbook: Any) -> Document:
        """Convert an openpyxl workbook to AST Document.

        Parameters
        ----------
        workbook : Any
            Openpyxl workbook

        Returns
        -------
        Document
            AST document with table nodes

        """
        children: list[Node] = []

        # Extract metadata
        metadata = self.extract_metadata(workbook)

        # Determine base filename for attachments
        base_filename = "spreadsheet"
        try:
            if hasattr(workbook, 'properties') and workbook.properties and workbook.properties.title:
                base_filename = workbook.properties.title.replace(' ', '_')
        except Exception:
            pass

        # Create attachment sequencer for unique filenames
        attachment_sequencer = create_attachment_sequencer()

        # Select sheets
        sheet_names: list[str] = list(workbook.sheetnames)
        if isinstance(self.options.sheets, list):
            sheet_names = [n for n in sheet_names if n in self.options.sheets]
        elif isinstance(self.options.sheets, str):
            pattern = re.compile(self.options.sheets)
            sheet_names = [n for n in sheet_names if pattern.search(n)]

        if not sheet_names:
            return Document(children=[], metadata=metadata.to_dict())

        for sname in sheet_names:
            sheet = workbook[sname]

            # Add sheet title if requested
            if self.options.include_sheet_titles:
                # Create heading node
                children.append(Heading(level=2, content=[Text(content=sname)]))

            # Process sheet data
            merged_map = _map_merged_cells(sheet)

            raw_rows: list[list[Any]] = []
            for row in _xlsx_iter_rows(sheet, self.options.max_rows, self.options.max_cols):
                if all((cell.value is None) for cell in row):
                    raw_rows.append(row)
                else:
                    raw_rows.append(row)

            if not raw_rows:
                continue

            # Convert to strings and handle merged cells
            str_rows: list[list[str]] = []
            for row in raw_rows:
                out: list[str] = []
                for cell in row:
                    coord = getattr(cell, "coordinate", None)
                    if coord and coord in merged_map and merged_map[coord] != coord:
                        out.append("")
                    else:
                        out.append(_format_link_or_text(cell, cell.value, self.options.preserve_newlines_in_cells))
                str_rows.append(out)

            # Trim empty rows based on trim_empty option
            str_rows = self._trim_rows(str_rows)

            if not str_rows:
                continue

            # Trim empty columns based on trim_empty option
            str_rows = self._trim_columns(str_rows)

            if not str_rows or not any(str_rows):
                continue

            header = str_rows[0]
            data = str_rows[1:] if len(str_rows) > 1 else []

            # Apply header case transformation
            header = self._transform_header_case(header)

            # Compute alignments from header cells
            alignments: list[Alignment] = []
            try:
                first_row_cells = next(sheet.iter_rows(min_row=1, max_row=1, values_only=False))
                for c_idx, cell in enumerate(first_row_cells, start=1):
                    if self.options.max_cols is not None and c_idx > self.options.max_cols:
                        break
                    alignments.append(_alignment_for_cell(cell))
            except Exception:
                alignments = cast(list[Alignment], ["center"] * len(header))

            # Build table AST
            table = _build_table_ast(header, data, alignments)
            children.append(table)

            # Add truncation indicator as paragraph if needed
            truncated_rows = self.options.max_rows is not None and sheet.max_row > self.options.max_rows
            truncated_cols = self.options.max_cols is not None and sheet.max_column > self.options.max_cols
            if truncated_rows or truncated_cols:
                children.append(
                    Paragraph(content=[HTMLInline(content=f"*{self.options.truncation_indicator}*")])
                )

            # Extract images from sheet
            sheet_images = _extract_sheet_images(sheet, base_filename, attachment_sequencer, self.options)
            children.extend(sheet_images)

            # Extract charts from sheet
            sheet_charts = _extract_sheet_charts(sheet, base_filename, self.options)
            children.extend(sheet_charts)

        return Document(children=children, metadata=metadata.to_dict())

    def _trim_rows(self, rows: list[list[str]]) -> list[list[str]]:
        """Trim empty rows based on trim_empty option.

        Parameters
        ----------
        rows : list[list[str]]
            Rows to trim

        Returns
        -------
        list[list[str]]
            Trimmed rows

        """
        if not rows or self.options.trim_empty == "none":
            return rows

        # Trim leading empty rows
        if self.options.trim_empty in ("leading", "both"):
            while rows and all(c == "" for c in rows[0]):
                rows.pop(0)

        # Trim trailing empty rows
        if self.options.trim_empty in ("trailing", "both"):
            while rows and all(c == "" for c in rows[-1]):
                rows.pop()

        return rows

    def _trim_columns(self, rows: list[list[str]]) -> list[list[str]]:
        """Trim empty columns based on trim_empty option.

        Parameters
        ----------
        rows : list[list[str]]
            Rows to trim columns from

        Returns
        -------
        list[list[str]]
            Rows with trimmed columns

        """
        if not rows or self.options.trim_empty == "none":
            return rows

        if not rows[0]:
            return rows

        num_cols = len(rows[0])

        # Find leading empty columns
        leading_empty = 0
        if self.options.trim_empty in ("leading", "both"):
            for col_idx in range(num_cols):
                if all(row[col_idx] == "" if col_idx < len(row) else True for row in rows):
                    leading_empty += 1
                else:
                    break

        # Find trailing empty columns
        trailing_empty = 0
        if self.options.trim_empty in ("trailing", "both"):
            for col_idx in range(num_cols - 1, -1, -1):
                if all(row[col_idx] == "" if col_idx < len(row) else True for row in rows):
                    trailing_empty += 1
                else:
                    break

        # Trim columns
        if leading_empty > 0 or trailing_empty > 0:
            end_col = num_cols - trailing_empty
            return [row[leading_empty:end_col] for row in rows]

        return rows

    def _transform_header_case(self, header: list[str]) -> list[str]:
        """Transform header case based on header_case option.

        Parameters
        ----------
        header : list[str]
            Header row

        Returns
        -------
        list[str]
            Transformed header

        """
        if self.options.header_case == "preserve":
            return header
        elif self.options.header_case == "title":
            return [cell.title() for cell in header]
        elif self.options.header_case == "upper":
            return [cell.upper() for cell in header]
        elif self.options.header_case == "lower":
            return [cell.lower() for cell in header]
        return header

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from XLSX workbook.

        Parameters
        ----------
        document : Any
            Excel workbook (openpyxl)

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Try to extract metadata from workbook properties
        try:
            props = document.properties
            if props:
                if props.title:
                    metadata.title = props.title
                if props.creator:
                    metadata.author = props.creator
                if props.subject:
                    metadata.subject = props.subject
                if props.keywords:
                    metadata.keywords = props.keywords.split(',') if isinstance(props.keywords, str) else []
                if props.created:
                    metadata.creation_date = str(props.created)
        except Exception:
            pass

        # Add custom metadata
        try:
            metadata.custom['sheet_count'] = len(document.sheetnames)
            metadata.custom['sheet_names'] = document.sheetnames
        except Exception:
            pass

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="xlsx",
    extensions=[".xlsx"],
    mime_types=["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    magic_bytes=[
        (b"PK\x03\x04", 0),
    ],
    parser_class=XlsxToAstConverter,
    renderer_class=None,
    parser_required_packages=[("openpyxl", "openpyxl", "")],
    renderer_required_packages=[],
    import_error_message="XLSX conversion requires 'openpyxl'. Install with: pip install openpyxl",
    parser_options_class="XlsxOptions",
    renderer_options_class=None,
    description="Convert Excel XLSX files to Markdown tables",
    priority=6
)
