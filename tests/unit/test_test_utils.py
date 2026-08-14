"""Tests for the test suite's own helpers in ``tests/utils.py``.

``assert_markdown_valid`` is called at ~300 sites across the docx/html/pptx/eml/pdf
unit, integration and e2e suites, always positioned as *the* validity check right
after a conversion. It previously asserted nothing at all -- every branch ended in
``pass`` -- so it accepted empty output, garbage, and structurally broken Markdown.

These tests exist to prove the oracle can actually fail. An oracle that has never
been re-run against known-bad input is not evidence of anything.
"""

import pytest
from utils import assert_markdown_valid

pytestmark = pytest.mark.unit


class TestAssertMarkdownValidRejectsGarbage:
    """The oracle must raise AssertionError on malformed input."""

    def test_rejects_none(self) -> None:
        with pytest.raises(AssertionError, match="expected Markdown as str"):
            assert_markdown_valid(None)  # type: ignore[arg-type]

    def test_rejects_bytes(self) -> None:
        with pytest.raises(AssertionError, match="expected Markdown as str"):
            assert_markdown_valid(b"# Heading")  # type: ignore[arg-type]

    def test_rejects_nul_byte(self) -> None:
        with pytest.raises(AssertionError, match="NUL byte"):
            assert_markdown_valid("Some text\x00more text")

    def test_rejects_leaked_python_repr(self) -> None:
        leaked = "Paragraph: <all2md.ast.nodes.Paragraph object at 0x000001F2A3B4C5D6>\n"
        with pytest.raises(AssertionError, match="leaked Python object repr"):
            assert_markdown_valid(leaked)

    def test_rejects_unclosed_backtick_fence(self) -> None:
        with pytest.raises(AssertionError, match="unclosed code fence"):
            assert_markdown_valid("# Title\n\n```python\nprint('hi')\n")

    def test_rejects_unclosed_tilde_fence(self) -> None:
        with pytest.raises(AssertionError, match="unclosed code fence"):
            assert_markdown_valid("~~~\nsome code\n")

    def test_rejects_stray_closing_fence(self) -> None:
        """A lone closing fence is itself read as an opener, so it must fail too."""
        with pytest.raises(AssertionError, match="unclosed code fence"):
            assert_markdown_valid("Some prose.\n\n```\n")

    def test_rejects_three_fences(self) -> None:
        markdown = "```\na\n```\n\n```python\nb\n"
        with pytest.raises(AssertionError, match="unclosed code fence"):
            assert_markdown_valid(markdown)

    def test_rejects_closing_fence_that_is_too_short(self) -> None:
        """A 4-backtick block is not closed by a 3-backtick fence."""
        with pytest.raises(AssertionError, match="unclosed code fence"):
            assert_markdown_valid("````\ncode with ``` inside\n```\n")

    def test_rejects_table_delimiter_without_header(self) -> None:
        markdown = "Some prose.\n\n|---|---|\n| a | b |\n"
        with pytest.raises(AssertionError, match="not preceded by a header row"):
            assert_markdown_valid(markdown)

    def test_rejects_table_delimiter_after_blank_line(self) -> None:
        markdown = "| a | b |\n\n| --- | --- |\n| 1 | 2 |\n"
        with pytest.raises(AssertionError, match="not preceded by a header row"):
            assert_markdown_valid(markdown)

    def test_rejects_table_delimiter_as_first_line(self) -> None:
        with pytest.raises(AssertionError, match="not preceded by a header row"):
            assert_markdown_valid("| --- | --- |\n| 1 | 2 |\n")

    def test_error_message_names_the_offending_line(self) -> None:
        with pytest.raises(AssertionError) as excinfo:
            assert_markdown_valid("para\n\n```js\nvar x = 1;\n")
        assert "line 3" in str(excinfo.value)


