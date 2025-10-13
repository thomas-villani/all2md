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
        """Test creating multi-level nested lists (level 1 -> 3)."""
        builder = ListBuilder()
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
        """Test complex nesting scenario: 1 -> 2 -> 1 -> 3 -> 2 -> 1."""
        builder = ListBuilder()
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
        builder.add_row([
            [Text(content="Name")],
            [Text(content="Age")]
        ])

        table = builder.get_table()

        assert len(table.rows) == 1
        assert len(table.rows[0].cells) == 2
        assert isinstance(table.rows[0].cells[0].content[0], Text)
        assert table.rows[0].cells[0].content[0].content == "Name"  # type: ignore

    def test_mixed_string_and_node_sequence_cells(self) -> None:
        """Test adding rows with mixed string and node sequence cells."""
        from all2md.ast import Strong, Text

        builder = TableBuilder()
        builder.add_row([
            "Name",
            [Text(content="Age: "), Strong(content=[Text(content="30")])]
        ])

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
        builder.add_row([
            "Name",
            [Text(content="Age")]
        ])

        table = builder.get_table()

        assert table.header is not None
        assert len(table.header.cells) == 2
        assert table.header.is_header is True
