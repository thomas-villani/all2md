#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/test_mcp_document_tools.py
"""Integration tests for MCP document manipulation tool (simplified interface).

Tests cover all 9 supported actions:
- list-sections
- extract
- add:before
- add:after
- remove
- replace
- insert:start
- insert:end
- insert:after_heading

"""


import pytest

from all2md.mcp.config import MCPConfig
from all2md.mcp.document_tools import edit_document_impl
from all2md.mcp.schemas import EditDocumentSimpleInput


@pytest.mark.integration
class TestMCPDocumentToolListSections:
    """Tests for list-sections action."""

    def test_list_sections_from_file(self, tmp_path):
        """Test listing sections from markdown file."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Chapter 1

Content for chapter 1.

## Section 1.1

Content for section 1.1.

# Chapter 2

Content for chapter 2.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="list-sections",
            doc=str(md_file)
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "3 section(s)" in result.message
        assert result.content is not None
        assert "Chapter 1" in result.content
        assert "Section 1.1" in result.content
        assert "Chapter 2" in result.content
        assert "[#0]" in result.content
        assert "[#1]" in result.content
        assert "[#2]" in result.content


@pytest.mark.integration
class TestMCPDocumentToolExtract:
    """Tests for extract action."""

    def test_extract_by_heading_text(self, tmp_path):
        """Test extracting section by heading text (case-insensitive)."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Introduction

Intro content.

# Methods

Methods content.

# Results

Results content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="extract",
            doc=str(md_file),
            target="Methods"  # Case-insensitive
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "extracted" in result.message.lower()
        assert "Methods" in result.message
        assert result.content is not None
        assert "Methods" in result.content
        assert "Methods content" in result.content
        assert "Introduction" not in result.content
        assert "Results" not in result.content

    def test_extract_by_heading_case_insensitive(self, tmp_path):
        """Test that heading matching is case-insensitive."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Introduction

Content here.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="extract",
            doc=str(md_file),
            target="introduction"  # Lowercase
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert result.content is not None
        assert "Introduction" in result.content

    def test_extract_by_index_notation(self, tmp_path):
        """Test extracting section by index notation (#0, #1, etc.)."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# First

Content.

# Second

Content.

# Third

Content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="extract",
            doc=str(md_file),
            target="#1"  # Second section (zero-based)
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "#1" in result.message
        assert result.content is not None
        assert "Second" in result.content
        assert "First" not in result.content
        assert "Third" not in result.content

    def test_extract_missing_section_returns_error(self, tmp_path):
        """Test that extracting nonexistent section returns error."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Existing

Content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="extract",
            doc=str(md_file),
            target="Nonexistent"
        )

        result = edit_document_impl(input_data, config)

        assert result.success is False
        assert "[ERROR]" in result.message
        assert "not found" in result.message.lower()


@pytest.mark.integration
class TestMCPDocumentToolAddSection:
    """Tests for add:before and add:after actions."""

    def test_add_section_after(self, tmp_path):
        """Test adding section after target."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# First

Content 1.

# Third

Content 3.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="add:after",
            doc=str(md_file),
            target="First",
            content="# Second\n\nContent 2."
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "added" in result.message.lower()
        assert "First" in result.message
        assert result.content is not None
        assert "# Second" in result.content
        # Verify ordering
        first_pos = result.content.index("First")
        second_pos = result.content.index("Second")
        third_pos = result.content.index("Third")
        assert first_pos < second_pos < third_pos

    def test_add_section_before(self, tmp_path):
        """Test adding section before target."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Second

Content 2.

# Third

Content 3.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="add:before",
            doc=str(md_file),
            target="Second",
            content="# First\n\nContent 1."
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "added" in result.message.lower()
        assert "before" in result.message
        assert result.content is not None
        assert "# First" in result.content
        # Verify ordering
        first_pos = result.content.index("First")
        second_pos = result.content.index("Second")
        assert first_pos < second_pos

    def test_add_section_using_index_notation(self, tmp_path):
        """Test adding section using index notation for target."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Section 1

Content 1.

# Section 2

Content 2.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="add:after",
            doc=str(md_file),
            target="#0",  # After first section
            content="# New Section\n\nNew content."
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "#0" in result.message
        assert result.content is not None
        assert "New Section" in result.content


@pytest.mark.integration
class TestMCPDocumentToolRemoveSection:
    """Tests for remove action."""

    def test_remove_section_by_heading(self, tmp_path):
        """Test removing section by heading text."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Keep This

Content.

# Remove This

Content to remove.

# Keep This Too

More content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="remove",
            doc=str(md_file),
            target="Remove This"
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "removed" in result.message.lower()
        assert "Remove This" in result.message
        assert result.content is not None
        assert "Remove This" not in result.content
        assert "Keep This" in result.content
        assert "Keep This Too" in result.content

    def test_remove_section_by_index(self, tmp_path):
        """Test removing section by index notation."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# First

Content.

# Second

Content.

# Third

Content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="remove",
            doc=str(md_file),
            target="#1"  # Remove middle section
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "#1" in result.message
        assert result.content is not None
        assert "Second" not in result.content
        assert "First" in result.content
        assert "Third" in result.content


@pytest.mark.integration
class TestMCPDocumentToolReplaceSection:
    """Tests for replace action."""

    def test_replace_section_content(self, tmp_path):
        """Test replacing section with new content."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Introduction

Old introduction content.

# Methods

Methods content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="replace",
            doc=str(md_file),
            target="Introduction",
            content="# Introduction\n\nNew introduction content with more details."
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "replaced" in result.message.lower()
        assert "Introduction" in result.message
        assert result.content is not None
        assert "New introduction content" in result.content
        assert "Old introduction content" not in result.content
        assert "Methods" in result.content  # Other sections preserved


@pytest.mark.integration
class TestMCPDocumentToolInsertContent:
    """Tests for insert:start, insert:end, and insert:after_heading actions."""

    def test_insert_content_at_end(self, tmp_path):
        """Test inserting content at end of section."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Section

Existing content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="insert:end",
            doc=str(md_file),
            target="Section",
            content="Additional paragraph at the end."
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "inserted" in result.message.lower()
        assert result.content is not None
        assert "Existing content" in result.content
        assert "Additional paragraph" in result.content

    def test_insert_content_at_start(self, tmp_path):
        """Test inserting content at start of section."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Section

Existing content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="insert:start",
            doc=str(md_file),
            target="Section",
            content="New first paragraph."
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "inserted" in result.message.lower()
        assert result.content is not None
        assert "New first paragraph" in result.content
        assert "Existing content" in result.content

    def test_insert_content_after_heading(self, tmp_path):
        """Test inserting content right after heading."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Section

Existing content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="insert:after_heading",
            doc=str(md_file),
            target="Section",
            content="Inserted right after heading."
        )

        result = edit_document_impl(input_data, config)

        assert result.success is True
        assert "inserted" in result.message.lower()
        assert result.content is not None
        assert "Inserted right after heading" in result.content


