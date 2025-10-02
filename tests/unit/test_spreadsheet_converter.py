"""Unit tests for spreadsheet converter with new options.

Tests for CSV delimiter override and header handling options.
"""

import io

from all2md.parsers.spreadsheet2markdown import (
    csv_to_markdown,
    spreadsheet_to_markdown,
    tsv_to_markdown,
)
from all2md.options import SpreadsheetOptions


class TestCSVDelimiterOption:
    """Test CSV delimiter override functionality."""

    def test_csv_with_semicolon_delimiter(self):
        """Test CSV parsing with semicolon delimiter override."""
        csv_data = "Name;Age;City\nJohn;30;NYC\nJane;25;LA"
        options = SpreadsheetOptions(csv_delimiter=";")

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected

    def test_csv_with_pipe_delimiter(self):
        """Test CSV parsing with pipe delimiter override."""
        csv_data = "Name|Age|City\nJohn|30|NYC\nJane|25|LA"
        options = SpreadsheetOptions(csv_delimiter="|")

        result = csv_to_markdown(io.StringIO(csv_data), options)

        # Note: pipes in cells are escaped
        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected

    def test_tsv_with_comma_delimiter_override(self):
        """Test TSV converter with comma delimiter override."""
        # Data actually uses commas, not tabs
        csv_data = "Name,Age,City\nJohn,30,NYC\nJane,25,LA"
        options = SpreadsheetOptions(csv_delimiter=",")

        result = tsv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected

    def test_delimiter_override_disables_dialect_detection(self):
        """Test that delimiter override takes precedence over dialect detection."""
        # Mixed delimiters - would normally be detected as comma
        csv_data = "Name,Age;City\nJohn,30;NYC\nJane,25;LA"
        options = SpreadsheetOptions(csv_delimiter=";", detect_csv_dialect=True)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        # Should use semicolon, ignoring commas
        expected = (
            "| Name,Age | City |\n"
            "|:---:|:---:|\n"
            "| John,30 | NYC |\n"
            "| Jane,25 | LA |"
        )
        assert result == expected

    def test_auto_detect_when_no_delimiter_specified(self):
        """Test that dialect detection works when no delimiter is specified."""
        csv_data = "Name;Age;City\nJohn;30;NYC\nJane;25;LA"
        options = SpreadsheetOptions(csv_delimiter=None, detect_csv_dialect=True)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected


class TestHeaderOption:
    """Test header handling functionality."""

    def test_csv_with_header_true_default(self):
        """Test default behavior with has_header=True."""
        csv_data = "Name,Age,City\nJohn,30,NYC\nJane,25,LA"
        options = SpreadsheetOptions(has_header=True)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected

    def test_csv_with_header_false(self):
        """Test CSV without headers - generates generic column names."""
        csv_data = "John,30,NYC\nJane,25,LA\nBob,35,SF"
        options = SpreadsheetOptions(has_header=False)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |\n"
            "| Bob | 35 | SF |"
        )
        assert result == expected

    def test_tsv_with_header_false(self):
        """Test TSV without headers."""
        tsv_data = "John\t30\tNYC\nJane\t25\tLA"
        options = SpreadsheetOptions(has_header=False)

        result = tsv_to_markdown(io.StringIO(tsv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected

    def test_single_row_with_header_false(self):
        """Test single row CSV with has_header=False."""
        csv_data = "John,30,NYC"
        options = SpreadsheetOptions(has_header=False)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |"
        )
        assert result == expected

    def test_empty_csv_with_header_false(self):
        """Test empty CSV with has_header=False."""
        csv_data = ""
        options = SpreadsheetOptions(has_header=False)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        assert result == ""

    def test_header_false_with_max_cols(self):
        """Test has_header=False with column truncation."""
        csv_data = "A,B,C,D,E\n1,2,3,4,5\nX,Y,Z,W,V"
        options = SpreadsheetOptions(has_header=False, max_cols=3)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| A | B | C |\n"
            "| 1 | 2 | 3 |\n"
            "| X | Y | Z |"
        )
        assert result == expected

    def test_header_false_with_max_rows(self):
        """Test has_header=False with row truncation."""
        csv_data = "A,B,C\n1,2,3\nX,Y,Z\nP,Q,R"
        options = SpreadsheetOptions(has_header=False, max_rows=2, truncation_indicator="[truncated]")

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| A | B | C |\n"
            "| 1 | 2 | 3 |\n\n"
            "*[truncated]*"
        )
        assert result == expected


