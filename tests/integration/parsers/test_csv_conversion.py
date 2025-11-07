"""Integration tests for CSV to Markdown conversion."""

import csv

import pytest
from fixtures import FIXTURES_PATH

from all2md import to_ast, to_markdown
from all2md.ast.nodes import Document
from all2md.options.csv import CsvOptions


@pytest.mark.integration
def test_csv_to_markdown_basic(tmp_path):
    """Test basic CSV to Markdown conversion."""
    csv_content = """Name,Age,City
Alice,30,NYC
Bob,25,LA
Charlie,35,Chicago"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Name" in result
    assert "Alice" in result
    assert "Bob" in result
    assert "Charlie" in result
    assert "NYC" in result


@pytest.mark.integration
def test_csv_to_markdown_with_header(tmp_path):
    """Test CSV with explicit header row."""
    csv_content = """First Name,Last Name,Email
John,Doe,john@example.com
Jane,Smith,jane@example.com"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "First Name" in result
    assert "Last Name" in result
    assert "Email" in result
    assert "John" in result
    assert "Jane" in result


@pytest.mark.integration
def test_csv_to_markdown_quoted_fields(tmp_path):
    """Test CSV with quoted fields."""
    csv_content = """Name,Description,Price
"Widget","A useful widget, very nice",10.99
"Gadget","Another product ""with quotes"",29.99"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Name" in result
    assert "Widget" in result
    assert "Gadget" in result
    assert "useful widget" in result


@pytest.mark.integration
def test_csv_to_markdown_empty_fields(tmp_path):
    """Test CSV with empty fields."""
    csv_content = """Col1,Col2,Col3
A,,C
,B,
X,Y,Z"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Col1" in result
    assert "Col2" in result
    assert "Col3" in result


@pytest.mark.integration
def test_csv_to_markdown_numeric_data(tmp_path):
    """Test CSV with numeric data."""
    csv_content = """Integer,Float,Scientific
100,3.14,1.5e-10
200,2.71,2.0e+5
300,1.41,3.5e0"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Integer" in result
    assert "100" in result
    assert "3.14" in result


@pytest.mark.integration
def test_csv_to_markdown_semicolon_delimiter(tmp_path):
    """Test CSV with semicolon delimiter."""
    csv_content = """Name;Age;City
Alice;30;NYC
Bob;25;LA"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # Use parser options to specify delimiter
    options = CsvOptions(delimiter=";")
    result = to_markdown(csv_file, source_format="csv", parser_options=options)

    assert "Name" in result
    assert "Alice" in result
    assert "NYC" in result


@pytest.mark.integration
def test_csv_to_markdown_tab_delimiter(tmp_path):
    """Test CSV with tab delimiter (TSV)."""
    csv_content = """Name\tAge\tCity
Alice\t30\tNYC
Bob\t25\tLA"""

    csv_file = tmp_path / "test.tsv"
    csv_file.write_text(csv_content, encoding="utf-8")

    options = CsvOptions(delimiter="\t")
    result = to_markdown(csv_file, parser_options=options)

    assert "Name" in result
    assert "Alice" in result


@pytest.mark.integration
def test_csv_to_markdown_single_column(tmp_path):
    """Test CSV with single column."""
    csv_content = """Items
Apple
Banana
Cherry
Date"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Items" in result
    assert "Apple" in result
    assert "Banana" in result


@pytest.mark.integration
def test_csv_to_markdown_single_row(tmp_path):
    """Test CSV with single row (header only)."""
    csv_content = """Name,Age,City"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert isinstance(result, str)


@pytest.mark.integration
def test_csv_to_markdown_multiline_fields(tmp_path):
    """Test CSV with multiline fields."""
    csv_content = """"Name","Description","Price"
"Widget","This is a long
multiline description
with several lines","10.99"
"Gadget","Another product","29.99\""""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Name" in result
    assert "Widget" in result
    assert "Gadget" in result


@pytest.mark.integration
def test_csv_to_markdown_special_characters(tmp_path):
    """Test CSV with special characters."""
    csv_content = """Text,Special
"Ampersand &","Less than <"
"Greater than >","Quotes "
"Asterisks **","Underscores __\""""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Text" in result
    assert "Special" in result


