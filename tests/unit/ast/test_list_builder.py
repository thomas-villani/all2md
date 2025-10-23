#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for ListBuilder and TableBuilder classes."""

import pytest

from all2md.ast import List, ListItem, Paragraph, Text
from all2md.ast.builder import ListBuilder, TableBuilder


@pytest.mark.unit
class TestListBuilderBasicFunctionality:
    """Test basic ListBuilder functionality."""

    def test_single_top_level_item(self) -> None:
        """Test adding a single top-level item."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])])
        doc = builder.get_document()

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], List)
        assert doc.children[0].ordered is False
        assert len(doc.children[0].items) == 1
        assert isinstance(doc.children[0].items[0], ListItem)

    def test_multiple_same_level_items_unordered(self) -> None:
        """Test adding multiple items at the same level (unordered)."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 2")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 3")])])
        doc = builder.get_document()

        assert len(doc.children) == 1
        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.ordered is False
        assert len(list_node.items) == 3
        assert isinstance(list_node.items[0].children[0], Paragraph)
        assert list_node.items[0].children[0].content[0].content == "Item 1"  # type: ignore
        assert list_node.items[1].children[0].content[0].content == "Item 2"  # type: ignore
        assert list_node.items[2].children[0].content[0].content == "Item 3"  # type: ignore

    def test_multiple_same_level_items_ordered(self) -> None:
        """Test adding multiple items at the same level (ordered)."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="First")])])
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Second")])])
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Third")])])
        doc = builder.get_document()

        assert len(doc.children) == 1
        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.ordered is True
        assert len(list_node.items) == 3


@pytest.mark.unit
class TestListBuilderNesting:
    """Test ListBuilder nesting functionality."""

    def test_simple_nested_list(self) -> None:
        """Test creating a simple nested list (level 1 -> 2)."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="Nested 1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="Nested 2")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 2")])])
        doc = builder.get_document()

        assert len(doc.children) == 1
        list_node = doc.children[0]
        assert len(list_node.items) == 2

        # First item should have nested list
        first_item = list_node.items[0]
        assert len(first_item.children) == 2  # Paragraph + nested List
        assert isinstance(first_item.children[1], List)
        nested_list = first_item.children[1]
        assert len(nested_list.items) == 2
        assert nested_list.items[0].children[0].content[0].content == "Nested 1"  # type: ignore
        assert nested_list.items[1].children[0].content[0].content == "Nested 2"  # type: ignore

        # Second item should not have nested list
        second_item = list_node.items[1]
        assert len(second_item.children) == 1
        assert isinstance(second_item.children[0], Paragraph)

    def test_multi_level_nesting(self) -> None:
        """Test creating multi-level nested lists (level 1 -> 3) with placeholders enabled."""
        builder = ListBuilder(allow_placeholders=True)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1")])])
        builder.add_item(level=3, ordered=False, content=[Paragraph(content=[Text(content="L3")])])
        doc = builder.get_document()

        # Should create intermediate list at level 2
        list_l1 = doc.children[0]
        assert isinstance(list_l1, List)
        assert len(list_l1.items) == 1

        item_l1 = list_l1.items[0]
        assert len(item_l1.children) == 2  # Paragraph + nested list

        list_l2 = item_l1.children[1]
        assert isinstance(list_l2, List)
        assert len(list_l2.items) == 1

        item_l2 = list_l2.items[0]
        assert len(item_l2.children) == 1  # Just nested list (no paragraph for intermediate level)

        list_l3 = item_l2.children[0]
        assert isinstance(list_l3, List)
        assert len(list_l3.items) == 1
        assert list_l3.items[0].children[0].content[0].content == "L3"  # type: ignore

    def test_ascending_back_to_parent_level(self) -> None:
        """Test ascending back to parent level (2 -> 1)."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="Nested")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 2")])])
        doc = builder.get_document()

        list_node = doc.children[0]
        assert len(list_node.items) == 2
        assert list_node.items[0].children[0].content[0].content == "Item 1"  # type: ignore
        assert list_node.items[1].children[0].content[0].content == "Item 2"  # type: ignore


@pytest.mark.unit
class TestListBuilderTypeChanges:
    """Test ListBuilder handling of list type changes."""

    def test_type_change_at_same_level(self) -> None:
        """Test changing list type at the same level creates sibling list."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Bullet 1")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Bullet 2")])])
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Number 1")])])
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Number 2")])])
        doc = builder.get_document()

        # Should create two separate lists
        assert len(doc.children) == 2

        # First list: unordered
        first_list = doc.children[0]
        assert isinstance(first_list, List)
        assert first_list.ordered is False
        assert len(first_list.items) == 2

        # Second list: ordered
        second_list = doc.children[1]
        assert isinstance(second_list, List)
        assert second_list.ordered is True
        assert len(second_list.items) == 2

    def test_type_change_at_nested_level(self) -> None:
        """Test changing list type at nested level creates sibling nested list."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="Sub bullet")])])
        builder.add_item(level=2, ordered=True, content=[Paragraph(content=[Text(content="Sub number")])])
        doc = builder.get_document()

        list_node = doc.children[0]
        first_item = list_node.items[0]

        # First item should have TWO nested lists (type changed at level 2)
        assert len(first_item.children) == 3  # Paragraph + 2 nested lists
        assert isinstance(first_item.children[1], List)
        assert first_item.children[1].ordered is False
        assert isinstance(first_item.children[2], List)
        assert first_item.children[2].ordered is True

    def test_alternating_types_creates_multiple_lists(self) -> None:
        """Test alternating between ordered and unordered creates multiple lists."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Bullet")])])
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Number")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Bullet")])])
        doc = builder.get_document()

        # Should create three separate lists
        assert len(doc.children) == 3
        assert doc.children[0].ordered is False  # type: ignore
        assert doc.children[1].ordered is True  # type: ignore
        assert doc.children[2].ordered is False  # type: ignore


