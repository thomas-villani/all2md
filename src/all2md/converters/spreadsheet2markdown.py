#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/spreadsheet2markdown.py

"""Spreadsheet (XLSX/CSV/TSV) to Markdown conversion module.

This module converts:
- XLSX (Excel workbooks) via openpyxl
- CSV and TSV via Python's csv module (with optional dialect detection)

Key Features
------------
- XLSX:
  - Per-sheet conversion to Markdown tables
  - Optional sheet selection by name list or regex
  - Hyperlink preservation ([text](url))
  - Best-effort handling for merged cells (blank out non-master cells)
  - Optional formula rendering (values vs formulas) via data_only
  - Column alignment inferred from header cell horizontal alignment
- CSV/TSV:
  - Optional dialect detection
  - Optional delimiter override (tsv uses tab)
  - First row used as header by default
- Row/column truncation with indicator
- Uses shared MarkdownOptions when available (escaping rules etc.)

Dependencies
------------
- openpyxl (only for XLSX). CSV/TSV use standard library.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import IO, Any, Iterable, Union

from all2md.constants import TABLE_ALIGNMENT_MAPPING
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, InputError, MarkdownConversionError
from all2md.options import MarkdownOptions, SpreadsheetOptions
from all2md.utils.inputs import escape_markdown_special, validate_and_convert_input

logger = logging.getLogger(__name__)


def _sanitize_cell_text(text: Any, md_options: MarkdownOptions | None = None) -> str:
    """Convert any cell value to a safe Markdown table string."""
    if text is None:
        s = ""
    else:
        s = str(text)

    # Normalize whitespace/newlines inside cells
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    # Escape markdown special characters if enabled
    if md_options and md_options.escape_special:
        s = escape_markdown_special(s)

    # Always escape the Markdown table pipe to avoid breaking the table
    s = s.replace("|", r"\|")
    return s


def _format_link_or_text(cell: Any, text: str, md_options: MarkdownOptions | None = None) -> str:
    """Render a cell as either a plain string or a Markdown link if hyperlink is present."""
    try:
        # openpyxl cell may have hyperlink attribute
        if hasattr(cell, "hyperlink") and cell.hyperlink and cell.hyperlink.target:
            disp = _sanitize_cell_text(text, md_options)
            url = cell.hyperlink.target
            return f"[{disp}]({url})"
    except Exception:
        pass

    return _sanitize_cell_text(text, md_options)


def _alignment_for_cell(cell: Any) -> str:
    """Map an openpyxl cell alignment to Markdown table alignment token."""
    try:
        align = getattr(cell, "alignment", None)
        if align and getattr(align, "horizontal", None):
            horiz = align.horizontal.lower()
            if horiz in TABLE_ALIGNMENT_MAPPING:
                return TABLE_ALIGNMENT_MAPPING[horiz]
    except Exception:
        pass

    # Default center (consistent with html2markdown default)
    return ":---:"


def _build_markdown_table(header: list[str], rows: list[list[str]], alignments: list[str]) -> str:
    """Assemble a Markdown table from header, rows, and column alignment tokens."""
    parts = []
    parts.append("| " + " | ".join(header) + " |")
    parts.append("|" + "|".join(alignments) + "|")
    for r in rows:
        parts.append("| " + " | ".join(r) + " |")
    return "\n".join(parts)


def _xlsx_iter_rows(sheet: Any, max_rows: int | None, max_cols: int | None) -> Iterable[list[Any]]:
    """Iterate rows of an openpyxl worksheet with optional truncation."""
    row_iter = sheet.iter_rows(values_only=False)  # need real cell objects
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
    """Return a map of cell.coordinate -> master.coordinate for merged ranges."""
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


def _xlsx_to_markdown(workbook: Any, options: SpreadsheetOptions) -> str:
    """Convert an openpyxl workbook instance to Markdown across selected sheets."""
    md_options = options.markdown_options or MarkdownOptions()

    # Select sheets
    sheet_names: list[str] = list(workbook.sheetnames)
    if isinstance(options.sheets, list):
        sheet_names = [n for n in sheet_names if n in options.sheets]
    elif isinstance(options.sheets, str):
        pattern = re.compile(options.sheets)
        sheet_names = [n for n in sheet_names if pattern.search(n)]

    if not sheet_names:
        return ""

    sections: list[str] = []
    for sname in sheet_names:
        sheet = workbook[sname]

        if options.include_sheet_titles:
            sections.append(f"## {sname}\n")

        # Determine rows and merged cells
        merged_map = _map_merged_cells(sheet)

        raw_rows: list[list[Any]] = []
        for row in _xlsx_iter_rows(sheet, options.max_rows, options.max_cols):
            # Skip trailing empty rows (full row empty)
            if all((cell.value is None) for cell in row):
                raw_rows.append(row)  # keep row; user may prefer to see empty rows at top
            else:
                raw_rows.append(row)

        # Early-out for empty sheet
        if not raw_rows:
            continue

        # Convert to strings and handle merged cells
        str_rows: list[list[str]] = []
        for row in raw_rows:
            out: list[str] = []
            for cell in row:
                coord = getattr(cell, "coordinate", None)
                # If merged and not master, render as empty
                if coord and coord in merged_map and merged_map[coord] != coord:
                    out.append("")
                else:
                    out.append(_format_link_or_text(cell, cell.value, md_options))
            str_rows.append(out)

        # Trim completely empty trailing rows
        while str_rows and all(c == "" for c in str_rows[-1]):
            str_rows.pop()

        if not str_rows:
            continue

        header = str_rows[0]
        data = str_rows[1:] if len(str_rows) > 1 else []

        # Compute alignments from header cells
        alignments: list[str] = []
        try:
            first_row_cells = next(sheet.iter_rows(min_row=1, max_row=1, values_only=False))
            for c_idx, cell in enumerate(first_row_cells, start=1):
                if options.max_cols is not None and c_idx > options.max_cols:
                    break
                alignments.append(_alignment_for_cell(cell))
        except Exception:
            alignments = [":---:"] * len(header)

        table_md = _build_markdown_table(header, data, alignments)
        sections.append(table_md)

        # Truncation indicator
        truncated_rows = options.max_rows is not None and sheet.max_row > options.max_rows
        truncated_cols = options.max_cols is not None and sheet.max_column > options.max_cols
        if truncated_rows or truncated_cols:
            sections.append(f"\n*{options.truncation_indicator}*")

    # Separate sheets with a blank line or configured separator if desired
    return "\n\n".join([s.strip() for s in sections if s.strip()])


def xlsx_to_markdown(
    input_data: Union[str, Path, IO[bytes], IO[Any]],
    options: SpreadsheetOptions | None = None
) -> str:
    """Convert XLSX workbook to Markdown tables."""
    if options is None:
        options = SpreadsheetOptions()

    # Lazy import to have clean dependency errors
    try:
        import openpyxl
    except ImportError as e:
        raise DependencyError(
            converter_name="xlsx",
            missing_packages=[("openpyxl", "")]
        ) from e

    # Validate and open
    try:
        doc_input, input_type = validate_and_convert_input(
            input_data, supported_types=["path-like", "file-like", "bytes", "document objects"], require_binary=True
        )

        # If already an openpyxl workbook
        if input_type == "object" and getattr(doc_input, "__class__", None).__name__ == "Workbook":
            wb = doc_input
        else:
            wb = openpyxl.load_workbook(doc_input, data_only=options.render_formulas)

        return _xlsx_to_markdown(wb, options)

    except InputError:
        raise
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to process XLSX file: {e}", conversion_stage="document_opening", original_error=e
        ) from e


def _read_text_stream_for_csv(input_data: Any) -> io.StringIO:
    """Read binary or text input and return a StringIO for CSV parsing."""
    # If it's a StringIO already, return as-is
    if isinstance(input_data, io.StringIO):
        input_data.seek(0)
        return input_data

    # If it's a binary stream or bytes, decode
    content = None
    if hasattr(input_data, "read"):
        pos = None
        try:
            pos = input_data.tell()
        except Exception:
            pass

        raw = input_data.read()
        if isinstance(raw, bytes):
            # Try utf-8-sig first (to trim BOM if present)
            try:
                content = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = raw.decode("utf-8", errors="replace")
        else:
            content = str(raw)

        # Restore pointer if possible (not strictly required)
        try:
            if pos is not None:
                input_data.seek(pos)
        except Exception:
            pass
    else:
        # Fallback: treat as path-like or bytes already handled by validate_and_convert_input
        content = str(input_data)

    return io.StringIO(content or "")


def _csv_or_tsv_to_markdown(
    input_data: Union[str, Path, IO[bytes], IO[str]],
    options: SpreadsheetOptions | None = None,
    delimiter: str | None = None,
    force_delimiter: bool = False
) -> str:
    """Common CSV/TSV conversion using csv module."""
    if options is None:
        options = SpreadsheetOptions()
    md_options = options.markdown_options or MarkdownOptions()

    # Validate and load text
    try:
        doc_input, _ = validate_and_convert_input(input_data, supported_types=["path-like", "file-like", "bytes"])
        if isinstance(doc_input, (str, Path)):
            with open(doc_input, "rb") as f:
                text_stream = _read_text_stream_for_csv(f)
        else:
            text_stream = _read_text_stream_for_csv(doc_input)
    except InputError:
        raise
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to read CSV/TSV input: {e}", conversion_stage="input_processing", original_error=e
        ) from e

    # Sniff dialect if desired and not forcing a known delimiter
    text_stream.seek(0)
    sample = text_stream.read(4096)
    text_stream.seek(0)

    if force_delimiter:
        dialect = csv.excel()
        dialect.delimiter = delimiter or "\t"
    elif options.detect_csv_dialect:
        try:
            sniffer = csv.Sniffer()
            detected = sniffer.sniff(sample, delimiters=[",", "\t", ";", "|", "\x1f"])
            dialect = detected
        except Exception:
            dialect = csv.excel()
            if delimiter:
                dialect.delimiter = delimiter
    else:
        dialect = csv.excel()
        if delimiter:
            dialect.delimiter = delimiter

    reader = csv.reader(text_stream, dialect=dialect)
    rows: list[list[str]] = []
    for r in reader:
        # Keep all rows; trimming happens below
        rows.append(r)

    # Drop leading/trailing fully empty rows
    def is_empty(row: list[str]) -> bool:
        return all((not (c or "").strip()) for c in row)

    while rows and is_empty(rows[0]):
        rows.pop(0)
    while rows and is_empty(rows[-1]):
        rows.pop()

    if not rows:
        return ""

    # Use first row as header by default
    header = rows[0]
    data_rows = rows[1:]

    # Truncate columns
    if options.max_cols is not None:
        header = header[: options.max_cols]
        data_rows = [r[: options.max_cols] for r in data_rows]

    # Truncate rows
    truncated = False
    if options.max_rows is not None and len(data_rows) > options.max_rows:
        data_rows = data_rows[: options.max_rows]
        truncated = True

    # Sanitize cells
    header = [_sanitize_cell_text(c, md_options).lstrip("\ufeff") for c in header]  # strip BOM in first header cell
    data_rows = [[_sanitize_cell_text(c, md_options) for c in r] for r in data_rows]

    # Alignments default to center
    alignments = [":---:"] * len(header)

    table_md = _build_markdown_table(header, data_rows, alignments)

    if truncated:
        table_md += f"\n\n*{options.truncation_indicator}*"

    return table_md


def csv_to_markdown(
    input_data: Union[str, Path, IO[bytes], IO[str]],
    options: SpreadsheetOptions | None = None
) -> str:
    """Convert CSV to Markdown table."""
    return _csv_or_tsv_to_markdown(
        input_data=input_data,
        options=options,
        delimiter=",",
        force_delimiter=False  # allow dialect/sniffer unless overridden by options
    )


def tsv_to_markdown(
    input_data: Union[str, Path, IO[bytes], IO[str]],
    options: SpreadsheetOptions | None = None
) -> str:
    """Convert TSV to Markdown table."""
    # For TSV, default to tab delimiter and force it unless user enabled dialect detection explicitly
    force = True
    if options and options.detect_csv_dialect:
        force = False
    return _csv_or_tsv_to_markdown(
        input_data=input_data,
        options=options,
        delimiter="\t",
        force_delimiter=force
    )


def _detect_spreadsheet_format(input_data: Union[str, Path, IO[bytes], IO[str]]) -> str:
    """Detect spreadsheet format from input data.

    Returns
    -------
    str
        Format name: "xlsx", "csv", or "tsv"
    """
    # If it's a path, check extension first
    if isinstance(input_data, (str, Path)):
        path = Path(input_data)
        ext = path.suffix.lower()
        if ext == ".xlsx":
            return "xlsx"
        elif ext == ".csv":
            return "csv"
        elif ext == ".tsv":
            return "tsv"

    # Check if file object has a name attribute
    elif hasattr(input_data, 'name'):
        filename = getattr(input_data, 'name', None)
        if filename:
            path = Path(filename)
            ext = path.suffix.lower()
            if ext == ".xlsx":
                return "xlsx"
            elif ext == ".csv":
                return "csv"
            elif ext == ".tsv":
                return "tsv"

    # Try content-based detection
    try:
        # For file-like objects, read a sample
        if hasattr(input_data, 'read'):
            pos = getattr(input_data, 'tell', lambda: 0)()
            try:
                input_data.seek(0)
                sample = input_data.read(1024)
                input_data.seek(pos)  # Restore position
            except Exception:
                sample = b""
        elif isinstance(input_data, bytes):
            sample = input_data[:1024]
        else:
            # String path case - read first 1KB
            try:
                with open(input_data, 'rb') as f:
                    sample = f.read(1024)
            except Exception:
                sample = b""

        # Check for XLSX (ZIP signature)
        if sample.startswith(b'PK\x03\x04'):
            return "xlsx"

        # Check for CSV/TSV patterns
        try:
            text_sample = sample.decode('utf-8', errors='ignore')
            lines = text_sample.split('\n')[:5]  # Check first 5 lines
            non_empty_lines = [line for line in lines if line.strip()]

            if len(non_empty_lines) >= 2:  # Need at least header + data
                comma_count = sum(line.count(',') for line in non_empty_lines)
                tab_count = sum(line.count('\t') for line in non_empty_lines)

                if tab_count >= len(non_empty_lines):  # At least one tab per line
                    return "tsv"
                elif comma_count >= len(non_empty_lines):  # At least one comma per line
                    return "csv"
        except UnicodeDecodeError:
            pass
    except Exception:
        pass

    # Default fallback to CSV
    return "csv"


def spreadsheet_to_markdown(
    input_data: Union[str, Path, IO[bytes], IO[str]],
    options: SpreadsheetOptions | None = None
) -> str:
    """Convert spreadsheet (XLSX/CSV/TSV) to Markdown table.

    This unified function detects the spreadsheet format and routes
    to the appropriate converter function.

    Parameters
    ----------
    input_data : Union[str, Path, IO[bytes], IO[str]]
        Input spreadsheet file or data
    options : SpreadsheetOptions | None, optional
        Conversion options

    Returns
    -------
    str
        Markdown table representation

    Raises
    ------
    DependencyError
        If required packages are not installed (openpyxl for XLSX)
    InputError
        If input is invalid
    MarkdownConversionError
        If conversion fails
    """
    if options is None:
        options = SpreadsheetOptions()

    # Detect the actual format
    detected_format = _detect_spreadsheet_format(input_data)
    logger.debug(f"Detected spreadsheet format: {detected_format}")

    # Route to appropriate converter
    if detected_format == "xlsx":
        return xlsx_to_markdown(input_data, options)
    elif detected_format == "csv":
        return csv_to_markdown(input_data, options)
    elif detected_format == "tsv":
        return tsv_to_markdown(input_data, options)
    else:
        # Fallback to CSV if detection fails
        logger.warning(f"Unknown format '{detected_format}', falling back to CSV")
        return csv_to_markdown(input_data, options)

CONVERTER_METADATA = ConverterMetadata(
    format_name="spreadsheet",
    extensions=[".xlsx", ".csv", ".tsv"],
    mime_types=[
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # XLSX
        "text/csv",
        "application/csv",
        "text/tab-separated-values"  # TSV
    ],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature for XLSX
    ],
    converter_module="all2md.converters.spreadsheet2markdown",
    converter_function="spreadsheet_to_markdown",
    required_packages=[("openpyxl", "")],  # Only required for XLSX, handled in xlsx_to_markdown
    import_error_message="XLSX conversion requires 'openpyxl'. Install with: pip install openpyxl",
    options_class="SpreadsheetOptions",
    description="Convert spreadsheets (XLSX, CSV, TSV) to Markdown tables",
    priority=7  # Use higher priority to catch XLSX before generic text detection
)