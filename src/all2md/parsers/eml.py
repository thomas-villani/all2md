#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/eml.py
"""Email (EML) to AST converter.

This module provides conversion from email messages to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations

import datetime
import re
from email import message_from_binary_file, message_from_bytes, policy
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import getaddresses, parsedate_to_datetime
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Optional, Union
from urllib.parse import unquote

from all2md.api import to_markdown
from all2md.ast import (
    Document,
    Heading,
    Node,
    Paragraph,
    Text,
    ThematicBreak,
)
from all2md.constants import DEFAULT_URL_WRAPPERS
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, MalformedFileError, ParsingError, ValidationError
from all2md.options.eml import EmlOptions
from all2md.options.html import HtmlOptions
from all2md.options.markdown import MarkdownRendererOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import process_attachment
from all2md.utils.metadata import DocumentMetadata


def _parse_date_with_fallback(msg: EmailMessage | Message) -> datetime.datetime | None:
    """Parse email date with fallback hierarchy: Date -> Sent -> Received.

    Parameters
    ----------
    msg : EmailMessage | Message
        Email message object containing date headers.

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


def format_eml_date(dt: datetime.datetime | None, options: EmlOptions) -> str:
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

        if content_type == "text/plain" and options.include_plain_parts:
            content = _extract_part_content(part, options)
            if content.strip():
                text_parts.append(content)
        elif content_type == "text/html" and options.include_html_parts:
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
            return convert_eml_html_to_markdown(html_content, options)
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
            # Check for extremely large text payloads (protection against memory exhaustion)
            if len(payload) > options.max_asset_size_bytes:
                return f"[Content too large ({len(payload)} bytes) - truncated for security]"
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