@pytest.mark.integration
class TestMCPDocumentToolErrorHandling:
    """Tests for error handling and validation."""

    def test_missing_target_for_extract_returns_error(self, tmp_path):
        """Test that extract without target returns error."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Content\n\nText.")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="extract",
            doc=str(md_file)
            # Missing target parameter
        )

        result = edit_document_impl(input_data, config)

        assert result.success is False
        assert "[ERROR]" in result.message
        assert "requires a target" in result.message

    def test_missing_content_for_add_returns_error(self, tmp_path):
        """Test that add without content returns error."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nContent.")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="add:after",
            doc=str(md_file),
            target="Section"
            # Missing content parameter
        )

        result = edit_document_impl(input_data, config)

        assert result.success is False
        assert "[ERROR]" in result.message
        assert "requires content" in result.message

    def test_invalid_index_notation_returns_error(self, tmp_path):
        """Test that invalid index notation returns error."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nContent.")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="extract",
            doc=str(md_file),
            target="#abc"  # Invalid - not a number
        )

        result = edit_document_impl(input_data, config)

        assert result.success is False
        assert "[ERROR]" in result.message
        assert "Invalid target index format" in result.message

    def test_path_not_in_allowlist_returns_error(self, tmp_path):
        """Test that path outside allowlist returns error."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        forbidden_file = forbidden_dir / "doc.md"
        forbidden_file.write_text("# Secret\n\nContent.")

        config = MCPConfig(read_allowlist=[str(allowed_dir)])
        input_data = EditDocumentSimpleInput(
            action="list-sections",
            doc=str(forbidden_file)
        )

        result = edit_document_impl(input_data, config)

        assert result.success is False
        assert "[ERROR]" in result.message
        assert "access denied" in result.message.lower()

    def test_nonexistent_file_returns_error(self, tmp_path):
        """Test that nonexistent file returns error."""
        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentSimpleInput(
            action="list-sections",
            doc=str(tmp_path / "nonexistent.md")
        )

        result = edit_document_impl(input_data, config)

        assert result.success is False
        assert "[ERROR]" in result.message
