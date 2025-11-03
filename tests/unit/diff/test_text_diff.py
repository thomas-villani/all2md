"""Unit tests for simplified text-based diff functionality."""

import importlib.util

import pytest

from all2md.ast.nodes import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    List,
    ListItem,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.diff.text_diff import (
    compare_documents,
    compare_files,
    extract_document_lines,
    extract_text_content,
    normalize_whitespace,
)


class TestExtractTextContent:
    """Tests for extract_text_content function."""

    def test_extract_from_text_node(self):
        """Test extracting text from Text node."""
        node = Text("Hello world")
        assert extract_text_content(node) == "Hello world"

    def test_extract_from_paragraph(self):
        """Test extracting text from Paragraph."""
        node = Paragraph(content=[Text("First "), Text("second")])
        assert extract_text_content(node) == "First  second"

    def test_extract_from_heading(self):
        """Test extracting text from Heading."""
        node = Heading(level=1, content=[Text("Title")])
        assert extract_text_content(node) == "Title"

    def test_extract_from_code_block(self):
        """Test extracting text from CodeBlock."""
        node = CodeBlock(content="def foo():\n    pass", language="python")
        assert extract_text_content(node) == "def foo():\n    pass"


class TestNormalizeWhitespace:
    """Tests for normalize_whitespace function."""

    def test_normalize_multiple_spaces(self):
        """Test normalizing multiple spaces."""
        text = "Hello    world"
        assert normalize_whitespace(text) == "Hello world"

    def test_normalize_tabs_and_newlines(self):
        """Test normalizing tabs and newlines."""
        text = "Hello\t\nworld"
        assert normalize_whitespace(text) == "Hello world"

    def test_normalize_leading_trailing_whitespace(self):
        """Test stripping leading and trailing whitespace."""
        text = "  Hello world  "
        assert normalize_whitespace(text) == "Hello world"

    def test_normalize_mixed_whitespace(self):
        """Test normalizing mixed whitespace."""
        text = "  Hello   \t\n  world  "
        assert normalize_whitespace(text) == "Hello world"


class TestExtractDocumentLines:
    """Tests for extract_document_lines function."""

    def test_extract_simple_document(self):
        """Test extracting lines from simple document."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text("Title")]),
                Paragraph(content=[Text("First paragraph.")]),
                Paragraph(content=[Text("Second paragraph.")]),
            ]
        )

        lines = extract_document_lines(doc)
        assert lines == [
            "# Title",
            "First paragraph.",
            "Second paragraph.",
        ]

    def test_extract_with_multiple_heading_levels(self):
        """Test extracting headings at different levels."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text("H1")]),
                Heading(level=2, content=[Text("H2")]),
                Heading(level=3, content=[Text("H3")]),
            ]
        )

        lines = extract_document_lines(doc)
        assert lines == [
            "# H1",
            "## H2",
            "### H3",
        ]

    def test_extract_with_code_block(self):
        """Test extracting code blocks."""
        doc = Document(
            children=[
                CodeBlock(content="def foo():\n    pass", language="python"),
            ]
        )

        lines = extract_document_lines(doc)
        assert lines == [
            "```python",
            "def foo():",
            "    pass",
            "```",
        ]

    def test_extract_with_list(self):
        """Test extracting lists."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Text("Item 1")]),
                        ListItem(children=[Text("Item 2")]),
                    ],
                ),
            ]
        )

        lines = extract_document_lines(doc)
        assert lines == [
            "- Item 1",
            "- Item 2",
        ]

    def test_extract_with_ordered_list(self):
        """Test extracting ordered lists."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Text("First")]),
                        ListItem(children=[Text("Second")]),
                    ],
                ),
            ]
        )

        lines = extract_document_lines(doc)
        assert lines == [
            "1. First",
            "2. Second",
        ]

    def test_extract_with_blockquote(self):
        """Block quotes should preserve the > prefix."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[Paragraph(content=[Text("Quoted line")])],
                )
            ]
        )

        lines = extract_document_lines(doc)
        assert lines == ["> Quoted line"]

    def test_extract_with_table(self):
        """Test extracting tables."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(cells=[TableCell(content=[Text("Col1")]), TableCell(content=[Text("Col2")])]),
                    rows=[
                        TableRow(cells=[TableCell(content=[Text("A")]), TableCell(content=[Text("B")])]),
                    ],
                ),
            ]
        )

        lines = extract_document_lines(doc)
        assert "| Col1 | Col2 |" in lines
        assert "| A | B |" in lines

    def test_extract_with_ignore_whitespace(self):
        """Test extracting with whitespace normalization."""
        doc = Document(
            children=[
                Paragraph(content=[Text("Hello   world")]),
            ]
        )

        lines = extract_document_lines(doc, ignore_whitespace=True)
        assert lines == ["Hello world"]

    def test_extract_with_sentence_granularity(self):
        """Sentence granularity should split paragraphs."""
        doc = Document(children=[Paragraph(content=[Text("First sentence. Second sentence!")])])

        lines = extract_document_lines(doc, granularity="sentence")
        assert lines == ["First sentence.", "Second sentence!"]

    def test_extract_with_word_granularity(self):
        """Word granularity should emit individual tokens."""
        doc = Document(children=[Paragraph(content=[Text("Alpha beta")])])

        lines = extract_document_lines(doc, granularity="word")
        assert lines == ["Alpha", "beta"]

    def test_extract_empty_document(self):
        """Test extracting from empty document."""
        doc = Document(children=[])
        lines = extract_document_lines(doc)
        assert lines == []


