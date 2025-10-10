#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for renderer security features.

This module tests the HTML sanitization features in all renderers,
including pass-through mode control, TOC text extraction, and language
attribute handling.
"""

import pytest

from all2md.ast import (
    Document,
    Heading,
    HTMLBlock,
    HTMLInline,
    Paragraph,
    Strong,
    Text,
)
from all2md.options import (
    AsciiDocRendererOptions,
    HtmlRendererOptions,
    MediaWikiOptions,
)
from all2md.renderers.asciidoc import AsciiDocRenderer
from all2md.renderers.html import HtmlRenderer
from all2md.renderers.mediawiki import MediaWikiRenderer


class TestHtmlRendererSecurity:
    """Test security features in HtmlRenderer."""

    def test_pass_through_mode_default(self):
        """Test that pass-through mode is the default and preserves HTML."""
        doc = Document(children=[
            HTMLBlock(content='<script>alert("xss")</script>')
        ])

        options = HtmlRendererOptions(standalone=False)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<script>alert("xss")</script>' in result

    def test_escape_mode_escapes_html_block(self):
        """Test that escape mode HTML-escapes HTMLBlock content."""
        doc = Document(children=[
            HTMLBlock(content='<script>alert("xss")</script>')
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="escape")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '&lt;script&gt;' in result
        assert '<script>' not in result

    def test_escape_mode_escapes_html_inline(self):
        """Test that escape mode HTML-escapes HTMLInline content."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Text with "),
                HTMLInline(content='<script>alert()</script>'),
                Text(content=" inline HTML")
            ])
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="escape")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '&lt;script&gt;' in result
        assert '<script>' not in result

    def test_drop_mode_removes_html_block(self):
        """Test that drop mode removes HTMLBlock content entirely."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Before")]),
            HTMLBlock(content='<script>alert("xss")</script>'),
            Paragraph(content=[Text(content="After")])
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="drop")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'Before' in result
        assert 'After' in result
        assert 'script' not in result

    def test_drop_mode_removes_html_inline(self):
        """Test that drop mode removes HTMLInline content."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Before "),
                HTMLInline(content='<span onclick="alert()">danger</span>'),
                Text(content=" after")
            ])
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="drop")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'Before' in result
        assert 'after' in result
        assert 'onclick' not in result
        assert 'danger' not in result

    def test_sanitize_mode_removes_dangerous_elements(self):
        """Test that sanitize mode removes dangerous elements."""
        doc = Document(children=[
            HTMLBlock(content='<script>alert()</script><p>Safe content</p>')
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="sanitize")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Script should be removed
        assert 'script' not in result.lower() or '&lt;script' in result
        # Safe content should be preserved
        assert 'Safe content' in result or 'safe content' in result.lower()

    def test_sanitize_mode_removes_dangerous_attributes(self):
        """Test that sanitize mode removes dangerous attributes."""
        doc = Document(children=[
            HTMLBlock(content='<div onclick="alert()">Click me</div>')
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="sanitize")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # onclick should be removed
        assert 'onclick' not in result

    def test_language_attribute_from_options(self):
        """Test that language attribute uses value from options."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello")])
        ])

        options = HtmlRendererOptions(standalone=True, language="fr")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<html lang="fr">' in result

    def test_language_attribute_from_metadata(self):
        """Test that language attribute prefers metadata over options."""
        doc = Document(
            metadata={'language': 'de'},
            children=[Paragraph(content=[Text(content="Hallo")])]
        )

        options = HtmlRendererOptions(standalone=True, language="en")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<html lang="de">' in result
        assert '<html lang="en">' not in result

    def test_language_attribute_default(self):
        """Test that language attribute defaults to 'en'."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello")])
        ])

        options = HtmlRendererOptions(standalone=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<html lang="en">' in result

    def test_toc_extracts_plain_text_from_heading(self):
        """Test that TOC entries contain plain text, not HTML tags."""
        doc = Document(children=[
            Heading(level=1, content=[
                Text(content="Title with "),
                Strong(content=[Text(content="bold")]),
                Text(content=" text")
            ])
        ])

        options = HtmlRendererOptions(standalone=True, include_toc=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # TOC should be present
        assert 'Table of Contents' in result

        # TOC entry should have plain text without <strong> tags
        # Find the TOC section
        toc_start = result.find('<nav id="table-of-contents">')
        toc_end = result.find('</nav>', toc_start)
        toc_section = result[toc_start:toc_end]

        # TOC link text should not contain HTML tags
        assert '<strong>' not in toc_section
        assert 'Title with bold text' in toc_section

    def test_toc_with_inline_html(self):
        """Test that TOC strips inline HTML from heading content."""
        doc = Document(children=[
            Heading(level=1, content=[
                Text(content="Title with "),
                HTMLInline(content='<span class="special">special</span>'),
                Text(content=" content")
            ])
        ])

        options = HtmlRendererOptions(
            standalone=True,
            include_toc=True,
            html_passthrough_mode="pass-through"
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Find the TOC section
        toc_start = result.find('<nav id="table-of-contents">')
        toc_end = result.find('</nav>', toc_start)
        toc_section = result[toc_start:toc_end]

        # TOC should have plain text, not HTML tags
        assert '<span' not in toc_section
        # Text content should be present
        assert 'Title with' in toc_section
        assert 'content' in toc_section


class TestAsciiDocRendererSecurity:
    """Test security features in AsciiDocRenderer."""

    def test_pass_through_mode_preserves_html_block(self):
        """Test that pass-through mode preserves HTMLBlock."""
        doc = Document(children=[
            HTMLBlock(content='<div>HTML content</div>')
        ])

        options = AsciiDocRendererOptions(html_passthrough_mode="pass-through")
        renderer = AsciiDocRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<div>HTML content</div>' in result

    def test_escape_mode_escapes_html_block(self):
        """Test that escape mode HTML-escapes HTMLBlock content."""
        doc = Document(children=[
            HTMLBlock(content='<script>alert("xss")</script>')
        ])

        options = AsciiDocRendererOptions(html_passthrough_mode="escape")
        renderer = AsciiDocRenderer(options)
        result = renderer.render_to_string(doc)

        assert '&lt;script&gt;' in result
        assert '<script>' not in result

    def test_drop_mode_removes_html_inline(self):
        """Test that drop mode removes HTMLInline content."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Before "),
                HTMLInline(content='<span>danger</span>'),
                Text(content=" after")
            ])
        ])

        options = AsciiDocRendererOptions(html_passthrough_mode="drop")
        renderer = AsciiDocRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'Before' in result
        assert 'after' in result
        assert '<span>' not in result

    def test_sanitize_mode_removes_script_tags(self):
        """Test that sanitize mode removes script tags."""
        doc = Document(children=[
            HTMLBlock(content='<script>alert()</script><p>Safe</p>')
        ])

        options = AsciiDocRendererOptions(html_passthrough_mode="sanitize")
        renderer = AsciiDocRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'script' not in result.lower() or '&lt;script' in result
        assert 'Safe' in result or 'safe' in result.lower()


class TestMediaWikiRendererSecurity:
    """Test security features in MediaWikiRenderer."""

    def test_pass_through_mode_preserves_html_block(self):
        """Test that pass-through mode preserves HTMLBlock."""
        doc = Document(children=[
            HTMLBlock(content='<div>HTML content</div>')
        ])

        options = MediaWikiOptions(html_passthrough_mode="pass-through")
        renderer = MediaWikiRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<div>HTML content</div>' in result

    def test_escape_mode_escapes_html_inline(self):
        """Test that escape mode HTML-escapes HTMLInline content."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Text "),
                HTMLInline(content='<script>alert()</script>'),
            ])
        ])

        options = MediaWikiOptions(html_passthrough_mode="escape")
        renderer = MediaWikiRenderer(options)
        result = renderer.render_to_string(doc)

        assert '&lt;script&gt;' in result
        assert '<script>' not in result

    def test_drop_mode_removes_html_block(self):
        """Test that drop mode removes HTMLBlock content."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Before")]),
            HTMLBlock(content='<iframe src="evil"></iframe>'),
            Paragraph(content=[Text(content="After")])
        ])

        options = MediaWikiOptions(html_passthrough_mode="drop")
        renderer = MediaWikiRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'Before' in result
        assert 'After' in result
        assert 'iframe' not in result

    def test_sanitize_mode_preserves_safe_html(self):
        """Test that sanitize mode preserves safe HTML."""
        doc = Document(children=[
            HTMLBlock(content='<p>Safe <strong>content</strong></p>')
        ])

        options = MediaWikiOptions(html_passthrough_mode="sanitize")
        renderer = MediaWikiRenderer(options)
        result = renderer.render_to_string(doc)

        # Safe HTML should be mostly preserved
        assert 'Safe' in result
        assert 'content' in result


class TestRendererSecurityEdgeCases:
    """Test edge cases for renderer security features."""

    def test_empty_html_block_handling(self):
        """Test handling of empty HTMLBlock nodes."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Before")]),
            HTMLBlock(content=''),
            Paragraph(content=[Text(content="After")])
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="escape")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'Before' in result
        assert 'After' in result

    def test_whitespace_only_html_content(self):
        """Test handling of whitespace-only HTML content."""
        doc = Document(children=[
            HTMLBlock(content='   \n\t   ')
        ])

        for mode in ["pass-through", "escape", "drop", "sanitize"]:
            options = HtmlRendererOptions(standalone=False, html_passthrough_mode=mode)
            renderer = HtmlRenderer(options)
            # Should not crash
            result = renderer.render_to_string(doc)
            assert isinstance(result, str)

    def test_mixed_safe_and_dangerous_html(self):
        """Test handling of mixed safe and dangerous HTML."""
        doc = Document(children=[
            HTMLBlock(content='<p>Safe</p><script>alert()</script><div>More safe</div>')
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="sanitize")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Safe content should be present
        assert 'Safe' in result or 'safe' in result.lower()
        # Dangerous content should be removed or escaped
        assert 'script' not in result.lower() or '&lt;script' in result

    def test_nested_html_blocks(self):
        """Test handling of nested HTML structures."""
        doc = Document(children=[
            HTMLBlock(content='<div><div><script>nested</script></div></div>')
        ])

        options = HtmlRendererOptions(standalone=False, html_passthrough_mode="sanitize")
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Script should be removed even when nested
        assert 'script' not in result.lower() or '&lt;script' in result

    def test_unicode_in_html_content(self):
        """Test handling of Unicode characters in HTML content."""
        doc = Document(children=[
            HTMLBlock(content='<p>Hello 世界 🌍</p>')
        ])

        for mode in ["pass-through", "escape", "drop", "sanitize"]:
            options = HtmlRendererOptions(standalone=False, html_passthrough_mode=mode)
            renderer = HtmlRenderer(options)
            result = renderer.render_to_string(doc)

            if mode != "drop":
                # Unicode should be preserved (except in drop mode)
                assert '世界' in result or '&' in result  # Either literal or escaped

    def test_all_modes_with_all_renderers(self):
        """Test that all modes work with all renderers without crashing."""
        doc = Document(children=[
            HTMLBlock(content='<script>test</script><p>Content</p>')
        ])

        modes = ["pass-through", "escape", "drop", "sanitize"]

        for mode in modes:
            # HtmlRenderer
            html_opts = HtmlRendererOptions(standalone=False, html_passthrough_mode=mode)
            html_renderer = HtmlRenderer(html_opts)
            html_result = html_renderer.render_to_string(doc)
            assert isinstance(html_result, str)

            # AsciiDocRenderer
            asciidoc_opts = AsciiDocRendererOptions(html_passthrough_mode=mode)
            asciidoc_renderer = AsciiDocRenderer(asciidoc_opts)
            asciidoc_result = asciidoc_renderer.render_to_string(doc)
            assert isinstance(asciidoc_result, str)

            # MediaWikiRenderer
            mediawiki_opts = MediaWikiOptions(html_passthrough_mode=mode)
            mediawiki_renderer = MediaWikiRenderer(mediawiki_opts)
            mediawiki_result = mediawiki_renderer.render_to_string(doc)
            assert isinstance(mediawiki_result, str)


class TestLanguageAttributeEdgeCases:
    """Test edge cases for HTML language attribute handling."""

    def test_language_special_characters(self):
        """Test language codes with special characters."""
        doc = Document(
            metadata={'language': 'zh-CN'},
            children=[Paragraph(content=[Text(content="中文")])]
        )

        options = HtmlRendererOptions(standalone=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'lang="zh-CN"' in result

    def test_language_empty_string(self):
        """Test empty string language code."""
        doc = Document(
            metadata={'language': ''},
            children=[Paragraph(content=[Text(content="Text")])]
        )

        options = HtmlRendererOptions(standalone=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Should handle empty language gracefully
        assert '<html lang=' in result

    def test_language_with_script_in_metadata(self):
        """Test that language attribute escapes dangerous content."""
        doc = Document(
            metadata={'language': '<script>alert()</script>'},
            children=[Paragraph(content=[Text(content="Text")])]
        )

        options = HtmlRendererOptions(standalone=True, escape_html=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Language should be escaped
        assert '<script>' not in result or '&lt;script&gt;' in result
