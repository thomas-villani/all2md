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

    >>> from all2md.emlfile import parse_email_chain
    >>> with open('message.eml', 'r') as f:
    ...     result = parse_email_chain(f)
    >>> print(result)

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
from email.message import EmailMessage, Message
from email.utils import getaddresses, parsedate_to_datetime
from io import StringIO
from typing import Any, Union

from ._attachment_utils import process_attachment
from .constants import DEFAULT_URL_WRAPPERS
from .exceptions import MdparseConversionError, MdparseInputError
from .options import EmlOptions


def _parse_date_with_fallback(msg: EmailMessage | Message, options: EmlOptions) -> datetime.datetime | None:
    """Parse email date with fallback hierarchy: Date -> Sent -> Received.

    Parameters
    ----------
    msg : EmailMessage | Message
        Email message object containing date headers.
    options : EmlOptions
        Configuration options for date parsing.

    Returns
    -------
    datetime.datetime | None
        Parsed datetime in UTC, or None if no valid date found.
    """
    # Try Date header first (most common)
    date_str = msg.get("Date")
    if date_str:
        parsed_date = _parse_date_safely(date_str)
        if parsed_date:
            return parsed_date

    # Fallback to Sent header
    sent_str = msg.get("Sent")
    if sent_str:
        parsed_date = _parse_date_safely(sent_str)
        if parsed_date:
            return parsed_date

    # Fallback to Received header (take the last/most recent one)
    received_headers = msg.get_all("Received")
    if received_headers:
        for received_str in reversed(received_headers):  # Most recent first
            # Extract date from Received header (format: "from ... ; date")
            if ";" in received_str:
                date_part = received_str.split(";")[-1].strip()
                parsed_date = _parse_date_safely(date_part)
                if parsed_date:
                    return parsed_date

    return None


def _parse_date_safely(date_str: str | None) -> datetime.datetime | None:
    """Safely parse a date string, returning None if parsing fails.

    Parameters
    ----------
    date_str : str | None
        Date string to parse.

    Returns
    -------
    datetime.datetime | None
        Parsed datetime in UTC, or None if parsing fails.
    """
    if not date_str:
        return None

    try:
        parsed = parsedate_to_datetime(date_str)
        # Ensure timezone awareness - convert to UTC if no timezone
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=datetime.timezone.utc)
        else:
            return parsed.astimezone(datetime.timezone.utc)
    except (ValueError, TypeError):
        return None


def _format_date(dt: datetime.datetime | None, options: EmlOptions) -> str:
    """Format datetime according to EmlOptions configuration.

    Parameters
    ----------
    dt : datetime.datetime | None
        Datetime to format.
    options : EmlOptions
        Configuration options for date formatting.

    Returns
    -------
    str
        Formatted date string, or empty string if dt is None.
    """
    if dt is None:
        return ""

    if options.date_format_mode == "iso8601":
        return dt.isoformat()
    elif options.date_format_mode == "locale":
        # Use locale-aware formatting
        return dt.strftime("%c")
    else:  # strftime mode
        return dt.strftime(options.date_strftime_pattern)


def format_email_chain_as_markdown(eml_chain: list[dict[str, Any]], options: EmlOptions | None = None) -> str:
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
    options : EmlOptions | None, default None
        Configuration options for formatting. If None, uses defaults.

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
    if options is None:
        options = EmlOptions()

    md = ""
    for item in eml_chain:
        if options.include_headers:
            md += f"From: {item['from']}\n"
            md += f"To: {item['to']}\n"
            if item.get("cc"):
                md += f"cc: {item['cc']}\n"
            if "date" in item and item['date'] is not None:
                formatted_date = _format_date(item['date'], options)
                if formatted_date:
                    md += f"Date: {formatted_date}\n"
            if "subject" in item:
                md += f"Subject: {item['subject']}\n"

        md += item["content"] + "\n---\n"
    return md