class TestAssertMarkdownValidAcceptsRealOutput:
    """Representative real conversion output must pass unchanged."""

    def test_accepts_empty_string(self) -> None:
        """Empty documents legitimately convert to empty output."""
        assert_markdown_valid("")

    def test_accepts_whitespace_only(self) -> None:
        assert_markdown_valid("\n\n")

    def test_accepts_plain_prose(self) -> None:
        assert_markdown_valid("# Main Heading\n\nA paragraph with **bold** and *italic* text.\n")

    def test_accepts_balanced_fence_with_info_string(self) -> None:
        markdown = "## Code Example\n\nInline `code` example.\n\n```python\ndef f():\n    return 1\n```\n"
        assert_markdown_valid(markdown)

    def test_accepts_fence_indented_inside_list_item(self) -> None:
        markdown = "- item\n\n  ```python\n  x = 1\n  ```\n\n- next item\n"
        assert_markdown_valid(markdown)

    def test_accepts_closing_fence_with_trailing_whitespace(self) -> None:
        assert_markdown_valid("```\ncode\n```   \n")

    def test_accepts_longer_closing_fence(self) -> None:
        assert_markdown_valid("```\ncode\n`````\n")

    def test_accepts_nested_fence_inside_longer_fence(self) -> None:
        """A markdown sample containing ``` inside a 4-backtick block is balanced."""
        assert_markdown_valid("````markdown\n```python\nx = 1\n```\n````\n")

    def test_accepts_tilde_fence(self) -> None:
        assert_markdown_valid("~~~python\nx = 1\n~~~\n")

    def test_accepts_well_formed_table(self) -> None:
        markdown = "| Name | Value |\n| --- | --- |\n| a | 1 |\n| b | 2 |\n"
        assert_markdown_valid(markdown)

    def test_accepts_table_with_alignment_row(self) -> None:
        markdown = "| L | C | R |\n|:---|:---:|---:|\n| a | b | c |\n"
        assert_markdown_valid(markdown)

    def test_accepts_table_delimiter_inside_code_block(self) -> None:
        """Delimiter-looking lines inside a fence are code, not tables."""
        markdown = "```\n|---|---|\n| a | b |\n```\n"
        assert_markdown_valid(markdown)

    def test_accepts_horizontal_rule(self) -> None:
        assert_markdown_valid("Above\n\n---\n\nBelow\n")

    def test_accepts_yaml_frontmatter(self) -> None:
        assert_markdown_valid("---\ntitle: Doc\n---\n\n# Doc\n")

    def test_accepts_setext_heading(self) -> None:
        assert_markdown_valid("Title\n-----\n\nBody.\n")

    def test_accepts_html_and_links(self) -> None:
        markdown = "A [link](https://example.com) and an ![img](data:image/png;base64,iVBOR)\n\n<br />\n"
        assert_markdown_valid(markdown)

    def test_accepts_merged_cell_table(self) -> None:
        """Merged cells produce ragged rows; that is measured, expected output.

        Markdown cannot express colspan/rowspan, so a DOCX/HTML table with merged
        cells renders rows whose cell counts differ from the delimiter row. 20 of 327
        real conversion outputs look like this. A column-count-consistency rule was
        measured, found to fail all of them, and dropped rather than special-cased.
        """
        markdown = "| Header 1 | Header Group |\n|---|---|---|\n| Sub Header 1 | Sub Header 2 |\n| Row 1 Cell 1 | Row 1 Cell 2 | Row 1 Cell 3 |\n"
        assert_markdown_valid(markdown)

    def test_accepts_non_nul_control_character(self) -> None:
        """An HTML entity test legitimately round-trips ``&#4;`` to a literal U+0004."""
        assert_markdown_valid("Incomplete: \\{ \x04 ©\n")

    @pytest.mark.parametrize(
        "markdown",
        [
            "# H1\n\n## H2\n\n- a\n- b\n\n1. one\n2. two\n",
            "> quoted\n> more\n\nAfter.\n",
            "Text with ~~strike~~ and ==highlight== and ^sup^ and ~sub~.\n",
            "| a |\n| --- |\n| 1 |\n",
            "Footnote ref[^1]\n\n[^1]: The note.\n",
            "Term\n\n: Definition\n",
        ],
    )
    def test_accepts_assorted_renderer_output(self, markdown: str) -> None:
        assert_markdown_valid(markdown)
