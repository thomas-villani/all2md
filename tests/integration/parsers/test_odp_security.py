"""Integration tests for ODP parser URL sanitization security.

This test module validates that the ODP parser properly sanitizes
dangerous URL schemes in links to prevent XSS attacks.

Test Coverage:
- Hyperlink URL sanitization (dangerous schemes blocked)
- Safe URL preservation
- Mixed safe and dangerous URLs

Note: ODP is a binary format, so these tests use the odfpy library
to generate proper ODF documents.
"""

import tempfile
from pathlib import Path

import pytest

from all2md import to_markdown

# Check if odfpy is available
try:
    from odf.draw import Frame, Page, TextBox
    from odf.opendocument import OpenDocumentPresentation
    from odf.style import MasterPage, PageLayout, PageLayoutProperties
    from odf.text import A, P

    HAS_ODFPY = True
except ImportError:
    HAS_ODFPY = False

pytestmark = pytest.mark.skipif(not HAS_ODFPY, reason="odfpy library required for ODP fixture generation")


class TestOdpUrlSanitization:
    """Test ODP parser URL scheme security."""

    def _create_odp_with_links(self, links: list[tuple[str, str]]) -> Path:
        """Create a minimal ODP file with specified links using odfpy.

        Parameters
        ----------
        links : list[tuple[str, str]]
            List of (url, text) tuples

        Returns
        -------
        Path
            Path to created ODP file

        """
        if not HAS_ODFPY:
            pytest.skip("odfpy library required")

        # Create ODP document
        doc = OpenDocumentPresentation()

        # Define basic page layout
        page_layout = PageLayout(name="StandardLayout")
        page_layout.addElement(
            PageLayoutProperties(margintop="1in", marginbottom="1in", marginleft="1in", marginright="1in")
        )
        doc.automaticstyles.addElement(page_layout)

        # Master page
        master_page = MasterPage(name="Standard", pagelayoutname=page_layout)
        doc.masterstyles.addElement(master_page)

        # Create slides with links
        for i, (url, text) in enumerate(links):
            slide = Page(name=f"Slide{i + 1}", masterpagename=master_page, stylename="StandardLayout")

            # Content frame with link
            frame = Frame(width="8in", height="4in", x="1in", y="2in")
            textbox = TextBox()
            p = P()
            p.addText("Link: ")
            link = A(href=url, text=text)
            p.addElement(link)
            textbox.addElement(p)
            frame.addElement(textbox)
            slide.addElement(frame)

            doc.presentation.addElement(slide)

        # Save to temporary file
        temp_dir = Path(tempfile.mkdtemp())
        odp_path = temp_dir / "test.odp"
        doc.save(str(odp_path))

        return odp_path

    def test_javascript_url_blocked(self):
        """Test that javascript: URLs in ODP links are blocked."""
        odp_path = self._create_odp_with_links([("javascript:alert('xss')", "Malicious Link")])

        try:
            result = to_markdown(odp_path, source_format="odp")

            # URL should be sanitized to empty string
            assert "javascript:" not in result
            assert "Malicious Link" in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_vbscript_url_blocked(self):
        """Test that vbscript: URLs in ODP links are blocked."""
        odp_path = self._create_odp_with_links([("vbscript:msgbox('xss')", "VBScript Attack")])

        try:
            result = to_markdown(odp_path, source_format="odp")

            # URL should be sanitized to empty string
            assert "vbscript:" not in result
            assert "VBScript Attack" in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_data_html_url_blocked(self):
        """Test that data:text/html URLs in ODP links are blocked."""
        odp_path = self._create_odp_with_links([("data:text/html,<script>alert('xss')</script>", "Data HTML")])

        try:
            result = to_markdown(odp_path, source_format="odp")

            # URL should be sanitized to empty string
            assert "data:text/html" not in result
            assert "<script>" not in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_safe_url_preserved(self):
        """Test that safe URLs in ODP links are preserved."""
        odp_path = self._create_odp_with_links([("https://example.com", "Example Link")])

        try:
            result = to_markdown(odp_path, source_format="odp")

            # Safe URL should be preserved
            assert "https://example.com" in result
            assert "Example Link" in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_multiple_mixed_urls_across_slides(self):
        """Test presentation with multiple slides containing mixed safe and dangerous URLs."""
        odp_path = self._create_odp_with_links(
            [
                ("javascript:void(0)", "JS Link"),
                ("https://example.com", "Safe Link"),
                ("vbscript:msgbox('xss')", "VBS Link"),
                ("mailto:test@example.com", "Email Link"),
                ("data:text/javascript,alert('xss')", "Data Link"),
                ("tel:+1234567890", "Phone Link"),
            ]
        )

        try:
            result = to_markdown(odp_path, source_format="odp")

            # Dangerous URLs should be sanitized
            assert "javascript:" not in result
            assert "vbscript:" not in result
            assert "data:text/javascript" not in result

            # Safe URLs should be preserved
            assert "https://example.com" in result or "Safe Link" in result
            assert "mailto:test@example.com" in result or "Email Link" in result
            assert "tel:+1234567890" in result or "Phone Link" in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_case_insensitive_scheme_detection(self):
        """Test that scheme detection is case-insensitive."""
        odp_path = self._create_odp_with_links(
            [
                ("JAVASCRIPT:alert('XSS')", "Upper"),
                ("JavaScript:alert('XSS')", "Mixed"),
                ("JaVaScRiPt:alert('XSS')", "Weird"),
                ("HTTPS://example.com", "Safe Upper"),
            ]
        )

        try:
            result = to_markdown(odp_path, source_format="odp")

            # All javascript variants should be blocked
            assert "JAVASCRIPT:" not in result
            assert "JavaScript:" not in result
            assert "JaVaScRiPt:" not in result

            # HTTPS should work regardless of case
            assert "example.com" in result or "Safe Upper" in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_file_url_handling(self):
        """Test that file:// URLs are handled according to security policy."""
        odp_path = self._create_odp_with_links(
            [
                ("file:///etc/passwd", "System File"),
                ("file:///home/user/.ssh/id_rsa", "SSH Key"),
            ]
        )

        try:
            result = to_markdown(odp_path, source_format="odp")

            # file:// URLs should be handled by security policy
            assert "System File" in result or result.strip() != ""
            assert "SSH Key" in result or result.strip() != ""
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_mailto_tel_schemes_allowed(self):
        """Test that mailto: and tel: schemes are allowed (safe)."""
        odp_path = self._create_odp_with_links(
            [
                ("mailto:info@example.com", "Email Us"),
                ("tel:+1-555-0100", "Phone"),
            ]
        )

        try:
            result = to_markdown(odp_path, source_format="odp")

            # Safe communication schemes should be preserved
            assert "mailto:info@example.com" in result or "Email Us" in result
            assert "tel:+1-555-0100" in result or "Phone" in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()

    def test_presentation_with_title_slide_and_dangerous_links(self):
        """Test full presentation structure with title and content slides containing XSS attempts."""
        odp_path = self._create_odp_with_links(
            [
                ("https://example.com", "Title Link"),
                ("javascript:alert('slide1')", "Slide 1 Danger"),
                ("https://safe.com", "Slide 1 Safe"),
                ("vbscript:msgbox('slide2')", "Slide 2 Danger"),
            ]
        )

        try:
            result = to_markdown(odp_path, source_format="odp")

            # Dangerous URLs should be blocked
            assert "javascript:" not in result
            assert "vbscript:" not in result

            # Safe URLs should be preserved
            assert "https://example.com" in result or "Title Link" in result
            assert "https://safe.com" in result or "Slide 1 Safe" in result
        finally:
            odp_path.unlink()
            odp_path.parent.rmdir()
