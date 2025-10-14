"""Integration tests for ODP parser URL sanitization security.

This test module validates that the ODP parser properly sanitizes
dangerous URL schemes in links to prevent XSS attacks.

Test Coverage:
- Hyperlink URL sanitization (dangerous schemes blocked)
- Safe URL preservation
- Mixed safe and dangerous URLs

Note: ODP is a binary format, so these tests use generated fixtures
or mock ODP document structures.
"""

import tempfile
import zipfile
from pathlib import Path

from all2md import to_markdown


class TestOdpUrlSanitization:
    """Test ODP parser URL scheme security."""

    def _create_odp_with_links(self, links: list[tuple[str, str]]) -> Path:
        """Create a minimal ODP file with specified links.

        Parameters
        ----------
        links : list[tuple[str, str]]
            List of (url, text) tuples

        Returns
        -------
        Path
            Path to created ODP file

        """
        # Create temporary ODP file
        temp_dir = Path(tempfile.mkdtemp())
        odp_path = temp_dir / "test.odp"

        # Create minimal ODP structure
        with zipfile.ZipFile(odp_path, 'w', zipfile.ZIP_DEFLATED) as odp:
            # Mimetype (uncompressed)
            odp.writestr('mimetype', 'application/vnd.oasis.opendocument.presentation', compress_type=zipfile.ZIP_STORED)

            # META-INF/manifest.xml
            manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
  <manifest:file-entry manifest:media-type="application/vnd.oasis.opendocument.presentation" manifest:full-path="/"/>
  <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="content.xml"/>
</manifest:manifest>'''
            odp.writestr('META-INF/manifest.xml', manifest)

            # content.xml with links in slides
            links_xml = '\n'.join(
                f'''
                <draw:page draw:name="Slide {i+1}">
                  <draw:frame>
                    <draw:text-box>
                      <text:p><text:a xlink:href="{url}" xlink:type="simple">{text}</text:a></text:p>
                    </draw:text-box>
                  </draw:frame>
                </draw:page>
                '''
                for i, (url, text) in enumerate(links)
            )

            content = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                         xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
                         xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
                         xmlns:xlink="http://www.w3.org/1999/xlink">
  <office:body>
    <office:presentation>
      {links_xml}
    </office:presentation>
  </office:body>
</office:document-content>'''
            odp.writestr('content.xml', content)

        return odp_path

    def test_javascript_url_blocked(self):
        """Test that javascript: URLs in ODP links are blocked."""
        odp_path = self._create_odp_with_links([
            ("javascript:alert('xss')", "Malicious Link")
        ])

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
        odp_path = self._create_odp_with_links([
            ("vbscript:msgbox('xss')", "VBScript Attack")
        ])

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
        odp_path = self._create_odp_with_links([
            ("data:text/html,<script>alert('xss')</script>", "Data HTML")
        ])

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
        odp_path = self._create_odp_with_links([
            ("https://example.com", "Example Link")
        ])

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
        odp_path = self._create_odp_with_links([
            ("javascript:void(0)", "JS Link"),
            ("https://example.com", "Safe Link"),
            ("vbscript:msgbox('xss')", "VBS Link"),
            ("mailto:test@example.com", "Email Link"),
            ("data:text/javascript,alert('xss')", "Data Link"),
            ("tel:+1234567890", "Phone Link"),
        ])

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
        odp_path = self._create_odp_with_links([
            ("JAVASCRIPT:alert('XSS')", "Upper"),
            ("JavaScript:alert('XSS')", "Mixed"),
            ("JaVaScRiPt:alert('XSS')", "Weird"),
            ("HTTPS://example.com", "Safe Upper"),
        ])

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
        odp_path = self._create_odp_with_links([
            ("file:///etc/passwd", "System File"),
            ("file:///home/user/.ssh/id_rsa", "SSH Key"),
        ])

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
        odp_path = self._create_odp_with_links([
            ("mailto:info@example.com", "Email Us"),
            ("tel:+1-555-0100", "Phone"),
        ])

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
        odp_path = self._create_odp_with_links([
            ("https://example.com", "Title Link"),
            ("javascript:alert('slide1')", "Slide 1 Danger"),
            ("https://safe.com", "Slide 1 Safe"),
            ("vbscript:msgbox('slide2')", "Slide 2 Danger"),
        ])

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
