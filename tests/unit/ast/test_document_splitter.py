#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for document splitting functionality."""

import pytest

from all2md.ast.document_splitter import DocumentSplitter, SplitResult, parse_split_spec
from all2md.ast.nodes import Document, Heading, Paragraph, Text
from all2md.ast.utils import extract_text


@pytest.fixture
def simple_doc():
    """Create a simple document with multiple H1 sections."""
    return Document(
        children=[
            Paragraph(content=[Text(content="This is preamble text before any headings.")]),
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(content=[Text(content="Introduction paragraph with some content.")]),
            Heading(level=1, content=[Text(content="Methods")]),
            Paragraph(content=[Text(content="Methods paragraph with methodology details.")]),
            Heading(level=1, content=[Text(content="Results")]),
            Paragraph(content=[Text(content="Results paragraph showing findings.")]),
        ]
    )


@pytest.fixture
def nested_doc():
    """Create a document with nested headings."""
    return Document(
        children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Paragraph(content=[Text(content="Chapter 1 intro.")]),
            Heading(level=2, content=[Text(content="Section 1.1")]),
            Paragraph(content=[Text(content="Section 1.1 content.")]),
            Heading(level=2, content=[Text(content="Section 1.2")]),
            Paragraph(content=[Text(content="Section 1.2 content.")]),
            Heading(level=1, content=[Text(content="Chapter 2")]),
            Paragraph(content=[Text(content="Chapter 2 intro.")]),
            Heading(level=2, content=[Text(content="Section 2.1")]),
            Paragraph(content=[Text(content="Section 2.1 content.")]),
        ]
    )


@pytest.fixture
def long_doc():
    """Create a long document with multiple sections for word count splitting."""
    children = []
    for i in range(10):
        children.append(Heading(level=1, content=[Text(content=f"Section {i+1}")]))
        text = " ".join([f"word{j}" for j in range(100)])
        children.append(Paragraph(content=[Text(content=text)]))
    return Document(children=children)


class TestParseSpliSpec:
    """Tests for parse_split_spec function."""

    def test_parse_heading_specs(self):
        """Test parsing heading level specifications."""
        assert parse_split_spec("h1") == ("heading", 1)
        assert parse_split_spec("h2") == ("heading", 2)
        assert parse_split_spec("h6") == ("heading", 6)
        assert parse_split_spec("H3") == ("heading", 3)

    def test_parse_length_spec(self):
        """Test parsing word count specifications."""
        assert parse_split_spec("length=500") == ("length", 500)
        assert parse_split_spec("length=1000") == ("length", 1000)
        assert parse_split_spec("LENGTH=200") == ("length", 200)

    def test_parse_parts_spec(self):
        """Test parsing parts specifications."""
        assert parse_split_spec("parts=3") == ("parts", 3)
        assert parse_split_spec("parts=10") == ("parts", 10)
        assert parse_split_spec("PARTS=5") == ("parts", 5)

    def test_parse_simple_specs(self):
        """Test parsing simple specifications."""
        assert parse_split_spec("auto") == ("auto", None)
        assert parse_split_spec("page") == ("page", None)
        assert parse_split_spec("chapter") == ("chapter", None)
        assert parse_split_spec("AUTO") == ("auto", None)

    def test_parse_delimiter_spec(self):
        """Test parsing delimiter specifications."""
        assert parse_split_spec("delimiter=-----") == ("delimiter", "-----")
        assert parse_split_spec("delimiter=***") == ("delimiter", "***")
        assert parse_split_spec("DELIMITER=-----") == ("delimiter", "-----")

        # Test with escape sequences
        strategy, param = parse_split_spec("delimiter=\\n---\\n")
        assert strategy == "delimiter"
        assert "\n" in param
        assert "---" in param

    def test_invalid_heading_level(self):
        """Test that invalid heading levels raise errors."""
        with pytest.raises(ValueError, match="Heading level must be between 1 and 6"):
            parse_split_spec("h7")

        with pytest.raises(ValueError, match="Heading level must be between 1 and 6"):
            parse_split_spec("h0")

    def test_invalid_length(self):
        """Test that invalid length values raise errors."""
        with pytest.raises(ValueError, match="Invalid length value"):
            parse_split_spec("length=abc")

        with pytest.raises(ValueError, match="Invalid length value"):
            parse_split_spec("length=0")

        with pytest.raises(ValueError, match="Invalid length value"):
            parse_split_spec("length=-5")

    def test_invalid_parts(self):
        """Test that invalid parts values raise errors."""
        with pytest.raises(ValueError, match="Invalid parts value"):
            parse_split_spec("parts=xyz")

        with pytest.raises(ValueError, match="Invalid parts value"):
            parse_split_spec("parts=0")

    def test_unknown_strategy(self):
        """Test that unknown strategies raise errors."""
        with pytest.raises(ValueError, match="Invalid split specification"):
            parse_split_spec("unknown")

        with pytest.raises(ValueError, match="Unknown split strategy"):
            parse_split_spec("badkey=123")


