#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_document_utils.py
"""Unit tests for document manipulation utilities.

Tests cover:
- Section extraction and query functions
- Section manipulation (add, remove, replace)
- Content insertion and positioning
- TOC generation and insertion
- Document splitting and utilities

"""

import pytest

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    List,
    Paragraph,
    Text,
)
from all2md.ast.document_utils import (
    Section,
    add_section_after,
    add_section_before,
    count_sections,
    extract_section,
    find_heading,
    find_section_by_heading,
    find_sections,
    generate_toc,
    get_all_sections,
    get_preamble,
    get_section_by_index,
    insert_into_section,
    insert_toc,
    remove_section,
    replace_section,
    split_by_sections,
)


@pytest.mark.unit
class TestSectionClass:
    """Tests for Section dataclass."""

    def test_create_section(self):
        """Test creating a section."""
        heading = Heading(level=1, content=[Text("Title")])
        para = Paragraph(content=[Text("Content")])
        section = Section(
            heading=heading,
            content=[para],
            level=1,
            start_index=0,
            end_index=2
        )

        assert section.heading == heading
        assert len(section.content) == 1
        assert section.level == 1
        assert section.start_index == 0
        assert section.end_index == 2

    def test_section_to_document(self):
        """Test converting section to document."""
        heading = Heading(level=2, content=[Text("Section")])
        para = Paragraph(content=[Text("Text")])
        section = Section(
            heading=heading,
            content=[para],
            level=2,
            start_index=0,
            end_index=0
        )

        doc = section.to_document()
        assert isinstance(doc, Document)
        assert len(doc.children) == 2
        assert doc.children[0] == heading
        assert doc.children[1] == para

    def test_get_heading_text(self):
        """Test extracting heading text."""
        from all2md.ast import Strong
        heading = Heading(level=1, content=[
            Text("Hello "),
            Strong(content=[Text("world")]),
            Text("!")
        ])
        section = Section(
            heading=heading,
            content=[],
            level=1,
            start_index=0,
            end_index=0
        )

        text = section.get_heading_text()
        # extract_text adds spaces between nodes, so "Hello " + "world " + "!" = "Hello  world !"
        assert text == "Hello  world !"


@pytest.mark.unit
class TestGetAllSections:
    """Tests for get_all_sections function."""

    def test_empty_document(self):
        """Test getting sections from empty document."""
        doc = Document()
        sections = get_all_sections(doc)
        assert sections == []

    def test_no_headings(self):
        """Test document with no headings."""
        doc = Document(children=[
            Paragraph(content=[Text("No headings here")])
        ])
        sections = get_all_sections(doc)
        assert sections == []

    def test_single_section(self):
        """Test document with single section."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Content")])
        ])
        sections = get_all_sections(doc)

        assert len(sections) == 1
        assert sections[0].level == 1
        assert sections[0].get_heading_text() == "Title"
        assert len(sections[0].content) == 1

    def test_multiple_sections_same_level(self):
        """Test document with multiple sections at same level."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Paragraph(content=[Text("First content")]),
            Heading(level=1, content=[Text("Second")]),
            Paragraph(content=[Text("Second content")])
        ])
        sections = get_all_sections(doc)

        assert len(sections) == 2
        assert sections[0].get_heading_text() == "First"
        assert sections[1].get_heading_text() == "Second"

    def test_nested_sections(self):
        """Test document with nested section hierarchy."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Paragraph(content=[Text("Intro")]),
            Heading(level=2, content=[Text("Section 1.1")]),
            Paragraph(content=[Text("Content 1.1")]),
            Heading(level=2, content=[Text("Section 1.2")]),
            Paragraph(content=[Text("Content 1.2")]),
            Heading(level=1, content=[Text("Chapter 2")]),
            Paragraph(content=[Text("Chapter 2 content")])
        ])
        sections = get_all_sections(doc)

        assert len(sections) == 4
        assert sections[0].get_heading_text() == "Chapter 1"
        assert sections[1].get_heading_text() == "Section 1.1"
        assert sections[2].get_heading_text() == "Section 1.2"
        assert sections[3].get_heading_text() == "Chapter 2"

    def test_level_filtering(self):
        """Test filtering sections by level range."""
        doc = Document(children=[
            Heading(level=1, content=[Text("H1")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=2, content=[Text("H2")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=3, content=[Text("H3")]),
            Paragraph(content=[Text("Content")])
        ])

        # Get only level 1
        sections_l1 = get_all_sections(doc, min_level=1, max_level=1)
        assert len(sections_l1) == 1
        assert sections_l1[0].level == 1

        # Get levels 2-3
        sections_l2_3 = get_all_sections(doc, min_level=2, max_level=3)
        assert len(sections_l2_3) == 2
        assert sections_l2_3[0].level == 2
        assert sections_l2_3[1].level == 3

    def test_section_with_multiple_content_types(self):
        """Test section containing various content types."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Paragraph")]),
            CodeBlock(content="code", language="python"),
            BlockQuote(children=[Paragraph(content=[Text("Quote")])]),
            Heading(level=1, content=[Text("Next")])
        ])
        sections = get_all_sections(doc)

        assert len(sections) == 2
        assert len(sections[0].content) == 3

    def test_invalid_level_range(self):
        """Test that invalid level range raises error."""
        doc = Document()

        with pytest.raises(ValueError, match="Invalid level range"):
            get_all_sections(doc, min_level=3, max_level=1)

        with pytest.raises(ValueError, match="Invalid level range"):
            get_all_sections(doc, min_level=0, max_level=6)