@pytest.mark.unit
class TestListBuilderTaskLists:
    """Test ListBuilder with task lists."""

    def test_task_list_items(self) -> None:
        """Test adding task list items."""
        builder = ListBuilder()
        builder.add_item(
            level=1, ordered=False, content=[Paragraph(content=[Text(content="Task 1")])], task_status="checked"
        )
        builder.add_item(
            level=1, ordered=False, content=[Paragraph(content=[Text(content="Task 2")])], task_status="unchecked"
        )
        doc = builder.get_document()

        list_node = doc.children[0]
        assert list_node.items[0].task_status == "checked"
        assert list_node.items[1].task_status == "unchecked"


@pytest.mark.unit
class TestListBuilderEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_level_raises_error(self) -> None:
        """Test that invalid level (< 1) raises ValueError."""
        builder = ListBuilder()
        with pytest.raises(ValueError, match="Level must be >= 1"):
            builder.add_item(level=0, ordered=False, content=[Paragraph(content=[Text(content="Invalid")])])

    def test_negative_level_raises_error(self) -> None:
        """Test that negative level raises ValueError."""
        builder = ListBuilder()
        with pytest.raises(ValueError, match="Level must be >= 1"):
            builder.add_item(level=-1, ordered=False, content=[Paragraph(content=[Text(content="Invalid")])])

    def test_empty_content_allowed(self) -> None:
        """Test that empty content is allowed."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[])
        doc = builder.get_document()

        assert len(doc.children) == 1
        assert len(doc.children[0].items) == 1  # type: ignore
        assert len(doc.children[0].items[0].children) == 0  # type: ignore

    def test_complex_nesting_scenario(self) -> None:
        """Test complex nesting scenario: 1 -> 2 -> 1 -> 3 -> 2 -> 1 with placeholders enabled."""
        builder = ListBuilder(allow_placeholders=True)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1-1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="L2-1")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1-2")])])
        builder.add_item(level=3, ordered=False, content=[Paragraph(content=[Text(content="L3-1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="L2-2")])])
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1-3")])])
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert len(list_node.items) == 3

        # Verify structure
        assert list_node.items[0].children[0].content[0].content == "L1-1"  # type: ignore
        assert list_node.items[1].children[0].content[0].content == "L1-2"  # type: ignore
        assert list_node.items[2].children[0].content[0].content == "L1-3"  # type: ignore


@pytest.mark.unit
class TestTableBuilderHasHeader:
    """Test TableBuilder has_header functionality."""

    def test_has_header_true_auto_sets_first_row_as_header(self) -> None:
        """Test that first row is automatically set as header when has_header=True."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"])
        builder.add_row(["Alice", "30"])
        builder.add_row(["Bob", "25"])

        table = builder.get_table()

        assert table.header is not None
        assert table.header.is_header is True
        assert len(table.header.cells) == 2
        assert table.header.cells[0].content[0].content == "Name"
        assert table.header.cells[1].content[0].content == "Age"
        assert len(table.rows) == 2
        assert table.rows[0].is_header is False
        assert table.rows[1].is_header is False

    def test_has_header_false_does_not_auto_set_header(self) -> None:
        """Test that first row is not automatically set as header when has_header=False."""
        builder = TableBuilder(has_header=False)
        builder.add_row(["Name", "Age"])
        builder.add_row(["Alice", "30"])

        table = builder.get_table()

        assert table.header is None
        assert len(table.rows) == 2

    def test_has_header_with_explicit_is_header_true(self) -> None:
        """Test that explicit is_header=True works with has_header=True."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"], is_header=True)
        builder.add_row(["Alice", "30"])

        table = builder.get_table()

        assert table.header is not None
        assert table.header.is_header is True
        assert len(table.rows) == 1

    def test_has_header_initializes_alignments(self) -> None:
        """Test that alignments are initialized when has_header=True and no alignments provided."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age", "City"])
        builder.add_row(["Alice", "30", "NYC"])

        table = builder.get_table()

        assert len(table.alignments) == 3
        assert all(alignment is None for alignment in table.alignments)

    def test_has_header_with_explicit_alignments(self) -> None:
        """Test that explicit alignments override default initialization."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"], alignments=["left", "right"])
        builder.add_row(["Alice", "30"])

        table = builder.get_table()

        assert len(table.alignments) == 2
        assert table.alignments[0] == "left"
        assert table.alignments[1] == "right"

    def test_has_header_second_row_not_treated_as_header(self) -> None:
        """Test that only the first row is treated as header, not subsequent rows."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"])
        builder.add_row(["Alice", "30"])
        builder.add_row(["Bob", "25"])

        table = builder.get_table()

        assert table.header is not None
        assert len(table.rows) == 2
        assert all(not row.is_header for row in table.rows)


