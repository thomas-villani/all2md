"""Outlook (MSG) fixture generators for testing Outlook file conversion.

This module provides functions to programmatically create Outlook MSG files
for testing. PST/OST files are not generated programmatically due to complexity,
and should be tested with real sample files when pypff is available.

Note: This requires extract-msg to be installed for MSG file creation.
"""

from __future__ import annotations

import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Iterable

from tests.utils import MINIMAL_PNG_BYTES


def create_simple_msg_data() -> dict:
    """Create simple MSG data for testing.

    Returns
    -------
    dict
        Dictionary with MSG message data

    Notes
    -----
    Since creating actual MSG files programmatically is complex and requires
    Windows-specific libraries, we provide test data that can be used to
    create EmailMessage objects for testing the conversion logic.

    """
    return {
        "subject": "Important Project Update",
        "from": "alice@company.com",
        "to": "bob@company.com",
        "date": datetime.datetime(2024, 5, 15, 14, 30, tzinfo=datetime.timezone.utc),
        "body": (
            "Hi Bob,\n\n"
            "Just wanted to update you on the project status.\n"
            "We're on track for the Q2 release.\n\n"
            "Key accomplishments:\n"
            "- Completed user testing\n"
            "- Fixed all critical bugs\n"
            "- Updated documentation\n\n"
            "Let me know if you have any questions.\n\n"
            "Best regards,\nAlice"
        ),
    }


def create_msg_with_attachments_data() -> dict:
    """Create MSG data with attachment information.

    Returns
    -------
    dict
        Dictionary with MSG message data including attachments

    """
    return {
        "subject": "Q2 Report - Please Review",
        "from": "finance@company.com",
        "to": "executives@company.com",
        "cc": "managers@company.com",
        "date": datetime.datetime(2024, 6, 30, 16, 0, tzinfo=datetime.timezone.utc),
        "body": (
            "Dear Executives,\n\n"
            "Please find attached the Q2 financial report.\n\n"
            "Highlights:\n"
            "- Revenue: $5.2M (+15% YoY)\n"
            "- Profit: $1.8M (+20% YoY)\n"
            "- Customer growth: 2,500 new customers\n\n"
            "Please review and let us know if you have questions.\n\n"
            "Finance Team"
        ),
        "attachments": [{"filename": "q2-report.png", "data": MINIMAL_PNG_BYTES, "content_type": "image/png"}],
    }


def create_msg_with_html_data() -> dict:
    """Create MSG data with HTML body.

    Returns
    -------
    dict
        Dictionary with MSG message data including HTML

    """
    return {
        "subject": "Newsletter - June 2024",
        "from": "marketing@company.com",
        "to": "subscribers@company.com",
        "date": datetime.datetime(2024, 6, 1, 9, 0, tzinfo=datetime.timezone.utc),
        "body_text": "View the newsletter in your email client.",
        "body_html": (
            "<html><body>"
            "<h1>June Newsletter</h1>"
            "<h2>Product Updates</h2>"
            "<ul>"
            "  <li><strong>New Feature:</strong> Dark mode is now available!</li>"
            "  <li><strong>Improvement:</strong> 50% faster page loads</li>"
            "  <li><strong>Bug Fix:</strong> Resolved login issues</li>"
            "</ul>"
            "<h2>Upcoming Events</h2>"
            "<p>Join us for our webinar on July 15th at 2 PM.</p>"
            "<p>Thanks for being a subscriber!</p>"
            "</body></html>"
        ),
    }


def msg_data_to_email_message(data: dict) -> EmailMessage:
    """Convert MSG data dictionary to EmailMessage for testing.

    Parameters
    ----------
    data : dict
        MSG data dictionary from create_*_msg_data functions

    Returns
    -------
    EmailMessage
        Email message object for testing

    """
    msg = EmailMessage()

    # Set headers
    if "subject" in data:
        msg["Subject"] = data["subject"]
    if "from" in data:
        msg["From"] = data["from"]
    if "to" in data:
        msg["To"] = data["to"]
    if "cc" in data:
        msg["Cc"] = data["cc"]
    if "date" in data:
        msg["Date"] = format_datetime(data["date"])

    # Set body
    if "body_html" in data:
        # HTML body
        if "body_text" in data:
            msg.set_content(data["body_text"])
            msg.add_alternative(data["body_html"], subtype="html")
        else:
            msg.set_content(data["body_html"], subtype="html")
    elif "body" in data:
        # Plain text body
        msg.set_content(data["body"])

    # Add attachments
    if "attachments" in data:
        for att in data["attachments"]:
            if att["content_type"].startswith("image/"):
                msg.add_attachment(
                    att["data"],
                    maintype="image",
                    subtype=att["content_type"].split("/")[1],
                    filename=att["filename"],
                )
            else:
                msg.add_attachment(
                    att["data"],
                    maintype="application",
                    subtype="octet-stream",
                    filename=att["filename"],
                )

    return msg


def write_email_as_eml(msg: EmailMessage, path: str) -> None:
    """Write an EmailMessage to an EML file.

    Parameters
    ----------
    msg : EmailMessage
        Email message to write
    path : str
        Destination file path

    Notes
    -----
    This creates an EML file, not a real MSG file. For MSG file testing,
    use real MSG sample files or the extract-msg library.

    """
    with open(path, "wb") as f:
        f.write(msg.as_bytes())


def batch_msg_data() -> Iterable[dict]:
    """Yield a representative set of MSG data for parametrized tests.

    Yields
    ------
    dict
        Various MSG data dictionaries

    """
    yield create_simple_msg_data()
    yield create_msg_with_attachments_data()
    yield create_msg_with_html_data()


# Note: Creating actual PST/OST files programmatically is extremely complex
# and typically requires Windows-specific APIs. For PST/OST testing:
# 1. Use small sample PST files from public sources
# 2. Test with pypff when available (skip tests if not installed)
# 3. Focus on the parser logic rather than file generation


def create_pst_test_note() -> str:
    """Return a note about PST file testing.

    Returns
    -------
    str
        Instructions for PST testing

    """
    return """
    PST/OST File Testing Notes:
    ===========================

    Creating PST/OST files programmatically is not practical because:
    1. Requires Windows-specific MAPI libraries
    2. Complex binary format (hundreds of pages of specification)
    3. pypff is read-only (cannot create PST files)

    For PST/OST testing:
    1. Use small real sample files (< 1MB)
    2. Skip tests when pypff is not installed
    3. Test with mock data when appropriate
    4. Focus on testing the parser logic with EmailMessage objects

    Example PST test sources:
    - Create a small PST manually in Outlook
    - Use publicly available sample PST files
    - Generate from MBOX using readpst --convert-to-pst (if available)
    """