@pytest.mark.unit
class TestFindSectionByHeading:
    """Tests for find_section_by_heading function."""

    def test_find_existing_section(self):
        """Test finding a section by heading text."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Introduction")]),
            Paragraph(content=[Text("Intro content")]),
            Heading(level=1, content=[Text("Methods")]),
            Paragraph(content=[Text("Methods content")])
        ])

        section = find_section_by_heading(doc, "Methods")
        assert section is not None
        assert section.get_heading_text() == "Methods"

    def test_find_nonexistent_section(self):
        """Test finding non-existent section returns None."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")])
        ])

        section = find_section_by_heading(doc, "Nonexistent")
        assert section is None

    def test_case_sensitive_search(self):
        """Test case-sensitive heading search."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Methods")]),
            Paragraph(content=[Text("Content")])
        ])

        # Case-sensitive: should not find
        section_sens = find_section_by_heading(doc, "methods", case_sensitive=True)
        assert section_sens is None

        # Case-insensitive: should find
        section_insens = find_section_by_heading(doc, "methods", case_sensitive=False)
        assert section_insens is not None
        assert section_insens.get_heading_text() == "Methods"

    def test_find_by_level(self):
        """Test finding section with specific level."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=2, content=[Text("Title")]),
            Paragraph(content=[Text("Content")])
        ])

        # Find level 1
        section_l1 = find_section_by_heading(doc, "Title", level=1)
        assert section_l1 is not None
        assert section_l1.level == 1

        # Find level 2
        section_l2 = find_section_by_heading(doc, "Title", level=2)
        assert section_l2 is not None
        assert section_l2.level == 2

    def test_find_first_match(self):
        """Test that first match is returned."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Duplicate")]),
            Paragraph(content=[Text("First")]),
            Heading(level=1, content=[Text("Duplicate")]),
            Paragraph(content=[Text("Second")])
        ])

        section = find_section_by_heading(doc, "Duplicate")
        assert section is not None
        assert section.start_index == 0


@pytest.mark.unit
class TestFindSections:
    """Tests for find_sections function."""

    def test_find_by_level(self):
        """Test finding sections by level."""
        doc = Document(children=[
            Heading(level=1, content=[Text("H1")]),
            Heading(level=2, content=[Text("H2")]),
            Heading(level=3, content=[Text("H3")])
        ])

        level_2_sections = find_sections(doc, lambda s: s.level == 2)
        assert len(level_2_sections) == 1
        assert level_2_sections[0].level == 2

    def test_find_by_content_length(self):
        """Test finding sections by content length."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Short")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("Long")]),
            Paragraph(content=[Text("Content 1")]),
            Paragraph(content=[Text("Content 2")]),
            Paragraph(content=[Text("Content 3")])
        ])

        long_sections = find_sections(doc, lambda s: len(s.content) >= 3)
        assert len(long_sections) == 1
        assert long_sections[0].get_heading_text() == "Long"

    def test_find_by_heading_text_pattern(self):
        """Test finding sections by heading text pattern."""
        doc = Document(children=[
            Heading(level=1, content=[Text("API Reference")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("API Usage")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("Installation")]),
            Paragraph(content=[Text("Content")])
        ])

        api_sections = find_sections(
            doc,
            lambda s: "API" in s.get_heading_text()
        )
        assert len(api_sections) == 2


