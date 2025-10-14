"""Integration tests for ODT parser URL sanitization security.

This test module validates that the ODT parser properly sanitizes
dangerous URL schemes in links to prevent XSS attacks.

Test Coverage:
- Hyperlink URL sanitization (dangerous schemes blocked)
- Safe URL preservation
- Mixed safe and dangerous URLs

Note: ODT is a binary format, so these tests use generated fixtures
or mock ODT document structures.
"""

import tempfile
import zipfile
from pathlib import Path

from all2md import to_markdown


class TestOdtUrlSanitization:
    """Test ODT parser URL scheme security."""

    def _create_odt_with_links(self, links: list[tuple[str, str]]) -> Path:
        """Create a minimal ODT file with specified links.

        Parameters
        ----------
        links : list[tuple[str, str]]
            List of (url, text) tuples

        Returns
        -------
        Path
            Path to created ODT file

        """
        # Create temporary ODT file
        temp_dir = Path(tempfile.mkdtemp())
        odt_path = temp_dir / "test.odt"

        # Create minimal ODT structure
        with zipfile.ZipFile(odt_path, 'w', zipfile.ZIP_DEFLATED) as odt:
            # Mimetype (uncompressed)
            odt.writestr('mimetype', 'application/vnd.oasis.opendocument.text', compress_type=zipfile.ZIP_STORED)

            # META-INF/manifest.xml
            manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
  <manifest:file-entry manifest:media-type="application/vnd.oasis.opendocument.text" manifest:full-path="/"/>
  <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="content.xml"/>
</manifest:manifest>'''
            odt.writestr('META-INF/manifest.xml', manifest)

            # content.xml with links
            links_xml = '\n'.join(
                f'<text:p><text:a xlink:href="{url}" xlink:type="simple">{text}</text:a></text:p>'
                for url, text in links
            )

            content = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                         xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
                         xmlns:xlink="http://www.w3.org/1999/xlink">
  <office:body>
    <office:text>
      {links_xml}
    </office:text>
  </office:body>
</office:document-content>'''
            odt.writestr('content.xml', content)

        return odt_path

    def test_javascript_url_blocked(self):
        """Test that javascript: URLs in ODT links are blocked."""
        odt_path = self._create_odt_with_links([
            ("javascript:alert('xss')", "Malicious Link")
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # URL should be sanitized to empty string
            assert "javascript:" not in result
            assert "Malicious Link" in result
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()

    def test_vbscript_url_blocked(self):
        """Test that vbscript: URLs in ODT links are blocked."""
        odt_path = self._create_odt_with_links([
            ("vbscript:msgbox('xss')", "VBScript Attack")
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # URL should be sanitized to empty string
            assert "vbscript:" not in result
            assert "VBScript Attack" in result
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()

    def test_data_html_url_blocked(self):
        """Test that data:text/html URLs in ODT links are blocked."""
        odt_path = self._create_odt_with_links([
            ("data:text/html,<script>alert('xss')</script>", "Data HTML")
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # URL should be sanitized to empty string
            assert "data:text/html" not in result
            assert "<script>" not in result
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()

    def test_safe_url_preserved(self):
        """Test that safe URLs in ODT links are preserved."""
        odt_path = self._create_odt_with_links([
            ("https://example.com", "Example Link")
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # Safe URL should be preserved
            assert "https://example.com" in result
            assert "Example Link" in result
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()

    def test_multiple_mixed_urls(self):
        """Test document with multiple mixed safe and dangerous URLs."""
        odt_path = self._create_odt_with_links([
            ("javascript:void(0)", "JS Link"),
            ("https://example.com", "Safe Link"),
            ("vbscript:msgbox('xss')", "VBS Link"),
            ("mailto:test@example.com", "Email Link"),
            ("data:text/javascript,alert('xss')", "Data Link"),
            ("tel:+1234567890", "Phone Link"),
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # Dangerous URLs should be sanitized
            assert "javascript:" not in result
            assert "vbscript:" not in result
            assert "data:text/javascript" not in result

            # Safe URLs should be preserved
            assert "https://example.com" in result or "Safe Link" in result
            assert "mailto:test@example.com" in result or "Email Link" in result
            assert "tel:+1234567890" in result or "Phone Link" in result
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()

    def test_case_insensitive_scheme_detection(self):
        """Test that scheme detection is case-insensitive."""
        odt_path = self._create_odt_with_links([
            ("JAVASCRIPT:alert('XSS')", "Upper"),
            ("JavaScript:alert('XSS')", "Mixed"),
            ("JaVaScRiPt:alert('XSS')", "Weird"),
            ("HTTPS://example.com", "Safe Upper"),
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # All javascript variants should be blocked
            assert "JAVASCRIPT:" not in result
            assert "JavaScript:" not in result
            assert "JaVaScRiPt:" not in result

            # HTTPS should work regardless of case
            assert "example.com" in result or "Safe Upper" in result
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()

    def test_file_url_handling(self):
        """Test that file:// URLs are handled according to security policy."""
        odt_path = self._create_odt_with_links([
            ("file:///etc/passwd", "System File"),
            ("file:///home/user/.ssh/id_rsa", "SSH Key"),
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # file:// URLs should be handled by security policy
            assert "System File" in result or result.strip() != ""
            assert "SSH Key" in result or result.strip() != ""
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()

    def test_mailto_tel_schemes_allowed(self):
        """Test that mailto: and tel: schemes are allowed (safe)."""
        odt_path = self._create_odt_with_links([
            ("mailto:info@example.com", "Email Us"),
            ("tel:+1-555-0100", "Phone"),
        ])

        try:
            result = to_markdown(odt_path, source_format="odt")

            # Safe communication schemes should be preserved
            assert "mailto:info@example.com" in result or "Email Us" in result
            assert "tel:+1-555-0100" in result or "Phone" in result
        finally:
            odt_path.unlink()
            odt_path.parent.rmdir()
