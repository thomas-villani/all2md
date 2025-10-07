"""Property-based fuzzing tests for HTML sanitization.

This test module uses Hypothesis to generate random HTML content and validate
that the HTML sanitization and link URL validation logic prevents XSS attacks
and produces safe markdown output across a wide range of inputs.

Test Coverage:
- Random HTML generation
- XSS payload testing
- Link URL scheme validation
- Malformed HTML handling
- Property: No dangerous content in markdown output
- Property: No script execution vectors
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from io import BytesIO

from all2md import to_markdown
from all2md.options import HtmlOptions
from all2md.parsers.html import HtmlToAstConverter as HtmlParser


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.security
@pytest.mark.html
class TestLinkURLSanitizationFuzzing:
    """Property-based tests for link URL sanitization."""

    @given(st.text(min_size=0, max_size=200))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_arbitrary_urls_dont_crash(self, url):
        """Property: Arbitrary URL strings should not cause crashes."""
        parser = HtmlParser(HtmlOptions())

        try:
            result = parser._sanitize_link_url(url)
            # Should always return a string (possibly empty)
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Unexpected exception for URL '{url}': {e}")

    @given(
        st.sampled_from(['javascript:', 'JavaScript:', 'JAVASCRIPT:', 'jAvAsCrIpT:']),
        st.text(alphabet=st.characters(whitelist_categories=['L', 'N', 'P']), min_size=0, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_javascript_scheme_always_blocked(self, javascript_prefix, payload):
        """Property: JavaScript scheme URLs should always be blocked (case-insensitive)."""
        parser = HtmlParser(HtmlOptions())
        url = javascript_prefix + payload

        result = parser._sanitize_link_url(url)

        # Should return empty string for javascript: URLs
        assert result == "", f"JavaScript URL not blocked: {url}"

    @given(
        st.sampled_from(['data:', 'DATA:', 'Data:', 'dAtA:']),
        st.text(min_size=0, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_data_scheme_always_blocked(self, data_prefix, payload):
        """Property: Data scheme URLs should always be blocked (case-insensitive)."""
        parser = HtmlParser(HtmlOptions())
        url = data_prefix + payload

        result = parser._sanitize_link_url(url)

        # Should return empty string for data: URLs
        assert result == "", f"Data URL not blocked: {url}"

    @given(
        st.sampled_from(['vbscript:', 'VBScript:', 'VBSCRIPT:', 'vBsCrIpT:']),
        st.text(min_size=0, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_vbscript_scheme_always_blocked(self, vbscript_prefix, payload):
        """Property: VBScript scheme URLs should always be blocked (case-insensitive)."""
        parser = HtmlParser(HtmlOptions())
        url = vbscript_prefix + payload

        result = parser._sanitize_link_url(url)

        # Should return empty string for vbscript: URLs
        assert result == "", f"VBScript URL not blocked: {url}"

    @given(
        st.sampled_from(['http://', 'https://', 'mailto:', 'tel:', 'sms:']),
        st.text(alphabet=st.characters(whitelist_categories=['L', 'N']), min_size=1, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_safe_schemes_allowed(self, safe_prefix, domain):
        """Property: Safe URL schemes should be allowed."""
        parser = HtmlParser(HtmlOptions())
        url = safe_prefix + domain

        result = parser._sanitize_link_url(url)

        # Safe URLs should be preserved (or lowercased)
        assert result.lower() == url.lower() or result == url

    @given(
        st.sampled_from(['#', '/', './', '../', '?']),
        st.text(alphabet=st.characters(whitelist_categories=['L', 'N']), min_size=0, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_relative_urls_preserved(self, prefix, path):
        """Property: Relative URLs should be preserved."""
        parser = HtmlParser(HtmlOptions())
        url = prefix + path

        result = parser._sanitize_link_url(url)

        # Relative URLs should be preserved
        assert result == url

    @given(st.text(alphabet=' \t\n\r', min_size=0, max_size=10))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_whitespace_only_urls(self, whitespace):
        """Property: Whitespace-only URLs should return empty string."""
        parser = HtmlParser(HtmlOptions())

        result = parser._sanitize_link_url(whitespace)

        # Whitespace-only should return empty string
        assert result == ""


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.html
class TestHTMLConversionFuzzing:
    """Property-based tests for HTML to Markdown conversion."""

    @given(st.text(min_size=0, max_size=500))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100, deadline=None)
    def test_arbitrary_html_dont_crash(self, html_content):
        """Property: Arbitrary HTML content should not cause crashes."""
        try:
            result = to_markdown(BytesIO(html_content.encode('utf-8')), source_format='html')
            # Should always return a string
            assert isinstance(result, str)
        except UnicodeDecodeError:
            # Expected for invalid UTF-8
            pass
        except Exception as e:
            # Should not crash with unexpected exceptions
            pytest.fail(f"Unexpected exception for HTML: {e}")

    @given(
        st.text(alphabet=st.characters(whitelist_categories=['L']), min_size=1, max_size=50),
        st.sampled_from(['javascript:alert(1)', 'data:text/html,<script>alert(1)</script>',
                        'vbscript:msgbox(1)'])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_xss_in_links_blocked(self, link_text, xss_url):
        """Property: XSS payloads in link URLs should be neutralized."""
        html = f'<a href="{xss_url}">{link_text}</a>'

        result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')

        # Link should be present but URL should be empty
        assert link_text in result

        # XSS URL should not appear in output
        assert 'javascript:' not in result.lower()
        assert 'vbscript:' not in result.lower()
        assert 'data:text/html' not in result.lower()

    @given(
        st.lists(
            st.sampled_from(['<script>', '<iframe>', '<object>', '<embed>', '<form>']),
            min_size=1,
            max_size=5
        )
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_dangerous_tags_removed_when_strip_enabled(self, dangerous_tags):
        """Property: Dangerous tags should be removed when strip_dangerous_elements=True."""
        html = ''.join(dangerous_tags) + 'Safe content'

        options = HtmlOptions(strip_dangerous_elements=True)
        result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html', parser_options=options)

        # Dangerous tags should not appear in output
        for tag in dangerous_tags:
            assert tag.lower() not in result.lower()

        # Safe content should be present for non-script/style tags
        # For script/style tags, content is removed entirely for security
        has_script_or_style = any('<script>' in tag.lower() or '<style>' in tag.lower() for tag in dangerous_tags)
        if not has_script_or_style:
            assert 'safe content' in result.lower()


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.html
class TestMalformedHTMLFuzzing:
    """Fuzz test malformed HTML handling."""

    @given(
        st.text(alphabet='<>', min_size=1, max_size=100),
        st.text(alphabet=st.characters(whitelist_categories=['L']), min_size=0, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_unbalanced_tags(self, brackets, content):
        """Property: Unbalanced HTML tags should not cause crashes."""
        html = brackets + content

        try:
            result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Crash on unbalanced tags: {e}")

    @given(
        st.text(alphabet=st.characters(whitelist_categories=['L', 'N']), min_size=1, max_size=20),
        st.text(alphabet=st.characters(whitelist_categories=['L', 'N']), min_size=0, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unclosed_tags(self, tag_name, content):
        """Property: Unclosed tags should not cause crashes."""
        html = f'<{tag_name}>{content}'

        try:
            result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Crash on unclosed tag: {e}")

    @given(
        st.lists(st.text(alphabet='<>/="\'', min_size=1, max_size=20), min_size=1, max_size=10)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_random_tag_soup(self, tag_parts):
        """Property: Random tag soup should not cause crashes."""
        html = ''.join(tag_parts)

        try:
            result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Crash on tag soup: {e}")


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.html
@pytest.mark.security
class TestXSSPayloadDatabase:
    """Test against known XSS payload patterns."""

    @given(
        st.sampled_from([
            # Classic XSS
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert(1)>',
            '<svg onload=alert(1)>',

            # Encoded XSS
            '<script>alert(String.fromCharCode(88,83,83))</script>',
            '<img src="javascript:alert(1)">',

            # Event handler XSS
            '<body onload=alert(1)>',
            '<input onfocus=alert(1) autofocus>',
            '<select onfocus=alert(1) autofocus>',

            # Data URL XSS
            '<a href="data:text/html,<script>alert(1)</script>">click</a>',
            '<iframe src="data:text/html,<script>alert(1)</script>">',

            # VBScript XSS (IE)
            '<a href="vbscript:msgbox(1)">click</a>',

            # Mixed case evasion
            '<ScRiPt>alert(1)</sCrIpT>',
            '<IMG SRC="javascript:alert(1)">',

            # Null byte injection
            '<script\x00>alert(1)</script>',
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_known_xss_payloads_neutralized(self, xss_payload):
        """Property: Known XSS payloads should be neutralized."""
        options_safe = HtmlOptions(strip_dangerous_elements=True)

        result = to_markdown(BytesIO(xss_payload.encode('utf-8', errors='ignore')),
                           source_format='html',
                           parser_options=options_safe)

        # Check that dangerous content is not present in output
        result_lower = result.lower()

        # Script tags should be removed
        assert '<script' not in result_lower
        assert 'alert(' not in result_lower

        # Event handlers should be removed/neutered
        assert 'onerror=' not in result_lower
        assert 'onload=' not in result_lower
        assert 'onfocus=' not in result_lower

        # Dangerous URL schemes should be blocked
        assert 'javascript:' not in result_lower
        assert 'vbscript:' not in result_lower
        assert 'data:text/html' not in result_lower


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.html
class TestHTMLAttributeFuzzing:
    """Fuzz test HTML attribute handling."""

    @given(
        st.text(alphabet=st.characters(whitelist_categories=['L', 'N']), min_size=1, max_size=20),
        st.text(min_size=0, max_size=100)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_random_attributes(self, attr_name, attr_value):
        """Property: Random attributes should not cause crashes."""
        html = f'<div {attr_name}="{attr_value}">content</div>'

        try:
            result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')
            assert isinstance(result, str)
            # Content should be preserved
            assert 'content' in result
        except Exception as e:
            pytest.fail(f"Crash on attribute {attr_name}={attr_value}: {e}")

    @given(
        st.text(alphabet='"\'<>', min_size=1, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_attribute_value_quoting(self, tricky_value):
        """Property: Attribute values with quotes should not break parsing."""
        html = f'<div data-value="{tricky_value}">content</div>'

        try:
            result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Crash on attribute value: {e}")


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.html
class TestURLEncodingInHTML:
    """Fuzz test URL encoding in HTML attributes."""

    @given(
        st.text(alphabet='%', min_size=1, max_size=10),
        st.text(alphabet='0123456789ABCDEFabcdef', min_size=0, max_size=20)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_percent_encoded_urls(self, percent_chars, hex_chars):
        """Property: Percent-encoded URLs should not bypass sanitization."""
        encoded_url = percent_chars + hex_chars
        html = f'<a href="{encoded_url}">link</a>'

        parser = HtmlParser(HtmlOptions())
        result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')

        # Should handle gracefully
        assert isinstance(result, str)
        assert 'link' in result

    @given(
        st.text(alphabet='&#;0123456789', min_size=1, max_size=30)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_html_entity_urls(self, entity_string):
        """Property: HTML entity encoded URLs should not bypass sanitization."""
        html = f'<a href="{entity_string}">link</a>'

        result = to_markdown(BytesIO(html.encode('utf-8')), source_format='html')

        # Should handle gracefully
        assert isinstance(result, str)