def extract_message_content(message: EmailMessage | Message, options: EmlOptions) -> str:
    """Extract text content from an email message with enhanced multipart handling.

    Processes both simple and multipart email messages to extract readable
    text content. For multipart messages, prefers text/plain content but can
    fall back to text/html with optional HTML-to-Markdown conversion.

    Parameters
    ----------
    message : EmailMessage | Message
        Email message object from Python's email library to extract content from.
    options : EmlOptions
        Configuration options for content extraction and processing.

    Returns
    -------
    str
        Extracted text content from the email message, with proper encoding
        handling and multipart content processing.

    Notes
    -----
    - For multipart/alternative: prefers text/plain, falls back to text/html
    - For multipart/mixed: combines all text parts
    - Optionally converts HTML to Markdown using html2markdown
    - Manages different character encodings with UTF-8 fallback
    - Uses error-safe decoding to handle malformed content
    """
    if not message.is_multipart():
        # Simple message - extract content directly
        return _extract_part_content(message, options)

    # Handle multipart messages with preference logic
    text_parts = []
    html_parts = []

    for part in message.walk():
        # Skip the main multipart container
        if part.is_multipart():
            continue

        content_type = part.get_content_type()

        if content_type == "text/plain":
            content = _extract_part_content(part, options)
            if content.strip():
                text_parts.append(content)
        elif content_type == "text/html":
            content = _extract_part_content(part, options)
            if content.strip():
                html_parts.append(content)

    # Preference logic: use text/plain if available, otherwise HTML
    if text_parts:
        return "\n\n".join(text_parts)
    elif html_parts:
        html_content = "\n\n".join(html_parts)
        if options.convert_html_to_markdown:
            # Convert HTML to Markdown
            return _convert_html_to_markdown(html_content, options)
        else:
            return html_content
    else:
        return ""


def _extract_part_content(part: EmailMessage | Message, options: EmlOptions) -> str:
    """Extract content from a single email part with proper encoding handling.

    Parameters
    ----------
    part : EmailMessage | Message
        Email part to extract content from.
    options : EmlOptions
        Configuration options for content extraction.

    Returns
    -------
    str
        Extracted text content with proper encoding.
    """
    try:
        # Get charset with fallback
        charset = part.get_content_charset() or "utf-8"

        # Get payload
        payload = part.get_payload(decode=True)

        if isinstance(payload, bytes):
            return payload.decode(charset, errors="replace")
        elif isinstance(payload, str):
            return payload
        else:
            return str(payload) if payload is not None else ""

    except (UnicodeDecodeError, LookupError):
        # Fallback for encoding issues
        try:
            if isinstance(payload, bytes):
                return payload.decode("utf-8", errors="replace")
            else:
                return str(payload) if payload is not None else ""
        except Exception:
            return ""


def _convert_html_to_markdown(html_content: str, options: EmlOptions) -> str:
    """Convert HTML content to Markdown using html2markdown.

    Parameters
    ----------
    html_content : str
        HTML content to convert.
    options : EmlOptions
        Configuration options for conversion.

    Returns
    -------
    str
        Converted Markdown content.
    """
    try:
        from .html2markdown import html_to_markdown
        from .options import HtmlOptions

        # Create HTML options that match EML preferences
        html_options = HtmlOptions(
            use_hash_headings=True,
            extract_title=False,
            preserve_nbsp=False,
            strip_dangerous_elements=True,
            attachment_mode=options.attachment_mode,
            attachment_output_dir=options.attachment_output_dir,
            attachment_base_url=options.attachment_base_url,
            markdown_options=options.markdown_options,
        )

        # Convert HTML to Markdown
        from io import StringIO
        return html_to_markdown(StringIO(html_content), html_options)

    except ImportError:
        # html2markdown not available, return HTML as-is
        return html_content
    except Exception:
        # Conversion failed, return HTML as-is
        return html_content