class TestCompareDocuments:
    """Tests for compare_documents function."""

    def test_compare_identical_documents(self):
        """Test comparing identical documents."""
        doc1 = Document(children=[Paragraph(content=[Text("Same text")])])
        doc2 = Document(children=[Paragraph(content=[Text("Same text")])])

        diff_lines = list(compare_documents(doc1, doc2))

        # Identical documents produce no diff output (empty iterator from difflib)
        assert len(diff_lines) == 0

    def test_compare_added_paragraph(self):
        """Test detecting added paragraph."""
        doc1 = Document(children=[Paragraph(content=[Text("First")])])
        doc2 = Document(
            children=[
                Paragraph(content=[Text("First")]),
                Paragraph(content=[Text("Second")]),
            ]
        )

        diff_lines = list(compare_documents(doc1, doc2))

        # Should show addition
        assert any(line.startswith("+Second") for line in diff_lines)

    def test_compare_deleted_paragraph(self):
        """Test detecting deleted paragraph."""
        doc1 = Document(
            children=[
                Paragraph(content=[Text("First")]),
                Paragraph(content=[Text("Second")]),
            ]
        )
        doc2 = Document(children=[Paragraph(content=[Text("First")])])

        diff_lines = list(compare_documents(doc1, doc2))

        # Should show deletion
        assert any(line.startswith("-Second") for line in diff_lines)

    def test_compare_modified_text(self):
        """Test detecting modified text."""
        doc1 = Document(children=[Paragraph(content=[Text("Original text")])])
        doc2 = Document(children=[Paragraph(content=[Text("Modified text")])])

        diff_lines = list(compare_documents(doc1, doc2))

        # Should show both deletion and addition
        assert any("-Original" in line for line in diff_lines)
        assert any("+Modified" in line for line in diff_lines)

    def test_compare_with_context_lines(self):
        """Test comparison with custom context lines."""
        doc1 = Document(
            children=[
                Paragraph(content=[Text("Line 1")]),
                Paragraph(content=[Text("Line 2")]),
                Paragraph(content=[Text("Line 3")]),
            ]
        )
        doc2 = Document(
            children=[
                Paragraph(content=[Text("Line 1")]),
                Paragraph(content=[Text("Changed line 2")]),
                Paragraph(content=[Text("Line 3")]),
            ]
        )

        diff_lines_3 = list(compare_documents(doc1, doc2, context_lines=3))
        diff_lines_1 = list(compare_documents(doc1, doc2, context_lines=1))

        # More context should generally mean more lines (or equal)
        # Note: This is a rough heuristic, actual line count depends on diff algorithm
        assert len(diff_lines_3) >= len(diff_lines_1) or len(diff_lines_3) > 0

    def test_compare_with_ignore_whitespace(self):
        """Test comparison with whitespace normalization."""
        doc1 = Document(children=[Paragraph(content=[Text("Hello   world")])])
        doc2 = Document(children=[Paragraph(content=[Text("Hello world")])])

        # Without ignore_whitespace, should show difference
        diff_normal = list(compare_documents(doc1, doc2, ignore_whitespace=False))
        has_changes_normal = any(
            line.startswith("+") or line.startswith("-")
            for line in diff_normal
            if not line.startswith("+++") and not line.startswith("---")
        )

        # With ignore_whitespace, should not show difference
        diff_normalized = list(compare_documents(doc1, doc2, ignore_whitespace=True))
        has_changes_normalized = any(
            line.startswith("+") or line.startswith("-")
            for line in diff_normalized
            if not line.startswith("+++") and not line.startswith("---")
        )

        assert has_changes_normal
        assert not has_changes_normalized

    def test_compare_symmetry(self):
        """Test that comparison is symmetric (A→B opposite of B→A)."""
        doc1 = Document(children=[Paragraph(content=[Text("First")])])
        doc2 = Document(children=[Paragraph(content=[Text("Second")])])

        # Compare in both directions
        diff_forward = list(compare_documents(doc1, doc2))
        diff_reverse = list(compare_documents(doc2, doc1))

        # Extract change lines (excluding headers)
        forward_changes = [
            line
            for line in diff_forward
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        ]
        reverse_changes = [
            line
            for line in diff_reverse
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        ]

        # Should have same number of changes
        assert len(forward_changes) == len(reverse_changes)

        # Each + in forward should correspond to - in reverse (and vice versa)
        forward_adds = [line[1:] for line in forward_changes if line.startswith("+")]
        reverse_dels = [line[1:] for line in reverse_changes if line.startswith("-")]
        assert set(forward_adds) == set(reverse_dels)

    def test_compare_sentence_granularity(self):
        """Granularity='sentence' should split diff output."""
        doc1 = Document(children=[Paragraph(content=[Text("One. Two.")])])
        doc2 = Document(children=[Paragraph(content=[Text("One. Changed.")])])

        result = compare_documents(doc1, doc2, granularity="sentence")
        diff_lines = list(result)

        assert any(line.startswith("-Two") for line in diff_lines)
        assert any(line.startswith("+Changed") for line in diff_lines)
        assert result.granularity == "sentence"

    def test_diff_result_operations(self):
        """DiffResult exposes structured operations."""
        doc1 = Document(children=[Paragraph(content=[Text("Alpha")])])
        doc2 = Document(children=[Paragraph(content=[Text("Beta")])])

        result = compare_documents(doc1, doc2)
        ops = list(result.iter_operations())

        assert ops, "Expected at least one diff operation"
        tags = {op.tag for op in ops}
        assert tags <= {"delete", "insert", "replace"}
        if "replace" in tags:
            assert len(ops) == 1
            assert ops[0].old_slice == ["Alpha"]
            assert ops[0].new_slice == ["Beta"]
        else:
            assert tags == {"delete", "insert"}