def convert_eml_html_to_markdown(html_content: str, options: EmlOptions) -> str:
    """Convert HTML content to Markdown.

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

        # Create MarkdownRendererOptions with default hash headings
        md_options = MarkdownRendererOptions(use_hash_headings=True)

        # Create HTML options that match EML preferences and security settings
        html_options = HtmlOptions(
            extract_title=False,
            convert_nbsp=False,
            strip_dangerous_elements=True,
            attachment_mode=options.attachment_mode,
            attachment_output_dir=options.attachment_output_dir,
            attachment_base_url=options.attachment_base_url,
            # Network security settings from EML options
            network=options.html_network,
        )

        # Convert HTML to Markdown

        return to_markdown(
            BytesIO(html_content.encode("utf-8")),
            source_format="html",
            parser_options=html_options,
            renderer_options=md_options,
        )

    except (ImportError, DependencyError):
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
    parsed_date = _parse_date_with_fallback(msg)

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
    normalized = re.sub(r"\s+", " ", value.strip())

    # Decode any encoded words
    try:
        decoded_parts = []
        for part, encoding in decode_header(normalized):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                decoded_parts.append(part)
        return "".join(decoded_parts)
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
        r"(From: (?P<from>.*?)\n(?:(?:Sent|Date):\s*(?P<date>.*?)\n)?"
        r"To: (?P<to>.*?)\n(?:Cc: (?P<cc>.*?)\n)?Subject: (?P<subject>.*?)\n)",
        re.MULTILINE | re.DOTALL,
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
            d["content"] = part[part_match.end() :]
            # Parse date if present
            if d.get("date"):
                d["date"] = _parse_date_safely(d["date"])
            # Clean None values
            d = {k: v for k, v in d.items() if v is not None}
            formatted_msgs.append(d)
        elif part.strip():  # Only add non-empty parts without headers
            formatted_msgs.append({"content": part})

    return formatted_msgs


def process_email_attachments(msg: Message, options: EmlOptions) -> tuple[str, dict[str, str]]:
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
    tuple[str, dict[str, str]]
        Tuple of (markdown representation of attachments, footnotes dict)

    """
    if options.attachment_mode == "skip":
        return "", {}

    attachments = []
    collected_footnotes: dict[str, str] = {}
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

            # Check attachment size limits for security
            if attachment_data and isinstance(attachment_data, bytes):
                if len(attachment_data) > options.max_asset_size_bytes:
                    # Skip attachment that exceeds size limit
                    continue

            # Determine if it's an image
            content_type = part.get_content_type()
            is_image = content_type.startswith("image/") if content_type else False

            # Process using unified attachment handling
            result = process_attachment(
                attachment_data=attachment_data,
                attachment_name=filename,
                alt_text=filename,
                attachment_mode=options.attachment_mode,
                attachment_output_dir=options.attachment_output_dir,
                attachment_base_url=options.attachment_base_url,
                is_image=is_image,
                alt_text_mode=options.alt_text_mode,
            )

            # Collect footnote info if present
            if result.get("footnote_label") and result.get("footnote_content"):
                collected_footnotes[result["footnote_label"]] = result["footnote_content"]

            if result.get("markdown"):
                attachments.append(result["markdown"])

    if attachments:
        if options.include_attach_section_heading:
            # Format as heading (## Attachments by default)
            return f"\n\n## {options.attach_section_title}\n\n" + "\n".join(attachments) + "\n", collected_footnotes
        else:
            return "\n\n" + "\n".join(attachments) + "\n", collected_footnotes
    return "", collected_footnotes


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
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        # Skip lines that contain wrapped URLs
        if any(f"<https://{wrapper}/" in line or f"https://{wrapper}/" in line for wrapper in url_wrappers):
            continue

        # Also clean inline wrapped URLs by extracting the original URL
        for wrapper in url_wrappers:
            # Pattern to match wrapped URLs and extract original
            pattern = rf"https://{re.escape(wrapper)}/[^?\s]*\?[^=]*=([^&\s]+)"
            line = re.sub(pattern, _unwrap_url, line)

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


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
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        # Handle various quote patterns
        if line == ">":
            # Standalone quote marker becomes empty line
            cleaned_lines.append("")
        elif line.startswith("> "):
            # Standard quote prefix - remove it
            cleaned_lines.append(line[2:])
        elif re.match(r"^>{2,}\s*", line):
            # Multiple quote levels (>>, >>>, etc.)
            # Count quote levels and remove them
            quote_match = re.match(r"^(>{2,})\s*", line)
            if quote_match:
                quote_prefix = quote_match.group(1)
                cleaned_lines.append(line[len(quote_prefix) :].lstrip())
        elif line.strip().startswith("|"):
            # Some email clients use | for quoting
            cleaned_lines.append(line.lstrip("| "))
        else:
            # Regular line - keep as is
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