@pytest.mark.unit
class TestGetSectionByIndex:
    """Tests for get_section_by_index function."""

    def test_get_by_positive_index(self):
        """Test getting section by positive index."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Heading(level=1, content=[Text("Second")]),
            Heading(level=1, content=[Text("Third")])
        ])

        section = get_section_by_index(doc, 1)
        assert section is not None
        assert section.get_heading_text() == "Second"

    def test_get_by_negative_index(self):
        """Test getting section by negative index."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Heading(level=1, content=[Text("Second")]),
            Heading(level=1, content=[Text("Third")])
        ])

        section = get_section_by_index(doc, -1)
        assert section is not None
        assert section.get_heading_text() == "Third"

    def test_get_out_of_range(self):
        """Test getting section with out-of-range index."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Only")])
        ])

        section = get_section_by_index(doc, 99)
        assert section is None

        section_neg = get_section_by_index(doc, -99)
        assert section_neg is None


@pytest.mark.unit
class TestAddSection:
    """Tests for add_section_after and add_section_before."""

    def test_add_section_after_by_heading(self):
        """Test adding section after target heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Paragraph(content=[Text("Content")])
        ])

        new_section = Section(
            heading=Heading(level=1, content=[Text("New")]),
            content=[Paragraph(content=[Text("New content")])],
            level=1,
            start_index=0,
            end_index=0
        )

        modified = add_section_after(doc, "First", new_section)

        assert len(modified.children) == 4
        assert isinstance(modified.children[2], Heading)
        sections = get_all_sections(modified)
        assert sections[1].get_heading_text() == "New"

    def test_add_section_before_by_heading(self):
        """Test adding section before target heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Second")]),
            Paragraph(content=[Text("Content")])
        ])

        new_section = Section(
            heading=Heading(level=1, content=[Text("First")]),
            content=[Paragraph(content=[Text("First content")])],
            level=1,
            start_index=0,
            end_index=0
        )

        modified = add_section_before(doc, "Second", new_section)

        sections = get_all_sections(modified)
        assert len(sections) == 2
        assert sections[0].get_heading_text() == "First"
        assert sections[1].get_heading_text() == "Second"

    def test_add_section_by_index(self):
        """Test adding section using index."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Heading(level=1, content=[Text("Third")])
        ])

        new_section = Section(
            heading=Heading(level=1, content=[Text("Second")]),
            content=[],
            level=1,
            start_index=0,
            end_index=0
        )

        modified = add_section_after(doc, 0, new_section)

        sections = get_all_sections(modified)
        assert len(sections) == 3
        assert sections[1].get_heading_text() == "Second"

    def test_add_section_document(self):
        """Test adding a Document instead of Section."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")])
        ])

        new_doc = Document(children=[
            Heading(level=1, content=[Text("Second")]),
            Paragraph(content=[Text("Content")])
        ])

        modified = add_section_after(doc, 0, new_doc)

        sections = get_all_sections(modified)
        assert len(sections) == 2

    def test_add_section_nonexistent_target(self):
        """Test that adding section to nonexistent target raises error."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Only")])
        ])

        new_section = Section(
            heading=Heading(level=1, content=[Text("New")]),
            content=[],
            level=1,
            start_index=0,
            end_index=0
        )

        with pytest.raises(ValueError, match="Target section not found"):
            add_section_after(doc, "Nonexistent", new_section)