@pytest.mark.unit
class TestTableBuilderMixedCellTypes:
    """Test TableBuilder with mixed cell types."""

    def test_all_string_cells(self) -> None:
        """Test adding rows with all string cells."""
        from all2md.ast import Text

        builder = TableBuilder()
        builder.add_row(["Name", "Age"])

        table = builder.get_table()

        assert len(table.rows) == 1
        assert len(table.rows[0].cells) == 2
        assert isinstance(table.rows[0].cells[0].content[0], Text)
        assert table.rows[0].cells[0].content[0].content == "Name"  # type: ignore

    def test_all_node_sequence_cells(self) -> None:
        """Test adding rows with all node sequence cells."""
        from all2md.ast import Text

        builder = TableBuilder()
        builder.add_row([[Text(content="Name")], [Text(content="Age")]])

        table = builder.get_table()

        assert len(table.rows) == 1
        assert len(table.rows[0].cells) == 2
        assert isinstance(table.rows[0].cells[0].content[0], Text)
        assert table.rows[0].cells[0].content[0].content == "Name"  # type: ignore

    def test_mixed_string_and_node_sequence_cells(self) -> None:
        """Test adding rows with mixed string and node sequence cells."""
        from all2md.ast import Strong, Text

        builder = TableBuilder()
        builder.add_row(["Name", [Text(content="Age: "), Strong(content=[Text(content="30")])]])

        table = builder.get_table()

        assert len(table.rows) == 1
        assert len(table.rows[0].cells) == 2

        # First cell is plain string
        assert isinstance(table.rows[0].cells[0].content[0], Text)
        assert table.rows[0].cells[0].content[0].content == "Name"  # type: ignore

        # Second cell has mixed inline nodes
        assert len(table.rows[0].cells[1].content) == 2
        assert isinstance(table.rows[0].cells[1].content[0], Text)
        assert isinstance(table.rows[0].cells[1].content[1], Strong)

    def test_empty_sequence_cells(self) -> None:
        """Test adding an empty row."""
        builder = TableBuilder()
        builder.add_row([])

        table = builder.get_table()

        assert len(table.rows) == 1
        assert len(table.rows[0].cells) == 0

    def test_header_with_mixed_cells(self) -> None:
        """Test adding header row with mixed cell types."""
        from all2md.ast import Text

        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", [Text(content="Age")]])

        table = builder.get_table()

        assert table.header is not None
        assert len(table.header.cells) == 2
        assert table.header.is_header is True