class TestCombinedOptions:
    """Test combinations of delimiter and header options."""

    def test_semicolon_delimiter_with_no_header(self):
        """Test semicolon delimiter with has_header=False."""
        csv_data = "John;30;NYC\nJane;25;LA"
        options = SpreadsheetOptions(csv_delimiter=";", has_header=False)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected

    def test_pipe_delimiter_with_header(self):
        """Test pipe delimiter with has_header=True."""
        csv_data = "Name|Age|City\nJohn|30|NYC"
        options = SpreadsheetOptions(csv_delimiter="|", has_header=True)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |"
        )
        assert result == expected

    def test_tab_delimiter_override_for_csv(self):
        """Test using tab delimiter for CSV converter."""
        tsv_data = "Name\tAge\tCity\nJohn\t30\tNYC"
        options = SpreadsheetOptions(csv_delimiter="\t", has_header=True)

        result = csv_to_markdown(io.StringIO(tsv_data), options)

        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |"
        )
        assert result == expected

    def test_special_characters_in_cells(self):
        """Test handling of special characters with delimiter override."""
        # Using semicolon delimiter with pipes in content
        csv_data = "Name;Description;Notes\nJohn;A|B|C;Test\nJane;X|Y;Demo"
        options = SpreadsheetOptions(csv_delimiter=";", has_header=True)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        # Pipes in content should be escaped
        expected = (
            "| Name | Description | Notes |\n"
            "|:---:|:---:|:---:|\n"
            "| John | A\\|B\\|C | Test |\n"
            "| Jane | X\\|Y | Demo |"
        )
        assert result == expected


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_varying_column_counts_with_no_header(self):
        """Test CSV with varying column counts when has_header=False."""
        csv_data = "A,B,C\n1,2\nX,Y,Z,W"
        options = SpreadsheetOptions(has_header=False)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        # Headers are generated based on first row column count
        # Rows with fewer columns will have missing cells
        # Rows with extra columns will show all columns
        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| A | B | C |\n"
            "| 1 | 2 |\n"  # Missing column renders as missing cell
            "| X | Y | Z | W |"    # Extra columns are included
        )
        assert result == expected

    def test_bom_handling_with_custom_delimiter(self):
        """Test BOM (Byte Order Mark) handling with custom delimiter."""
        # UTF-8 BOM at start
        csv_data = "\ufeffName;Age;City\nJohn;30;NYC"
        options = SpreadsheetOptions(csv_delimiter=";", has_header=True)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        # BOM should be stripped from first header
        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |"
        )
        assert result == expected

    def test_empty_cells_handling(self):
        """Test handling of empty cells with custom options."""
        csv_data = "A;;C\n;2;3\n1;;Z"
        options = SpreadsheetOptions(csv_delimiter=";", has_header=False)

        result = csv_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| A |  | C |\n"
            "|  | 2 | 3 |\n"
            "| 1 |  | Z |"
        )
        assert result == expected


class TestSpreadsheetAutoDetection:
    """Test the unified spreadsheet_to_markdown function."""

    def test_auto_detect_csv_with_options(self):
        """Test spreadsheet_to_markdown auto-detects CSV and applies options."""
        csv_data = "Name;Age;City\nJohn;30;NYC"
        options = SpreadsheetOptions(csv_delimiter=";", has_header=True)

        # Using StringIO simulates content-based detection
        result = spreadsheet_to_markdown(io.StringIO(csv_data), options)

        expected = (
            "| Name | Age | City |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |"
        )
        assert result == expected

    def test_auto_detect_tsv_with_no_header(self):
        """Test spreadsheet_to_markdown with TSV-like content and no header."""
        tsv_data = "John\t30\tNYC\nJane\t25\tLA"
        options = SpreadsheetOptions(has_header=False)

        result = spreadsheet_to_markdown(io.StringIO(tsv_data), options)

        expected = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "|:---:|:---:|:---:|\n"
            "| John | 30 | NYC |\n"
            "| Jane | 25 | LA |"
        )
        assert result == expected