class EmlToAstConverter(BaseParser):
    """Convert email messages to AST representation.

    This converter processes parsed email data and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : EmlOptions or None
        Conversion options

    """

    def __init__(self, options: EmlOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the EML parser with options and progress callback."""
        BaseParser._validate_options_type(options, EmlOptions, "eml")
        options = options or EmlOptions()
        super().__init__(options, progress_callback)
        self.options: EmlOptions = options
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse EML file into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input email document to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw email bytes

        Returns
        -------
        Document
            AST Document node representing the parsed email structure

        Raises
        ------
        MalformedFileError
            If parsing fails due to invalid email format
        ParsingError
            If content processing fails
        ValidationError
            If input type is not supported

        """
        # Reset parser state to prevent leakage across parse calls
        self._attachment_footnotes = {}

        # Parse the email message
        try:
            if isinstance(input_data, (str, Path)):
                # Use binary file reading to avoid encoding assumptions
                with open(input_data, "rb") as f:
                    eml_msg = message_from_binary_file(f, policy=policy.default)
            elif isinstance(input_data, bytes):
                eml_msg = message_from_bytes(input_data, policy=policy.default)
            elif hasattr(input_data, "read"):
                # Handle IO[bytes] - read binary data and parse directly
                if hasattr(input_data, "seek"):
                    input_data.seek(0)  # Ensure we're at the beginning
                content = input_data.read()
                eml_msg = message_from_bytes(content, policy=policy.default)
            else:
                raise ValidationError(
                    f"Unsupported input type: {type(input_data).__name__}. Expected str, Path, or binary file object",
                    parameter_name="input_data",
                    parameter_value=input_data,
                )
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            else:
                raise MalformedFileError(
                    f"Failed to parse email data: {e!r}",
                    file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                    original_error=e,
                ) from e

        # Parse the message content
        try:
            # Parse the primary message
            message = parse_single_message(eml_msg, self.options)

            # Process attachments if needed
            if self.options.attachment_mode != "skip":
                attachment_content, attachment_footnotes = process_email_attachments(eml_msg, self.options)
                # Merge footnotes from attachments
                self._attachment_footnotes.update(attachment_footnotes)
                if attachment_content:
                    message["content"] += attachment_content

            messages = []

            # Enhanced chain splitting with reply detection (only if preserve_thread_structure is enabled)
            if self.options.preserve_thread_structure and message["content"]:
                # Clean unicode characters that cause issues
                cleaned_content = message["content"].replace("\u200b", "").replace("\u202f", " ")
                split_messages = split_chain(cleaned_content, self.options)

                if len(split_messages) > 1:
                    # Update the first message with the original metadata
                    for key in message:
                        if key != "content" and key not in split_messages[0]:
                            split_messages[0][key] = message[key]
                    messages = split_messages
                else:
                    messages = [message]
            else:
                # No thread splitting - treat as single message
                messages = [message]

            # Clean message content
            for msg in messages:
                if "content" in msg:
                    msg["content"] = clean_message(msg["content"], self.options)

            # Sort messages chronologically based on sort_order option
            messages.sort(
                key=lambda m: m.get("date") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                reverse=(self.options.sort_order == "desc"),
            )

            # Extract metadata from original message
            metadata = self.extract_metadata(eml_msg)

            # Convert to AST
            doc = self.format_email_chain_as_ast(messages)
            doc.metadata = metadata.to_dict()
            return doc

        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(
                f"Failed to process email content: {str(e)}", parsing_stage="content_processing", original_error=e
            ) from e

    def format_email_chain_as_ast(self, eml_chain: list[dict[str, Any]]) -> Document:
        """Convert email chain to AST Document.

        Parameters
        ----------
        eml_chain : list[dict[str, Any]]
            List of email dictionaries with 'from', 'to', 'subject', 'date', 'content'

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        for item in eml_chain:
            # Add subject as H1 heading if requested
            if self.options.subject_as_h1 and "subject" in item and item["subject"]:
                children.append(Heading(level=1, content=[Text(content=item["subject"])]))

            # Add email headers as paragraphs if requested
            if self.options.include_headers:
                header_lines = []
                if "from" in item:
                    header_lines.append(f"From: {item['from']}")
                if "to" in item:
                    header_lines.append(f"To: {item['to']}")

                if item.get("cc"):
                    header_lines.append(f"cc: {item['cc']}")

                if "date" in item and item["date"] is not None:
                    formatted_date = self._format_date(item["date"])
                    if formatted_date:
                        header_lines.append(f"Date: {formatted_date}")

                # Only include subject in headers if not already shown as H1
                if not self.options.subject_as_h1 and "subject" in item:
                    header_lines.append(f"Subject: {item['subject']}")

                # Create a single paragraph with all headers (only if we have any)
                if header_lines:
                    header_text = "\n".join(header_lines)
                    children.append(Paragraph(content=[Text(content=header_text)]))

            # Add content - parse safely to avoid XSS via HTMLInline
            content = item.get("content", "")
            if content.strip():
                content_nodes = self._parse_email_content(content)
                children.extend(content_nodes)

            # Add separator
            children.append(ThematicBreak())

        # Append attachment footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        return Document(children=children)

    def _parse_email_content(self, content: str) -> list[Node]:
        """Parse email content into AST nodes safely.

        This method avoids using HTMLInline which bypasses renderer sanitization.
        Content is treated as plain text and split into paragraphs.

        Parameters
        ----------
        content : str
            Email content (plain text or markdown)

        Returns
        -------
        list[Node]
            List of AST nodes (paragraphs)

        """
        nodes: list[Node] = []

        # Split content into paragraphs (by double newlines)
        paragraphs = re.split(r"\n\n+", content.strip())

        for para_text in paragraphs:
            para_text = para_text.strip()
            if not para_text:
                continue

            # Create paragraph with Text nodes
            # This is safe and doesn't bypass sanitization like HTMLInline would
            nodes.append(Paragraph(content=[Text(content=para_text)]))

        return nodes if nodes else [Paragraph(content=[Text(content=content)])]

    def _format_date(self, dt: datetime.datetime | None) -> str:
        """Format datetime according to EmlOptions configuration.

        Parameters
        ----------
        dt : datetime.datetime | None
            Datetime to format

        Returns
        -------
        str
            Formatted date string

        """
        if dt is None:
            return ""

        if self.options.date_format_mode == "iso8601":
            return dt.isoformat()
        elif self.options.date_format_mode == "locale":
            return dt.strftime("%c")
        else:  # strftime mode
            return dt.strftime(self.options.date_strftime_pattern)

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from email message.

        Parameters
        ----------
        document : EmailMessage | Message
            Email message object

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract subject as title
        subject = document.get("Subject", "")
        if subject:
            metadata.title = subject.strip()

        # Extract from address as author
        from_header = document.get("From", "")
        if from_header:
            # Parse email addresses
            from_list = getaddresses([from_header])
            if from_list:
                name, email = from_list[0]
                metadata.author = name if name else email

        # Extract date
        date_obj = _parse_date_with_fallback(document)
        if date_obj:
            metadata.creation_date = date_obj

        # Extract additional email-specific metadata
        to_header = document.get("To", "")
        if to_header:
            to_list = getaddresses([to_header])
            metadata.custom["to"] = [f"{name} <{email}>" if name else email for name, email in to_list]

        cc_header = document.get("Cc", "")
        if cc_header:
            cc_list = getaddresses([cc_header])
            metadata.custom["cc"] = [f"{name} <{email}>" if name else email for name, email in cc_list]

        # Message ID
        message_id = document.get("Message-ID", "")
        if message_id:
            metadata.custom["message_id"] = message_id.strip()

        # Reply-To
        reply_to = document.get("Reply-To", "")
        if reply_to:
            metadata.custom["reply_to"] = reply_to.strip()

        # In-Reply-To (for threading)
        in_reply_to = document.get("In-Reply-To", "")
        if in_reply_to:
            metadata.custom["in_reply_to"] = in_reply_to.strip()

        # References (for threading)
        references = document.get("References", "")
        if references:
            metadata.custom["references"] = references.strip()

        # X-Mailer or User-Agent
        mailer = document.get("X-Mailer", "") or document.get("User-Agent", "")
        if mailer:
            metadata.creator = mailer.strip()

        # Priority/Importance
        priority = document.get("X-Priority", "") or document.get("Importance", "")
        if priority:
            metadata.custom["priority"] = priority.strip()

        # Content type
        content_type = document.get_content_type()
        if content_type:
            metadata.custom["content_type"] = content_type

        # Organization
        org = document.get("Organization", "")
        if org:
            metadata.custom["organization"] = org.strip()

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="eml",
    extensions=[".eml", ".msg"],
    mime_types=["message/rfc822"],
    magic_bytes=[
        (b"Return-Path:", 0),
        (b"Received:", 0),
        (b"From:", 0),
        (b"To:", 0),
        (b"Subject:", 0),
        (b"Content-Type:", 0),
        (b"MIME-Version:", 0),
    ],
    parser_class=EmlToAstConverter,
    renderer_class=None,
    parser_required_packages=[],
    renderer_required_packages=[],
    parser_options_class=EmlOptions,
    renderer_options_class=None,
    description="Convert email messages to Markdown",
    priority=6,
)
