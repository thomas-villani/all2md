#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/csv.py
"""CSV/TSV to AST converter.

This module provides conversion from CSV and TSV files to AST representation.
It replaces the combined spreadsheet parser with a focused delimiter-separated values parser.

"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import IO, Any, Iterator, Optional, Union, cast

from all2md.ast import Alignment, Document, HTMLInline, Node, Paragraph
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.csv import CsvOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.encoding import read_text_with_encoding_detection
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.spreadsheet import build_table_ast, sanitize_cell_text, transform_header_case

logger = logging.getLogger(__name__)


def _validate_csv_delimiter(
    sample: str, dialect: type[csv.Dialect], min_columns: int = 2, min_valid_lines: int = 2
) -> bool:
    """Validate that a CSV dialect produces reasonable column counts.

    Parameters
    ----------
    sample : str
        Sample text to validate
    dialect : type[csv.Dialect]
        CSV dialect to test
    min_columns : int, default 2
        Minimum number of columns expected (1 column suggests wrong delimiter)
    min_valid_lines : int, default 2
        Minimum number of lines that should have >= min_columns

    Returns
    -------
    bool
        True if the dialect appears to produce valid column counts

    """
    try:
        reader = csv.reader(io.StringIO(sample), dialect=dialect)
        valid_line_count = 0
        total_lines = 0

        for row in reader:
            total_lines += 1
            # Count non-empty cells
            non_empty_cells = sum(1 for cell in row if cell.strip())
            if non_empty_cells >= min_columns:
                valid_line_count += 1

            # Early exit if we have enough valid lines
            if valid_line_count >= min_valid_lines:
                return True

            # Don't check too many lines
            if total_lines >= 10:
                break

        # Valid if we have enough lines with multiple columns
        return valid_line_count >= min_valid_lines

    except Exception as e:
        logger.debug(f"Dialect validation failed: {e}")
        return False


def _make_csv_dialect(
    delimiter: str | None = None,
    quotechar: str | None = None,
    escapechar: str | None = None,
    doublequote: bool | None = None,
) -> type[csv.Dialect]:
    r"""Create a CSV dialect class with custom parameters.

    This function creates a dialect subclass based on csv.excel with custom
    parameters, avoiding the need to mutate dialect instances.

    Parameters
    ----------
    delimiter : str | None, default None
        The delimiter character (e.g., ',', '\\t', ';', '|')
    quotechar : str | None, default None
        The quote character (e.g., '"', "'")
    escapechar : str | None, default None
        The escape character (e.g., '\\\\')
    doublequote : bool | None, default None
        Whether to use double quoting

    Returns
    -------
    type[csv.Dialect]
        A dialect class based on csv.excel with the specified parameters

    """
    attrs: dict[str, Any] = {}
    if delimiter is not None:
        attrs["delimiter"] = delimiter
    if quotechar is not None:
        attrs["quotechar"] = quotechar
    if escapechar is not None:
        attrs["escapechar"] = escapechar
    if doublequote is not None:
        attrs["doublequote"] = doublequote

    return type("CustomDialect", (csv.excel,), attrs)


class CsvToAstConverter(BaseParser):
    """Convert CSV/TSV files to AST representation.

    This converter handles CSV and TSV (tab-separated values) formats
    by building Table nodes from delimited text data.

    Parameters
    ----------
    options : CsvOptions or None
        Conversion options

    """

    def __init__(self, options: Any = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the CSV parser with options and progress callback."""
        BaseParser._validate_options_type(options, CsvOptions, "csv")
        options = options or CsvOptions()
        super().__init__(options, progress_callback)
        self.options: CsvOptions = options

    def parse(self, input_data: Union[str, Path, IO[bytes], IO[str], bytes]) -> Document:
        """Parse CSV/TSV file into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], IO[str], or bytes
            The input CSV/TSV file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed spreadsheet structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid format

        """
        # Determine delimiter
        delimiter = self._determine_delimiter(input_data)

        return self.csv_to_ast(input_data, delimiter)

    def _determine_delimiter(self, input_data: Union[str, Path, IO[bytes], IO[str], bytes]) -> str:
        """Determine the delimiter for the CSV/TSV file.

        Parameters
        ----------
        input_data : various
            Input data to analyze

        Returns
        -------
        str
            Delimiter character

        """
        # If explicitly set, use that
        if self.options.delimiter:
            return self.options.delimiter

        # Check file extension for TSV
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            if path.suffix.lower() == ".tsv":
                return "\t"
        elif hasattr(input_data, "name"):
            filename = getattr(input_data, "name", "")
            if filename and Path(filename).suffix.lower() == ".tsv":
                return "\t"

        # Default to comma
        return ","

    def _detect_csv_dialect(self, sample: str, delimiter: str | None) -> type[csv.Dialect]:
        """Detect or create CSV dialect from sample.

        Parameters
        ----------
        sample : str
            Sample text for dialect detection
        delimiter : str or None
            Optional explicit delimiter

        Returns
        -------
        type[csv.Dialect]
            CSV dialect to use

        """
        # If any custom dialect options are set, create custom dialect
        if (
            self.options.delimiter
            or self.options.quote_char
            or self.options.escape_char
            or self.options.double_quote is not None
        ):
            return _make_csv_dialect(
                delimiter=self.options.delimiter or delimiter,
                quotechar=self.options.quote_char,
                escapechar=self.options.escape_char,
                doublequote=self.options.double_quote,
            )

        if not self.options.detect_csv_dialect:
            return _make_csv_dialect(delimiter=delimiter) if delimiter else csv.excel

        # Try dialect detection
        try:
            sniffer = csv.Sniffer()
            detected_dialect = sniffer.sniff(sample, delimiters=",\t;|\x1f")

            # Validate the detected delimiter
            if _validate_csv_delimiter(sample, detected_dialect):
                logger.debug(f"CSV Sniffer detected and validated delimiter: {repr(detected_dialect.delimiter)}")
                return detected_dialect

            # Try alternatives
            logger.debug(
                f"CSV Sniffer detected delimiter {repr(detected_dialect.delimiter)} "
                f"but validation failed, trying alternatives"
            )
            for candidate in [",", "\t", ";", "|"]:
                test_dialect = _make_csv_dialect(delimiter=candidate)
                if _validate_csv_delimiter(sample, test_dialect):
                    logger.debug(f"Alternative delimiter validated: {repr(candidate)}")
                    return test_dialect

            logger.debug("No delimiter validated, using detected or default")
            return detected_dialect

        except Exception as e:
            logger.debug(f"CSV dialect detection failed: {e}, using fallback")
            return _make_csv_dialect(delimiter=delimiter) if delimiter else csv.excel

    def _read_csv_rows(self, reader: Iterator[list[str]]) -> list[list[str]]:
        """Read CSV rows with max_rows limit.

        Parameters
        ----------
        reader : Iterator[list[str]]
            CSV reader iterator

        Returns
        -------
        list[list[str]]
            List of rows

        """
        rows: list[list[str]] = []

        # Calculate maximum rows to read
        max_total_rows = None
        if self.options.max_rows is not None:
            max_total_rows = (self.options.max_rows + 1) if self.options.has_header else self.options.max_rows

        # Read rows with early termination
        row_count = 0
        for r in reader:
            rows.append(r)
            row_count += 1
            if max_total_rows is not None and row_count >= max_total_rows:
                break

        # Skip empty rows if requested
        if self.options.skip_empty_rows:

            def is_empty(row: list[str]) -> bool:
                return all((not (c or "").strip()) for c in row)

            while rows and is_empty(rows[0]):
                rows.pop(0)
            while rows and is_empty(rows[-1]):
                rows.pop()

        return rows

    def _process_csv_headers_and_data(self, rows: list[list[str]]) -> tuple[list[str], list[list[str]], bool]:
        """Process CSV headers and data rows.

        Parameters
        ----------
        rows : list[list[str]]
            Raw CSV rows

        Returns
        -------
        tuple[list[str], list[list[str]], bool]
            Tuple of (header, data_rows, truncated)

        """
        if not rows:
            return [], [], False

        # Separate header and data
        if self.options.has_header:
            header = rows[0]
            data_rows = rows[1:]
        else:
            num_cols = len(rows[0])
            header = [f"Column {i + 1}" for i in range(num_cols)]
            data_rows = rows

        # Truncate columns
        if self.options.max_cols is not None:
            header = header[: self.options.max_cols]
            data_rows = [r[: self.options.max_cols] for r in data_rows]

        # Truncate rows
        truncated = False
        if self.options.max_rows is not None and len(data_rows) > self.options.max_rows:
            data_rows = data_rows[: self.options.max_rows]
            truncated = True

        # Sanitize cells
        if self.options.has_header:
            header = [sanitize_cell_text(c).lstrip("\ufeff") for c in header]
        else:
            header = [sanitize_cell_text(c) for c in header]
        data_rows = [[sanitize_cell_text(c) for c in r] for r in data_rows]

        # Strip whitespace if requested
        if self.options.strip_whitespace:
            header = [c.strip() for c in header]
            data_rows = [[c.strip() for c in r] for r in data_rows]

        # Apply header case transformation
        header = transform_header_case(header, self.options.header_case)

        return header, data_rows, truncated

    def csv_to_ast(
        self,
        input_data: Union[str, Path, IO[bytes], IO[str], bytes],
        delimiter: str | None = None,
    ) -> Document:
        r"""Convert CSV/TSV to AST Document.

        Parameters
        ----------
        input_data : Union[str, Path, IO[bytes], IO[str], bytes]
            Input data
        delimiter : str | None
            Delimiter character to use (e.g., ',' for CSV, '\\t' for TSV)

        Returns
        -------
        Document
            AST document with table node

        """
        # Validate and load text
        try:
            doc_input, _ = validate_and_convert_input(input_data, supported_types=["path-like", "file-like", "bytes"])
            if isinstance(doc_input, (str, Path)):
                with open(doc_input, "rb") as f:
                    text_stream = self._read_text_stream_for_csv(f)
            else:
                text_stream = self._read_text_stream_for_csv(doc_input)
        except Exception as e:
            raise ParsingError(
                f"Failed to read CSV/TSV input: {e}", parsing_stage="input_processing", original_error=e
            ) from e

        # Detect dialect
        text_stream.seek(0)
        sample = text_stream.read(self.options.dialect_sample_size)
        text_stream.seek(0)
        dialect_obj = self._detect_csv_dialect(sample, delimiter)

        # Read rows
        reader = csv.reader(text_stream, dialect=dialect_obj)
        rows = self._read_csv_rows(reader)

        # Extract metadata
        metadata = self.extract_metadata(None)

        if not rows:
            return Document(children=[], metadata=metadata.to_dict())

        # Process headers and data
        header, data_rows, truncated = self._process_csv_headers_and_data(rows)

        if not header:
            return Document(children=[], metadata=metadata.to_dict())

        # Build table AST
        alignments: list[Alignment] = cast(list[Alignment], ["center"] * len(header))
        table = build_table_ast(header, data_rows, alignments)

        children: list[Node] = [table]
        if truncated:
            children.append(Paragraph(content=[HTMLInline(content=f"*{self.options.truncation_indicator}*")]))

        return Document(children=children, metadata=metadata.to_dict())

    def _read_text_stream_for_csv(self, input_data: Any) -> io.StringIO:
        """Read binary or text input and return a StringIO for CSV parsing with encoding detection.

        Parameters
        ----------
        input_data : Any
            Input stream or data

        Returns
        -------
        io.StringIO
            Text stream for CSV parsing

        """
        if isinstance(input_data, io.StringIO):
            input_data.seek(0)
            return input_data

        content = None
        if hasattr(input_data, "read"):
            pos = None
            try:
                pos = input_data.tell()
            except Exception:
                pass

            raw = input_data.read()
            if isinstance(raw, bytes):
                # Use encoding detection with utf-8-sig as first fallback (handles BOM)
                content = read_text_with_encoding_detection(raw, fallback_encodings=["utf-8-sig", "utf-8", "latin-1"])
            else:
                content = str(raw)

            try:
                if pos is not None:
                    input_data.seek(pos)
            except Exception:
                pass
        else:
            content = str(input_data)

        return io.StringIO(content or "")

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from CSV/TSV document.

        Parameters
        ----------
        document : Any
            Document object (None for CSV/TSV)

        Returns
        -------
        DocumentMetadata
            Empty metadata (CSV/TSV don't have structured metadata)

        """
        return DocumentMetadata()


def _detect_csv_tsv_content(content: bytes) -> bool:
    """Content-based detector for CSV/TSV formats.

    This function is used by the registry to detect CSV/TSV files
    based on content patterns when file extensions are not available.

    Parameters
    ----------
    content : bytes
        File content to analyze

    Returns
    -------
    bool
        True if content appears to be CSV or TSV

    """
    try:
        content_str = content.decode("utf-8", errors="ignore")
        non_empty_lines = [line.strip() for line in content_str.split("\n") if line.strip()]

        if len(non_empty_lines) >= 2:
            comma_count = sum(line.count(",") for line in non_empty_lines)
            tab_count = sum(line.count("\t") for line in non_empty_lines)

            if comma_count >= len(non_empty_lines):
                logger.debug(f"CSV pattern detected: {comma_count} commas in {len(non_empty_lines)} lines")
                return True
            elif tab_count >= len(non_empty_lines):
                logger.debug(f"TSV pattern detected: {tab_count} tabs in {len(non_empty_lines)} lines")
                return True
    except UnicodeDecodeError:
        pass

    return False


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="csv",
    extensions=[".csv", ".tsv"],
    mime_types=["text/csv", "application/csv", "text/tab-separated-values"],
    magic_bytes=[],
    content_detector=_detect_csv_tsv_content,
    parser_class=CsvToAstConverter,
    renderer_class="all2md.renderers.csv.CsvRenderer",
    renders_as_string=True,
    parser_required_packages=[],
    renderer_required_packages=[],
    import_error_message="CSV/TSV conversion uses Python standard library (no dependencies)",
    parser_options_class=CsvOptions,
    renderer_options_class="all2md.options.csv.CsvRendererOptions",
    description="Convert CSV and TSV files to/from Markdown tables",
    priority=6,
)
