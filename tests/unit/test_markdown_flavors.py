#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for markdown flavor functionality."""
import pytest

from all2md import to_markdown
from all2md.ast import Document, Heading, Paragraph, Strikethrough, Table, TableCell, TableRow, Text
from all2md.options import MarkdownOptions
from all2md.options.markdown import get_flavor_defaults, validate_flavor_compatibility
from all2md.renderers.markdown import MarkdownRenderer
from all2md.utils.flavors import (
    CommonMarkFlavor,
    GFMFlavor,
    KramdownFlavor,
    MultiMarkdownFlavor,
    PandocFlavor,
)


@pytest.mark.unit
class TestFlavorCapabilities:
    """Test flavor capability checks."""

    def test_commonmark_capabilities(self):
        """Test CommonMark flavor capabilities."""
        flavor = CommonMarkFlavor()
        assert flavor.name == "CommonMark"
        assert not flavor.supports_tables()
        assert not flavor.supports_task_lists()
        assert not flavor.supports_strikethrough()
        assert flavor.supports_autolinks()
        assert not flavor.supports_footnotes()
        assert not flavor.supports_definition_lists()
        assert not flavor.supports_math()

    def test_gfm_capabilities(self):
        """Test GFM flavor capabilities."""
        flavor = GFMFlavor()
        assert flavor.name == "GFM"
        assert flavor.supports_tables()
        assert flavor.supports_task_lists()
        assert flavor.supports_strikethrough()
        assert flavor.supports_autolinks()
        assert not flavor.supports_footnotes()
        assert not flavor.supports_definition_lists()
        assert flavor.supports_math()

    def test_multimarkdown_capabilities(self):
        """Test MultiMarkdown flavor capabilities."""
        flavor = MultiMarkdownFlavor()
        assert flavor.name == "MultiMarkdown"
        assert flavor.supports_tables()
        assert not flavor.supports_task_lists()
        assert not flavor.supports_strikethrough()
        assert flavor.supports_autolinks()
        assert flavor.supports_footnotes()
        assert flavor.supports_definition_lists()
        assert flavor.supports_math()

    def test_pandoc_capabilities(self):
        """Test Pandoc flavor capabilities."""
        flavor = PandocFlavor()
        assert flavor.name == "Pandoc"
        assert flavor.supports_tables()
        assert flavor.supports_task_lists()
        assert flavor.supports_strikethrough()
        assert flavor.supports_autolinks()
        assert flavor.supports_footnotes()
        assert flavor.supports_definition_lists()
        assert flavor.supports_math()

    def test_kramdown_capabilities(self):
        """Test Kramdown flavor capabilities."""
        flavor = KramdownFlavor()
        assert flavor.name == "Kramdown"
        assert flavor.supports_tables()
        assert flavor.supports_task_lists()
        assert flavor.supports_strikethrough()
        assert flavor.supports_autolinks()
        assert flavor.supports_footnotes()
        assert flavor.supports_definition_lists()
        assert flavor.supports_math()


@pytest.mark.unit
class TestFlavorDefaults:
    """Test flavor default option values."""

    def test_commonmark_defaults(self):
        """Test CommonMark default options."""
        defaults = get_flavor_defaults("commonmark")
        assert defaults["unsupported_table_mode"] == "html"
        assert defaults["unsupported_inline_mode"] == "html"

    def test_gfm_defaults(self):
        """Test GFM default options."""
        defaults = get_flavor_defaults("gfm")
        assert defaults["unsupported_table_mode"] == "html"
        assert defaults["unsupported_inline_mode"] == "html"

    def test_multimarkdown_defaults(self):
        """Test MultiMarkdown default options."""
        defaults = get_flavor_defaults("multimarkdown")
        assert defaults["unsupported_table_mode"] == "html"
        assert defaults["unsupported_inline_mode"] == "html"

    def test_pandoc_defaults(self):
        """Test Pandoc default options."""
        defaults = get_flavor_defaults("pandoc")
        assert defaults["unsupported_table_mode"] == "force"
        assert defaults["unsupported_inline_mode"] == "force"

    def test_kramdown_defaults(self):
        """Test Kramdown default options."""
        defaults = get_flavor_defaults("kramdown")
        assert defaults["unsupported_table_mode"] == "force"
        assert defaults["unsupported_inline_mode"] == "force"


@pytest.mark.unit
class TestFlavorValidation:
    """Test flavor compatibility validation."""

    def test_commonmark_table_warning(self):
        """Test warning when using tables with CommonMark."""
        options = MarkdownOptions(
            flavor="commonmark",
            unsupported_table_mode="force",
            pad_table_cells=False
        )
        warnings = validate_flavor_compatibility("commonmark", options)
        assert len(warnings) > 0
        assert "does not support tables natively" in warnings[0]

    def test_commonmark_drop_tables_with_padding(self):
        """Test warning when dropping tables but pad_table_cells is True."""
        options = MarkdownOptions(
            flavor="commonmark",
            unsupported_table_mode="drop",
            pad_table_cells=True
        )
        warnings = validate_flavor_compatibility("commonmark", options)
        assert len(warnings) > 0
        assert "Tables will be dropped entirely" in warnings[0]

    def test_gfm_no_warnings(self):
        """Test no warnings for GFM with compatible options."""
        options = MarkdownOptions(
            flavor="gfm",
            unsupported_table_mode="force",
            pad_table_cells=True
        )
        warnings = validate_flavor_compatibility("gfm", options)
        assert len(warnings) == 0

    def test_commonmark_strikethrough_force_warning(self):
        """Test warning when forcing strikethrough with CommonMark."""
        options = MarkdownOptions(
            flavor="commonmark",
            unsupported_inline_mode="force",
            unsupported_table_mode="html"  # Avoid table warning
        )
        warnings = validate_flavor_compatibility("commonmark", options)
        assert len(warnings) > 0
        assert any("not valid CommonMark" in w for w in warnings)

    def test_multimarkdown_task_lists_warning(self):
        """Test warning when forcing task lists with MultiMarkdown."""
        options = MarkdownOptions(
            flavor="multimarkdown",
            unsupported_inline_mode="force"
        )
        warnings = validate_flavor_compatibility("multimarkdown", options)
        assert len(warnings) > 0
        assert "does not support task lists" in warnings[0]


