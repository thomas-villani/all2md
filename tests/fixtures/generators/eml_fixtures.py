"""EML fixture generators using the standard library email package."""

from __future__ import annotations

import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from io import BytesIO
from typing import Iterable

from utils import MINIMAL_PNG_BYTES


def create_simple_email() -> EmailMessage:
    """Create a plain-text email with basic headers."""
    msg = EmailMessage()
    msg["Subject"] = "Project Update"
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg["Date"] = format_datetime(datetime.datetime(2025, 2, 28, 12, 30))
    msg.set_content(
        "Hello Bob,\n\n"
        "Here is the latest update on the project.\n"
        "We completed the integration tests and deployed to staging.\n\n"
        "Regards,\n"
        "Alice\n"
    )
    return msg


def create_email_with_html_and_attachment() -> EmailMessage:
    """Create an email containing both plain text, HTML, and an image attachment."""
    msg = EmailMessage()
    msg["Subject"] = "Release Notes"
    msg["From"] = "releases@example.com"
    msg["To"] = "team@example.com"
    msg["Message-ID"] = make_msgid(domain="example.com")
    msg["Date"] = format_datetime(datetime.datetime(2025, 3, 1, 9, 0))

    text_body = (
        "Team,\n\n"
        "Release 2.3.0 is live. See the HTML body for highlights.\n\n"
        "Thanks,\nRelease Engineering\n"
    )
    html_body = (
        "<html><body>"
        "<h1>Release 2.3.0</h1>"
        "<ul>"
        "  <li><strong>Feature:</strong> New dashboard</li>"
        "  <li><strong>Improvement:</strong> Faster exports</li>"
        "</ul>"
        "<p>Regards,<br>Release Engineering</p>"
        "</body></html>"
    )

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    msg.add_attachment(
        MINIMAL_PNG_BYTES,
        maintype="image",
        subtype="png",
        filename="chart.png",
    )
    return msg


def create_email_with_thread_headers() -> EmailMessage:
    """Create an email representing a reply in a thread with references."""
    msg = EmailMessage()
    msg["Subject"] = "Re: Meeting Follow-up"
    msg["From"] = "carol@example.com"
    msg["To"] = "alice@example.com, bob@example.com"
    msg["Cc"] = "project@example.com"
    msg["In-Reply-To"] = "<initial-message@example.com>"
    msg["References"] = "<initial-message@example.com> <followup@example.com>"
    msg["Date"] = format_datetime(datetime.datetime(2025, 3, 2, 16, 45))

    msg.set_content(
        "Hi team,\n\n"
        "Following up on the action items:\n"
        "- Alice will draft the proposal.\n"
        "- Bob will confirm timelines.\n"
        "- Carol will update stakeholders.\n\n"
        "Thanks!\n"
    )
    return msg


def email_to_bytes(message: EmailMessage) -> bytes:
    """Serialize an EmailMessage to raw bytes."""
    return message.as_bytes()


def email_bytes_io(message: EmailMessage) -> BytesIO:
    """Return a BytesIO stream containing the serialized email."""
    return BytesIO(email_to_bytes(message))


def write_email_to_file(message: EmailMessage, path: str) -> None:
    """Persist an EmailMessage to a file on disk."""
    with open(path, "wb") as handle:
        handle.write(email_to_bytes(message))


def batch_messages() -> Iterable[EmailMessage]:
    """Yield a representative set of email fixtures for parametrized tests."""
    yield create_simple_email()
    yield create_email_with_html_and_attachment()
    yield create_email_with_thread_headers()
