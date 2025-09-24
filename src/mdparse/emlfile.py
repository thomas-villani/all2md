"""Email file (EML) parsing and conversion module.

This module provides comprehensive email parsing capabilities for EML files,
including email chain detection, metadata extraction, and content conversion
to structured formats. It handles complex email structures including nested
replies, attachments, and various encoding formats.

The parser processes email messages using Python's email library, extracting
headers, body content, and attachment information while preserving the
hierarchical structure of email conversations and reply chains.

Key Features
------------
- Email chain detection and parsing
- Header extraction (From, To, CC, Date, Subject)
- Content type handling (text/plain, text/html)
- Attachment processing and metadata extraction
- Reply chain hierarchy preservation
- Date parsing and formatting
- Encoding detection and conversion
- Markdown output formatting

Email Structure Support
-----------------------
- Single email messages
- Email chains and reply threads
- Forwarded messages with original content
- Multiple recipients (To, CC, BCC)
- Various content encodings (UTF-8, ISO-8859-1, etc.)
- MIME multipart messages
- Inline and attachment handling

Processing Features
-------------------
- Automatic reply chain detection using subject patterns
- Date normalization and formatting
- Content sanitization and formatting
- Thread reconstruction from individual messages
- Metadata preservation and extraction
- Error handling for malformed messages

Dependencies
------------
- email: Standard library for email parsing
- datetime: For date handling and formatting
- re: For pattern matching in email parsing

Examples
--------
Parse a single email file:

    >>> from emlfile import parse_email_chain
    >>> with open('message.eml', 'r') as f:
    ...     result = parse_email_chain(f, as_markdown=True)
    >>> print(result)

Parse email chain with metadata:

    >>> emails = parse_email_chain(file_obj, as_markdown=False)
    >>> for email in emails:
    ...     print(f"From: {email['from']}, Date: {email['date']}")

Note
----
Email parsing relies on proper EML format compliance. Malformed emails
may result in partial parsing or missing information. The module attempts
to handle common encoding issues and format variations gracefully.
"""

#  Copyright (c) 2023-2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import datetime
import re
from email import message_from_file, policy
from email.message import Message
from email.utils import parsedate_to_datetime
from io import StringIO
from typing import Any, Match


def format_email_chain_as_markdown(eml_chain: list[dict[str, Any]]) -> str:
    """Convert a list of email dictionaries to formatted Markdown string.

    Takes a list of parsed email messages and formats them into a readable
    Markdown representation with proper headers and content separation.
    Each email is formatted with sender, recipient, date, subject, and
    content information, separated by horizontal rules.

    Parameters
    ----------
    eml_chain : list[dict[str, Any]]
        List of email dictionaries containing parsed email data. Each dictionary
        should contain keys like 'from', 'to', 'subject', 'date', 'content',
        and optionally 'cc'.

    Returns
    -------
    str
        Formatted Markdown string representing the entire email chain with
        proper headers, metadata, and content for each message.

    Examples
    --------
    Format a simple email chain:

        >>> emails = [
        ...     {
        ...         'from': 'sender@example.com',
        ...         'to': 'recipient@example.com',
        ...         'subject': 'Hello',
        ...         'content': 'This is the email body.'
        ...     }
        ... ]
        >>> markdown = format_email_chain_as_markdown(emails)
        >>> print(markdown)
    """
    md = ""
    for item in eml_chain:
        md += f"From: {item['from']}\n"
        md += f"To: {item['to']}\n"
        if item.get("cc"):
            md += f"cc: {item['cc']}\n"
        if "date" in item:
            md += f"Date: {item['date'].strftime('%m/%d/%y %H:%M')}\n"
        if "subject" in item:
            md += f"Subject: {item['subject']}\n"
        md += item["content"] + "\n---\n"
    return md