def parse_single_message(msg: EmailMessage | Message, options: EmlOptions) -> dict[str, Any]:
    """Parse a single email message into a structured dictionary with enhanced processing.

    Extracts all relevant metadata and content from an email message object,
    including headers, dates, recipients, and message content. Handles date
    parsing with fallback hierarchy and advanced content extraction.

    Parameters
    ----------
    msg : EmailMessage | Message
        Email message object from Python's email library containing the
        message to parse.
    options : EmlOptions
        Configuration options for parsing and processing.

    Returns
    -------
    dict[str, Any]
        Dictionary containing parsed email data with keys:
        - 'from': sender email address (normalized if enabled)
        - 'to': recipient email address(es) (normalized if enabled)
        - 'cc': carbon copy recipients (if present and normalized if enabled)
        - 'bcc': blind carbon copy recipients (if present and normalized if enabled)
        - 'subject': email subject line
        - 'date': parsed datetime object in UTC (or None)
        - 'content': extracted text content
        - 'message_id': unique message identifier
        - 'in_reply_to': reference to replied message
        - 'references': message thread references
        - 'raw_headers': raw header values (if preserve_raw_headers enabled)

    Notes
    -----
    - Uses fallback date hierarchy: Date -> Sent -> Received
    - Converts dates to UTC timezone for consistency
    - Extracts content with multipart handling and HTML conversion
    - Preserves thread information through message IDs and references
    - Optionally normalizes headers and preserves raw values
    """
    # Extract and normalize headers
    headers = _extract_headers(msg, options)

    # Parse date with fallback hierarchy
    parsed_date = _parse_date_with_fallback(msg, options)

    # Extract content with enhanced multipart handling
    content = extract_message_content(msg, options)

    result = {
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": parsed_date,
        "content": content,
        "message_id": headers.get("message_id", ""),
        "in_reply_to": headers.get("in_reply_to", ""),
        "references": headers.get("references", ""),
    }

    # Add CC and BCC if present
    if "cc" in headers:
        result["cc"] = headers["cc"]
    if "bcc" in headers:
        result["bcc"] = headers["bcc"]

    # Add raw headers if requested
    if options.preserve_raw_headers and "raw_headers" in headers:
        result["raw_headers"] = headers["raw_headers"]

    return result


def _extract_headers(msg: EmailMessage | Message, options: EmlOptions) -> dict[str, Any]:
    """Extract and normalize headers from an email message.

    Parameters
    ----------
    msg : EmailMessage | Message
        Email message object containing headers to extract.
    options : EmlOptions
        Configuration options for header processing.

    Returns
    -------
    dict[str, Any]
        Dictionary containing processed headers.
    """
    headers: dict[str, Any] = {}
    raw_headers: dict[str, str] = {}

    # Extract basic headers
    for header_name in ["from", "to", "cc", "bcc", "subject", "message-id", "in-reply-to", "references"]:
        header_value = msg.get(header_name)
        if header_value:
            raw_headers[header_name] = header_value
            if options.normalize_headers:
                headers[header_name.replace("-", "_")] = _normalize_header_value(header_value, header_name)
            else:
                headers[header_name.replace("-", "_")] = header_value

    # Handle address lists with proper parsing
    for address_header in ["from", "to", "cc", "bcc"]:
        header_key = address_header.replace("-", "_")
        if header_key in headers and headers[header_key]:
            headers[header_key] = _normalize_email_addresses(headers[header_key], options)

    if options.preserve_raw_headers:
        headers["raw_headers"] = raw_headers

    return headers


def _normalize_header_value(value: str, header_name: str) -> str:
    """Normalize a header value by cleaning whitespace and encoding.

    Parameters
    ----------
    value : str
        Header value to normalize.
    header_name : str
        Name of the header for context.

    Returns
    -------
    str
        Normalized header value.
    """
    if not value:
        return ""

    # Clean up whitespace
    normalized = re.sub(r'\s+', ' ', value.strip())

    # Decode any encoded words
    try:
        from email.header import decode_header
        decoded_parts = []
        for part, encoding in decode_header(normalized):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or 'utf-8', errors='replace'))
            else:
                decoded_parts.append(part)
        return ''.join(decoded_parts)
    except Exception:
        return normalized


def _normalize_email_addresses(addresses: str, options: EmlOptions) -> str:
    """Normalize email addresses using proper parsing.

    Parameters
    ----------
    addresses : str
        Address string to normalize.
    options : EmlOptions
        Configuration options for normalization.

    Returns
    -------
    str
        Normalized address string.
    """
    if not addresses or not options.normalize_headers:
        return addresses

    try:
        # Use email.utils.getaddresses for proper parsing
        parsed_addresses = getaddresses([addresses])
        normalized_addresses = []

        for name, email in parsed_addresses:
            if name and email:
                # Format as "Name <email@domain.com>"
                normalized_addresses.append(f"{name} <{email}>")
            elif email:
                # Just email address
                normalized_addresses.append(email)

        return ", ".join(normalized_addresses)
    except Exception:
        return addresses