@pytest.mark.unit
class TestRemoveSection:
    """Tests for remove_section function."""

    def test_remove_section_by_heading(self):
        """Test removing section by heading text."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Keep")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("Remove")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("Keep")])
        ])

        modified = remove_section(doc, "Remove")

        sections = get_all_sections(modified)
        assert len(sections) == 2
        assert all(s.get_heading_text() == "Keep" for s in sections)

    def test_remove_section_by_index(self):
        """Test removing section by index."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Heading(level=1, content=[Text("Second")]),
            Heading(level=1, content=[Text("Third")])
        ])

        modified = remove_section(doc, 1)

        sections = get_all_sections(modified)
        assert len(sections) == 2
        assert sections[0].get_heading_text() == "First"
        assert sections[1].get_heading_text() == "Third"

    def test_remove_section_with_content(self):
        """Test that section content is removed with heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Remove")]),
            Paragraph(content=[Text("Content 1")]),
            Paragraph(content=[Text("Content 2")]),
            CodeBlock(content="code"),
            Heading(level=1, content=[Text("Keep")])
        ])

        modified = remove_section(doc, "Remove")

        # Should have removed 4 nodes (heading + 3 content)
        assert len(modified.children) == 1

    def test_remove_nonexistent_section(self):
        """Test that removing nonexistent section raises error."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Only")])
        ])

        with pytest.raises(ValueError, match="Target section not found"):
            remove_section(doc, "Nonexistent")


@pytest.mark.unit
class TestReplaceSection:
    """Tests for replace_section function."""

    def test_replace_section_with_new_section(self):
        """Test replacing section with new content."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Old")]),
            Paragraph(content=[Text("Old content")])
        ])

        new_section = Section(
            heading=Heading(level=1, content=[Text("New")]),
            content=[Paragraph(content=[Text("New content")])],
            level=1,
            start_index=0,
            end_index=0
        )

        modified = replace_section(doc, "Old", new_section)

        sections = get_all_sections(modified)
        assert len(sections) == 1
        assert sections[0].get_heading_text() == "New"

    def test_replace_section_with_nodes(self):
        """Test replacing section with list of nodes."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Old")]),
            Paragraph(content=[Text("Content")])
        ])

        new_nodes = [
            Heading(level=1, content=[Text("Replaced")]),
            Paragraph(content=[Text("New paragraph 1")]),
            Paragraph(content=[Text("New paragraph 2")])
        ]

        modified = replace_section(doc, "Old", new_nodes)

        sections = get_all_sections(modified)
        assert len(sections) == 1
        assert len(sections[0].content) == 2


@pytest.mark.unit
class TestInsertIntoSection:
    """Tests for insert_into_section function."""

    def test_insert_at_end(self):
        """Test inserting content at end of section."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Existing")])
        ])

        new_para = Paragraph(content=[Text("Added at end")])
        modified = insert_into_section(doc, "Title", new_para, position="end")

        sections = get_all_sections(modified)
        assert len(sections[0].content) == 2
        assert isinstance(sections[0].content[1], Paragraph)

    def test_insert_at_start(self):
        """Test inserting content at start of section."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Existing")])
        ])

        new_para = Paragraph(content=[Text("Added at start")])
        modified = insert_into_section(doc, "Title", new_para, position="start")

        sections = get_all_sections(modified)
        assert len(sections[0].content) == 2
        assert isinstance(sections[0].content[0], Paragraph)

    def test_insert_after_heading(self):
        """Test inserting content right after heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Existing")])
        ])

        new_para = Paragraph(content=[Text("After heading")])
        modified = insert_into_section(doc, "Title", new_para, position="after_heading")

        sections = get_all_sections(modified)
        assert len(sections[0].content) == 2

    def test_insert_multiple_nodes(self):
        """Test inserting multiple nodes at once."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Existing")])
        ])

        new_nodes = [
            Paragraph(content=[Text("New 1")]),
            Paragraph(content=[Text("New 2")])
        ]

        modified = insert_into_section(doc, "Title", new_nodes, position="end")

        sections = get_all_sections(modified)
        assert len(sections[0].content) == 3