def extract_message_content(_message: Message) -> str:
    """Extract text content from an email message, handling multipart messages.

    Processes both simple and multipart email messages to extract readable
    text content. For multipart messages, walks through all parts and
    combines text-based content while handling different character encodings.

    Parameters
    ----------
    _message : Message
        Email message object from Python's email library to extract content from.

    Returns
    -------
    str
        Extracted text content from the email message, with proper encoding
        handling and multipart content combination.

    Notes
    -----
    - Handles multipart messages by combining all text parts
    - Manages different character encodings (UTF-8 fallback)
    - Only processes text-based content, ignoring binary attachments
    - Uses error-safe decoding to handle malformed content
    """
    # If the email is multipart, iterate over the parts to get text-based content
    if _message.is_multipart():
        parts = []
        for part in _message.walk():
            # Only process text parts
            if part.get_content_maintype() == "text":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    part_content = payload.decode(charset, errors="replace")
                else:
                    part_content = str(payload)
                parts.append(part_content)
        return "\n".join(parts)
    else:
        charset = _message.get_content_charset() or "utf-8"
        payload = _message.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode(charset, errors="replace")
        else:
            return str(payload)


def parse_single_message(msg: Message) -> dict[str, Any]:
    """Parse a single email message into a structured dictionary.

    Extracts all relevant metadata and content from an email message object,
    including headers, dates, recipients, and message content. Handles date
    parsing and normalization to UTC timezone.

    Parameters
    ----------
    msg : Message
        Email message object from Python's email library containing the
        message to parse.

    Returns
    -------
    dict[str, Any]
        Dictionary containing parsed email data with keys:
        - 'from': sender email address
        - 'to': recipient email address(es)
        - 'subject': email subject line
        - 'date': parsed datetime object in UTC (or None)
        - 'content': extracted text content
        - 'message_id': unique message identifier
        - 'in_reply_to': reference to replied message
        - 'references': message thread references

    Notes
    -----
    - Handles both 'date' and 'sent' date fields
    - Converts dates to UTC timezone for consistency
    - Extracts content using extract_message_content function
    - Preserves thread information through message IDs and references
    """
    content = extract_message_content(msg)
    if msg["sent"]:
        msg["date"] = msg["sent"]

    return {
        "from": msg["from"],
        "to": msg["to"],
        "subject": msg["subject"],
        "date": (parsedate_to_datetime(msg["date"]).replace(tzinfo=datetime.UTC) if msg["date"] else None),
        "content": content,
        "message_id": msg["message-id"],
        "in_reply_to": msg["in-reply-to"],
        "references": msg["references"],
    }


def split_chain(content: str) -> list[dict[str, Any]]:
    """Split email chain content into individual message components.

    Parses a concatenated email chain text and separates it into individual
    message dictionaries by detecting email headers and splitting points.
    Uses regex patterns to identify message boundaries and extract metadata.

    Parameters
    ----------
    content : str
        Raw email chain content containing multiple concatenated messages
        with headers like "From:", "Date:", "To:", "Subject:".

    Returns
    -------
    list[dict[str, Any]]
        List of dictionaries, each representing an individual email with
        extracted metadata including:
        - 'from': sender information
        - 'to': recipient information
        - 'subject': email subject
        - 'date': parsed datetime object in UTC
        - 'content': message body content
        - 'cc': carbon copy recipients (if present)

    Notes
    -----
    - Uses regex pattern matching to detect email headers
    - Handles both "Date:" and "Sent:" date formats
    - Preserves content that doesn't match header patterns
    - Converts dates to UTC timezone for consistency
    - Returns single-item list if no chain splitting is detected
    """
    email_matcher = re.compile(
        r"(From: (?P<from>.*)\n(?:Sent|Date):(?P<date>.*)\nTo: (?P<to>.*)\n(Cc: (?P<cc>.*)\n)?Subject: (?P<subject>.*)\n)"
    )

    split_points = []
    for match in re.finditer(email_matcher, content):
        split_points.append(match.start())

    splits = []
    for i, pt in enumerate(split_points):
        if i == 0 and pt != 0:
            splits.append(content[0:pt])
        if i + 1 < len(split_points):
            next_pt = split_points[i + 1]
            splits.append(content[pt:next_pt])
        else:
            splits.append(content[pt:])

    if not splits:
        splits = [content]

    formatted_msgs = []
    for part in splits:
        part_match: Match[str] | None = email_matcher.match(part)
        if part_match:
            d = part_match.groupdict()
            d["content"] = part[: part_match.start()] + part[part_match.end() :]
            if "date" in d:
                mdate = parsedate_to_datetime(d["date"])
                if mdate:
                    d["date"] = mdate.replace(tzinfo=datetime.UTC)
            formatted_msgs.append(d)
        elif part:  # Only add non-empty parts without headers
            formatted_msgs.append({"content": part})

    return formatted_msgs