def split_chain(content: str, options: EmlOptions) -> list[dict[str, Any]]:
    """Split email chain content into individual message components with enhanced detection.

    Parses a concatenated email chain text and separates it into individual
    message dictionaries by detecting email headers, reply separators, and
    quoted content boundaries. Uses multiple patterns for robust detection.

    Parameters
    ----------
    content : str
        Raw email chain content containing multiple concatenated messages
        with headers like "From:", "Date:", "To:", "Subject:".
    options : EmlOptions
        Configuration options for chain splitting and content processing.

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
    - Uses enhanced regex patterns for better header detection
    - Detects common reply separators like "On <date>, <name> wrote:"
    - Handles both "Date:" and "Sent:" date formats
    - Preserves content that doesn't match header patterns
    - Converts dates to UTC timezone for consistency
    - Returns single-item list if no chain splitting is detected
    """
    # Enhanced email header pattern
    email_matcher = re.compile(
        r"(From: (?P<from>.*?)\n(?:(?:Sent|Date):\s*(?P<date>.*?)\n)?To: (?P<to>.*?)\n(?:Cc: (?P<cc>.*?)\n)?Subject: (?P<subject>.*?)\n)",
        re.MULTILINE | re.DOTALL
    )

    # Common reply separator patterns
    reply_patterns = [
        # "On <date>, <name> wrote:"
        re.compile(r"On .+?,? .+? wrote:", re.IGNORECASE),
        # "<name> wrote on <date>:"
        re.compile(r".+? wrote on .+?:", re.IGNORECASE),
        # "--- Original Message ---" and variants
        re.compile(r"---+\s*Original Message\s*---+", re.IGNORECASE),
        re.compile(r"---+\s*Forwarded Message\s*---+", re.IGNORECASE),
        # "From: <name> [mailto:email]"
        re.compile(r"From: .+? \[mailto:.+?\]", re.IGNORECASE),
    ]

    split_points = []

    # Find header-based split points
    for match in re.finditer(email_matcher, content):
        split_points.append(match.start())

    # Find reply separator split points if enabled
    if options.detect_reply_separators:
        for pattern in reply_patterns:
            for match in re.finditer(pattern, content):
                split_points.append(match.start())

    # Remove duplicates and sort
    split_points = sorted(set(split_points))

    # Create content splits
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

    # Parse each split into message components
    formatted_msgs = []
    for part in splits:
        part_match = email_matcher.match(part)
        if part_match:
            d = part_match.groupdict()
            # Extract content after header
            d["content"] = part[part_match.end():]
            # Parse date if present
            if d.get("date"):
                d["date"] = _parse_date_safely(d["date"])
            # Clean None values
            d = {k: v for k, v in d.items() if v is not None}
            formatted_msgs.append(d)
        elif part.strip():  # Only add non-empty parts without headers
            formatted_msgs.append({"content": part})

    return formatted_msgs


def process_email_attachments(msg: Message, options: EmlOptions) -> str:
    """Process email attachments and return markdown representation.

    Extracts attachments from an email message and processes them according
    to the specified attachment mode.

    Parameters
    ----------
    msg : Message
        Email message object containing attachments
    options : EmlOptions
        Configuration options for attachment processing

    Returns
    -------
    str
        Markdown representation of attachments
    """
    if options.attachment_mode == "skip":
        return ""

    attachments = []
    attachment_count = 0

    for part in msg.walk():
        # Skip the main message parts
        if part.get_content_maintype() == "multipart":
            continue

        # Check if this is an attachment
        content_disposition = part.get("Content-Disposition")
        if content_disposition and "attachment" in content_disposition:
            attachment_count += 1
            filename = part.get_filename()
            if not filename:
                filename = f"attachment_{attachment_count}"

            # Get attachment data
            attachment_data = part.get_payload(decode=True)
            if not isinstance(attachment_data, (bytes, type(None))):
                attachment_data = None

            # Determine if it's an image
            content_type = part.get_content_type()
            is_image = content_type.startswith("image/") if content_type else False

            # Process using unified attachment handling
            processed_attachment = process_attachment(
                attachment_data=attachment_data,
                attachment_name=filename,
                alt_text=filename,
                attachment_mode=options.attachment_mode,
                attachment_output_dir=options.attachment_output_dir,
                attachment_base_url=options.attachment_base_url,
                is_image=is_image,
            )

            if processed_attachment:
                attachments.append(processed_attachment)

    if attachments:
        return "\n\n**Attachments:**\n" + "\n".join(attachments) + "\n"
    return ""


