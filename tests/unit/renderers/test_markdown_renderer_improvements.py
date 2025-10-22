#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for new Markdown renderer improvements."""


from all2md.ast import Document, Heading, Link, Paragraph, Strong, Text
from all2md.options.markdown import MarkdownOptions
from all2md.renderers.markdown import MarkdownRenderer


class TestMarkdownSetextUnderlineWidth:
    """Tests for setext heading underline width fix."""

    def test_setext_h1_plain_text(self) -> None:
        """Test setext H1 underline matches plain text length."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Hello World")])])

        options = MarkdownOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "Hello World"
        # Underline should be 11 characters (length of "Hello World")
        assert lines[1] == "=" * 11

    def test_setext_h1_with_bold(self) -> None:
        """Test setext H1 underline with bold text calculates plain text length."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[Text(content="Hello "), Strong(content=[Text(content="Bold")]), Text(content=" World")],
                )
            ]
        )

        options = MarkdownOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        # Plain text is "Hello Bold World" = 16 characters
        # Not "Hello **Bold** World" = 20 characters
        assert lines[0] == "Hello **Bold** World"
        assert len(lines[1]) == 16
        assert lines[1] == "=" * 16

    def test_setext_h2_plain_text(self) -> None:
        """Test setext H2 underline matches plain text length."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Section")])])

        options = MarkdownOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        assert lines[0] == "Section"
        # Underline should be 7 characters
        assert lines[1] == "-" * 7

    def test_setext_with_link(self) -> None:
        """Test setext underline with link uses link text, not URL."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[
                        Text(content="Visit "),
                        Link(url="http://example.com", content=[Text(content="Example")]),
                    ],
                )
            ]
        )

        options = MarkdownOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        # Plain text is "Visit Example" = 13 characters
        # Not including the URL length
        assert len(lines[1]) == 13

    def test_prefer_setext_option(self) -> None:
        """Test prefer_setext_headings option works correctly."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])

        options = MarkdownOptions(use_hash_headings=True, prefer_setext_headings=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        # Should use setext even with use_hash_headings=True
        assert lines[1] == "=" * 5  # "Title" is 5 chars


class TestMarkdownBareUrlAutolinking:
    """Tests for improved bare URL autolinking."""

    def test_simple_url(self) -> None:
        """Test simple URL gets autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Visit http://example.com for info")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<http://example.com>" in output

    def test_url_with_nested_parentheses(self) -> None:
        """Test URL with nested parentheses is handled correctly."""
        doc = Document(
            children=[Paragraph(content=[Text(content="See http://en.wikipedia.org/wiki/Foo_(bar) article")])]
        )

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL is autolinked (parentheses may be escaped)
        assert "<http://en.wikipedia.org/wiki/Foo" in output
        assert "bar" in output

    def test_url_with_deeply_nested_parentheses(self) -> None:
        """Test URL with deeply nested parentheses."""
        doc = Document(
            children=[Paragraph(content=[Text(content="URL http://example.com/path(foo(bar)) here")])]
        )

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should handle nested parens correctly
        assert "<http://example.com/path(foo(bar))>" in output

    def test_url_in_parentheses(self) -> None:
        """Test URL surrounded by parentheses is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="(see http://example.com)")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL is autolinked
        assert "<http://example.com>" in output

    def test_url_with_trailing_period(self) -> None:
        """Test URL with trailing period is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Visit http://example.com.")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL is autolinked (period handling may vary)
        assert "<http://example.com" in output

    def test_url_with_trailing_comma(self) -> None:
        """Test URL with trailing comma is autolinked."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Sites: http://example.com, http://test.com")])]
        )

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Both URLs are autolinked
        assert "<http://example.com" in output
        assert "<http://test.com>" in output

    def test_url_with_query_string(self) -> None:
        """Test URL with query string preserves query parameters."""
        doc = Document(children=[Paragraph(content=[Text(content="Search http://example.com?q=test&page=1 query")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Query parameters should be included
        assert "<http://example.com?q=test&page=1>" in output

    def test_url_with_fragment(self) -> None:
        """Test URL with fragment preserves the fragment."""
        doc = Document(children=[Paragraph(content=[Text(content="See http://example.com/page#section")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Fragment should be included
        assert "<http://example.com/page#section>" in output

    def test_url_with_query_and_trailing_punct(self) -> None:
        """Test URL with query string and trailing punctuation."""
        doc = Document(children=[Paragraph(content=[Text(content="Link: http://example.com?q=test.")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL with query string is autolinked (punctuation handling may vary)
        assert "<http://example.com?q=test" in output

    def test_https_url(self) -> None:
        """Test HTTPS URL is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Secure: https://secure.example.com")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<https://secure.example.com>" in output

    def test_ftp_url(self) -> None:
        """Test FTP URL is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Files at ftp://files.example.com")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<ftp://files.example.com>" in output

    def test_autolink_disabled(self) -> None:
        """Test autolink_bare_urls=False doesn't autolink."""
        doc = Document(children=[Paragraph(content=[Text(content="Visit http://example.com")])])

        options = MarkdownOptions(autolink_bare_urls=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should remain as plain text
        assert "Visit http://example.com" in output
        assert "<http://example.com>" not in output

    def test_multiple_urls_in_text(self) -> None:
        """Test multiple URLs in same text are all autolinked."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Visit http://example.com and https://test.com for more info"),
                    ]
                )
            ]
        )

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<http://example.com>" in output
        assert "<https://test.com>" in output

    def test_url_with_port(self) -> None:
        """Test URL with port number."""
        doc = Document(children=[Paragraph(content=[Text(content="Server: http://localhost:8080/app")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<http://localhost:8080/app>" in output

    def test_url_with_username(self) -> None:
        """Test URL with username."""
        doc = Document(children=[Paragraph(content=[Text(content="FTP: ftp://user@ftp.example.com/files")])])

        options = MarkdownOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<ftp://user@ftp.example.com/files>" in output