@pytest.mark.unit
class TestExtractSection:
    """Tests for extract_section function."""

    def test_extract_section_by_heading(self):
        """Test extracting section as standalone document."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Extract")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("Other")])
        ])

        extracted = extract_section(doc, "Extract")

        assert isinstance(extracted, Document)
        assert len(extracted.children) == 2
        sections = get_all_sections(extracted)
        assert len(sections) == 1

    def test_extract_section_by_index(self):
        """Test extracting section by index."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Heading(level=1, content=[Text("Second")]),
            Heading(level=1, content=[Text("Third")])
        ])

        extracted = extract_section(doc, 1)

        sections = get_all_sections(extracted)
        assert len(sections) == 1
        assert sections[0].get_heading_text() == "Second"


@pytest.mark.unit
class TestSplitBySection:
    """Tests for split_by_sections function."""

    def test_split_document(self):
        """Test splitting document into multiple documents."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First")]),
            Paragraph(content=[Text("Content 1")]),
            Heading(level=1, content=[Text("Second")]),
            Paragraph(content=[Text("Content 2")])
        ])

        docs = split_by_sections(doc, include_preamble=False)

        assert len(docs) == 2
        assert isinstance(docs[0], Document)
        assert isinstance(docs[1], Document)

    def test_split_with_preamble(self):
        """Test splitting document with preamble included."""
        doc = Document(children=[
            Paragraph(content=[Text("Preamble content")]),
            Heading(level=1, content=[Text("First")]),
            Paragraph(content=[Text("Content")])
        ])

        docs = split_by_sections(doc, include_preamble=True)

        assert len(docs) == 2
        assert len(docs[0].children) == 1
        assert isinstance(docs[0].children[0], Paragraph)

    def test_split_without_preamble(self):
        """Test splitting document without preamble."""
        doc = Document(children=[
            Paragraph(content=[Text("Preamble")]),
            Heading(level=1, content=[Text("First")])
        ])

        docs = split_by_sections(doc, include_preamble=False)

        assert len(docs) == 1


@pytest.mark.unit
class TestGenerateTOC:
    """Tests for generate_toc function."""

    def test_generate_markdown_toc(self):
        """Test generating markdown-style TOC."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=2, content=[Text("Section 1.1")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("Chapter 2")])
        ])

        toc = generate_toc(doc, max_level=3, style="markdown")

        assert isinstance(toc, str)
        assert "Chapter 1" in toc
        assert "Section 1.1" in toc
        assert "Chapter 2" in toc

    def test_generate_list_toc(self):
        """Test generating list-style TOC."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title 1")]),
            Heading(level=1, content=[Text("Title 2")])
        ])

        toc = generate_toc(doc, style="list")

        assert isinstance(toc, List)
        assert len(toc.items) == 2

    def test_toc_max_level(self):
        """Test TOC respects max_level."""
        doc = Document(children=[
            Heading(level=1, content=[Text("H1")]),
            Heading(level=2, content=[Text("H2")]),
            Heading(level=3, content=[Text("H3")]),
            Heading(level=4, content=[Text("H4")])
        ])

        toc = generate_toc(doc, max_level=2, style="markdown")

        assert "H1" in toc
        assert "H2" in toc
        assert "H3" not in toc
        assert "H4" not in toc

    def test_generate_nested_toc_two_levels(self):
        """Test generating nested TOC with two levels (H1 > H2)."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=2, content=[Text("Section 1.1")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=2, content=[Text("Section 1.2")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=1, content=[Text("Chapter 2")]),
            Paragraph(content=[Text("Content")]),
        ])

        toc = generate_toc(doc, max_level=3, style="nested")

        assert isinstance(toc, List)
        # Should have 2 top-level items (Chapter 1 and Chapter 2)
        assert len(toc.items) == 2

        # First item should be Chapter 1
        first_item = toc.items[0]
        assert len(first_item.children) == 2  # Paragraph + nested List
        assert isinstance(first_item.children[0], Paragraph)

        # Check nested list exists under Chapter 1
        nested_list = first_item.children[1]
        assert isinstance(nested_list, List)
        # Should have 2 nested items (Section 1.1 and 1.2)
        assert len(nested_list.items) == 2

    def test_generate_nested_toc_three_levels(self):
        """Test generating nested TOC with three levels (H1 > H2 > H3)."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Heading(level=2, content=[Text("Section 1.1")]),
            Heading(level=3, content=[Text("Subsection 1.1.1")]),
            Heading(level=3, content=[Text("Subsection 1.1.2")]),
            Heading(level=2, content=[Text("Section 1.2")]),
        ])

        toc = generate_toc(doc, max_level=3, style="nested")

        assert isinstance(toc, List)
        # Top level: Chapter 1
        assert len(toc.items) == 1

        # Chapter 1 should have nested list
        chapter1_item = toc.items[0]
        chapter1_nested = chapter1_item.children[1]
        assert isinstance(chapter1_nested, List)
        # Two sections under Chapter 1
        assert len(chapter1_nested.items) == 2

        # Section 1.1 should have nested list with 2 subsections
        section11_item = chapter1_nested.items[0]
        section11_nested = section11_item.children[1]
        assert isinstance(section11_nested, List)
        assert len(section11_nested.items) == 2

    def test_generate_nested_toc_level_jumps(self):
        """Test generating nested TOC with level jumps (H1 > H3)."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Heading(level=3, content=[Text("Subsection 1.0.1")]),  # Skip H2
            Heading(level=1, content=[Text("Chapter 2")]),
        ])

        toc = generate_toc(doc, max_level=3, style="nested")

        assert isinstance(toc, List)
        # Two top-level items
        assert len(toc.items) == 2

        # Chapter 1 should have nested structure even with level jump
        chapter1_item = toc.items[0]
        assert len(chapter1_item.children) == 2  # Paragraph + nested List

        # There should be an intermediate level created
        intermediate_list = chapter1_item.children[1]
        assert isinstance(intermediate_list, List)

    def test_generate_nested_toc_empty_document(self):
        """Test generating nested TOC from empty document."""
        doc = Document(children=[])

        toc = generate_toc(doc, style="nested")

        assert isinstance(toc, List)
        assert len(toc.items) == 0

    def test_generate_nested_toc_back_to_higher_level(self):
        """Test nested TOC correctly handles returning to higher levels."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Heading(level=2, content=[Text("Section 1.1")]),
            Heading(level=3, content=[Text("Subsection 1.1.1")]),
            Heading(level=1, content=[Text("Chapter 2")]),  # Back to H1
            Heading(level=2, content=[Text("Section 2.1")]),
        ])

        toc = generate_toc(doc, max_level=3, style="nested")

        assert isinstance(toc, List)
        # Two top-level chapters
        assert len(toc.items) == 2

        # Verify Chapter 2 has its own nested structure
        chapter2_item = toc.items[1]
        assert len(chapter2_item.children) == 2
        chapter2_nested = chapter2_item.children[1]
        assert isinstance(chapter2_nested, List)
        assert len(chapter2_nested.items) == 1  # Section 2.1

    def test_generate_nested_vs_flat_toc(self):
        """Test that nested and flat TOC have same number of total items."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Heading(level=2, content=[Text("Section 1.1")]),
            Heading(level=2, content=[Text("Section 1.2")]),
            Heading(level=1, content=[Text("Chapter 2")]),
        ])

        flat_toc = generate_toc(doc, style="list")
        nested_toc = generate_toc(doc, style="nested")

        # Count items in flat TOC
        flat_count = len(flat_toc.items)

        # Count items in nested TOC (recursively)
        def count_nested_items(lst):
            count = 0
            for item in lst.items:
                count += 1
                for child in item.children:
                    if isinstance(child, List):
                        count += count_nested_items(child)
            return count

        nested_count = count_nested_items(nested_toc)

        # Both should have same total number of items
        assert flat_count == nested_count == 4