def clean_message(raw: str, options: EmlOptions) -> str:
    """Clean and normalize email message content with enhanced processing.

    Processes raw email content to remove security-related URL redirects,
    clean up quoted message formatting, and normalize line structures.
    Uses configurable patterns for comprehensive cleaning.

    Parameters
    ----------
    raw : str
        Raw email message content that may contain URL redirects, quoted
        text markers, and other email client formatting artifacts.
    options : EmlOptions
        Configuration options for content cleaning and processing.

    Returns
    -------
    str
        Cleaned message content with unwanted elements removed and
        quote formatting normalized according to configuration.

    Notes
    -----
    - Removes lines containing configured URL wrapper domains
    - Handles various quote prefixes (>, >>, etc.) if quote cleaning enabled
    - Converts standalone quote markers to empty lines
    - Preserves overall message structure and readability
    - Configurable URL cleaning patterns for different security services
    """
    if not raw:
        return ""

    # Get URL wrappers to clean
    url_wrappers = options.url_wrappers or DEFAULT_URL_WRAPPERS

    # Clean URL wrappers first if enabled
    if options.clean_wrapped_urls:
        raw = _clean_wrapped_urls(raw, url_wrappers)

    # Clean quotes if enabled
    if options.clean_quotes:
        raw = _clean_quoted_content(raw)

    return raw.strip()


def _clean_wrapped_urls(content: str, url_wrappers: list[str]) -> str:
    """Remove wrapped URLs from various security services.

    Parameters
    ----------
    content : str
        Content containing potentially wrapped URLs.
    url_wrappers : list[str]
        List of URL wrapper domains to clean.

    Returns
    -------
    str
        Content with wrapped URLs cleaned.
    """
    lines = content.split('\n')
    cleaned_lines = []

    for line in lines:
        # Skip lines that contain wrapped URLs
        if any(f"<https://{wrapper}/" in line or f"https://{wrapper}/" in line for wrapper in url_wrappers):
            continue

        # Also clean inline wrapped URLs by extracting the original URL
        for wrapper in url_wrappers:
            # Pattern to match wrapped URLs and extract original
            pattern = rf'https://{re.escape(wrapper)}/[^?\s]*\?[^=]*=([^&\s]+)'
            line = re.sub(pattern, _unwrap_url, line)

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def _unwrap_url(match: re.Match[str]) -> str:
    """Extract original URL from wrapped URL match.

    Parameters
    ----------
    match : re.Match
        Regex match object containing wrapped URL.

    Returns
    -------
    str
        Unwrapped URL or original wrapped URL if unwrapping fails.
    """
    try:
        from urllib.parse import unquote
        wrapped_url = match.group(1)
        return unquote(wrapped_url)
    except Exception:
        return match.group(0)  # Return original if unwrapping fails


