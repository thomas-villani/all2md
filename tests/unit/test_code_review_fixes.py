#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for code review fixes.

This module tests fixes for issues identified in code review:
- parse_page_ranges reversed range handling
- render_math_html HTML injection prevention
"""

import pytest

from all2md.utils.html_utils import render_math_html
from all2md.utils.inputs import parse_page_ranges


class TestParsePageRangesEnhancements:
    """Test enhanced parse_page_ranges with reversed range handling."""

    def test_reversed_range_auto_swap(self):
        """Test that reversed ranges are automatically swapped."""
        # "10-5" should be treated as "5-10"
        result = parse_page_ranges("10-5", 20)
        assert result == [4, 5, 6, 7, 8, 9]

    def test_reversed_range_multiple(self):
        """Test multiple reversed ranges in one spec."""
        result = parse_page_ranges("10-8,3-1", 20)
        # Should be: [8,9,10] + [1,2,3] -> [0,1,2,7,8,9]
        assert sorted(result) == [0, 1, 2, 7, 8, 9]

    def test_normal_range_unchanged(self):
        """Test that normal ranges still work correctly."""
        result = parse_page_ranges("1-3,5-7", 10)
        assert result == [0, 1, 2, 4, 5, 6]

    def test_open_ended_range(self):
        """Test open-ended ranges like '8-'."""
        result = parse_page_ranges("8-", 10)
        assert result == [7, 8, 9]

    def test_single_pages(self):
        """Test single page specifications."""
        result = parse_page_ranges("1,5,10", 20)
        assert result == [0, 4, 9]

    def test_mixed_ranges_and_singles(self):
        """Test combining ranges and single pages."""
        result = parse_page_ranges("1-3,5,8-10", 20)
        assert result == [0, 1, 2, 4, 7, 8, 9]

    def test_reversed_with_open_end(self):
        """Test reversed range with open end should not happen but handle gracefully."""
        # "-5" is a valid range meaning "from start to 5"
        result = parse_page_ranges("-5", 10)
        assert result == [0, 1, 2, 3, 4]

    def test_edge_case_same_start_and_end(self):
        """Test range where start equals end."""
        result = parse_page_ranges("5-5", 10)
        assert result == [4]

    def test_backward_compatibility(self):
        """Test that existing behavior is preserved."""
        # All these should work as before
        assert parse_page_ranges("1-3,5", 10) == [0, 1, 2, 4]
        assert parse_page_ranges("8-", 10) == [7, 8, 9]
        assert parse_page_ranges("1", 10) == [0]


class TestRenderMathHtmlEnhancements:
    """Test enhanced render_math_html with HTML injection prevention."""

    def test_latex_notation_with_escaping(self):
        """Test LaTeX notation with escaping enabled."""
        result = render_math_html(
            "x < y & z > 0",
            notation="latex",
            inline=True,
            escape_enabled=True
        )
        # Should escape HTML special chars
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result

    def test_latex_notation_without_escaping(self):
        """Test LaTeX notation with escaping disabled."""
        result = render_math_html(
            "x < y & z > 0",
            notation="latex",
            inline=True,
            escape_enabled=False
        )
        # Should NOT escape
        assert "x < y & z > 0" in result

    def test_html_notation_with_escaping(self):
        """Test HTML notation with escaping enabled (XSS prevention)."""
        malicious = "<script>alert('XSS')</script>"
        result = render_math_html(
            malicious,
            notation="html",
            inline=True,
            escape_enabled=True
        )
        # Should escape to prevent XSS
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
        assert "<script>" not in result

    def test_html_notation_without_escaping(self):
        """Test HTML notation with escaping disabled (trusted content)."""
        trusted_html = "<em>emphasis</em>"
        result = render_math_html(
            trusted_html,
            notation="html",
            inline=True,
            escape_enabled=False
        )
        # Should NOT escape trusted content
        assert "<em>emphasis</em>" in result

    def test_mathml_notation_valid_xml(self):
        """Test MathML notation with valid XML."""
        mathml = "<math><mi>x</mi></math>"
        result = render_math_html(
            mathml,
            notation="mathml",
            inline=True,
            escape_enabled=True
        )
        # Should preserve valid MathML
        assert "<math><mi>x</mi></math>" in result

    def test_mathml_notation_text_content(self):
        """Test MathML notation with plain text (should wrap)."""
        result = render_math_html(
            "x + y",
            notation="mathml",
            inline=True,
            escape_enabled=True
        )
        # Should wrap in <math> tags
        assert "<math>" in result
        assert "x + y" in result
        assert "</math>" in result

    def test_block_math_formatting(self):
        """Test block math formatting."""
        result = render_math_html(
            "E = mc^2",
            notation="latex",
            inline=False,
            escape_enabled=True
        )
        # Should use div and block formatting
        assert "<div" in result
        assert "math math-block" in result
        assert "$$\nE = mc^2\n$$" in result

    def test_inline_math_formatting(self):
        """Test inline math formatting."""
        result = render_math_html(
            "E = mc^2",
            notation="latex",
            inline=True,
            escape_enabled=True
        )
        # Should use span and inline formatting
        assert "<span" in result
        assert "math math-inline" in result
        assert "$E = mc^2$" in result

    def test_data_notation_attribute(self):
        """Test that data-notation attribute is included."""
        result = render_math_html(
            "x",
            notation="latex",
            inline=True,
            escape_enabled=True
        )
        assert 'data-notation="latex"' in result

        result = render_math_html(
            "x",
            notation="html",
            inline=True,
            escape_enabled=True
        )
        assert 'data-notation="html"' in result

    def test_xss_prevention_complex_payload(self):
        """Test XSS prevention with complex malicious payload."""
        xss_payload = '<img src=x onerror="alert(\'XSS\')">'
        result = render_math_html(
            xss_payload,
            notation="html",
            inline=True,
            escape_enabled=True
        )
        # Should escape all HTML tags and attributes
        assert "&lt;img" in result
        assert "onerror" not in result or "&quot;" in result
        assert "<img" not in result

    def test_backward_compatibility_latex(self):
        """Test that default behavior for LaTeX is unchanged."""
        # Default escape_enabled=True should work
        result = render_math_html(
            "x < y",
            notation="latex",
            inline=True
        )
        assert "&lt;" in result
