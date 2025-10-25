#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for HTML attribute sanitization security features.

This module tests the comprehensive attribute sanitization added to prevent XSS
attacks through event handler attributes and JavaScript framework attributes.

Tests cover:
- Event handler attribute detection (on* pattern)
- JavaScript framework attribute detection (x-*, v-*, ng-*, hx-*, etc.)
- Case-insensitive matching
- Attribute prefix patterns
- Integration with is_element_safe() function
"""

import pytest

try:
    from bs4 import BeautifulSoup

    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

from all2md.utils.html_sanitizer import is_element_safe


@pytest.mark.unit
@pytest.mark.skipif(not BEAUTIFULSOUP_AVAILABLE, reason="BeautifulSoup not available")
class TestEventHandlerAttributeSanitization:
    """Test suite for event handler attribute sanitization."""

    def test_common_event_handlers_detected(self):
        """Test that common event handler attributes are detected and blocked."""
        dangerous_attrs = [
            "onclick",
            "onload",
            "onerror",
            "onmouseover",
            "onfocus",
            "onblur",
            "onsubmit",
            "onchange",
            "oninput",
        ]

        for attr in dangerous_attrs:
            html = f"<div {attr}=\"alert('XSS')\">Content</div>"
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.div), f"Failed to detect dangerous attribute: {attr}"

    def test_all_mouse_event_handlers_detected(self):
        """Test that all mouse-related event handlers are detected."""
        mouse_events = [
            "onmousedown",
            "onmouseup",
            "onmousemove",
            "onmouseenter",
            "onmouseleave",
            "onmouseout",
            "oncontextmenu",
            "onwheel",
        ]

        for event in mouse_events:
            html = f'<div {event}="doSomething()">Content</div>'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.div), f"Failed to detect {event}"

    def test_all_keyboard_event_handlers_detected(self):
        """Test that all keyboard-related event handlers are detected."""
        keyboard_events = ["onkeydown", "onkeyup", "onkeypress"]

        for event in keyboard_events:
            html = f'<input {event}="handleKey(event)" />'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.input), f"Failed to detect {event}"

    def test_form_event_handlers_detected(self):
        """Test that form-related event handlers are detected."""
        form_events = ["onsubmit", "onreset", "onchange", "oninput", "oninvalid", "onselect"]

        for event in form_events:
            html = f'<form {event}="validateForm()"><input /></form>'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.form), f"Failed to detect {event}"

    def test_media_event_handlers_detected(self):
        """Test that media-related event handlers are detected."""
        media_events = [
            "onplay",
            "onpause",
            "onended",
            "onvolumechange",
            "onloadedmetadata",
            "ontimeupdate",
        ]

        for event in media_events:
            html = f'<video {event}="trackPlayback()"></video>'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.video), f"Failed to detect {event}"

    def test_drag_drop_event_handlers_detected(self):
        """Test that drag and drop event handlers are detected."""
        drag_events = ["ondrag", "ondragstart", "ondragend", "ondrop", "ondragover", "ondragenter", "ondragleave"]

        for event in drag_events:
            html = f'<div {event}="handleDrag(event)" draggable="true">Drag me</div>'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.div), f"Failed to detect {event}"

    def test_clipboard_event_handlers_detected(self):
        """Test that clipboard event handlers are detected."""
        clipboard_events = ["oncopy", "oncut", "onpaste"]

        for event in clipboard_events:
            html = f'<div {event}="interceptClipboard()">Text</div>'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.div), f"Failed to detect {event}"

    def test_animation_event_handlers_detected(self):
        """Test that animation and transition event handlers are detected."""
        animation_events = ["onanimationstart", "onanimationend", "onanimationiteration", "ontransitionend"]

        for event in animation_events:
            html = f'<div {event}="handleAnimation()">Animated</div>'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.div), f"Failed to detect {event}"

    def test_case_insensitive_event_handler_detection(self):
        """Test that event handler detection is case-insensitive."""
        case_variations = [
            "onclick",
            "onClick",
            "OnClick",
            "ONCLICK",
            "onCLICK",
        ]

        for attr in case_variations:
            html = f'<div {attr}="alert()">Content</div>'
            soup = BeautifulSoup(html, "html.parser")
            # BeautifulSoup normalizes attributes to lowercase, but we should handle both
            assert not is_element_safe(soup.div), f"Failed to detect case variation: {attr}"

    def test_pattern_based_on_prefix_detection(self):
        """Test that any attribute starting with 'on' is caught by pattern matching."""
        # Test some uncommon or future event handlers
        uncommon_events = ["onwebkitanimationend", "onmozfullscreenchange", "oncustomevent"]

        for event in uncommon_events:
            html = f'<div {event}="customHandler()">Content</div>'
            soup = BeautifulSoup(html, "html.parser")
            assert not is_element_safe(soup.div), f"Pattern matching failed for: {event}"

    def test_safe_attributes_not_blocked(self):
        """Test that safe attributes are not blocked by the on* pattern."""
        safe_attrs = ["class", "id", "data-value", "aria-label", "role", "one-time", "only-when"]

        for attr in safe_attrs:
            html = f'<div {attr}="safe-value">Content</div>'
            soup = BeautifulSoup(html, "html.parser")
            assert is_element_safe(soup.div), f"Safe attribute incorrectly blocked: {attr}"

    def test_multiple_dangerous_attributes(self):
        """Test detection when element has multiple dangerous attributes."""
        html = '<div onclick="alert(1)" onmouseover="alert(2)" onload="alert(3)">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.div)

    def test_mixed_safe_and_dangerous_attributes(self):
        """Test that elements with both safe and dangerous attributes are flagged."""
        html = '<div class="container" id="main" onclick="hack()">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.div)


@pytest.mark.unit
@pytest.mark.skipif(not BEAUTIFULSOUP_AVAILABLE, reason="BeautifulSoup not available")
class TestFrameworkAttributeSanitization:
    """Test suite for JavaScript framework attribute sanitization."""

    def test_alpine_js_attributes_detected_when_enabled(self):
        """Test that Alpine.js attributes are detected when framework stripping enabled."""
        alpine_attrs = [
            "x-data",
            "x-show",
            "x-bind",
            "x-on",
            "x-text",
            "x-html",
            "x-model",
            "x-if",
            "x-for",
            "x-init",
        ]

        for attr in alpine_attrs:
            html = f'<div {attr}="{{open: false}}">Alpine</div>'
            soup = BeautifulSoup(html, "html.parser")

            # Should be safe without framework stripping
            assert is_element_safe(
                soup.div, strip_framework_attributes=False
            ), f"Incorrectly blocked {attr} without framework stripping"

            # Should be blocked with framework stripping
            assert not is_element_safe(
                soup.div, strip_framework_attributes=True
            ), f"Failed to detect {attr} with framework stripping"

    def test_vue_js_attributes_detected_when_enabled(self):
        """Test that Vue.js attributes are detected when framework stripping enabled."""
        vue_attrs = [
            "v-bind",
            "v-on",
            "v-model",
            "v-if",
            "v-else",
            "v-for",
            "v-show",
            "v-html",
            "v-text",
        ]

        for attr in vue_attrs:
            html = f'<div {attr}="value">Vue</div>'
            soup = BeautifulSoup(html, "html.parser")

            assert is_element_safe(soup.div, strip_framework_attributes=False)
            assert not is_element_safe(soup.div, strip_framework_attributes=True), f"Failed to detect {attr}"

    def test_angular_attributes_detected_when_enabled(self):
        """Test that Angular attributes are detected when framework stripping enabled."""
        angular_attrs = [
            "ng-app",
            "ng-bind",
            "ng-click",
            "ng-model",
            "ng-if",
            "ng-repeat",
            "ng-show",
            "ng-hide",
            "ng-init",
        ]

        for attr in angular_attrs:
            html = f'<div {attr}="expression">Angular</div>'
            soup = BeautifulSoup(html, "html.parser")

            assert is_element_safe(soup.div, strip_framework_attributes=False)
            assert not is_element_safe(soup.div, strip_framework_attributes=True), f"Failed to detect {attr}"

    def test_htmx_attributes_detected_when_enabled(self):
        """Test that HTMX attributes are detected when framework stripping enabled."""
        htmx_attrs = [
            "hx-get",
            "hx-post",
            "hx-put",
            "hx-delete",
            "hx-trigger",
            "hx-target",
            "hx-swap",
            "hx-vals",
        ]

        for attr in htmx_attrs:
            html = f'<div {attr}="/api/data">HTMX</div>'
            soup = BeautifulSoup(html, "html.parser")

            assert is_element_safe(soup.div, strip_framework_attributes=False)
            assert not is_element_safe(soup.div, strip_framework_attributes=True), f"Failed to detect {attr}"

    def test_framework_prefix_patterns_detected(self):
        """Test that framework attribute prefixes are properly detected."""
        prefix_examples = [
            ("x-custom-attr", "Alpine.js custom"),
            ("v-custom", "Vue.js custom"),
            ("ng-custom", "Angular custom"),
            ("hx-custom", "HTMX custom"),
        ]

        for attr, description in prefix_examples:
            html = f'<div {attr}="value">{description}</div>'
            soup = BeautifulSoup(html, "html.parser")

            assert is_element_safe(
                soup.div, strip_framework_attributes=False
            ), f"{description}: Safe without framework stripping"
            assert not is_element_safe(
                soup.div, strip_framework_attributes=True
            ), f"{description}: Should be blocked with framework stripping"

    def test_data_prefixed_framework_attributes(self):
        """Test detection of framework attributes with data- prefix."""
        data_attrs = ["data-x-show", "data-v-model", "data-ng-click", "data-hx-get"]

        for attr in data_attrs:
            html = f'<div {attr}="value">Framework</div>'
            soup = BeautifulSoup(html, "html.parser")

            assert is_element_safe(soup.div, strip_framework_attributes=False)
            assert not is_element_safe(
                soup.div, strip_framework_attributes=True
            ), f"Failed to detect data-prefixed attribute: {attr}"

    def test_regular_data_attributes_not_blocked(self):
        """Test that regular data-* attributes are not blocked."""
        safe_data_attrs = ["data-id", "data-value", "data-config", "data-timestamp", "data-user-id"]

        for attr in safe_data_attrs:
            html = f'<div {attr}="123">Content</div>'
            soup = BeautifulSoup(html, "html.parser")

            # These should be safe even with framework stripping
            assert is_element_safe(
                soup.div, strip_framework_attributes=True
            ), f"Safe data attribute incorrectly blocked: {attr}"


@pytest.mark.unit
@pytest.mark.skipif(not BEAUTIFULSOUP_AVAILABLE, reason="BeautifulSoup not available")
class TestEdgeCasesAndRegressions:
    """Test edge cases and potential regressions in attribute sanitization."""

    def test_empty_attribute_value(self):
        """Test handling of empty attribute values."""
        html = '<div onclick="">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        # Even empty values should be blocked for dangerous attributes
        assert not is_element_safe(soup.div)

    def test_attribute_without_value(self):
        """Test handling of boolean attributes without values."""
        # Note: onclick should always have a value, but test defensive handling
        html = "<div onclick>Content</div>"
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.div)

    def test_safe_element_with_no_attributes(self):
        """Test that elements without attributes are safe."""
        html = "<div>Safe content</div>"
        soup = BeautifulSoup(html, "html.parser")
        assert is_element_safe(soup.div)

    def test_combined_event_and_framework_attributes(self):
        """Test element with both event handlers and framework attributes."""
        html = '<div onclick="alert()" x-data="{open: false}">Content</div>'
        soup = BeautifulSoup(html, "html.parser")

        # Should be unsafe due to onclick regardless of framework stripping
        assert not is_element_safe(soup.div, strip_framework_attributes=False)
        assert not is_element_safe(soup.div, strip_framework_attributes=True)

    def test_safe_attributes_with_framework_stripping_enabled(self):
        """Test that normal attributes remain safe with framework stripping enabled."""
        html = '<div class="container" id="main" data-value="123">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert is_element_safe(soup.div, strip_framework_attributes=True)

    def test_oncustom_pattern_detection(self):
        """Test that custom event handlers following on* pattern are detected."""
        # Even if not a standard HTML event, should be blocked by pattern
        html = '<div oncustomevent="handleCustom()">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.div)

    def test_attribute_name_with_on_substring_but_not_prefix(self):
        """Test that attributes containing 'on' but not as prefix are safe."""
        html = '<div common="value" button="click">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert is_element_safe(soup.div)

    def test_dangerous_element_types_still_detected(self):
        """Test that dangerous element types are still detected."""
        dangerous_elements = ["<script>alert(1)</script>", "<style>body{display:none}</style>", "<iframe src='x'>"]

        for html in dangerous_elements:
            soup = BeautifulSoup(html, "html.parser")
            element = soup.find()
            assert not is_element_safe(element), f"Failed to detect dangerous element: {html}"

    def test_url_scheme_checking_still_works(self):
        """Test that URL scheme checking for href/src still works."""
        html = "<a href=\"javascript:alert('XSS')\">Click</a>"
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.a)

    def test_style_attribute_checking_still_works(self):
        """Test that dangerous style attributes are still detected."""
        html = '<div style="background: url(javascript:alert(1))">Content</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.div)


@pytest.mark.unit
@pytest.mark.skipif(not BEAUTIFULSOUP_AVAILABLE, reason="BeautifulSoup not available")
class TestRealWorldXSSVectors:
    """Test real-world XSS attack vectors to ensure they're blocked."""

    def test_xss_via_onerror_image(self):
        """Test XSS via onerror on image tag."""
        html = '<img src="invalid.jpg" onerror="alert(\'XSS\')" />'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.img)

    def test_xss_via_onload_body(self):
        """Test XSS via onload on body tag."""
        html = '<body onload="maliciousCode()">Content</body>'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.body)

    def test_xss_via_onmouseover_link(self):
        """Test XSS via onmouseover on link."""
        html = '<a href="#" onmouseover="stealCookies()">Hover me</a>'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.a)

    def test_xss_via_onfocus_input(self):
        """Test XSS via onfocus on input field."""
        html = '<input type="text" onfocus="alert(document.cookie)" />'
        soup = BeautifulSoup(html, "html.parser")
        assert not is_element_safe(soup.input)

    def test_xss_via_alpine_js_x_html(self):
        """Test potential XSS via Alpine.js x-html attribute."""
        html = '<div x-html="userProvidedContent">Content</div>'
        soup = BeautifulSoup(html, "html.parser")

        # Safe without framework stripping (no Alpine.js in output context)
        assert is_element_safe(soup.div, strip_framework_attributes=False)

        # Blocked with framework stripping (Alpine.js might be present)
        assert not is_element_safe(soup.div, strip_framework_attributes=True)

    def test_xss_via_vue_v_html(self):
        """Test potential XSS via Vue.js v-html attribute."""
        html = '<div v-html="maliciousHTML">Content</div>'
        soup = BeautifulSoup(html, "html.parser")

        assert is_element_safe(soup.div, strip_framework_attributes=False)
        assert not is_element_safe(soup.div, strip_framework_attributes=True)

    def test_xss_via_angular_ng_bind_html(self):
        """Test potential XSS via Angular ng-bind-html."""
        html = '<div ng-bind-html="unsafeContent">Content</div>'
        soup = BeautifulSoup(html, "html.parser")

        assert is_element_safe(soup.div, strip_framework_attributes=False)
        assert not is_element_safe(soup.div, strip_framework_attributes=True)

    def test_multiple_xss_vectors_combined(self):
        """Test multiple XSS vectors in single element."""
        html = '<div onclick="alert(1)" x-data="{}" v-html="xss">Dangerous</div>'
        soup = BeautifulSoup(html, "html.parser")

        # Should be blocked due to onclick alone
        assert not is_element_safe(soup.div, strip_framework_attributes=False)
        assert not is_element_safe(soup.div, strip_framework_attributes=True)