def _clean_quoted_content(content: str) -> str:
    """Clean quoted email content with enhanced quote detection.

    Parameters
    ----------
    content : str
        Content containing quoted email text.

    Returns
    -------
    str
        Content with quotes cleaned and normalized.
    """
    lines = content.split('\n')
    cleaned_lines = []

    for line in lines:
        # Handle various quote patterns
        if line == ">":
            # Standalone quote marker becomes empty line
            cleaned_lines.append("")
        elif line.startswith("> "):
            # Standard quote prefix - remove it
            cleaned_lines.append(line[2:])
        elif re.match(r'^>{2,}\s*', line):
            # Multiple quote levels (>>, >>>, etc.)
            # Count quote levels and remove them
            quote_match = re.match(r'^(>{2,})\s*', line)
            if quote_match:
                quote_prefix = quote_match.group(1)
                cleaned_lines.append(line[len(quote_prefix):].lstrip())
        elif line.strip().startswith('|'):
            # Some email clients use | for quoting
            cleaned_lines.append(line.lstrip('| '))
        else:
            # Regular line - keep as is
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def parse_email_chain(input_data: Union[str, StringIO], options: EmlOptions | None = None) -> str:
    """Parse EML file containing email chain into Markdown format.

    Processes email files (.eml format) using enhanced parsing with robust
    multipart handling, date fallbacks, quote processing, and URL cleaning.
    Handles complex email structures and preserves thread hierarchy.

    Parameters
    ----------
    input_data : str or StringIO
        Path to the EML file as a string, or StringIO object containing
        the email content to parse.
    options : EmlOptions | None, default None
        Configuration options for email parsing and processing. If None,
        uses default settings.

    Returns
    -------
    str
        Formatted Markdown string representation of the email chain with
        headers, content, and attachments processed according to options.

    Examples
    --------
    Parse email with default settings:

        >>> markdown = parse_email_chain('conversation.eml')
        >>> print(markdown)

    Parse with custom options:

        >>> opts = EmlOptions(
        ...     date_format_mode="iso8601",
        ...     convert_html_to_markdown=True,
        ...     clean_quotes=True
        ... )
        >>> markdown = parse_email_chain('conversation.eml', options=opts)

    Notes
    -----
    - Uses EmailMessage with policy=default for robust parsing
    - Handles multipart messages with text/plain preference
    - Supports HTML-to-Markdown conversion when enabled
    - Enhanced date parsing with fallback hierarchy (Date -> Sent -> Received)
    - Configurable quote cleaning and URL unwrapping
    - Preserves message threading and reply relationships
    - Supports both file paths and StringIO objects as input
    """
    # Initialize options with defaults
    if options is None:
        options = EmlOptions()

    # Validate and process input with enhanced EmailMessage parsing
    try:
        if isinstance(input_data, str):
            with open(input_data, encoding="utf-8") as f:
                eml_msg = message_from_file(f, policy=policy.default)
        elif isinstance(input_data, StringIO):
            eml_msg = message_from_file(input_data, policy=policy.default)
        else:
            raise MdparseInputError(
                f"Unsupported input type: {type(input_data).__name__}. Expected str (file path) or StringIO object",
                parameter_name="input_data",
                parameter_value=input_data,
            )
    except Exception as e:
        if isinstance(e, (MdparseInputError, MdparseConversionError)):
            raise
        else:
            raise MdparseConversionError(
                f"Failed to parse email data: {str(e)}",
                conversion_stage="email_parsing",
                original_error=e
            ) from e

    messages = []

    try:
        # Parse the primary message with enhanced processing
        message = parse_single_message(eml_msg, options)

        # Process attachments if needed
        if options.attachment_mode != "skip":
            attachment_content = process_email_attachments(eml_msg, options)
            if attachment_content:
                message["content"] += attachment_content

        # Enhanced chain splitting with reply detection
        if message["content"]:
            # Clean unicode characters that cause issues
            cleaned_content = message["content"].replace("\u200b", "").replace("\u202f", " ")
            split_messages = split_chain(cleaned_content, options)

            if len(split_messages) > 1:
                # Update the first message with the original metadata
                for key in message:
                    if key != "content" and key not in split_messages[0]:
                        split_messages[0][key] = message[key]
                messages = split_messages
            else:
                messages = [message]
        else:
            messages = [message]

        # Clean message content with enhanced processing
        for msg in messages:
            if "content" in msg:
                msg["content"] = clean_message(msg["content"], options)

        # Sort messages chronologically (older messages first)
        messages.sort(key=lambda m: m.get("date") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc))

        # Convert to Markdown format
        return format_email_chain_as_markdown(messages, options)

    except Exception as e:
        raise MdparseConversionError(
            f"Failed to process email content: {str(e)}",
            conversion_stage="content_processing",
            original_error=e
        ) from e