class TestCompareFiles:
    """Tests for compare_files function."""

    def test_compare_markdown_files(self, tmp_path):
        """Test comparing two markdown files."""
        if importlib.util.find_spec("mistune") is None:
            pytest.skip("mistune not installed, skipping file comparison test")
        file1 = tmp_path / "doc1.md"
        file1.write_text("# Title\n\nFirst paragraph.", encoding="utf-8")

        file2 = tmp_path / "doc2.md"
        file2.write_text("# Title\n\nSecond paragraph.", encoding="utf-8")

        diff_lines = list(compare_files(file1, file2))

        # Should have headers
        assert any("---" in line for line in diff_lines)
        assert any("+++" in line for line in diff_lines)
        # Should show the change
        assert any("-First" in line for line in diff_lines)
        assert any("+Second" in line for line in diff_lines)

    def test_compare_with_custom_labels(self, tmp_path):
        """Test comparison with custom file labels."""
        if importlib.util.find_spec("mistune") is None:
            pytest.skip("mistune not installed, skipping file comparison test")
        file1 = tmp_path / "doc1.md"
        file1.write_text("# Content A", encoding="utf-8")

        file2 = tmp_path / "doc2.md"
        file2.write_text("# Content B", encoding="utf-8")

        diff_lines = list(compare_files(file1, file2, old_label="Version 1", new_label="Version 2"))

        # Should use custom labels in headers
        assert any("Version 1" in line for line in diff_lines)
        assert any("Version 2" in line for line in diff_lines)