class TestSplitResult:
    """Tests for SplitResult class."""

    def test_filename_slug_basic(self):
        """Test basic filename slug generation."""
        split = SplitResult(
            document=Document(children=[]),
            index=1,
            title="Introduction",
            word_count=100,
        )
        assert split.get_filename_slug() == "introduction"

    def test_filename_slug_with_spaces(self):
        """Test slug generation with spaces."""
        split = SplitResult(
            document=Document(children=[]),
            index=1,
            title="Chapter 1: Getting Started",
            word_count=100,
        )
        assert split.get_filename_slug() == "chapter-1-getting-started"

    def test_filename_slug_with_special_chars(self):
        """Test slug generation with special characters."""
        split = SplitResult(
            document=Document(children=[]),
            index=1,
            title="Methods & Results (2024)",
            word_count=100,
        )
        assert split.get_filename_slug() == "methods-results-2024"

    def test_filename_slug_truncation(self):
        """Test that long titles are truncated."""
        long_title = "This is a very long title " * 20
        split = SplitResult(
            document=Document(children=[]),
            index=1,
            title=long_title,
            word_count=100,
        )
        slug = split.get_filename_slug()
        assert len(slug) <= 100

    def test_filename_slug_empty_title(self):
        """Test slug generation with no title."""
        split = SplitResult(
            document=Document(children=[]),
            index=1,
            title=None,
            word_count=100,
        )
        assert split.get_filename_slug() == ""


class TestSplitByHeadingLevel:
    """Tests for split_by_heading_level method."""

    def test_split_by_h1(self, simple_doc):
        """Test splitting by H1 headings."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_heading_level(simple_doc, level=1)

        assert len(splits) == 4
        assert splits[0].title == "Preamble"
        assert splits[1].title == "Introduction"
        assert splits[2].title == "Methods"
        assert splits[3].title == "Results"

        for i, split in enumerate(splits, 1):
            assert split.index == i
            assert split.word_count > 0

    def test_split_by_h1_no_preamble(self, simple_doc):
        """Test splitting without preamble."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_heading_level(simple_doc, level=1, include_preamble=False)

        assert len(splits) == 3
        assert splits[0].title == "Introduction"
        assert splits[1].title == "Methods"
        assert splits[2].title == "Results"

    def test_split_by_h2(self, nested_doc):
        """Test splitting by H2 headings."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_heading_level(nested_doc, level=2)

        assert len(splits) == 3
        assert "Section 1.1" in splits[0].title
        assert "Section 1.2" in splits[1].title
        assert "Section 2.1" in splits[2].title

    def test_split_no_headings(self):
        """Test splitting document with no headings."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Just some text.")]),
                Paragraph(content=[Text(content="More text here.")]),
            ]
        )
        splitter = DocumentSplitter()
        splits = splitter.split_by_heading_level(doc, level=1)

        assert len(splits) == 1
        assert splits[0].title == "Preamble" or splits[0].title is None
        assert splits[0].metadata.get("reason") == "no_headings_found" or splits[0].title == "Preamble"

    def test_invalid_heading_level(self, simple_doc):
        """Test that invalid heading levels raise errors."""
        splitter = DocumentSplitter()

        with pytest.raises(ValueError, match="Heading level must be between 1 and 6"):
            splitter.split_by_heading_level(simple_doc, level=0)

        with pytest.raises(ValueError, match="Heading level must be between 1 and 6"):
            splitter.split_by_heading_level(simple_doc, level=7)