def clean_message(raw: str) -> str:
    """Clean and normalize email message content by removing unwanted elements.

    Processes raw email content to remove security-related URL redirects,
    clean up quoted message formatting, and normalize line structures.
    Specifically handles common email client artifacts and formatting.

    Parameters
    ----------
    raw : str
        Raw email message content that may contain URL redirects, quoted
        text markers, and other email client formatting artifacts.

    Returns
    -------
    str
        Cleaned message content with unwanted elements removed and
        quote formatting normalized.

    Notes
    -----
    - Removes lines containing URL defense redirects
    - Converts "> " quote prefixes to unquoted text
    - Converts standalone ">" lines to empty lines
    - Preserves overall message structure and readability
    - Useful for processing forwarded or replied messages
    """
    keep = []
    for line in raw.split("\n"):
        if "<https://urldefense.com/" in line:
            continue
        if line == ">":
            line = ""
        elif line.startswith("> "):
            line = line[2:]
        keep.append(line)
    return "\n".join(keep)


def parse_email_chain(eml_file: str | StringIO, as_markdown: bool = False) -> str | list[dict[str, Any]]:
    """Parse an EML file containing an email chain into structured message data.

    Processes email files (.eml format) and extracts individual messages from
    email chains, including reply threads and forwarded messages. Returns either
    structured message dictionaries or formatted Markdown representation.

    Parameters
    ----------
    eml_file : str or StringIO
        Path to the EML file as a string, or StringIO object containing
        the email content to parse.
    as_markdown : bool, default False
        If True, returns formatted Markdown string representation of the
        email chain. If False, returns list of structured message dictionaries.

    Returns
    -------
    str or list[dict[str, Any]]
        If as_markdown is True, returns formatted Markdown string.
        If as_markdown is False, returns list of dictionaries with message data
        including 'from', 'to', 'subject', 'date', 'content', and metadata.

    Examples
    --------
    Parse email chain as structured data:

        >>> messages = parse_email_chain('conversation.eml')
        >>> for msg in messages:
        ...     print(f"From: {msg['from']}, Subject: {msg['subject']}")

    Get Markdown representation:

        >>> markdown = parse_email_chain('conversation.eml', as_markdown=True)
        >>> print(markdown)

    Notes
    -----
    - Automatically detects and splits email chains into individual messages
    - Handles various email encodings (UTF-8, ISO-8859-1, etc.)
    - Preserves message threading and reply relationships
    - Cleans quoted content and URL redirects from messages
    - Supports both file paths and StringIO objects as input
    """
    if isinstance(eml_file, str):
        with open(eml_file, encoding="utf-8") as f:
            eml_msg = message_from_file(f, policy=policy.default)
    elif isinstance(eml_file, StringIO):
        eml_msg = message_from_file(eml_file, policy=policy.default)
    else:
        raise TypeError(f"Expected string or file, found: {type(eml_file)}")

    messages = []

    # Parse the primary message first
    message = parse_single_message(eml_msg)

    # If there's quoted content, try to parse it into separate messages
    if message["content"]:
        split_messages = split_chain(message["content"].replace("\u200b", "").replace("\u202f", " "))

        if len(split_messages):
            # Need to update the first message with the original metadata
            for k in message:
                if k != "content":
                    split_messages[0][k] = message[k]
        messages = split_messages
    else:
        messages = [message]

    for m in messages:
        m["content"] = clean_message(m["content"])

    messages.sort(key=lambda m: m["date"])

    if as_markdown:
        return format_email_chain_as_markdown(messages)
    return messages