@pytest.mark.unit
class TestTableBuilderSingleNodeCells:
    """Test TableBuilder with single Node cells (Issue 8)."""

    def test_add_row_with_single_node_cells(self) -> None:
        """Test adding rows with single Node instances as cells."""
        from all2md.ast import Text

        builder = TableBuilder()
        builder.add_row([Text(content="Name"), Text(content="Age")])
        builder.add_row([Text(content="Alice"), Text(content="30")])

        table = builder.get_table()

        assert len(table.rows) == 2
        assert len(table.rows[0].cells) == 2
        assert isinstance(table.rows[0].cells[0].content[0], Text)
        assert table.rows[0].cells[0].content[0].content == "Name"

    def test_add_row_mixed_nodes_and_sequences(self) -> None:
        """Test adding rows with mix of single Nodes and sequences."""
        from all2md.ast import Strong, Text

        builder = TableBuilder()
        builder.add_row(
            [
                Text(content="Name"),  # Single node
                [Text(content="Age: "), Strong(content=[Text(content="30")])],  # Sequence
            ]
        )

        table = builder.get_table()

        assert len(table.rows) == 1
        # First cell has single node
        assert len(table.rows[0].cells[0].content) == 1
        assert table.rows[0].cells[0].content[0].content == "Name"
        # Second cell has sequence
        assert len(table.rows[0].cells[1].content) == 2

    def test_add_row_mixed_strings_nodes_sequences(self) -> None:
        """Test adding rows with strings, single Nodes, and sequences."""
        from all2md.ast import Emphasis, Text

        builder = TableBuilder()
        builder.add_row(
            [
                "Name",  # String
                Text(content="Age"),  # Single node
                [Text(content="City: "), Emphasis(content=[Text(content="NYC")])],  # Sequence
            ]
        )

        table = builder.get_table()

        assert len(table.rows) == 1
        assert len(table.rows[0].cells) == 3
        # All cells should be properly converted
        assert table.rows[0].cells[0].content[0].content == "Name"
        assert table.rows[0].cells[1].content[0].content == "Age"
        assert len(table.rows[0].cells[2].content) == 2

    def test_header_with_single_node_cells(self) -> None:
        """Test header row with single Node cells."""
        from all2md.ast import Strong, Text

        builder = TableBuilder(has_header=True)
        builder.add_row([Strong(content=[Text(content="Name")]), Strong(content=[Text(content="Age")])])
        builder.add_row([Text(content="Alice"), Text(content="30")])

        table = builder.get_table()

        assert table.header is not None
        assert len(table.header.cells) == 2
        # Header cells should contain Strong nodes
        assert isinstance(table.header.cells[0].content[0], Strong)
        assert isinstance(table.header.cells[1].content[0], Strong)


