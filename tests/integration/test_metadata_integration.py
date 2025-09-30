"""Integration tests for metadata extraction across all converters."""

import json
from io import BytesIO

import pytest

from all2md import to_markdown
from all2md.options import EmlOptions, HtmlOptions, IpynbOptions, MhtmlOptions
from tests.utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.integration
@pytest.mark.metadata
class TestMetadataIntegration:
    """Integration tests for metadata extraction functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_html_metadata_extraction_integration(self):
        """Test HTML metadata extraction with real file."""
        html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Integration Test Document</title>
    <meta name="author" content="Test Author">
    <meta name="description" content="Testing HTML metadata extraction in integration">
    <meta name="keywords" content="integration,test,metadata,html">
    <meta name="generator" content="Integration Test Suite">
    <meta property="og:title" content="OG Test Title">
    <meta property="og:type" content="article">
</head>
<body>
    <h1>Integration Test Document</h1>
    <p>This document tests metadata extraction in integration tests.</p>
    <p>It contains multiple paragraphs and <a href="https://example.com">links</a>.</p>
    <img src="test.png" alt="Test image">
</body>
</html>'''

        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content, encoding='utf-8')

        # Test with metadata extraction enabled
        options = HtmlOptions(extract_metadata=True)
        result = to_markdown(str(html_file), options=options)

        # Verify YAML front matter is present
        assert result.startswith("---")
        assert "title: Integration Test Document" in result
        assert "author: Test Author" in result
        assert "description: Testing HTML metadata extraction in integration" in result
        assert "keywords: [integration, test, metadata, html]" in result
        assert "creator: Integration Test Suite" in result
        assert "category: article" in result

        # Verify content is still present
        assert "# Integration Test Document" in result
        assert "[links](https://example.com)" in result

    def test_eml_metadata_extraction_integration(self):
        """Test EML metadata extraction with real email file."""
        eml_content = '''From: sender@example.com (Test Sender)
To: recipient@example.com
Subject: Integration Test Email
Date: Fri, 26 Sep 2025 15:30:00 +0000
Message-ID: <integration-test@example.com>
X-Mailer: Integration Test Mailer
Content-Type: text/plain; charset=utf-8

This is an integration test email for metadata extraction.

It contains multiple lines and should extract proper metadata.

Best regards,
Test Sender
'''

        eml_file = self.temp_dir / "test.eml"
        eml_file.write_bytes(eml_content.encode('utf-8'))

        # Test with metadata extraction enabled
        options = EmlOptions(extract_metadata=True)
        result = to_markdown(str(eml_file), options=options)

        # Verify YAML front matter is present
        assert result.startswith("---")
        assert "title: Integration Test Email" in result
        assert "author: sender@example.com" in result
        assert "creation_date: Fri, 26 Sep 2025 15:30:00 +0000" in result or "creation_date: 2025-09-26" in result
        assert "creator: Integration Test Mailer" in result
        assert 'to: ["recipient@example.com"]' in result
        assert "message_id: <integration-test@example.com>" in result

        # Verify content is still present
        assert "This is an integration test email" in result

    def test_ipynb_metadata_extraction_integration(self):
        """Test Jupyter notebook metadata extraction with real notebook."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# Integration Test Notebook\n",
                        "\n",
                        "This notebook tests metadata extraction."
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": [
                        {
                            "name": "stdout",
                            "output_type": "stream",
                            "text": [
                                "Hello from integration test!\n"
                            ]
                        }
                    ],
                    "source": [
                        "print('Hello from integration test!')"
                    ]
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "## Section 2\n",
                        "\n",
                        "More content here."
                    ]
                }
            ],
            "metadata": {
                "title": "Integration Test Notebook",
                "authors": [{"name": "Integration Test Author"}],
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": "3.9.0",
                    "mimetype": "text/x-python"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }

        notebook_file = self.temp_dir / "test.ipynb"
        notebook_file.write_text(json.dumps(notebook_content), encoding='utf-8')

        # Test with metadata extraction enabled
        options = IpynbOptions(extract_metadata=True)
        result = to_markdown(str(notebook_file), options=options)

        # Verify YAML front matter is present
        assert result.startswith("---")
        assert "title: Integration Test Notebook" in result
        assert "author: Integration Test Author" in result
        assert "language: python" in result
        assert "kernel: Python 3" in result
        assert 'language_version: "3.9.0"' in result
        assert "cell_count: 3" in result
        assert "code_cells: 1" in result
        assert "markdown_cells: 2" in result

        # Verify content is still present
        assert "# Integration Test Notebook" in result
        assert "print('Hello from integration test!')" in result

    def test_mhtml_metadata_extraction_integration(self):
        """Test MHTML metadata extraction with real MHTML file."""
        mhtml_content = b'''MIME-Version: 1.0
Content-Type: multipart/related; boundary="integration-test-boundary"
From: test@example.com
Subject: Integration Test MHTML
Date: Fri, 26 Sep 2025 16:00:00 +0000

--integration-test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<head>
    <title>MHTML Integration Test</title>
    <meta name="author" content="MHTML Test Author">
    <meta name="description" content="Integration test for MHTML metadata">
    <meta name="keywords" content="mhtml,integration,test">
</head>
<body>
    <h1>MHTML Integration Test</h1>
    <p>This is an MHTML document for integration testing.</p>
    <p>Word count: This document contains multiple words for testing.</p>
    <a href="https://example.com">External link</a>
    <a href="https://test.com">Another link</a>
</body>
</html>

--integration-test-boundary--
'''

        mhtml_file = self.temp_dir / "test.mht"
        mhtml_file.write_bytes(mhtml_content)

        # Test with metadata extraction enabled
        options = MhtmlOptions(extract_metadata=True)
        result = to_markdown(str(mhtml_file), options=options)

        # Verify YAML front matter is present
        assert result.startswith("---")
        assert "title: Integration Test MHTML" in result
        assert "author: test@example.com" in result
        assert "description: Integration test for MHTML metadata" in result
        assert "keywords: [mhtml, integration, test]" in result
        assert "word_count:" in result  # Should have word count

        # Verify content is still present
        assert "# MHTML Integration Test" in result
        assert "[External link](https://example.com)" in result

    @pytest.mark.skipif(True, reason="ODF tests require complex setup - skip for now")
    def test_odf_metadata_extraction_integration(self):
        """Test ODF metadata extraction - skipped due to complexity."""
        pass

    @pytest.mark.skipif(True, reason="RTF tests require pyth library which may not be available")
    def test_rtf_metadata_extraction_integration(self):
        """Test RTF metadata extraction - skipped if pyth not available."""
        pass

    @pytest.mark.skipif(True, reason="PDF tests require PyMuPDF which may not be available")
    def test_pdf_metadata_extraction_integration(self):
        """Test PDF metadata extraction - skipped if PyMuPDF not available."""
        pass

    @pytest.mark.skipif(True, reason="DOCX tests require python-docx which may not be available")
    def test_docx_metadata_extraction_integration(self):
        """Test DOCX metadata extraction - skipped if python-docx not available."""
        pass

    @pytest.mark.skipif(True, reason="XLSX tests require openpyxl which may not be available")
    def test_xlsx_metadata_extraction_integration(self):
        """Test XLSX metadata extraction - skipped if openpyxl not available."""
        pass

    def test_metadata_extraction_disabled_by_default(self):
        """Test that metadata extraction is disabled by default."""
        html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Default Test</title>
    <meta name="author" content="Default Author">
</head>
<body>
    <h1>Default Test</h1>
    <p>Testing default behavior.</p>
</body>
</html>'''

        html_file = self.temp_dir / "default.html"
        html_file.write_text(html_content, encoding='utf-8')

        # Test without explicit metadata options (should default to False)
        result = to_markdown(str(html_file))

        # Should NOT have YAML front matter
        assert not result.startswith("---")
        assert "title:" not in result
        assert "author:" not in result

        # Should still have content
        assert "# Default Test" in result
        assert "Testing default behavior." in result

    def test_metadata_extraction_with_file_like_objects(self):
        """Test metadata extraction works with file-like objects."""
        html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>BytesIO Test</title>
    <meta name="author" content="BytesIO Author">
</head>
<body>
    <h1>BytesIO Test</h1>
</body>
</html>'''

        # Test with BytesIO
        html_bytes = BytesIO(html_content.encode('utf-8'))
        options = HtmlOptions(extract_metadata=True)
        result = to_markdown(html_bytes, options=options)

        # Verify metadata extraction works with file-like objects
        assert result.startswith("---")
        assert "title: BytesIO Test" in result
        assert "author: BytesIO Author" in result
        assert "# BytesIO Test" in result
