#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/test_mcp_document_tools.py
"""Integration tests for the MCP edit_document tool (batch, in-place).

edit_document applies an ordered batch of edits to a single parse of a document
and, when the batch mutates the document, writes it back to disk in its original
format. The batch is atomic. Mutating responses echo only the edited region.

Actions covered: list-sections, extract, add:before, add:after, remove, replace,
insert:start, insert:end, insert:after_heading.
"""

import pytest

from all2md.mcp.config import MCPConfig
from all2md.mcp.document_tools import edit_document_impl
from all2md.mcp.schemas import EditDocumentInput, EditOperation


def _edit(doc, ops, config):
    """Run edit_document_impl with a list of EditOperation."""
    return edit_document_impl(EditDocumentInput(doc=str(doc), edits=ops), config)


def _rw_config(tmp_path):
    """Config allowing both reads and writes within tmp_path."""
    return MCPConfig(read_allowlist=[str(tmp_path)], write_allowlist=[str(tmp_path)])


@pytest.mark.integration
class TestListSectionsAndExtract:
    """Read-only actions: list-sections and extract (no disk writes)."""

    def test_list_sections_from_file(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text(
            "# Chapter 1\n\nContent for chapter 1.\n\n"
            "## Section 1.1\n\nContent for section 1.1.\n\n"
            "# Chapter 2\n\nContent for chapter 2.\n"
        )
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [EditOperation(action="list-sections")], config)

        assert result.success is True
        assert result.disk_written is False
        region = result.results[0].edited_region
        assert region is not None
        assert "Chapter 1" in region
        assert "Section 1.1" in region
        assert "[#0]" in region and "[#1]" in region and "[#2]" in region

    def test_extract_by_heading_case_insensitive(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Introduction\n\nIntro content.\n\n# Methods\n\nMethods content.\n")
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [EditOperation(action="extract", target="methods")], config)

        assert result.success is True
        assert result.disk_written is False
        region = result.results[0].edited_region
        assert region is not None
        assert "Methods content" in region
        assert "Introduction" not in region

    def test_extract_by_index_notation(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# First\n\nA.\n\n# Second\n\nB.\n\n# Third\n\nC.\n")
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [EditOperation(action="extract", target="#1")], config)

        assert result.success is True
        region = result.results[0].edited_region
        assert region is not None
        assert "Second" in region
        assert "First" not in region and "Third" not in region

    def test_extract_missing_section_fails(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Existing\n\nContent.\n")
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [EditOperation(action="extract", target="Nonexistent")], config)

        assert result.success is False
        assert "nonexistent" in result.results[0].message.lower()