@pytest.mark.unit
class TestInsertTOC:
    """Tests for insert_toc function."""

    def test_insert_toc_at_start(self):
        """Test inserting TOC at document start."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Paragraph(content=[Text("Content")])
        ])

        modified = insert_toc(doc, position="start", max_level=3)

        assert len(modified.children) > 2

    def test_insert_toc_after_first_heading(self):
        """Test inserting TOC after first heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=2, content=[Text("Section")])
        ])

        modified = insert_toc(doc, position="after_first_heading", max_level=3)

        # TOC should be inserted after first heading
        assert len(modified.children) > 3

    def test_insert_toc_builds_ast_directly(self):
        """Test that insert_toc builds AST directly without markdown parsing."""
        from all2md.ast import Link, ListItem

        doc = Document(children=[
            Heading(level=1, content=[Text("Chapter 1")]),
            Paragraph(content=[Text("Content")]),
            Heading(level=2, content=[Text("Section 1.1")]),
            Paragraph(content=[Text("Content")])
        ])

        modified = insert_toc(doc, position="start", max_level=3, style="markdown")

        # Verify TOC was inserted
        assert len(modified.children) > 4

        # First child should be TOC heading
        assert isinstance(modified.children[0], Heading)
        assert modified.children[0].level == 1
        toc_heading_text = modified.children[0].content[0].content
        assert toc_heading_text == "Table of Contents"

        # Second child should be the TOC list
        assert isinstance(modified.children[1], List)
        toc_list = modified.children[1]

        # List should have items with links
        assert len(toc_list.items) == 2  # Chapter 1 and Section 1.1

        # First item should contain a link to Chapter 1
        first_item = toc_list.items[0]
        assert isinstance(first_item, ListItem)
        first_para = first_item.children[0]
        assert isinstance(first_para, Paragraph)
        first_link = first_para.content[0]
        assert isinstance(first_link, Link)
        assert first_link.url == "#chapter-1"
        assert first_link.content[0].content == "Chapter 1"


