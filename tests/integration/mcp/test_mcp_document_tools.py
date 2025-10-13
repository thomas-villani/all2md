#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/test_mcp_document_tools.py
"""Integration tests for MCP document manipulation tool.

Tests cover all 8 operations:
- list_sections
- get_section
- add_section
- remove_section
- replace_section
- insert_content
- generate_toc
- split_document

"""


import pytest

from all2md.mcp.config import MCPConfig
from all2md.mcp.document_tools import edit_document_ast_impl
from all2md.mcp.schemas import EditDocumentInput


@pytest.mark.integration
class TestMCPDocumentToolListSections:
    """Tests for list_sections operation."""

    def test_list_sections_from_markdown(self, tmp_path):
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
        input_data = EditDocumentInput(
            operation="list_sections",
            source_path=str(md_file),
            source_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.sections is not None
        assert result.section_count == 3
        assert len(result.sections) == 3
        assert result.sections[0].heading_text == "Chapter 1"
        assert result.sections[0].level == 1
        assert result.sections[1].heading_text == "Section 1.1"
        assert result.sections[1].level == 2

    def test_list_sections_from_inline_content(self):
        """Test listing sections from inline markdown content."""
        markdown_content = """# Title

Content here.

## Subtitle

More content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="list_sections",
            source_content=markdown_content,
            content_encoding="plain",
            source_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.section_count == 2
        assert result.sections[0].heading_text == "Title"
        assert result.sections[1].heading_text == "Subtitle"


@pytest.mark.integration
class TestMCPDocumentToolGetSection:
    """Tests for get_section operation."""

    def test_get_section_by_heading(self, tmp_path):
        """Test extracting section by heading text."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Introduction

Intro content.

# Methods

Methods content.

# Results

Results content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentInput(
            operation="get_section",
            source_path=str(md_file),
            source_format="markdown",
            target_heading="Methods",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Methods" in result.content
        assert "Methods content" in result.content
        assert "Introduction" not in result.content
        assert "Results" not in result.content
        assert result.sections_modified == 1

    def test_get_section_by_index(self, tmp_path):
        """Test extracting section by index."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# First

Content.

# Second

Content.

# Third

Content.
""")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentInput(
            operation="get_section",
            source_path=str(md_file),
            source_format="markdown",
            target_index=1,  # Second section
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Second" in result.content

    def test_get_section_to_file(self, tmp_path):
        """Test extracting section and writing to file."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("""# Section 1

Content 1.

# Section 2

Content 2.
""")

        output_file = tmp_path / "section.md"

        config = MCPConfig(
            read_allowlist=[str(tmp_path)],
            write_allowlist=[str(tmp_path)]
        )
        input_data = EditDocumentInput(
            operation="get_section",
            source_path=str(md_file),
            source_format="markdown",
            target_heading="Section 2",
            output_path=str(output_file),
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.output_path is not None
        assert output_file.exists()
        content = output_file.read_text()
        assert "Section 2" in content


@pytest.mark.integration
class TestMCPDocumentToolAddSection:
    """Tests for add_section operation."""

    def test_add_section_after(self):
        """Test adding section after target."""
        markdown_content = """# First

Content 1.

# Third

Content 3.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="add_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="First",
            position="after",
            content="# Second\n\nContent 2.",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "# Second" in result.content
        assert result.content.index("Second") > result.content.index("First")
        assert result.content.index("Second") < result.content.index("Third")
        assert result.sections_modified == 1

    def test_add_section_before(self):
        """Test adding section before target."""
        markdown_content = """# Second

Content 2.

# Third

Content 3.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="add_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Second",
            position="before",
            content="# First\n\nContent 1.",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "# First" in result.content
        assert result.content.index("First") < result.content.index("Second")


@pytest.mark.integration
class TestMCPDocumentToolRemoveSection:
    """Tests for remove_section operation."""

    def test_remove_section_by_heading(self):
        """Test removing section by heading text."""
        markdown_content = """# Keep This

Content.

# Remove This

Content to remove.

# Keep This Too

More content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="remove_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Remove This",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Remove This" not in result.content
        assert "Keep This" in result.content
        assert "Keep This Too" in result.content
        assert result.sections_modified == 1

    def test_remove_section_by_index(self):
        """Test removing section by index."""
        markdown_content = """# First

Content.

# Second

Content.

# Third

Content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="remove_section",
            source_content=markdown_content,
            source_format="markdown",
            target_index=1,  # Remove middle section
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Second" not in result.content
        assert "First" in result.content
        assert "Third" in result.content


@pytest.mark.integration
class TestMCPDocumentToolReplaceSection:
    """Tests for replace_section operation."""

    def test_replace_section_content(self):
        """Test replacing section with new content."""
        markdown_content = """# Introduction

Old introduction content.

# Methods

Methods content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="replace_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Introduction",
            content="# Introduction\n\nNew introduction content with more details.",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "New introduction content" in result.content
        assert "Old introduction content" not in result.content
        assert "Methods" in result.content  # Other sections preserved
        assert result.sections_modified == 1


@pytest.mark.integration
class TestMCPDocumentToolInsertContent:
    """Tests for insert_content operation."""

    def test_insert_content_at_end(self):
        """Test inserting content at end of section."""
        markdown_content = """# Section

Existing content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="insert_content",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Section",
            position="end",
            content="Additional paragraph at the end.",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Existing content" in result.content
        assert "Additional paragraph" in result.content
        assert result.sections_modified == 1

    def test_insert_content_at_start(self):
        """Test inserting content at start of section."""
        markdown_content = """# Section

Existing content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="insert_content",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Section",
            position="start",
            content="New first paragraph.",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "New first paragraph" in result.content
        assert "Existing content" in result.content

    def test_insert_content_after_heading(self):
        """Test inserting content right after heading."""
        markdown_content = """# Section

Existing content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="insert_content",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Section",
            position="after_heading",
            content="Inserted right after heading.",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Inserted right after heading" in result.content


@pytest.mark.integration
class TestMCPDocumentToolGenerateTOC:
    """Tests for generate_toc operation."""

    def test_generate_toc_markdown_style(self):
        """Test generating markdown-style TOC."""
        markdown_content = """# Chapter 1

Content.

## Section 1.1

Content.

# Chapter 2

Content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="generate_toc",
            source_content=markdown_content,
            source_format="markdown",
            max_toc_level=3,
            toc_style="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Table of Contents" in result.content
        assert "Chapter 1" in result.content
        assert "Section 1.1" in result.content
        assert "Chapter 2" in result.content

    def test_generate_toc_to_file(self, tmp_path):
        """Test generating TOC and writing to file."""
        markdown_content = """# Title 1

Content.

# Title 2

Content.
"""

        output_file = tmp_path / "toc.md"

        config = MCPConfig(write_allowlist=[str(tmp_path)])
        input_data = EditDocumentInput(
            operation="generate_toc",
            source_content=markdown_content,
            source_format="markdown",
            output_path=str(output_file),
            max_toc_level=2
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.output_path is not None
        assert output_file.exists()
        toc_content = output_file.read_text()
        assert "Title 1" in toc_content
        assert "Title 2" in toc_content


@pytest.mark.integration
class TestMCPDocumentToolSplitDocument:
    """Tests for split_document operation."""

    def test_split_document_by_sections(self):
        """Test splitting document into sections."""
        markdown_content = """# Section 1

Content 1.

# Section 2

Content 2.

# Section 3

Content 3.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="split_document",
            source_content=markdown_content,
            source_format="markdown",
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert result.sections_modified == 3
        # Check that sections are separated by thematic breaks
        assert "---" in result.content

    def test_split_document_to_file(self, tmp_path):
        """Test splitting document and writing to file."""
        markdown_content = """# Part 1

Content 1.

# Part 2

Content 2.
"""

        output_file = tmp_path / "split.md"

        config = MCPConfig(write_allowlist=[str(tmp_path)])
        input_data = EditDocumentInput(
            operation="split_document",
            source_content=markdown_content,
            source_format="markdown",
            output_path=str(output_file),
            output_format="markdown"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.output_path is not None
        assert output_file.exists()
        content = output_file.read_text()
        assert "Part 1" in content
        assert "Part 2" in content


@pytest.mark.integration
class TestMCPDocumentToolErrorHandling:
    """Tests for error handling and edge cases."""

    def test_missing_target_raises_error(self):
        """Test that missing target raises appropriate error."""
        markdown_content = """# Existing

Content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="get_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Nonexistent"
        )

        with pytest.raises(ValueError, match="Target section not found"):
            edit_document_ast_impl(input_data, config)

    def test_missing_content_for_add_raises_error(self):
        """Test that missing content for add operation raises error."""
        markdown_content = """# Section

Content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="add_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Section",
            position="after"
            # Missing content parameter
        )

        with pytest.raises(ValueError, match="content is required"):
            edit_document_ast_impl(input_data, config)

    def test_invalid_position_raises_error(self):
        """Test that invalid position raises error."""
        markdown_content = """# Section

Content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="insert_content",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="Section",
            position="invalid",  # Invalid position
            content="New content"
        )

        with pytest.raises(ValueError, match="Invalid position"):
            edit_document_ast_impl(input_data, config)

    def test_both_path_and_content_raises_error(self, tmp_path):
        """Test that specifying both source_path and source_content raises error."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Title\n\nContent.")

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentInput(
            operation="list_sections",
            source_path=str(md_file),
            source_content="# Other\n\nContent.",  # Both specified
            source_format="markdown"
        )

        with pytest.raises(ValueError, match="Cannot specify both"):
            edit_document_ast_impl(input_data, config)

    def test_neither_path_nor_content_raises_error(self):
        """Test that specifying neither source_path nor source_content raises error."""
        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="list_sections",
            # Neither source_path nor source_content specified
            source_format="markdown"
        )

        with pytest.raises(ValueError, match="Must specify either"):
            edit_document_ast_impl(input_data, config)


@pytest.mark.integration
class TestMCPDocumentToolSecurity:
    """Tests for security and path validation."""

    def test_read_path_validation(self, tmp_path):
        """Test that read path is validated against allowlist."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        forbidden_file = forbidden_dir / "doc.md"
        forbidden_file.write_text("# Secret\n\nContent.")

        config = MCPConfig(read_allowlist=[str(allowed_dir)])
        input_data = EditDocumentInput(
            operation="list_sections",
            source_path=str(forbidden_file),
            source_format="markdown"
        )

        from all2md.mcp.security import MCPSecurityError
        with pytest.raises(MCPSecurityError, match="not in allowlist"):
            edit_document_ast_impl(input_data, config)

    def test_write_path_validation(self, tmp_path):
        """Test that write path is validated against allowlist."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        output_file = forbidden_dir / "output.md"

        config = MCPConfig(write_allowlist=[str(allowed_dir)])
        input_data = EditDocumentInput(
            operation="get_section",
            source_content="# Title\n\nContent.",
            source_format="markdown",
            target_index=0,
            output_path=str(output_file)
        )

        from all2md.mcp.security import MCPSecurityError
        with pytest.raises(MCPSecurityError, match="not in allowlist"):
            edit_document_ast_impl(input_data, config)


@pytest.mark.integration
class TestMCPDocumentToolFormats:
    """Tests for different format support."""

    def test_ast_json_input_format(self, tmp_path):
        """Test loading document from AST JSON format."""
        from all2md.ast import Document, Heading, Paragraph, Text
        from all2md.ast.serialization import ast_to_json

        # Create a document and serialize to JSON
        doc = Document(children=[
            Heading(level=1, content=[Text("Title")]),
            Paragraph(content=[Text("Content")])
        ])
        json_content = ast_to_json(doc)

        json_file = tmp_path / "doc.json"
        json_file.write_text(json_content)

        config = MCPConfig(read_allowlist=[str(tmp_path)])
        input_data = EditDocumentInput(
            operation="list_sections",
            source_path=str(json_file),
            source_format="ast_json"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.section_count == 1
        assert result.sections[0].heading_text == "Title"

    def test_ast_json_output_format(self):
        """Test outputting document in AST JSON format."""
        markdown_content = """# Title

Content here.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="get_section",
            source_content=markdown_content,
            source_format="markdown",
            target_index=0,
            output_format="ast_json"
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        # Should be valid JSON
        import json
        json_data = json.loads(result.content)
        assert json_data["node_type"] == "Document"


@pytest.mark.integration
class TestMCPDocumentToolCaseSensitivity:
    """Tests for case-sensitive heading matching."""

    def test_case_insensitive_match(self):
        """Test case-insensitive heading matching (default)."""
        markdown_content = """# Methods

Content.

# Results

Content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="get_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="methods",  # Lowercase
            case_sensitive=False
        )

        result = edit_document_ast_impl(input_data, config)

        assert result.content is not None
        assert "Methods" in result.content

    def test_case_sensitive_match(self):
        """Test case-sensitive heading matching."""
        markdown_content = """# Methods

Content.
"""

        config = MCPConfig()
        input_data = EditDocumentInput(
            operation="get_section",
            source_content=markdown_content,
            source_format="markdown",
            target_heading="methods",  # Lowercase
            case_sensitive=True
        )

        # Should not find the section
        with pytest.raises(ValueError, match="Target section not found"):
            edit_document_ast_impl(input_data, config)
