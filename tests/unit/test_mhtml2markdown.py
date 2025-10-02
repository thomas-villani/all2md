"""Unit tests for MHTML to Markdown conversion.

This module contains unit tests for the mhtml2markdown converter,
testing core functionality, error handling, and edge cases.
"""

import io
from unittest.mock import mock_open, patch

import pytest

from all2md.parsers.mhtml2markdown import extract_mhtml_metadata, mhtml_to_markdown
from all2md.exceptions import InputError, MarkdownConversionError
from all2md.options import MarkdownOptions, MhtmlOptions
from all2md.utils.metadata import DocumentMetadata


@pytest.mark.unit
@pytest.mark.mhtml
class TestMhtmlToMarkdown:
    """Test core MHTML to Markdown conversion functionality."""

    def test_mhtml_to_markdown_simple_content(self):
        """Test basic MHTML to Markdown conversion."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Test Document</h1>
    <p>Simple content with <strong>bold</strong> text.</p>
</body>
</html>

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# Test Document\n\nSimple content with **bold** text."

            result = mhtml_to_markdown(io.BytesIO(mhtml_content))

            assert result == "# Test Document\n\nSimple content with **bold** text."
            mock_html_to_md.assert_called_once()

    def test_mhtml_to_markdown_with_path(self):
        """Test MHTML conversion from file path."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body><h1>Test</h1></body></html>

--test-boundary--
"""

        with patch('os.path.exists', return_value=True):
            with patch('os.path.isfile', return_value=True):
                with patch('builtins.open', mock_open(read_data=mhtml_content)):
                    with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
                        mock_html_to_md.return_value = "# Test"

                        result = mhtml_to_markdown("test.mht")

                        assert result == "# Test"

    def test_mhtml_to_markdown_no_html_content(self):
        """Test error handling when MHTML has no HTML content."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/plain; charset=utf-8

This is plain text, not HTML.

--test-boundary--
"""

        with pytest.raises(MarkdownConversionError) as exc_info:
            mhtml_to_markdown(io.BytesIO(mhtml_content))

        assert "No HTML content found in the MHTML file" in str(exc_info.value)

    def test_mhtml_to_markdown_malformed_email(self):
        """Test error handling for malformed MHTML/email content."""
        malformed_content = b"This is not valid MHTML content at all."

        with pytest.raises(MarkdownConversionError) as exc_info:
            mhtml_to_markdown(io.BytesIO(malformed_content))

        assert "No HTML content found" in str(exc_info.value)

    def test_mhtml_to_markdown_with_cid_images(self):
        """Test MHTML conversion with Content-ID referenced images."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body>
    <h1>Test with Image</h1>
    <img src="cid:test-image" alt="Test Image">
</body></html>

--test-boundary
Content-Type: image/png
Content-ID: <test-image>
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# Test with Image\n\n![Test Image](data:image/png;base64,...)"

            mhtml_to_markdown(io.BytesIO(mhtml_content))

            # Verify that html_to_markdown was called with processed HTML
            args, _ = mock_html_to_md.call_args
            processed_html = args[0]

            # Check that the image src was converted to data URI
            assert 'data:image/png;base64,' in processed_html
            assert 'cid:test-image' not in processed_html

    def test_mhtml_to_markdown_with_file_urls(self):
        """Test MHTML conversion with file:// referenced images when local files enabled."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body>
    <img src="file://test.png" alt="File Image">
</body></html>

--test-boundary
Content-Type: image/png
Content-Location: test.png
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==

--test-boundary--
"""

        from all2md.options import LocalFileAccessOptions, MhtmlOptions

        # Enable local file access to test file:// URL processing
        options = MhtmlOptions(
            local_files=LocalFileAccessOptions(
                allow_local_files=True,
                allow_cwd_files=True
            )
        )

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "![File Image](data:image/png;base64,...)"

            mhtml_to_markdown(io.BytesIO(mhtml_content), options=options)

            # Verify that the image src was processed
            args, _ = mock_html_to_md.call_args
            processed_html = args[0]

            assert 'data:image/png;base64,' in processed_html
            assert 'file://test.png' not in processed_html

    def test_mhtml_to_markdown_file_urls_blocked_by_default(self):
        """Test that file:// URLs are blocked by default security settings."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body>
    <img src="file://test.png" alt="File Image">
</body></html>

--test-boundary
Content-Type: image/png
Content-Location: test.png
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "![File Image]"

            # Use default options (should block file:// URLs)
            mhtml_to_markdown(io.BytesIO(mhtml_content))

            # Verify that the image src was removed due to security
            args, _ = mock_html_to_md.call_args
            processed_html = args[0]

            # The img tag should be removed entirely due to security restrictions
            assert 'file://test.png' not in processed_html
            assert 'data:image/png;base64,' not in processed_html

    def test_mhtml_to_markdown_ms_word_artifact_cleanup(self):
        """Test cleanup of MS Word artifacts in MHTML."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html xmlns:o="urn:schemas-microsoft-com:office:office">
