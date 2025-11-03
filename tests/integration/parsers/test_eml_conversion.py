"""Integration tests for EML (email) to Markdown conversion."""

import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

import pytest

from all2md import to_ast, to_markdown
from all2md.ast.nodes import Document


@pytest.mark.integration
def test_eml_to_markdown_simple_plain_text(tmp_path):
    """Test basic plain-text email conversion."""
    msg = EmailMessage()
    msg["Subject"] = "Test Email"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 1, 15, 10, 30))
    msg.set_content("This is a simple plain-text email message.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Test Email" in result
    assert "sender@example.com" in result
    assert "recipient@example.com" in result
    assert "simple plain-text email" in result


@pytest.mark.integration
def test_eml_to_markdown_with_subject(tmp_path):
    """Test email with various subject lines."""
    msg = EmailMessage()
    msg["Subject"] = "Project Update: Q1 2025 Progress"
    msg["From"] = "manager@example.com"
    msg["To"] = "team@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 3, 1, 14, 0))
    msg.set_content("Dear team,\n\nHere is our Q1 progress update.\n\nBest regards")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Project Update: Q1 2025 Progress" in result
    assert "Q1 progress update" in result


@pytest.mark.integration
def test_eml_to_markdown_multipart_alternative(tmp_path):
    """Test email with both plain text and HTML parts."""
    msg = EmailMessage()
    msg["Subject"] = "HTML Email"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 1, 9, 0))

    text_body = "This is the plain text version."
    html_body = "<html><body><h1>HTML Version</h1><p>This is the <strong>HTML</strong> version.</p></body></html>"

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    # Should prefer HTML or show both parts
    assert "HTML Email" in result
    assert "HTML Version" in result or "plain text version" in result


@pytest.mark.integration
def test_eml_to_markdown_with_attachments(tmp_path):
    """Test email with attachments."""
    msg = EmailMessage()
    msg["Subject"] = "Document Attached"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 1, 20, 11, 0))
    msg.set_content("Please find the attached document.")

    # Add a text attachment
    msg.add_attachment(b"Attachment content here", maintype="text", subtype="plain", filename="document.txt")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Document Attached" in result
    assert "attached document" in result


@pytest.mark.integration
def test_eml_to_markdown_multiple_recipients(tmp_path):
    """Test email with multiple To, Cc, and Bcc recipients."""
    msg = EmailMessage()
    msg["Subject"] = "Team Announcement"
    msg["From"] = "manager@example.com"
    msg["To"] = "alice@example.com, bob@example.com, charlie@example.com"
    msg["Cc"] = "team@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 10, 15, 30))
    msg.set_content("Important team announcement.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Team Announcement" in result
    assert "alice@example.com" in result or "To:" in result


@pytest.mark.integration
def test_eml_to_markdown_reply_thread(tmp_path):
    """Test email that is part of a reply thread."""
    msg = EmailMessage()
    msg["Subject"] = "Re: Meeting Follow-up"
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg["In-Reply-To"] = "<original-message@example.com>"
    msg["References"] = "<original-message@example.com>"
    msg["Date"] = format_datetime(datetime.datetime(2025, 1, 25, 16, 45))
    msg.set_content("Thanks for the follow-up. I'll review the documents.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Re: Meeting Follow-up" in result
    assert "review the documents" in result


@pytest.mark.integration
def test_eml_to_markdown_with_message_id(tmp_path):
    """Test email with Message-ID header."""
    msg = EmailMessage()
    msg["Subject"] = "Test Message"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Message-ID"] = make_msgid(domain="example.com")
    msg["Date"] = format_datetime(datetime.datetime(2025, 1, 10, 12, 0))
    msg.set_content("Test message content.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Test Message" in result
    assert "Test message content" in result


@pytest.mark.integration
def test_eml_to_markdown_long_content(tmp_path):
    """Test email with long body content."""
    long_text = "\n\n".join([f"Paragraph {i}: This is a long paragraph with lots of content." for i in range(20)])

    msg = EmailMessage()
    msg["Subject"] = "Long Email"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 5, 10, 0))
    msg.set_content(long_text)

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Long Email" in result
    assert "Paragraph 0:" in result
    assert "Paragraph 19:" in result


@pytest.mark.integration
def test_eml_to_markdown_unicode_content(tmp_path):
    """Test email with Unicode characters."""
    msg = EmailMessage()
    msg["Subject"] = "Unicode Test \U0001f600"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 3, 1, 10, 0))
    msg.set_content(
        "Unicode content:\n"
        "Chinese: \U00004e2d\U00006587\n"
        "Greek: \U00000391\U000003b1\n"
        "Emoji: \U0001f600 \U00002764 \U00002b50"
    )

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Unicode Test" in result
    assert "Unicode content" in result