@pytest.mark.integration
def test_csv_to_markdown_unicode_content(tmp_path):
    """Test CSV with Unicode characters."""
    csv_content = """Language,Text
Chinese,\U00004e2d\U00006587
Greek,\U00000391\U000003b1
Emoji,\U0001f600 \U00002764"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Language" in result
    assert "Text" in result


@pytest.mark.integration
def test_csv_to_markdown_large_file(tmp_path):
    """Test CSV with many rows."""
    csv_file = tmp_path / "large.csv"

    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "Value", "Category"])

        for i in range(1000):
            writer.writerow([i, i * 10, f"Category_{i % 5}"])

    result = to_markdown(csv_file)

    assert "Index" in result
    assert "Value" in result
    assert "Category" in result


@pytest.mark.integration
def test_csv_to_markdown_inconsistent_columns(tmp_path):
    """Test CSV with inconsistent number of columns per row."""
    csv_content = """Name,Age,City
Alice,30,NYC
Bob,25
Charlie,35,Chicago,Extra"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    # Should handle gracefully
    assert "Name" in result
    assert "Alice" in result


@pytest.mark.integration
def test_csv_to_markdown_bom_encoding(tmp_path):
    """Test CSV with BOM (Byte Order Mark)."""
    csv_content = """Name,Age,City
Alice,30,NYC
Bob,25,LA"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text("\ufeff" + csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Name" in result
    assert "Alice" in result


@pytest.mark.integration
def test_csv_to_markdown_empty_file(tmp_path):
    """Test empty CSV file."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("", encoding="utf-8")

    result = to_markdown(csv_file)

    # Should complete without error
    assert isinstance(result, str)


@pytest.mark.integration
def test_csv_to_markdown_whitespace_fields(tmp_path):
    """Test CSV with whitespace in fields."""
    csv_content = """Name,Age,City
  Alice  ,  30  ,  NYC
Bob,25,LA
  Charlie  ,35,Chicago"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Name" in result
    assert "Alice" in result or "  Alice  " in result


@pytest.mark.integration
def test_csv_to_markdown_comments(tmp_path):
    """Test CSV with comment lines (if supported)."""
    csv_content = """# This is a comment
Name,Age,City
Alice,30,NYC
# Another comment
Bob,25,LA"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # Without special handling, comments may be treated as data
    result = to_markdown(csv_file)

    assert isinstance(result, str)


@pytest.mark.integration
def test_csv_to_ast_conversion(tmp_path):
    """Test CSV to AST conversion pipeline."""
    csv_content = """Name,Value
Test,123
Data,456"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    doc = to_ast(csv_file)

    # Verify AST structure
    assert isinstance(doc, Document)
    assert doc.children is not None

    # Verify content through markdown conversion
    result = to_markdown(csv_file)
    assert "Name" in result
    assert "Test" in result


@pytest.mark.integration
def test_csv_to_markdown_from_existing_fixture():
    """Test CSV conversion using existing test fixture."""
    csv_file = FIXTURES_PATH / "basic.csv"

    if not csv_file.exists():
        pytest.skip("Test fixture not found")

    result = to_markdown(csv_file)

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.integration
def test_csv_to_markdown_pipe_delimiter(tmp_path):
    """Test CSV with pipe delimiter."""
    csv_content = """Name|Age|City
Alice|30|NYC
Bob|25|LA"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    options = CsvOptions(delimiter="|")
    result = to_markdown(csv_file, source_format="csv", parser_options=options)

    assert "Name" in result
    assert "Alice" in result


@pytest.mark.integration
def test_csv_to_markdown_custom_quote_char(tmp_path):
    """Test CSV with custom quote character."""
    csv_content = """Name,Description
'Product A','This is 'good''
'Product B','Another item'"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    options = CsvOptions(quote_char="'")
    result = to_markdown(csv_file, parser_options=options)

    assert "Name" in result
    assert "Product A" in result


@pytest.mark.integration
def test_csv_to_markdown_no_header(tmp_path):
    """Test CSV without header row."""
    csv_content = """Alice,30,NYC
Bob,25,LA
Charlie,35,Chicago"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    assert "Alice" in result
    assert "Bob" in result
    assert "Charlie" in result


@pytest.mark.integration
def test_csv_to_markdown_duplicate_headers(tmp_path):
    """Test CSV with duplicate column headers."""
    csv_content = """Name,Age,Name
Alice,30,Smith
Bob,25,Jones"""

    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = to_markdown(csv_file)

    # Should handle duplicate headers
    assert "Name" in result
    assert "Alice" in result


@pytest.mark.integration
def test_csv_to_markdown_very_wide_table(tmp_path):
    """Test CSV with many columns."""
    headers = [f"Col{i}" for i in range(50)]
    data_row = [f"Data{i}" for i in range(50)]

    csv_file = tmp_path / "wide.csv"

    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(data_row)

    result = to_markdown(csv_file)

    assert "Col0" in result
    assert "Col49" in result
    assert "Data0" in result
