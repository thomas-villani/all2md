"""MBOX fixture generators for testing mailbox archive conversion.

This module provides functions to programmatically create MBOX mailbox
archives for testing various aspects of mailbox-to-Markdown conversion.
"""

from __future__ import annotations

import datetime
import mailbox
import tempfile
from email.utils import format_datetime
from pathlib import Path
from typing import Iterable


def create_simple_mbox() -> mailbox.mbox:
    """Create a simple mbox with 3 messages for basic testing.

    Returns
    -------
    mailbox.mbox
        MBOX mailbox with 3 simple messages

    """
    # Create temp mbox file
    tmp_file = tempfile.NamedTemporaryFile(suffix=".mbox", delete=False)
    tmp_file.close()

    mbox = mailbox.mbox(tmp_file.name)

    # Message 1
    msg1 = mailbox.mboxMessage()
    msg1["Subject"] = "Welcome to the Team"
    msg1["From"] = "hr@company.com"
    msg1["To"] = "newemployee@company.com"
    msg1["Date"] = format_datetime(datetime.datetime(2024, 1, 15, 9, 0, tzinfo=datetime.timezone.utc))
    msg1.set_payload(
        "Welcome to the team!\n\n"
        "We're excited to have you join us. Your first day is Monday.\n\n"
        "Best regards,\nHR Team"
    )
    mbox.add(msg1)

    # Message 2
    msg2 = mailbox.mboxMessage()
    msg2["Subject"] = "Project Kickoff Meeting"
    msg2["From"] = "manager@company.com"
    msg2["To"] = "team@company.com"
    msg2["Cc"] = "stakeholders@company.com"
    msg2["Date"] = format_datetime(datetime.datetime(2024, 2, 10, 14, 30, tzinfo=datetime.timezone.utc))
    msg2.set_payload(
        "Team,\n\n"
        "Let's meet on Friday at 2 PM to kick off the new project.\n"
        "Please review the project brief before the meeting.\n\n"
        "Thanks,\nProject Manager"
    )
    mbox.add(msg2)

    # Message 3
    msg3 = mailbox.mboxMessage()
    msg3["Subject"] = "Quarterly Review Results"
    msg3["From"] = "ceo@company.com"
    msg3["To"] = "all@company.com"
    msg3["Date"] = format_datetime(datetime.datetime(2024, 3, 31, 17, 0, tzinfo=datetime.timezone.utc))
    msg3.set_payload(
        "Team,\n\n"
        "Great work this quarter! Revenue is up 25%.\n"
        "We exceeded all our KPIs and delivered ahead of schedule.\n\n"
        "Thank you all for your hard work!\n\nCEO"
    )
    mbox.add(msg3)

    mbox.close()
    return mbox


def create_mbox_with_thread() -> mailbox.mbox:
    """Create an mbox with a threaded conversation for testing thread detection.

    Returns
    -------
    mailbox.mbox
        MBOX mailbox with threaded messages

    """
    tmp_file = tempfile.NamedTemporaryFile(suffix=".mbox", delete=False)
    tmp_file.close()

    mbox = mailbox.mbox(tmp_file.name)

    # Original message
    msg1 = mailbox.mboxMessage()
    msg1["Subject"] = "Bug in Production"
    msg1["From"] = "qa@company.com"
    msg1["To"] = "dev@company.com"
    msg1["Message-ID"] = "<bug-report-001@company.com>"
    msg1["Date"] = format_datetime(datetime.datetime(2024, 6, 1, 10, 0, tzinfo=datetime.timezone.utc))
    msg1.set_payload(
        "Team,\n\n"
        "We found a critical bug in the payment flow.\n"
        "Users cannot complete checkout.\n\n"
        "QA Team"
    )
    mbox.add(msg1)

    # Reply 1
    msg2 = mailbox.mboxMessage()
    msg2["Subject"] = "Re: Bug in Production"
    msg2["From"] = "dev1@company.com"
    msg2["To"] = "qa@company.com"
    msg2["Cc"] = "dev@company.com"
    msg2["Message-ID"] = "<reply-001@company.com>"
    msg2["In-Reply-To"] = "<bug-report-001@company.com>"
    msg2["References"] = "<bug-report-001@company.com>"
    msg2["Date"] = format_datetime(datetime.datetime(2024, 6, 1, 10, 30, tzinfo=datetime.timezone.utc))
    msg2.set_payload(
        "Looking into it now. Will have a fix in 30 minutes.\n\n"
        "On Sat, Jun 1, 2024 at 10:00 AM qa@company.com wrote:\n"
        "> Team,\n"
        "> We found a critical bug in the payment flow.\n"
        "> Users cannot complete checkout.\n"
    )
    mbox.add(msg2)

    # Reply 2
    msg3 = mailbox.mboxMessage()
    msg3["Subject"] = "Re: Bug in Production"
    msg3["From"] = "dev1@company.com"
    msg3["To"] = "qa@company.com"
    msg3["Cc"] = "dev@company.com"
    msg3["Message-ID"] = "<reply-002@company.com>"
    msg3["In-Reply-To"] = "<reply-001@company.com>"
    msg3["References"] = "<bug-report-001@company.com> <reply-001@company.com>"
    msg3["Date"] = format_datetime(datetime.datetime(2024, 6, 1, 11, 0, tzinfo=datetime.timezone.utc))
    msg3.set_payload("Fix deployed. Please verify.\n\nThanks!")
    mbox.add(msg3)

    mbox.close()
    return mbox


def create_maildir() -> mailbox.Maildir:
    """Create a maildir with messages in different folders.

    Returns
    -------
    mailbox.Maildir
        Maildir with messages in multiple folders

    """
    tmp_dir = tempfile.mkdtemp(suffix="_maildir")
    maildir_path = Path(tmp_dir)

    md = mailbox.Maildir(str(maildir_path))

    # Message in main folder
    msg1 = mailbox.MaildirMessage()
    msg1["Subject"] = "Inbox Message"
    msg1["From"] = "sender@example.com"
    msg1["To"] = "recipient@example.com"
    msg1["Date"] = format_datetime(datetime.datetime(2024, 4, 1, 12, 0, tzinfo=datetime.timezone.utc))
    msg1.set_payload("This is a message in the inbox folder.")
    md.add(msg1)

    # Create "Sent" subfolder
    try:
        sent_folder = md.add_folder("Sent")

        msg2 = mailbox.MaildirMessage()
        msg2["Subject"] = "Sent Message"
        msg2["From"] = "recipient@example.com"
        msg2["To"] = "sender@example.com"
        msg2["Date"] = format_datetime(datetime.datetime(2024, 4, 2, 12, 0, tzinfo=datetime.timezone.utc))
        msg2.set_payload("This is a message in the sent folder.")
        sent_folder.add(msg2)
    except Exception:
        # Folder creation might fail on some platforms
        pass

    md.close()
    return md


def write_mbox_to_file(mbox: mailbox.mbox, path: str) -> None:
    """Write an mbox to a file on disk.

    Parameters
    ----------
    mbox : mailbox.mbox
        Mailbox to write
    path : str
        Destination file path

    """
    # Get the temp file path from the mbox
    import shutil
    shutil.copy(mbox._path, path)


def batch_mboxes() -> Iterable[mailbox.mbox]:
    """Yield a representative set of mbox fixtures for parametrized tests.

    Yields
    ------
    mailbox.mbox
        Various mbox fixtures

    """
    yield create_simple_mbox()
    yield create_mbox_with_thread()
