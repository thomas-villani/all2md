"""Advanced tests for HTML nested element handling edge cases."""

from all2md import to_markdown as html_to_markdown
from all2md.options import HtmlOptions
from tests.utils import assert_markdown_valid


class TestHtmlNestedElements:
    """Test complex nested element scenarios in HTML documents."""


    def test_nested_lists_and_blockquotes(self):
        """Test complex nesting of lists and blockquotes."""
        html = """
        <blockquote>
            <p>Quote with <em>emphasis</em></p>
            <ul>
                <li>List in quote
                    <blockquote>
                        <p>Nested quote in list</p>
                        <ol>
                            <li>Ordered in quote in list</li>
                            <li>Second ordered item</li>
                        </ol>
                    </blockquote>
                </li>
                <li>Second list item in quote</li>
            </ul>
            <p>More quote content</p>
        </blockquote>
        """

        options = HtmlOptions(preserve_nested_structure=True)
        markdown = html_to_markdown(html, source_format="html", parser_options=options)
        assert_markdown_valid(markdown)

        # Should preserve blockquote structure
        assert "> " in markdown

        # Should handle nested lists
        assert "* " in markdown or "- " in markdown  # Unordered list
        assert "1. " in markdown  # Ordered list

        # Content should be preserved
        assert "emphasis" in markdown
        assert "List in quote" in markdown
        assert "Nested quote" in markdown
        assert "Ordered in quote" in markdown


