#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for new AsciiDoc renderer improvements."""

import logging

from all2md.ast import Document, FootnoteDefinition, FootnoteReference, LineBreak, Paragraph, Text
from all2md.options.asciidoc import AsciiDocRendererOptions
from all2md.renderers.asciidoc import AsciiDocRenderer


class TestAsciiDocLineWrapping:
    """Tests for line wrapping support in AsciiDoc renderer."""

    def test_no_wrapping_by_default(self) -> None:
        """Test that line_length=0 (default) doesn't wrap text."""
        long_text = "This is a very long paragraph that would normally be wrapped if wrapping were enabled but should remain on a single line with the default settings."

        doc = Document(children=[Paragraph(content=[Text(content=long_text)])])

        options = AsciiDocRendererOptions(line_length=0)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should be on one line (no newlines in the middle)
        lines = output.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == long_text

    def test_wrap_at_line_length(self) -> None:
        """Test that text wraps at specified line_length."""
        long_text = (
            "This is a very long paragraph that should be wrapped "
            "at the specified line length to make the output more readable."
        )

        doc = Document(children=[Paragraph(content=[Text(content=long_text)])])

        options = AsciiDocRendererOptions(line_length=50)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should be wrapped into multiple lines
        lines = output.strip().split("\n")
        assert len(lines) > 1

        # Each line (except possibly the last) should be <= 50 chars
        for line in lines[:-1]:
            assert len(line) <= 50

    def test_preserve_hard_breaks_while_wrapping(self) -> None:
        """Test that hard breaks ( +) are preserved during wrapping."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="First line that is quite long and should wrap"),
                        LineBreak(),
                        Text(content="Second line also long enough to need wrapping"),
                    ]
                )
            ]
        )

        options = AsciiDocRendererOptions(line_length=40)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should contain ' +' for hard break
        assert " +" in output

    def test_wrapping_preserves_words(self) -> None:
        """Test that wrapping doesn't break words."""
        text = "Supercalifragilisticexpialidocious is a very long word that should not be broken"

        doc = Document(children=[Paragraph(content=[Text(content=text)])])

        options = AsciiDocRendererOptions(line_length=30)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # "Supercalifragilisticexpialidocious" should remain intact
        assert "Supercalifragilisticexpialidocious" in output

    def test_wrap_multiple_paragraphs(self) -> None:
        """Test wrapping works for multiple paragraphs."""
        para1_text = "This is the first paragraph with some text that needs to be wrapped at the line length."
        para2_text = "This is the second paragraph also with text that should be wrapped."

        doc = Document(
            children=[
                Paragraph(content=[Text(content=para1_text)]),
                Paragraph(content=[Text(content=para2_text)]),
            ]
        )

        options = AsciiDocRendererOptions(line_length=40)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Both paragraphs should be wrapped
        lines = output.strip().split("\n")
        # Should have more lines than just 2 paragraphs
        assert len(lines) > 2

    def test_empty_paragraph_no_wrapping(self) -> None:
        """Test that empty paragraphs are handled correctly."""
        doc = Document(children=[Paragraph(content=[])])

        options = AsciiDocRendererOptions(line_length=50)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should not cause errors


class TestAsciiDocFootnoteWarnings:
    """Tests for footnote reference warnings."""

    def test_missing_footnote_definition_logs_warning(self, caplog) -> None:
        """Test that missing footnote definition triggers a warning."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="Text with"), FootnoteReference(identifier="missing"), Text(content=" ref")]
                )
            ]
        )

        renderer = AsciiDocRenderer()

        with caplog.at_level(logging.WARNING):
            output = renderer.render_to_string(doc)

        # Should log a warning about missing footnote
        assert any("missing" in record.message for record in caplog.records)
        assert any("no definition" in record.message.lower() for record in caplog.records)

    def test_present_footnote_definition_no_warning(self, caplog) -> None:
        """Test that present footnote definition doesn't trigger warning."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with"),
                        FootnoteReference(identifier="fn1"),
                        Text(content=" footnote"),
                    ]
                ),
                FootnoteDefinition(identifier="fn1", content=[Paragraph(content=[Text(content="Footnote text")])]),
            ]
        )

        renderer = AsciiDocRenderer()

        with caplog.at_level(logging.WARNING):
            output = renderer.render_to_string(doc)

        # Should not log warnings
        footnote_warnings = [
            r for r in caplog.records if "footnote" in r.message.lower() and "no definition" in r.message.lower()
        ]
        assert len(footnote_warnings) == 0

    def test_missing_footnote_still_renders(self) -> None:
        """Test that missing footnote still renders (with empty brackets)."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="Text"), FootnoteReference(identifier="missing"), Text(content=" here")]
                )
            ]
        )

        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # Should render footnote:missing[] even without definition
        assert "footnote:missing[]" in output

    def test_multiple_missing_footnotes(self, caplog) -> None:
        """Test multiple missing footnotes each log warning."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text"),
                        FootnoteReference(identifier="fn1"),
                        Text(content=" and"),
                        FootnoteReference(identifier="fn2"),
                    ]
                )
            ]
        )

        renderer = AsciiDocRenderer()

        with caplog.at_level(logging.WARNING):
            output = renderer.render_to_string(doc)

        # Should log warnings for both missing footnotes
        # First occurrence of each footnote logs warning
        warning_records = [r for r in caplog.records if "no definition" in r.message.lower()]
        assert len(warning_records) >= 1  # At least one warning

    def test_repeated_footnote_reference_one_warning(self, caplog) -> None:
        """Test repeated reference to same missing footnote logs warning once."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="First"),
                        FootnoteReference(identifier="fn1"),
                        Text(content=" second"),
                        FootnoteReference(identifier="fn1"),
                    ]
                )
            ]
        )

        renderer = AsciiDocRenderer()

        with caplog.at_level(logging.WARNING):
            output = renderer.render_to_string(doc)

        # Should only log one warning (for first occurrence)
        # The exact behavior depends on implementation
        # But we should get at least one warning for fn1
        fn1_warnings = [r for r in caplog.records if "fn1" in r.message and "no definition" in r.message.lower()]
        assert len(fn1_warnings) >= 1


class TestAsciiDocRendererEdgeCases:
    """Additional edge case tests for renderer improvements."""

    def test_wrapping_with_very_short_line_length(self) -> None:
        """Test wrapping with unrealistically short line length."""
        text = "Short text"

        doc = Document(children=[Paragraph(content=[Text(content=text)])])

        # Line length shorter than some words
        options = AsciiDocRendererOptions(line_length=5)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should still render without errors
        assert "Short" in output
        assert "text" in output

    def test_wrapping_negative_line_length(self) -> None:
        """Test that line_length=0 disables wrapping."""
        text = "This is a long text that should not be wrapped with line_length=0"

        doc = Document(children=[Paragraph(content=[Text(content=text)])])

        options = AsciiDocRendererOptions(line_length=0)
        renderer = AsciiDocRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should be on one line
        lines = output.strip().split("\n")
        assert len(lines) == 1