@pytest.mark.unit
class TestTableBuilderAlignmentValidation:
    """Test TableBuilder alignment validation (Issue 9)."""

    def test_alignment_mismatch_raises_error(self) -> None:
        """Test that mismatched alignment length raises ValueError."""
        builder = TableBuilder(has_header=True)

        # Header with 3 cells but only 2 alignments - should raise
        with pytest.raises(ValueError, match="Alignment count .* must match cell count"):
            builder.add_row(["Name", "Age", "City"], alignments=["left", "right"])

    def test_alignment_too_many_raises_error(self) -> None:
        """Test that too many alignments raises ValueError."""
        builder = TableBuilder(has_header=True)

        # Header with 2 cells but 3 alignments - should raise
        with pytest.raises(ValueError, match="Alignment count .* must match cell count"):
            builder.add_row(["Name", "Age"], alignments=["left", "right", "center"])

    def test_alignment_exact_match_works(self) -> None:
        """Test that exact alignment match works correctly."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age", "City"], alignments=["left", "right", "center"])
        builder.add_row(["Alice", "30", "NYC"])

        table = builder.get_table()

        assert len(table.alignments) == 3
        assert table.alignments == ["left", "right", "center"]

    def test_alignment_auto_padding_on_wider_body_row(self) -> None:
        """Test that alignments auto-pad when body rows have more columns."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"], alignments=["left", "right"])
        # Body row with extra column should auto-pad alignments
        builder.add_row(["Alice", "30", "NYC"])

        table = builder.get_table()

        # Alignments should be auto-padded with None
        assert len(table.alignments) == 3
        assert table.alignments == ["left", "right", None]

    def test_alignment_auto_padding_multiple_rows(self) -> None:
        """Test alignment auto-padding with multiple progressively wider rows."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["A", "B"], alignments=["left", "right"])
        builder.add_row(["1", "2"])  # Same width
        builder.add_row(["X", "Y", "Z"])  # Wider - should pad to 3
        builder.add_row(["P", "Q", "R", "S"])  # Even wider - should pad to 4

        table = builder.get_table()

        assert len(table.alignments) == 4
        assert table.alignments == ["left", "right", None, None]

    def test_alignment_no_auto_padding_if_not_needed(self) -> None:
        """Test that no auto-padding occurs if body rows match or are narrower."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age", "City"], alignments=["left", "right", "center"])
        builder.add_row(["Alice", "30", "NYC"])
        builder.add_row(["Bob", "25"])  # Narrower row - no padding needed

        table = builder.get_table()

        assert len(table.alignments) == 3
        assert table.alignments == ["left", "right", "center"]

    def test_set_column_alignment_auto_pads(self) -> None:
        """Test that set_column_alignment auto-pads when setting new column."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"])

        # Set alignment for column 3 (doesn't exist yet)
        builder.set_column_alignment(2, "center")

        table = builder.get_table()

        # Should have padded to index 2
        assert len(table.alignments) == 3
        assert table.alignments == [None, None, "center"]


@pytest.mark.unit
class TestTableBuilderMultipleHeaders:
    """Test TableBuilder multiple header prevention (Issue 10)."""

    def test_multiple_headers_raises_error(self) -> None:
        """Test that adding multiple headers raises ValueError."""
        builder = TableBuilder()
        builder.add_row(["Name", "Age"], is_header=True)

        # Attempting to add another header should raise
        with pytest.raises(ValueError, match="Table already has a header row"):
            builder.add_row(["Column 1", "Column 2"], is_header=True)

    def test_multiple_headers_with_has_header_raises_error(self) -> None:
        """Test that has_header=True doesn't allow multiple headers."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"])  # Auto-treated as header

        # Attempting to add another explicit header should raise
        with pytest.raises(ValueError, match="Table already has a header row"):
            builder.add_row(["Column 1", "Column 2"], is_header=True)

    def test_header_then_body_rows_works(self) -> None:
        """Test that header followed by body rows works correctly."""
        builder = TableBuilder()
        builder.add_row(["Name", "Age"], is_header=True)
        builder.add_row(["Alice", "30"])
        builder.add_row(["Bob", "25"])

        table = builder.get_table()

        assert table.header is not None
        assert len(table.rows) == 2

    def test_has_header_followed_by_body_rows_works(self) -> None:
        """Test that has_header=True followed by body rows works correctly."""
        builder = TableBuilder(has_header=True)
        builder.add_row(["Name", "Age"])  # Auto-treated as header
        builder.add_row(["Alice", "30"])  # Body row
        builder.add_row(["Bob", "25"])  # Body row

        table = builder.get_table()

        assert table.header is not None
        assert len(table.rows) == 2

    def test_explicit_false_is_header_after_header_works(self) -> None:
        """Test that explicitly passing is_header=False after header works."""
        builder = TableBuilder()
        builder.add_row(["Name", "Age"], is_header=True)
        builder.add_row(["Alice", "30"], is_header=False)

        table = builder.get_table()

        assert table.header is not None
        assert len(table.rows) == 1