@pytest.mark.integration
class TestMutatingEditsPersist:
    """Mutating actions write back to disk in the source format."""

    def test_add_section_after_persists(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# First\n\nContent 1.\n\n# Third\n\nContent 3.\n")
        config = _rw_config(tmp_path)

        result = _edit(
            md_file,
            [EditOperation(action="add:after", target="First", content="# Second\n\nContent 2.")],
            config,
        )

        assert result.success is True
        assert result.disk_written is True
        assert result.output_path == str(md_file.resolve())
        saved = md_file.read_text()
        assert "Second" in saved
        assert saved.index("First") < saved.index("Second") < saved.index("Third")
        # Region echoes only the added section, not the whole document.
        assert "Second" in (result.results[0].edited_region or "")
        assert "Third" not in (result.results[0].edited_region or "")

    def test_remove_section_persists(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Keep\n\nA.\n\n# Drop\n\nB.\n\n# KeepToo\n\nC.\n")
        config = _rw_config(tmp_path)

        result = _edit(md_file, [EditOperation(action="remove", target="Drop")], config)

        assert result.success is True
        assert result.disk_written is True
        saved = md_file.read_text()
        assert "Drop" not in saved
        assert "Keep" in saved and "KeepToo" in saved

    def test_replace_section_persists(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Intro\n\nOld intro.\n\n# Methods\n\nMethods.\n")
        config = _rw_config(tmp_path)

        result = _edit(
            md_file,
            [EditOperation(action="replace", target="Intro", content="# Intro\n\nBrand new intro.")],
            config,
        )

        assert result.success is True
        assert result.disk_written is True
        saved = md_file.read_text()
        assert "Brand new intro" in saved
        assert "Old intro" not in saved
        assert "Methods" in saved

    def test_insert_end_persists(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nExisting content.\n")
        config = _rw_config(tmp_path)

        result = _edit(
            md_file,
            [EditOperation(action="insert:end", target="Section", content="Appended paragraph.")],
            config,
        )

        assert result.success is True
        assert result.disk_written is True
        saved = md_file.read_text()
        assert "Existing content" in saved
        assert "Appended paragraph" in saved


@pytest.mark.integration
class TestBatchSemantics:
    """Batch ordering, persistence across edits, and atomicity."""

    def test_multiple_edits_in_one_call_all_persist(self, tmp_path):
        """Sequential edits in a batch all land (the stale-state fix)."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nStart.\n")
        config = _rw_config(tmp_path)

        result = _edit(
            md_file,
            [
                EditOperation(action="insert:end", target="Section", content="First addition."),
                EditOperation(action="insert:end", target="Section", content="Second addition."),
            ],
            config,
        )

        assert result.success is True
        assert result.disk_written is True
        assert len(result.results) == 2
        saved = md_file.read_text()
        assert "First addition" in saved
        assert "Second addition" in saved

    def test_atomic_abort_writes_nothing(self, tmp_path):
        """If any edit fails, none are persisted."""
        md_file = tmp_path / "doc.md"
        original = "# Section\n\nStart.\n"
        md_file.write_text(original)
        config = _rw_config(tmp_path)

        result = _edit(
            md_file,
            [
                EditOperation(action="insert:end", target="Section", content="Would-be addition."),
                EditOperation(action="replace", target="Nonexistent", content="# X\n\nY."),
            ],
            config,
        )

        assert result.success is False
        assert result.disk_written is False
        assert result.results[1].success is False
        # Nothing was written to disk.
        assert "Would-be addition" not in md_file.read_text()


@pytest.mark.integration
class TestWriteBackBoundaries:
    """Format and allowlist boundaries for in-place writes."""

    def test_unsupported_format_for_inplace_write(self, tmp_path):
        """A format with no in-place renderer (e.g. .csv) is rejected clearly."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b\n1,2\n")
        config = _rw_config(tmp_path)

        result = _edit(csv_file, [EditOperation(action="insert:end", target="#0", content="x")], config)

        assert result.success is False
        assert result.disk_written is False
        assert any("cannot write" in w.lower() for w in result.warnings)

    def test_read_only_folder_cannot_be_edited(self, tmp_path):
        """A file readable but not writable cannot be mutated in place."""
        read_dir = tmp_path / "readonly"
        write_dir = tmp_path / "writable"
        read_dir.mkdir()
        write_dir.mkdir()
        md_file = read_dir / "doc.md"
        md_file.write_text("# Section\n\nContent.\n")
        config = MCPConfig(read_allowlist=[str(read_dir)], write_allowlist=[str(write_dir)])

        result = _edit(md_file, [EditOperation(action="insert:end", target="Section", content="x")], config)

        assert result.success is False
        assert result.disk_written is False
        assert result.warnings


@pytest.mark.integration
class TestEditValidation:
    """Input validation and access errors."""

    def test_missing_target_for_extract(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Content\n\nText.")
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [EditOperation(action="extract")], config)

        assert result.success is False
        assert "requires a target" in result.results[0].message

    def test_missing_content_for_add(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nContent.")
        config = _rw_config(tmp_path)

        result = _edit(md_file, [EditOperation(action="add:after", target="Section")], config)

        assert result.success is False
        assert "requires a content" in result.results[0].message

    def test_invalid_index_notation(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nContent.")
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [EditOperation(action="extract", target="#abc")], config)

        assert result.success is False
        assert "Invalid target index format" in result.results[0].message

    def test_invalid_action(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nContent.")
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [EditOperation(action="frobnicate", target="Section")], config)

        assert result.success is False
        assert "invalid action" in result.results[0].message.lower()

    def test_path_not_in_allowlist(self, tmp_path):
        allowed = tmp_path / "allowed"
        forbidden = tmp_path / "forbidden"
        allowed.mkdir()
        forbidden.mkdir()
        forbidden_file = forbidden / "doc.md"
        forbidden_file.write_text("# Secret\n\nContent.")
        config = MCPConfig(read_allowlist=[str(allowed)])

        result = _edit(forbidden_file, [EditOperation(action="list-sections")], config)

        assert result.success is False
        # File is outside the read allowlist, so it isn't found relative to it.
        assert result.warnings

    def test_nonexistent_file(self, tmp_path):
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(tmp_path / "nope.md", [EditOperation(action="list-sections")], config)

        assert result.success is False
        assert any("not found" in w.lower() for w in result.warnings)

    def test_no_edits(self, tmp_path):
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Section\n\nContent.")
        config = MCPConfig(read_allowlist=[str(tmp_path)])

        result = _edit(md_file, [], config)

        assert result.success is False