@pytest.mark.unit
class TestGetPreamble:
    """Tests for get_preamble function."""

    def test_get_preamble_with_content(self):
        """Test getting preamble from document."""
        doc = Document(children=[
            Paragraph(content=[Text("Preamble line 1")]),
            Paragraph(content=[Text("Preamble line 2")]),
            Heading(level=1, content=[Text("First Section")]),
            Paragraph(content=[Text("Content")])
        ])

        preamble = get_preamble(doc)

        assert len(preamble) == 2
        assert all(isinstance(node, Paragraph) for node in preamble)

    def test_get_preamble_empty(self):
        """Test getting preamble from document starting with heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text("First Section")]),
            Paragraph(content=[Text("Content")])
        ])

        preamble = get_preamble(doc)

        assert preamble == []

    def test_get_preamble_no_headings(self):
        """Test getting preamble from document with no headings."""
        doc = Document(children=[
            Paragraph(content=[Text("All content")]),
            Paragraph(content=[Text("More content")])
        ])

        preamble = get_preamble(doc)

        assert len(preamble) == 2


@pytest.mark.unit
class TestCountSections:
    """Tests for count_sections function."""

    def test_count_all_sections(self):
        """Test counting all sections."""
        doc = Document(children=[
            Heading(level=1, content=[Text("H1")]),
            Heading(level=2, content=[Text("H2")]),
            Heading(level=3, content=[Text("H3")])
        ])

        count = count_sections(doc)
        assert count == 3

    def test_count_sections_by_level(self):
        """Test counting sections at specific level."""
        doc = Document(children=[
            Heading(level=1, content=[Text("H1")]),
            Heading(level=2, content=[Text("H2")]),
            Heading(level=3, content=[Text("H3")])
        ])

        count_l1 = count_sections(doc, level=1)
        assert count_l1 == 1

        count_l2 = count_sections(doc, level=2)
        assert count_l2 == 1


@pytest.mark.unit
class TestFindHeading:
    """Tests for find_heading function."""

    def test_find_heading_by_text(self):
        """Test finding heading by text."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Content")])
        ])

        result = find_heading(doc, "Title")

        assert result is not None
        assert result[0] == 0
        assert isinstance(result[1], Heading)

    def test_find_heading_returns_none(self):
        """Test finding nonexistent heading returns None."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")])
        ])

        result = find_heading(doc, "Nonexistent")

        assert result is None

    def test_find_heading_case_insensitive(self):
        """Test finding heading case-insensitively."""
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")])
        ])

        result = find_heading(doc, "title", case_sensitive=False)

        assert result is not None
        assert result[0] == 0