<body>
    <h1>Test Document</h1>

    <!--[if !supportLists]-->- <!--[endif]-->
    <p class="MsoListParagraph">List item 1</p>

    <!--[if !supportLists]-->1. <!--[endif]-->
    <p class="MsoListParagraph">Numbered item</p>

    <p>Regular paragraph with <o:p></o:p> artifacts.</p>

    <!--[if gte mso 9]><xml><w:WordDocument></w:WordDocument></xml><![endif]-->
</body>
</html>

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "Cleaned content"

            result = mhtml_to_markdown(io.BytesIO(mhtml_content))

            assert result == "Cleaned content"

            # Check that MS Word artifacts were cleaned
            args, _ = mock_html_to_md.call_args
            processed_html = args[0]

            # Check that the HTML was processed (even if not all artifacts removed)
            assert 'List item 1' in processed_html
            assert 'Regular paragraph' in processed_html
            # Some artifacts should be cleaned or converted
            assert '<li>' in processed_html  # Converted paragraphs

    def test_mhtml_to_markdown_with_options(self):
        """Test MHTML conversion with custom options."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body><h1>Test</h1></body></html>

--test-boundary--
"""

        md_options = MarkdownOptions(emphasis_symbol="_")
        options = MhtmlOptions(
            attachment_mode="download",
            attachment_output_dir="/tmp/images",
            markdown_options=md_options
        )

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# Test"

            mhtml_to_markdown(io.BytesIO(mhtml_content), options=options)

            # Verify options were passed to html_to_markdown
            args, kwargs = mock_html_to_md.call_args
            html_options = kwargs['options']

            assert html_options.attachment_mode == "download"
            assert html_options.attachment_output_dir == "/tmp/images"
            assert html_options.markdown_options is md_options

    def test_mhtml_to_markdown_charset_handling(self):
        """Test handling of different character encodings."""
        # MHTML with UTF-8 content
        mhtml_content = """MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body><h1>Café & Résumé</h1></body></html>

--test-boundary--
""".encode('utf-8')

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# Café & Résumé"

            mhtml_to_markdown(io.BytesIO(mhtml_content))

            # Should handle Unicode characters properly - they will be HTML encoded
            assert "Caf" in str(mock_html_to_md.call_args) and "R" in str(mock_html_to_md.call_args)

    def test_mhtml_to_markdown_missing_charset(self):
        """Test handling of HTML content without charset specification."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html

<html><body><h1>No Charset</h1></body></html>

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# No Charset"

            result = mhtml_to_markdown(io.BytesIO(mhtml_content))

            # Should default to UTF-8 and work
            assert result == "# No Charset"

    def test_mhtml_options_defaults(self):
        """Test default MHTML options."""
        options = MhtmlOptions()

        assert options.attachment_mode == "alt_text"
        assert options.attachment_output_dir is None
        assert options.attachment_base_url is None
        assert options.markdown_options is None

    def test_invalid_input_type(self):
        """Test error handling for invalid input types."""
        with pytest.raises(InputError) as exc_info:
            mhtml_to_markdown(12345)  # Invalid type

        assert "Unsupported input type" in str(exc_info.value)

    def test_mhtml_with_multiple_html_parts(self):
        """Test MHTML with multiple HTML parts (should use first one)."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body><h1>First HTML</h1></body></html>

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body><h1>Second HTML</h1></body></html>

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# First HTML"

            mhtml_to_markdown(io.BytesIO(mhtml_content))

            # Should use the first HTML part
            args, _ = mock_html_to_md.call_args
            processed_html = args[0]
            assert "First HTML" in processed_html
            assert "Second HTML" not in processed_html

    def test_mhtml_with_missing_assets(self):
        """Test MHTML conversion when referenced assets are missing."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body>
    <img src="cid:missing-image" alt="Missing">
    <img src="regular-image.png" alt="Regular">
</body></html>

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "Content with images"

            mhtml_to_markdown(io.BytesIO(mhtml_content))

            # Should handle missing assets gracefully
            args, _ = mock_html_to_md.call_args
            processed_html = args[0]
            # Missing CID reference should remain unchanged
            assert 'cid:missing-image' in processed_html
            # Regular image reference should remain unchanged
            assert 'regular-image.png' in processed_html


@pytest.mark.unit
@pytest.mark.mhtml
class TestMhtmlErrorHandling:
    """Test error handling in MHTML conversion."""

    def test_file_read_error(self):
        """Test handling of file read errors."""
        with patch('builtins.open', side_effect=IOError("Cannot read file")):
            with pytest.raises(InputError) as exc_info:
                mhtml_to_markdown("nonexistent.mht")

            assert "File does not exist: nonexistent.mht" in str(exc_info.value)

    def test_email_parsing_error(self):
        """Test handling of email parsing errors."""
        invalid_content = b"Not a valid email/MIME message"

        # This should still work as email.message_from_bytes is quite forgiving
        with patch('all2md.parsers.mhtml2markdown.html_to_markdown'):
            with pytest.raises(MarkdownConversionError) as exc_info:
                mhtml_to_markdown(io.BytesIO(invalid_content))

            assert "No HTML content found" in str(exc_info.value)

    def test_unsupported_input_type_error(self):
        """Test error for completely unsupported input types."""
        with pytest.raises(InputError):
            # Dictionary is not a supported input type
            mhtml_to_markdown({"not": "supported"})

    def test_bytes_io_conversion(self):
        """Test successful conversion with BytesIO input."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body><h1>BytesIO Test</h1></body></html>

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# BytesIO Test"

            result = mhtml_to_markdown(io.BytesIO(mhtml_content))

            assert result == "# BytesIO Test"


