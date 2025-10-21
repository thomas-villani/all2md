#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for CSV dialect options."""

import io

from all2md.options.csv import CsvOptions
from all2md.parsers.csv import CsvToAstConverter


class TestCsvDialectOptions:
    """Tests for CSV dialect customization options."""

    def test_custom_delimiter(self):
        """Test using a custom delimiter (semicolon)."""
        csv_data = "Name;Age;City\nAlice;30;NYC\nBob;25;LA"

        options = CsvOptions(delimiter=";")
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        # Should have one table
        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        # Check header
        assert table.header.cells[0].content[0].content == "Name"
        assert table.header.cells[1].content[0].content == "Age"
        assert table.header.cells[2].content[0].content == "City"

        # Check first data row
        assert table.rows[0].cells[0].content[0].content == "Alice"
        assert table.rows[0].cells[1].content[0].content == "30"
        assert table.rows[0].cells[2].content[0].content == "NYC"

    def test_custom_quotechar(self):
        """Test using a custom quote character (single quote)."""
        csv_data = "Name,Description\n'Alice','Says ''hello'''\n'Bob','Normal text'"

        options = CsvOptions(quote_char="'", double_quote=True)
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        # Check that quotes were properly handled
        assert table.rows[0].cells[0].content[0].content == "Alice"
        assert table.rows[0].cells[1].content[0].content == "Says 'hello'"

    def test_custom_escapechar(self):
        """Test using a custom escape character (backslash)."""
        csv_data = 'Name,Description\nAlice,"She said \\"hello\\""\nBob,"Normal text"'

        options = CsvOptions(escape_char="\\", double_quote=False)
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        # Check that escape character was properly handled
        assert table.rows[0].cells[0].content[0].content == "Alice"
        # The escaped quotes should be properly parsed
        assert (
            '"hello"' in table.rows[0].cells[1].content[0].content
            or "hello" in table.rows[0].cells[1].content[0].content
        )

    def test_pipe_delimiter(self):
        """Test using pipe as delimiter."""
        csv_data = "Name|Age|City\nAlice|30|NYC\nBob|25|LA"

        options = CsvOptions(delimiter="|")
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        assert len(table.header.cells) == 3
        assert table.header.cells[0].content[0].content == "Name"
        assert table.rows[0].cells[1].content[0].content == "30"

    def test_tab_delimiter_explicit(self):
        """Test explicitly setting tab as delimiter."""
        csv_data = "Name\tAge\tCity\nAlice\t30\tNYC\nBob\t25\tLA"

        options = CsvOptions(delimiter="\t")
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        assert len(table.header.cells) == 3
        assert table.header.cells[0].content[0].content == "Name"

    def test_doublequote_false(self):
        """Test disabling double quoting."""
        # With doublequote=False, two quotes don't represent a single quote
        csv_data = 'Name,Value\n"Alice","100"\n"Bob","200"'

        options = CsvOptions(double_quote=False)
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        assert table.rows[0].cells[0].content[0].content == "Alice"

    def test_combined_dialect_options(self):
        """Test using multiple dialect options together."""
        csv_data = "Name;Description\n'Alice';'She said ''hi'''\n'Bob';'Normal'"

        options = CsvOptions(delimiter=";", quote_char="'", double_quote=True)
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        assert table.header.cells[0].content[0].content == "Name"
        assert table.rows[0].cells[0].content[0].content == "Alice"
        # Check that the doubled quotes were properly handled
        assert "hi" in table.rows[0].cells[1].content[0].content


class TestCsvDialectDetection:
    """Tests for CSV dialect auto-detection."""

    def test_auto_detect_semicolon(self):
        """Test that auto-detection works for semicolon-delimited files."""
        csv_data = "Name;Age;City\nAlice;30;NYC\nBob;25;LA"

        options = CsvOptions(detect_csv_dialect=True)
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        # If auto-detection worked, we should have 3 columns
        assert len(table.header.cells) == 3

    def test_explicit_delimiter_overrides_detection(self):
        """Test that explicit delimiter option overrides auto-detection."""
        csv_data = "Name;Age;City\nAlice;30;NYC\nBob;25;LA"

        options = CsvOptions(detect_csv_dialect=True, delimiter=";")
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

        table = tables[0]
        # Should use the explicit delimiter
        assert len(table.header.cells) == 3


class TestCsvDialectSampleSize:
    """Tests for CSV dialect sample size option."""

    def test_custom_dialect_sample_size(self):
        """Test using a custom dialect sample size."""
        # Create a CSV with multiple patterns - first pattern in small sample, second later
        csv_data = "A,B,C\n1,2,3\n" + ("x,y,z\n" * 100)

        options = CsvOptions(dialect_sample_size=8192)  # Larger sample size
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1

    def test_default_dialect_sample_size(self):
        """Test that default sample size is 4096."""
        options = CsvOptions()
        assert options.dialect_sample_size == 4096

    def test_small_dialect_sample_size(self):
        """Test using a smaller dialect sample size."""
        csv_data = "Name;Age;City\nAlice;30;NYC\nBob;25;LA"

        options = CsvOptions(dialect_sample_size=100, detect_csv_dialect=True)
        parser = CsvToAstConverter(options=options)
        doc = parser.parse(io.BytesIO(csv_data.encode()))

        tables = [node for node in doc.children if node.__class__.__name__ == "Table"]
        assert len(tables) == 1


class TestMakeCSVDialect:
    """Tests for the _make_csv_dialect helper function."""

    def test_make_dialect_with_all_parameters(self):
        """Test creating a dialect with all custom parameters."""
        from all2md.parsers.csv import _make_csv_dialect

        dialect_class = _make_csv_dialect(delimiter="|", quotechar="'", escapechar="\\", doublequote=False)

        # Create an instance to check attributes
        dialect = dialect_class()
        assert dialect.delimiter == "|"
        assert dialect.quotechar == "'"
        assert dialect.escapechar == "\\"
        assert dialect.doublequote is False

    def test_make_dialect_with_partial_parameters(self):
        """Test creating a dialect with only some parameters."""
        from all2md.parsers.csv import _make_csv_dialect

        dialect_class = _make_csv_dialect(delimiter=";")

        dialect = dialect_class()
        assert dialect.delimiter == ";"
        # Other attributes should come from csv.excel
        assert hasattr(dialect, "quotechar")

    def test_make_dialect_no_parameters(self):
        """Test creating a dialect with no parameters (defaults to excel)."""
        from all2md.parsers.csv import _make_csv_dialect

        dialect_class = _make_csv_dialect()

        dialect = dialect_class()
        # Should have excel defaults
        assert hasattr(dialect, "delimiter")
        assert hasattr(dialect, "quotechar")