@pytest.mark.unit
class TestFlavorRendering:
    """Test rendering with different flavors."""

    def test_commonmark_table_as_html(self):
        """Test CommonMark renders tables as HTML."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Header 1")]),
                    TableCell(content=[Text(content="Header 2")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Cell 1")]),
                        TableCell(content=[Text(content="Cell 2")])
                    ])
                ]
            )
        ])
        options = MarkdownOptions(flavor="commonmark", unsupported_table_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "<table>" in result
        assert "<th>Header 1</th>" in result

    def test_commonmark_table_as_ascii(self):
        """Test CommonMark can render tables as ASCII art."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Header 1")]),
                    TableCell(content=[Text(content="Header 2")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Cell 1")]),
                        TableCell(content=[Text(content="Cell 2")])
                    ])
                ]
            )
        ])
        options = MarkdownOptions(flavor="commonmark", unsupported_table_mode="ascii")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "+" in result  # ASCII table borders
        assert "-" in result
        assert "|" in result

    def test_commonmark_table_drop(self):
        """Test CommonMark can drop tables entirely."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Header 1")]),
                    TableCell(content=[Text(content="Header 2")])
                ]),
                rows=[]
            ),
            Paragraph(content=[Text(content="After table")])
        ])
        options = MarkdownOptions(flavor="commonmark", unsupported_table_mode="drop")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "Title" in result
        assert "After table" in result
        assert "Header 1" not in result  # Table dropped

    def test_gfm_table_as_pipe(self):
        """Test GFM renders tables as pipe tables."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Header 1")]),
                    TableCell(content=[Text(content="Header 2")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Cell 1")]),
                        TableCell(content=[Text(content="Cell 2")])
                    ])
                ]
            )
        ])
        options = MarkdownOptions(flavor="gfm")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "| Header 1 | Header 2 |" in result
        assert "|---|---|" in result
        assert "| Cell 1 | Cell 2 |" in result

    def test_commonmark_strikethrough_plain(self):
        """Test CommonMark renders strikethrough as plain text."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Strikethrough(content=[Text(content="deleted")]),
                Text(content=" text")
            ])
        ])
        options = MarkdownOptions(flavor="commonmark", unsupported_inline_mode="plain")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "This is deleted text"

    def test_commonmark_strikethrough_html(self):
        """Test CommonMark renders strikethrough as HTML."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Strikethrough(content=[Text(content="deleted")]),
                Text(content=" text")
            ])
        ])
        options = MarkdownOptions(flavor="commonmark", unsupported_inline_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "<del>deleted</del>" in result

    def test_gfm_strikethrough_markdown(self):
        """Test GFM renders strikethrough as markdown."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Strikethrough(content=[Text(content="deleted")]),
                Text(content=" text")
            ])
        ])
        options = MarkdownOptions(flavor="gfm")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "~~deleted~~" in result


@pytest.mark.unit
class TestToMarkdownFlavorParameter:
    """Test flavor parameter in to_markdown function."""

    def test_flavor_parameter_commonmark(self):
        """Test specifying CommonMark flavor via parameter."""
        # Create a simple text file
        text_content = "Hello World"
        result = to_markdown(text_content.encode(), source_format="txt", flavor="commonmark")
        assert result == "Hello World"

    def test_flavor_parameter_gfm(self):
        """Test specifying GFM flavor via parameter."""
        text_content = "Hello World"
        result = to_markdown(text_content.encode(), source_format="txt", flavor="gfm")
        assert result == "Hello World"

    def test_flavor_parameter_multimarkdown(self):
        """Test specifying MultiMarkdown flavor via parameter."""
        text_content = "Hello World"
        result = to_markdown(text_content.encode(), source_format="txt", flavor="multimarkdown")
        assert result == "Hello World"

    def test_flavor_parameter_pandoc(self):
        """Test specifying Pandoc flavor via parameter."""
        text_content = "Hello World"
        result = to_markdown(text_content.encode(), source_format="txt", flavor="pandoc")
        assert result == "Hello World"

    def test_flavor_parameter_kramdown(self):
        """Test specifying Kramdown flavor via parameter."""
        text_content = "Hello World"
        result = to_markdown(text_content.encode(), source_format="txt", flavor="kramdown")
        assert result == "Hello World"

    def test_flavor_kwarg_priority(self):
        """Test flavor kwarg overrides options."""
        text_content = "Hello World"
        options = MarkdownOptions(flavor="commonmark")
        # flavor kwarg should override options
        result = to_markdown(text_content.encode(), source_format="txt", renderer_options=options, flavor="gfm")
        assert result == "Hello World"
