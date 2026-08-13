"""Tests for parser helper utilities related to attachments."""

from all2md.ast import Document, Emphasis, Image, Node, Paragraph, Strong, Text
from all2md.renderers.markdown import MarkdownRenderer
from all2md.utils.parser_helpers import attachment_result_to_image_node, group_and_format_runs

# A run is a (text, (bold, italic)) pair for these tests.
Run = tuple[str, tuple[bool, bool]]

PLAIN = (False, False)
BOLD = (True, False)
ITALIC = (False, True)


def _group(runs: list[Run]) -> list[Node]:
    """Run ``group_and_format_runs`` over simple (text, format) tuples."""
    return group_and_format_runs(
        runs,
        text_extractor=lambda run: run[0],
        format_extractor=lambda run: run[1],
    )


def _render(nodes: list[Node]) -> str:
    """Render inline nodes as a single markdown paragraph."""
    document = Document(children=[Paragraph(content=nodes)])
    return MarkdownRenderer().render_to_string(document).strip()


class TestAttachmentResultToImageNode:
    """Tests for converting attachment results into image nodes."""

    def test_sets_metadata_for_base64_source(self) -> None:
        """Image metadata should indicate base64 source when provided."""
        result = {
            "markdown": "![alt](data:image/png;base64,AAA)",
            "url": "data:image/png;base64,AAA",
            "source_data": "base64",
        }

        image_node = attachment_result_to_image_node(result, fallback_alt_text="image")
        assert isinstance(image_node, Image)
        assert image_node.metadata.get("source_data") == "base64"

    def test_leaves_metadata_empty_when_not_supplied(self) -> None:
        """No metadata key should be added when source data is absent."""
        result = {
            "markdown": "![alt](http://example.com/image.png)",
            "url": "http://example.com/image.png",
        }

        image_node = attachment_result_to_image_node(result, fallback_alt_text="image")
        assert isinstance(image_node, Image)
        assert "source_data" not in image_node.metadata


class TestGroupAndFormatRunsWhitespace:
    """Whitespace at a formatting boundary must survive grouping."""

    def test_boundary_space_survives_a_format_change(self) -> None:
        """The canonical three-run case must not fuse words around the bold span."""
        nodes = _group([("This is ", PLAIN), ("bold", BOLD), (" and after.", PLAIN)])

        assert _render(nodes) == "This is **bold** and after."

    def test_boundary_space_stays_outside_the_formatting_wrapper(self) -> None:
        """A space inside emphasis markers is invalid markdown, so keep it outside."""
        nodes = _group([("This is ", PLAIN), ("bold", BOLD), (" and after.", PLAIN)])

        assert len(nodes) == 3
        assert nodes[0] == Text(content="This is ")
        strong = nodes[1]
        assert isinstance(strong, Strong)
        assert strong.content == [Text(content="bold")]
        assert nodes[2] == Text(content=" and after.")

    def test_separator_node_used_between_two_formatted_groups(self) -> None:
        """With no plain neighbour to carry it, the space becomes its own node."""
        nodes = _group([("bold ", BOLD), ("italic", ITALIC)])

        assert len(nodes) == 3
        assert isinstance(nodes[0], Strong)
        assert nodes[1] == Text(content=" ")
        assert isinstance(nodes[2], Emphasis)
        assert _render(nodes) == "**bold** *italic*"

    def test_whitespace_only_middle_group_collapses_to_one_space(self) -> None:
        """A whitespace-only group separates its neighbours without adding a node."""
        nodes = _group([("This is", PLAIN), ("  ", BOLD), ("and after.", PLAIN)])

        assert nodes == [Text(content="This is "), Text(content="and after.")]
        assert _render(nodes) == "This is and after."

    def test_consecutive_whitespace_only_groups_collapse_to_one_space(self) -> None:
        """Several whitespace-only groups in a row still yield a single space."""
        nodes = _group([("a", PLAIN), ("  ", BOLD), ("\t", ITALIC), ("b", PLAIN)])

        assert nodes == [Text(content="a "), Text(content="b")]
        assert _render(nodes) == "a b"

    def test_paragraph_edge_whitespace_is_dropped(self) -> None:
        """Leading/trailing whitespace at the true edges of the run sequence goes away."""
        nodes = _group([("  lead ", PLAIN), ("mid", BOLD), (" trail   ", PLAIN)])

        assert nodes[0] == Text(content="lead ")
        assert nodes[-1] == Text(content=" trail")
        assert _render(nodes) == "lead **mid** trail"

    def test_leading_and_trailing_whitespace_only_groups_are_dropped(self) -> None:
        """Whitespace-only groups at the edges contribute nothing at all."""
        nodes = _group([("   ", BOLD), ("word", PLAIN), ("   ", ITALIC)])

        assert nodes == [Text(content="word")]
        assert _render(nodes) == "word"

    def test_multiple_consecutive_format_changes_keep_every_space(self) -> None:
        """Every boundary in a plain/bold/italic/plain chain keeps its separator."""
        nodes = _group([("a ", PLAIN), ("b ", BOLD), ("c ", ITALIC), ("d", PLAIN)])

        assert _render(nodes) == "a **b** *c* d"

    def test_interior_whitespace_is_preserved_verbatim(self) -> None:
        """Only edge whitespace is collapsed; runs inside a group are untouched."""
        nodes = _group([("a   b ", PLAIN), ("c", BOLD)])

        assert nodes[0] == Text(content="a   b ")

    def test_runs_without_boundary_whitespace_still_fuse(self) -> None:
        """No whitespace at the boundary means no space is invented."""
        nodes = _group([("un", PLAIN), ("break", BOLD), ("able", PLAIN)])

        assert _render(nodes) == "un**break**able"

    def test_whitespace_only_input_yields_no_nodes(self) -> None:
        """A run sequence made entirely of whitespace produces nothing."""
        assert _group([("   ", PLAIN), ("\t", BOLD)]) == []