@pytest.mark.unit
class TestListBuilderPlaceholderMode:
    """Test ListBuilder placeholder handling (Issue 11)."""

    def test_placeholder_disabled_raises_error_on_level_skip(self) -> None:
        """Test that skipping levels raises error when placeholders disabled (default)."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1")])])

        # Jumping to level 3 should raise error (intermediate level 2 has no items)
        with pytest.raises(ValueError, match="Cannot nest to level 3 without a parent item at level 2"):
            builder.add_item(level=3, ordered=False, content=[Paragraph(content=[Text(content="L3")])])

    def test_placeholder_disabled_raises_error_on_direct_nest_without_parent(self) -> None:
        """Test that nesting without parent item raises error when placeholders disabled."""
        builder = ListBuilder()

        # Starting at level 2 should raise error (intermediate level 1 has no items)
        with pytest.raises(ValueError, match="Cannot nest to level 2 without a parent item at level 1"):
            builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="L2")])])

    def test_placeholder_enabled_creates_placeholder_with_metadata(self) -> None:
        """Test that placeholders are created with metadata when enabled."""
        builder = ListBuilder(allow_placeholders=True)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1")])])
        builder.add_item(level=3, ordered=False, content=[Paragraph(content=[Text(content="L3")])])
        doc = builder.get_document()

        # Navigate to level 2 intermediate list
        list_l1 = doc.children[0]
        assert isinstance(list_l1, List)
        item_l1 = list_l1.items[0]
        list_l2 = item_l1.children[1]  # Second child (first is Paragraph)
        assert isinstance(list_l2, List)

        # Level 2 should have a placeholder item
        assert len(list_l2.items) == 1
        placeholder_item = list_l2.items[0]
        assert placeholder_item.metadata.get("placeholder") is True

    def test_placeholder_enabled_allows_complex_nesting(self) -> None:
        """Test that complex level jumps work with placeholders enabled."""
        builder = ListBuilder(allow_placeholders=True)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1")])])
        builder.add_item(level=4, ordered=False, content=[Paragraph(content=[Text(content="L4")])])
        doc = builder.get_document()

        # Should create intermediate levels 2 and 3 with placeholders
        list_l1 = doc.children[0]
        item_l1 = list_l1.items[0]

        # Check level 2 has placeholder
        list_l2 = item_l1.children[1]
        assert isinstance(list_l2, List)
        assert list_l2.items[0].metadata.get("placeholder") is True

        # Check level 3 has placeholder
        list_l3 = list_l2.items[0].children[0]
        assert isinstance(list_l3, List)
        assert list_l3.items[0].metadata.get("placeholder") is True

        # Check level 4 has real content
        list_l4 = list_l3.items[0].children[0]
        assert isinstance(list_l4, List)
        assert list_l4.items[0].children[0].content[0].content == "L4"  # type: ignore

    def test_placeholder_disabled_works_with_proper_nesting(self) -> None:
        """Test that proper nesting works fine with placeholders disabled."""
        builder = ListBuilder()  # default: allow_placeholders=False
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="L2")])])
        builder.add_item(level=3, ordered=False, content=[Paragraph(content=[Text(content="L3")])])
        doc = builder.get_document()

        # Should work fine since we're nesting properly
        assert len(doc.children) == 1
        list_l1 = doc.children[0]
        assert isinstance(list_l1, List)
        assert len(list_l1.items) == 1


@pytest.mark.unit
class TestListBuilderStartAndTight:
    """Test ListBuilder start and tight parameters (Issue 12)."""

    def test_default_start_and_tight_values(self) -> None:
        """Test that default start=1 and tight=True are used."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Item 1")])])
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.start == 1
        assert list_node.tight is True

    def test_custom_default_start(self) -> None:
        """Test custom default_start parameter."""
        builder = ListBuilder(default_start=5)
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Item 1")])])
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.start == 5

    def test_custom_default_tight(self) -> None:
        """Test custom default_tight parameter."""
        builder = ListBuilder(default_tight=False)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])])
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.tight is False

    def test_custom_default_start_and_tight(self) -> None:
        """Test both custom default_start and default_tight."""
        builder = ListBuilder(default_start=10, default_tight=False)
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Item 1")])])
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.start == 10
        assert list_node.tight is False

    def test_per_item_start_override(self) -> None:
        """Test that per-item start parameter overrides default."""
        builder = ListBuilder(default_start=1)
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Item 1")])], start=5)
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.start == 5

    def test_per_item_tight_override(self) -> None:
        """Test that per-item tight parameter overrides default."""
        builder = ListBuilder(default_tight=True)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])], tight=False)
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.tight is False

    def test_multiple_lists_different_start_values(self) -> None:
        """Test multiple lists with different start values via type change."""
        builder = ListBuilder(default_start=1)
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="First")])], start=1)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Bullet")])])
        builder.add_item(level=1, ordered=True, content=[Paragraph(content=[Text(content="Second")])], start=10)
        doc = builder.get_document()

        # Should have 3 lists
        assert len(doc.children) == 3

        first_list = doc.children[0]
        assert isinstance(first_list, List)
        assert first_list.ordered is True
        assert first_list.start == 1

        second_list = doc.children[1]
        assert isinstance(second_list, List)
        assert second_list.ordered is False

        third_list = doc.children[2]
        assert isinstance(third_list, List)
        assert third_list.ordered is True
        assert third_list.start == 10

    def test_nested_list_with_custom_tight(self) -> None:
        """Test nested list with custom tight value."""
        builder = ListBuilder(default_tight=True)
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="L1")])])
        builder.add_item(level=2, ordered=False, content=[Paragraph(content=[Text(content="L2")])], tight=False)
        doc = builder.get_document()

        list_l1 = doc.children[0]
        assert isinstance(list_l1, List)
        assert list_l1.tight is True  # Uses default

        item_l1 = list_l1.items[0]
        list_l2 = item_l1.children[1]
        assert isinstance(list_l2, List)
        assert list_l2.tight is False  # Uses override

    def test_start_parameter_ignored_for_unordered_lists(self) -> None:
        """Test that start parameter is set even for unordered lists (renderer decision)."""
        builder = ListBuilder()
        builder.add_item(level=1, ordered=False, content=[Paragraph(content=[Text(content="Item 1")])], start=5)
        doc = builder.get_document()

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.start == 5  # Parameter is set even though it's unordered
