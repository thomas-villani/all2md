"""Advanced tests for EML multipart message handling."""

import email
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO

from utils import MINIMAL_PNG_BYTES, assert_markdown_valid

from all2md import EmlOptions, to_markdown as eml_to_markdown


class TestEmlMultipart:
    """Test complex multipart email scenarios."""

    def test_multipart_alternative_html_plain(self):
        """Test multipart/alternative with both HTML and plain text."""
        msg = MIMEMultipart('alternative')
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Multipart Alternative Test'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Plain text part
        plain_text = "This is the plain text version.\nWith multiple lines."
        text_part = MIMEText(plain_text, 'plain')
        msg.attach(text_part)

        # HTML part
        html_content = '''
        <html>
        <body>
            <h1>HTML Version</h1>
            <p>This is the <strong>HTML</strong> version with <em>formatting</em>.</p>
            <ul>
                <li>List item 1</li>
                <li>List item 2</li>
            </ul>
        </body>
        </html>
        '''
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should prefer HTML content or gracefully handle both
        assert "sender@example.com" in result
        assert "Multipart Alternative Test" in result
        # Content should include either plain or HTML version
        assert "plain text version" in result or "HTML Version" in result

    def test_multipart_mixed_with_attachments(self):
        """Test multipart/mixed with text content and attachments."""
        msg = MIMEMultipart('mixed')
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Email with Attachments'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Text content
        text_part = MIMEText('Please find the attached documents.', 'plain')
        msg.attach(text_part)

        # Image attachment
        img_part = MIMEImage(MINIMAL_PNG_BYTES)
        img_part.add_header('Content-Disposition', 'attachment; filename="image.png"')
        msg.attach(img_part)

        # Document attachment
        doc_content = b"This is a fake document content for testing."
        doc_part = MIMEApplication(doc_content, _subtype='pdf')
        doc_part.add_header('Content-Disposition', 'attachment; filename="document.pdf"')
        msg.attach(doc_part)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should contain main text
        assert "attached documents" in result
        assert "Email with Attachments" in result

        # Attachment handling depends on options and implementation

    def test_multipart_related_with_inline_images(self):
        """Test multipart/related with inline images."""
        msg = MIMEMultipart('related')
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Inline Images Test'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # HTML content referencing inline image
        html_content = '''
        <html>
        <body>
            <h1>Newsletter</h1>
            <p>Check out our logo:</p>
            <img src="cid:logo" alt="Company Logo" />
            <p>Isn't it nice?</p>
        </body>
        </html>
        '''
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        # Inline image with Content-ID
        img_part = MIMEImage(MINIMAL_PNG_BYTES)
        img_part.add_header('Content-ID', '<logo>')
        msg.attach(img_part)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should contain HTML content or processed version
        assert "Newsletter" in result
        assert "Company Logo" in result or "logo" in result
        assert "nice" in result

    def test_deeply_nested_multipart(self):
        """Test deeply nested multipart structure."""
        # Outer multipart/mixed
        outer_msg = MIMEMultipart('mixed')
        outer_msg['From'] = 'complex@example.com'
        outer_msg['To'] = 'recipient@example.com'
        outer_msg['Subject'] = 'Complex Nested Structure'
        outer_msg['Date'] = email.utils.formatdate(localtime=True)

        # Inner multipart/alternative
        inner_alternative = MIMEMultipart('alternative')

        # Plain text version
        plain_part = MIMEText('This is the plain text version of the nested content.', 'plain')
        inner_alternative.attach(plain_part)

        # HTML version
        html_part = MIMEText(
            '<html><body><p>This is the <strong>HTML version</strong> of nested content.</p></body></html>', 'html')
        inner_alternative.attach(html_part)

        # Attach inner alternative to outer
        outer_msg.attach(inner_alternative)

        # Add attachment to outer
        attachment = MIMEText('Attachment content here.', 'plain')
        attachment.add_header('Content-Disposition', 'attachment; filename="notes.txt"')
        outer_msg.attach(attachment)

        eml_content = outer_msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should handle nested structure
        assert "Complex Nested Structure" in result
        assert "nested content" in result

    def test_multipart_with_calendar_invite(self):
        """Test multipart message with calendar invitation."""
        msg = MIMEMultipart('mixed')
        msg['From'] = 'organizer@example.com'
        msg['To'] = 'attendee@example.com'
        msg['Subject'] = 'Meeting Invitation'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Text description
        text_part = MIMEText('You are invited to a meeting. Please see the calendar invitation.', 'plain')
        msg.attach(text_part)

        # Calendar invitation (simplified)
        cal_content = '''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
DTSTART:20231201T140000Z
DTEND:20231201T150000Z
SUMMARY:Team Meeting
DESCRIPTION:Weekly team sync meeting
LOCATION:Conference Room A
ORGANIZER:organizer@example.com
ATTENDEE:attendee@example.com
END:VEVENT
END:VCALENDAR'''

        cal_part = MIMEText(cal_content, 'calendar')
        cal_part.add_header('Content-Disposition', 'attachment; filename="meeting.ics"')
        msg.attach(cal_part)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should contain invitation text
        assert "Meeting Invitation" in result
        assert "invited to a meeting" in result

    def test_multipart_with_encrypted_content(self):
        """Test multipart message with encrypted/signed content simulation."""
        msg = MIMEMultipart('signed', protocol="application/pgp-signature")
        msg['From'] = 'secure@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Signed Message'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Message content
        text_part = MIMEText('This message is digitally signed for authenticity.', 'plain')
        msg.attach(text_part)

        # Signature part (simulated)
        sig_content = '''-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQEcBAEBAgAGBQJExample...
[Simulated PGP signature content]
-----END PGP SIGNATURE-----'''

        sig_part = MIMEApplication(sig_content.encode(), _subtype='pgp-signature')
        sig_part.add_header('Content-Disposition', 'attachment; filename="signature.asc"')
        msg.attach(sig_part)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should contain main message content
        assert "Signed Message" in result
        assert "digitally signed" in result

    def test_multipart_with_large_attachments(self):
        """Test multipart message with large attachments."""
        msg = MIMEMultipart('mixed')
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Large Files Attached'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Brief text
        text_part = MIMEText('Large files attached.', 'plain')
        msg.attach(text_part)

        # Simulate large attachment with truncated content
        large_content = b"Large file content " * 1000  # Simulate large file
        large_part = MIMEApplication(large_content, _subtype='zip')
        large_part.add_header('Content-Disposition', 'attachment; filename="archive.zip"')
        msg.attach(large_part)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should handle large attachments gracefully
        assert "Large Files Attached" in result
        assert "Large files attached" in result

    def test_multipart_with_forwarded_message(self):
        """Test multipart containing forwarded message."""
        msg = MIMEMultipart('mixed')
        msg['From'] = 'forwarder@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Fwd: Original Message'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Forwarding comment
        text_part = MIMEText('Please see the forwarded message below.', 'plain')
        msg.attach(text_part)

        # Original message as attachment
        original_msg = MIMEText('''From: original@example.com
To: forwarder@example.com
Subject: Original Message
Date: Thu, 30 Nov 2023 10:00:00 +0000

This was the original message content.
It had multiple lines and some important information.''', 'plain')

        original_msg.add_header('Content-Disposition', 'attachment; filename="original.eml"')
        msg.attach(original_msg)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should contain forwarding info and original content
        assert "Fwd: Original Message" in result
        assert "forwarded message" in result
        # Original content might be included depending on implementation

    def test_multipart_with_delivery_reports(self):
        """Test multipart with delivery status notifications."""
        msg = MIMEMultipart('report', report_type="delivery-status")
        msg['From'] = 'mailer-daemon@example.com'
        msg['To'] = 'sender@example.com'
        msg['Subject'] = 'Delivery Status Notification'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Human readable part
        text_part = MIMEText('''This is a delivery status notification.

The following message was successfully delivered:
  To: recipient@example.com
  Subject: Test Message
  Date: Thu, 30 Nov 2023 09:30:00 +0000''', 'plain')
        msg.attach(text_part)

        # Machine readable part - delivery status reports should be text/plain
        # The message/delivery-status type causes issues with Python's email generator
        # since it expects Message objects, not text content
        status_part = MIMEText('''Reporting-MTA: dns; mail.example.com
Final-Recipient: rfc822;recipient@example.com
Action: delivered
Status: 2.0.0
Diagnostic-Code: smtp; 250 OK''', 'plain')
        msg.attach(status_part)

        eml_content = msg.as_string()
        result = eml_to_markdown(BytesIO(eml_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should contain delivery notification info
        assert "Delivery Status Notification" in result
        assert "successfully delivered" in result

    def test_malformed_multipart_boundaries(self):
        """Test handling of malformed multipart boundaries."""
        # Manually construct malformed multipart message
        malformed_content = '''From: test@example.com
To: recipient@example.com
Subject: Malformed Multipart
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

This is the first part.

--boundary123
Content-Type: text/plain

This is the second part.

--boundary123--
Extra content after boundary end.
'''

        result = eml_to_markdown(BytesIO(malformed_content.encode('utf-8')))
        assert_markdown_valid(result)

        # Should handle malformed structure gracefully
        assert "Malformed Multipart" in result
        # Content extraction depends on parser robustness

    def test_multipart_attachment_options(self):
        """Test different attachment handling options."""
        msg = MIMEMultipart('mixed')
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'
        msg['Subject'] = 'Attachment Options Test'
        msg['Date'] = email.utils.formatdate(localtime=True)

        # Main text
        text_part = MIMEText('Message with attachment.', 'plain')
        msg.attach(text_part)

        # Image attachment
        img_part = MIMEImage(MINIMAL_PNG_BYTES)
        img_part.add_header('Content-Disposition', 'attachment; filename="test.png"')
        msg.attach(img_part)

        eml_content = msg.as_string()

        # Test different attachment modes
        options_skip = EmlOptions(attachment_mode="skip")
        result_skip = eml_to_markdown(BytesIO(eml_content.encode('utf-8')), parser_options=options_skip)
        assert_markdown_valid(result_skip)

        options_alt = EmlOptions(attachment_mode="alt_text")
        result_alt = eml_to_markdown(BytesIO(eml_content.encode('utf-8')), parser_options=options_alt)
        assert_markdown_valid(result_alt)

        # Both should contain main text
        assert "Message with attachment" in result_skip
        assert "Message with attachment" in result_alt

        # Attachment handling should differ based on options