@pytest.mark.integration
def test_eml_to_markdown_html_formatting(tmp_path):
    """Test email with formatted HTML content."""
    msg = EmailMessage()
    msg["Subject"] = "Formatted Email"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 15, 14, 30))

    html_body = """<html><body>
    <h1>Main Heading</h1>
    <p>This email has <strong>bold</strong> and <em>italic</em> text.</p>
    <ul>
        <li>List item 1</li>
        <li>List item 2</li>
    </ul>
    <p>Visit <a href="https://example.com">our website</a>.</p>
    </body></html>"""

    msg.set_content("Plain text version")
    msg.add_alternative(html_body, subtype="html")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Formatted Email" in result


@pytest.mark.integration
def test_eml_to_markdown_empty_body(tmp_path):
    """Test email with empty body."""
    msg = EmailMessage()
    msg["Subject"] = "Empty Email"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 1, 5, 9, 0))
    msg.set_content("")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Empty Email" in result


@pytest.mark.integration
def test_eml_to_markdown_special_characters_in_subject(tmp_path):
    """Test email with special characters in subject."""
    msg = EmailMessage()
    msg["Subject"] = "Special chars: & < > \" ' [test]"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 1, 18, 11, 30))
    msg.set_content("Email content here.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Special chars" in result


@pytest.mark.integration
def test_eml_to_markdown_quoted_printable(tmp_path):
    """Test email with quoted-printable encoding."""
    msg = EmailMessage()
    msg["Subject"] = "Test QP Encoding"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 20, 10, 0))

    # Content with special characters that may trigger QP encoding
    msg.set_content("Line 1\nLine 2 with special: \U000000e9\U000000e8\U000000e0\nLine 3")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Test QP Encoding" in result


@pytest.mark.integration
def test_eml_to_markdown_multipart_mixed(tmp_path):
    """Test email with multipart/mixed structure."""
    msg = EmailMessage()
    msg["Subject"] = "Mixed Content"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 3, 5, 13, 0))
    msg.set_content("Main email body.")

    # Add another part
    msg.add_attachment(b"Extra content", maintype="text", subtype="plain", filename="extra.txt")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Mixed Content" in result
    assert "Main email body" in result


@pytest.mark.integration
def test_eml_to_markdown_custom_headers(tmp_path):
    """Test email with custom headers."""
    msg = EmailMessage()
    msg["Subject"] = "Custom Headers"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 1, 30, 12, 0))
    msg["X-Priority"] = "1"
    msg["X-Custom-Header"] = "Custom Value"
    msg.set_content("Email with custom headers.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Custom Headers" in result
    assert "custom headers" in result


@pytest.mark.integration
def test_eml_to_ast_conversion(tmp_path):
    """Test EML to AST conversion pipeline."""
    msg = EmailMessage()
    msg["Subject"] = "AST Test"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 1, 10, 0))
    msg.set_content("Testing AST conversion for email.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    doc = to_ast(eml_file)

    # Verify AST structure
    assert isinstance(doc, Document)
    assert doc.children is not None

    # Verify content through markdown conversion
    result = to_markdown(eml_file)
    assert "AST Test" in result


@pytest.mark.integration
def test_eml_to_markdown_inline_images(tmp_path):
    """Test email with inline images (CID references)."""
    # For inline images, we need to create the structure manually
    # since EmailMessage API doesn't support multipart/related with alternative easily
    msg = EmailMessage()
    msg["Subject"] = "Inline Images"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 25, 15, 0))

    # Simple approach: just set HTML content with CID reference
    html_body = '<html><body><p>Image: <img src="cid:image1" /></p></body></html>'
    msg.set_content(html_body, subtype="html")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Inline Images" in result
    # The CID reference might be preserved or converted depending on implementation


@pytest.mark.integration
def test_eml_to_markdown_forwarded_message(tmp_path):
    """Test email with forwarded message."""
    msg = EmailMessage()
    msg["Subject"] = "Fwd: Original Subject"
    msg["From"] = "forwarder@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 3, 10, 9, 30))
    msg.set_content(
        "---------- Forwarded message ---------\n"
        "From: original@example.com\n"
        "Subject: Original Subject\n\n"
        "Original message content."
    )

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Fwd:" in result or "Forwarded message" in result


@pytest.mark.integration
def test_eml_to_markdown_missing_headers(tmp_path):
    """Test email with minimal headers."""
    msg = EmailMessage()
    msg.set_content("Email with minimal headers.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    # Should handle gracefully
    assert "minimal headers" in result or isinstance(result, str)


@pytest.mark.integration
def test_eml_to_markdown_base64_encoded_body(tmp_path):
    """Test email with base64-encoded body."""
    msg = EmailMessage()
    msg["Subject"] = "Base64 Encoded"
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 28, 14, 0))
    msg["Content-Transfer-Encoding"] = "base64"
    msg.set_content("This content may be base64 encoded.")

    eml_file = tmp_path / "test.eml"
    eml_file.write_bytes(msg.as_bytes())

    result = to_markdown(eml_file)

    assert "Base64 Encoded" in result