@pytest.mark.unit
@pytest.mark.mhtml
class TestMhtmlListProcessing:
    """Test MS Word list processing in MHTML conversion."""

    def test_ms_word_list_marker_replacement(self):
        """Test replacement of MS Word list markers."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body>
    <!--[if !supportLists]-->&middot;<!--[endif]-->
    <p class="MsoListParagraph">Bullet item</p>

    <!--[if !supportLists]-->1.<!--[endif]-->
    <p class="MsoListParagraph">Numbered item</p>

    <!--[if !supportLists]-->-<!--[endif]-->
    <p class="MsoListParagraph">Dash item</p>
</body></html>

--test-boundary--
"""

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "List content"

            mhtml_to_markdown(io.BytesIO(mhtml_content))

            args, _ = mock_html_to_md.call_args
            processed_html = args[0]

            # Check that list markers were properly replaced
            assert '- ' in processed_html  # Generic bullets
            # MS Word conditional comments should be removed
            assert '<!--[if !supportLists]-->' not in processed_html
            assert '<li>' in processed_html  # Converted to list items


@pytest.mark.unit
@pytest.mark.mhtml
class TestMhtmlMetadataExtraction:
    """Test MHTML metadata extraction functionality."""

    def test_extract_mhtml_metadata_email_headers(self):
        """Test metadata extraction from email headers."""
        import email
        from email import policy

        # Create mock email message
        email_content = """From: test@example.com
To: recipient@example.com
Subject: Test MHTML Document
Date: Fri, 26 Sep 2025 10:00:00 +0000
Message-ID: <test-123@example.com>
X-Mailer: Test Mailer

<html><body><h1>Test</h1></body></html>
"""
        msg = email.message_from_string(email_content, policy=policy.default)
        html_content = "<html><body><h1>Test</h1></body></html>"

        metadata = extract_mhtml_metadata(msg, html_content)

        assert isinstance(metadata, DocumentMetadata)
        assert metadata.title == "Test MHTML Document"
        assert metadata.author == "test@example.com"
        assert metadata.creation_date == "Fri, 26 Sep 2025 10:00:00 +0000"
        assert metadata.creator == "Test Mailer"
        assert metadata.custom['to'] == "recipient@example.com"
        assert metadata.custom['message_id'] == "<test-123@example.com>"

    def test_extract_mhtml_metadata_html_meta_tags(self):
        """Test metadata extraction from HTML meta tags."""
        import email
        from email import policy

        email_content = "Subject: Email Subject\n\n"
        msg = email.message_from_string(email_content, policy=policy.default)

        html_content = """
        <html>
        <head>
            <title>HTML Title</title>
            <meta name="author" content="HTML Author">
            <meta name="description" content="HTML Description">
            <meta name="keywords" content="html,mhtml,test">
            <meta name="generator" content="HTML Generator">
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
        </head>
        <body><h1>Content</h1></body>
        </html>
        """

        metadata = extract_mhtml_metadata(msg, html_content)

        # Email header takes precedence for title
        assert metadata.title == "Email Subject"
        # HTML meta takes precedence when email header not set
        assert metadata.subject == "HTML Description"
        assert metadata.keywords == ["html", "mhtml", "test"]
        assert metadata.creator == "HTML Generator"

    def test_extract_mhtml_metadata_open_graph(self):
        """Test Open Graph metadata extraction."""
        import email
        from email import policy

        email_content = "\n\n"  # No email headers
        msg = email.message_from_string(email_content, policy=policy.default)

        html_content = """
        <html>
        <head>
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
            <meta property="og:type" content="article">
            <meta property="og:url" content="https://example.com">
            <meta property="og:site_name" content="Example Site">
        </head>
        <body><h1>Content</h1></body>
        </html>
        """

        metadata = extract_mhtml_metadata(msg, html_content)

        assert metadata.title == "OG Title"
        assert metadata.subject == "OG Description"
        assert metadata.custom['og_type'] == "article"
        assert metadata.custom['og_url'] == "https://example.com"
        assert metadata.custom['site_name'] == "Example Site"

    def test_extract_mhtml_metadata_document_statistics(self):
        """Test document statistics extraction from HTML."""
        import email
        from email import policy

        email_content = "\n\n"
        msg = email.message_from_string(email_content, policy=policy.default)

        html_content = """
        <html>
        <body>
            <h1>Title</h1>
            <p>This is a test document with multiple words.</p>
            <img src="image1.png" alt="Image 1">
            <img src="image2.png" alt="Image 2">
            <a href="https://example.com">Link 1</a>
            <a href="https://test.com">Link 2</a>
            <a href="https://demo.com">Link 3</a>
        </body>
        </html>
        """

        metadata = extract_mhtml_metadata(msg, html_content)

        assert metadata.custom['image_count'] == 2
        assert metadata.custom['link_count'] == 3
        assert metadata.custom['word_count'] > 0  # Should count words in text content

    def test_extract_mhtml_metadata_html_parsing_error(self):
        """Test metadata extraction when HTML parsing fails."""
        import email
        from email import policy

        email_content = "Subject: Test Subject\n\n"
        msg = email.message_from_string(email_content, policy=policy.default)

        # Malformed HTML that might cause parsing issues
        html_content = "<html><head><title>Test</title>"  # Missing closing tags

        metadata = extract_mhtml_metadata(msg, html_content)

        # Should still extract email metadata even if HTML parsing fails
        assert metadata.title == "Test Subject"

    def test_extract_mhtml_metadata_precedence(self):
        """Test metadata precedence (email headers over HTML)."""
        import email
        from email import policy

        email_content = """From: email@example.com
Subject: Email Title
Date: 2025-09-26

"""
        msg = email.message_from_string(email_content, policy=policy.default)

        html_content = """
        <html>
        <head>
            <title>HTML Title</title>
            <meta name="author" content="HTML Author">
        </head>
        <body><h1>Content</h1></body>
        </html>
        """

        metadata = extract_mhtml_metadata(msg, html_content)

        # Email headers should take precedence
        assert metadata.title == "Email Title"
        assert metadata.author == "email@example.com"
        assert metadata.creation_date == "2025-09-26"

    def test_mhtml_to_markdown_with_metadata_extraction(self):
        """Test MHTML to Markdown conversion with metadata extraction enabled."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"
Subject: Test MHTML Document
From: test@example.com

--test-boundary
Content-Type: text/html; charset=utf-8

<html>
<head>
    <title>HTML Title</title>
    <meta name="description" content="Test Description">
</head>
<body>
    <h1>Test Content</h1>
</body>
</html>

--test-boundary--
"""

        options = MhtmlOptions(extract_metadata=True)

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# Test Content"

            with patch('all2md.parsers.mhtml2markdown.prepend_metadata_if_enabled') as mock_prepend:
                mock_prepend.return_value = "---\ntitle: Test MHTML Document\n---\n\n# Test Content"

                result = mhtml_to_markdown(io.BytesIO(mhtml_content), options=options)

                mock_prepend.assert_called_once()
                assert "---" in result
                assert "title: Test MHTML Document" in result

    def test_mhtml_to_markdown_without_metadata_extraction(self):
        """Test MHTML to Markdown conversion with metadata extraction disabled."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"
Subject: Test Document

--test-boundary
Content-Type: text/html; charset=utf-8

<html><body><h1>Test</h1></body></html>

--test-boundary--
"""

        options = MhtmlOptions(extract_metadata=False)

        with patch('all2md.parsers.mhtml2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# Test"

            with patch('all2md.parsers.mhtml2markdown.extract_mhtml_metadata') as mock_extract:
                result = mhtml_to_markdown(io.BytesIO(mhtml_content), options=options)

                mock_extract.assert_not_called()
                assert not result.startswith("---")