class TestSplitByWordCount:
    """Tests for split_by_word_count method."""

    def test_split_by_word_count(self, long_doc):
        """Test splitting by word count."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_word_count(long_doc, target_words=200)

        assert len(splits) > 1

        for split in splits:
            assert split.word_count > 0

    def test_split_respects_boundaries(self, simple_doc):
        """Test that splits respect section boundaries."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_word_count(simple_doc, target_words=5)

        assert len(splits) >= 3

        for split in splits:
            has_heading = any(isinstance(child, Heading) for child in split.document.children)
            assert has_heading or split.title == "Preamble"

    def test_invalid_word_count(self, simple_doc):
        """Test that invalid word counts raise errors."""
        splitter = DocumentSplitter()

        with pytest.raises(ValueError, match="target_words must be at least 1"):
            splitter.split_by_word_count(simple_doc, target_words=0)

        with pytest.raises(ValueError, match="target_words must be at least 1"):
            splitter.split_by_word_count(simple_doc, target_words=-10)

    def test_split_no_sections(self):
        """Test splitting document with no sections."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Just some text.")]),
            ]
        )
        splitter = DocumentSplitter()
        splits = splitter.split_by_word_count(doc, target_words=100)

        assert len(splits) == 1
        assert splits[0].metadata.get("reason") == "no_sections"


class TestSplitByParts:
    """Tests for split_by_parts method."""

    def test_split_by_parts(self, long_doc):
        """Test splitting into equal parts."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_parts(long_doc, num_parts=3)

        assert len(splits) >= 2

        total_words = sum(split.word_count for split in splits)
        avg_words = total_words / len(splits)

        for split in splits:
            assert split.word_count > 0
            assert abs(split.word_count - avg_words) / avg_words < 2.0

    def test_split_into_one_part(self, simple_doc):
        """Test splitting into one part (no split)."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_parts(simple_doc, num_parts=1)

        assert len(splits) >= 1

    def test_invalid_num_parts(self, simple_doc):
        """Test that invalid num_parts raises errors."""
        splitter = DocumentSplitter()

        with pytest.raises(ValueError, match="num_parts must be at least 1"):
            splitter.split_by_parts(simple_doc, num_parts=0)

        with pytest.raises(ValueError, match="num_parts must be at least 1"):
            splitter.split_by_parts(simple_doc, num_parts=-5)

    def test_split_empty_doc(self):
        """Test splitting empty document."""
        doc = Document(children=[])
        splitter = DocumentSplitter()
        splits = splitter.split_by_parts(doc, num_parts=3)

        assert len(splits) == 1
        assert splits[0].word_count == 0


class TestSplitByDelimiter:
    """Tests for split_by_delimiter method."""

    def test_split_by_delimiter_basic(self):
        """Test basic delimiter splitting."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First section content.")]),
                Paragraph(content=[Text(content="-----")]),
                Paragraph(content=[Text(content="Second section content.")]),
                Paragraph(content=[Text(content="-----")]),
                Paragraph(content=[Text(content="Third section content.")]),
            ]
        )

        splitter = DocumentSplitter()
        splits = splitter.split_by_delimiter(doc, delimiter="-----")

        assert len(splits) == 3
        assert splits[0].title == "Part 1"
        assert splits[1].title == "Part 2"
        assert splits[2].title == "Part 3"

        for split in splits:
            assert split.word_count > 0

    def test_split_by_delimiter_no_matches(self):
        """Test delimiter splitting with no matches."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Just some content.")]),
                Paragraph(content=[Text(content="More content here.")]),
            ]
        )

        splitter = DocumentSplitter()
        splits = splitter.split_by_delimiter(doc, delimiter="-----")

        # When no delimiters found, it treats whole document as one part
        assert len(splits) == 1
        assert splits[0].title == "Part 1"

    def test_split_by_delimiter_whitespace_handling(self):
        """Test that delimiters with whitespace are handled correctly."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Content 1")]),
                Paragraph(content=[Text(content="  -----  ")]),  # Whitespace around delimiter
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        splitter = DocumentSplitter()
        splits = splitter.split_by_delimiter(doc, delimiter="-----")

        assert len(splits) == 2

    def test_split_by_delimiter_custom_markers(self):
        """Test splitting with custom markers."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Section A")]),
                Paragraph(content=[Text(content="***")]),
                Paragraph(content=[Text(content="Section B")]),
                Paragraph(content=[Text(content="***")]),
                Paragraph(content=[Text(content="Section C")]),
            ]
        )

        splitter = DocumentSplitter()
        splits = splitter.split_by_delimiter(doc, delimiter="***")

        assert len(splits) == 3

    def test_split_by_empty_delimiter(self):
        """Test that empty delimiter raises error."""
        doc = Document(children=[Paragraph(content=[Text(content="test")])])
        splitter = DocumentSplitter()

        with pytest.raises(ValueError, match="Delimiter cannot be empty"):
            splitter.split_by_delimiter(doc, delimiter="")

    def test_split_by_delimiter_at_start(self):
        """Test handling delimiter at document start."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="-----")]),
                Paragraph(content=[Text(content="Content after delimiter.")]),
            ]
        )

        splitter = DocumentSplitter()
        splits = splitter.split_by_delimiter(doc, delimiter="-----")

        assert len(splits) == 1
        assert "Content after delimiter" in extract_text(splits[0].document.children)

    def test_split_by_delimiter_at_end(self):
        """Test handling delimiter at document end."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Content before delimiter.")]),
                Paragraph(content=[Text(content="-----")]),
            ]
        )

        splitter = DocumentSplitter()
        splits = splitter.split_by_delimiter(doc, delimiter="-----")

        assert len(splits) == 1
        assert "Content before delimiter" in extract_text(splits[0].document.children)


class TestSplitAuto:
    """Tests for split_auto method."""

    def test_auto_prefers_h1(self, simple_doc):
        """Test that auto mode prefers H1 when sections are reasonable."""
        splitter = DocumentSplitter()
        splits = splitter.split_auto(simple_doc, target_words=1000)

        assert len(splits) >= 3
        assert any("auto:h1" in split.metadata.get("strategy", "") for split in splits)

    def test_auto_uses_h2_for_large_h1(self, nested_doc):
        """Test that auto mode uses H2 when H1 sections are large."""
        splitter = DocumentSplitter()

        doc_with_large_h1 = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content=" ".join([f"word{i}" for i in range(2000)]))]),
                Heading(level=2, content=[Text(content="Section 1.1")]),
                Paragraph(content=[Text(content="Section 1.1 content.")]),
                Heading(level=2, content=[Text(content="Section 1.2")]),
                Paragraph(content=[Text(content="Section 1.2 content.")]),
            ]
        )

        splits = splitter.split_auto(doc_with_large_h1, target_words=100)

        assert len(splits) >= 2

    def test_auto_falls_back_to_word_count(self):
        """Test that auto mode falls back to word count for unstructured docs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content=" ".join([f"word{i}" for i in range(1000)]))]),
            ]
        )
        splitter = DocumentSplitter()
        splits = splitter.split_auto(doc, target_words=200)

        assert len(splits) >= 1
