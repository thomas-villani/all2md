#  Copyright (c) 2025 Tom Villani, Ph.D.
# src/all2md/parsers/eml2markdown.py
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

    >>> from all2md.parsers.eml2markdown import eml_to_markdown
    >>> with open('message.eml', 'r') as f:
    ...     result = eml_to_markdown(f)
    >>> print(result)

Note
----
Email parsing relies on proper EML format compliance. Malformed emails
may result in partial parsing or missing information. The module attempts
to handle common encoding issues and format variations gracefully.
"""

import datetime
from email import message_from_binary_file, message_from_bytes, message_from_file, policy
from email.message import EmailMessage, Message
from email.utils import getaddresses
from io import StringIO
from pathlib import Path
from typing import IO, Union

from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import InputError, MarkdownConversionError
from all2md.options import EmlOptions, MarkdownOptions
from all2md.parsers.eml import _parse_date_with_fallback, parse_single_message, split_chain, process_email_attachments, \
    clean_message
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled


# TODO: remove


# TODO: remove in lieu of proper html2markdown converter


def extract_eml_metadata(msg: EmailMessage | Message, options: EmlOptions) -> DocumentMetadata:
    """Extract metadata from email message.

    Parameters
    ----------
    msg : EmailMessage | Message
        Email message object
    options : EmlOptions
        Email conversion options

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Extract subject as title
    subject = msg.get('Subject', '')
    if subject:
        metadata.title = subject.strip()

    # Extract from address as author
    from_header = msg.get('From', '')
    if from_header:
        # Parse email addresses
        from_list = getaddresses([from_header])
        if from_list:
            name, email = from_list[0]
            metadata.author = name if name else email

    # Extract date
    date_obj = _parse_date_with_fallback(msg, options)
    if date_obj:
        metadata.creation_date = date_obj

    # Extract additional email-specific metadata
    to_header = msg.get('To', '')
    if to_header:
        to_list = getaddresses([to_header])
        metadata.custom['to'] = [f"{name} <{email}>" if name else email for name, email in to_list]

    cc_header = msg.get('Cc', '')
    if cc_header:
        cc_list = getaddresses([cc_header])
        metadata.custom['cc'] = [f"{name} <{email}>" if name else email for name, email in cc_list]

    # Message ID
    message_id = msg.get('Message-ID', '')
    if message_id:
        metadata.custom['message_id'] = message_id.strip()

    # Reply-To
    reply_to = msg.get('Reply-To', '')
    if reply_to:
        metadata.custom['reply_to'] = reply_to.strip()

    # In-Reply-To (for threading)
    in_reply_to = msg.get('In-Reply-To', '')
    if in_reply_to:
        metadata.custom['in_reply_to'] = in_reply_to.strip()

    # References (for threading)
    references = msg.get('References', '')
    if references:
        metadata.custom['references'] = references.strip()

    # X-Mailer or User-Agent
    mailer = msg.get('X-Mailer', '') or msg.get('User-Agent', '')
    if mailer:
        metadata.creator = mailer.strip()

    # Priority/Importance
    priority = msg.get('X-Priority', '') or msg.get('Importance', '')
    if priority:
        metadata.custom['priority'] = priority.strip()

    # Content type
    content_type = msg.get_content_type()
    if content_type:
        metadata.custom['content_type'] = content_type

    # Organization
    org = msg.get('Organization', '')
    if org:
        metadata.custom['organization'] = org.strip()

    return metadata


def eml_to_markdown(input_data: Union[str, Path, IO[bytes]], options: EmlOptions | None = None) -> str:
    """Parse EML file containing email chain into Markdown format.

    Processes email files (.eml format) using enhanced parsing with robust
    multipart handling, date fallbacks, quote processing, and URL cleaning.
    Handles complex email structures and preserves thread hierarchy.

    Parameters
    ----------
    input_data : str, Path, or IO[bytes]
        Path to the EML file as a string or Path object, or binary file object containing
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

        >>> markdown = eml_to_markdown('conversation.eml')
        >>> print(markdown)

    Parse with custom options:

        >>> opts = EmlOptions(
        ...     date_format_mode="iso8601",
        ...     convert_html_to_markdown=True,
        ...     clean_quotes=True
        ... )
        >>> markdown = eml_to_markdown('conversation.eml', options=opts)

    Notes
    -----
    - Uses EmailMessage with policy=default for robust parsing
    - Handles multipart messages with text/plain preference
    - Supports HTML-to-Markdown conversion when enabled
    - Enhanced date parsing with fallback hierarchy (Date -> Sent -> Received)
    - Configurable quote cleaning and URL unwrapping
    - Preserves message threading and reply relationships
    - Supports file paths and binary file objects as input
    """
    # Initialize options with defaults
    if options is None:
        options = EmlOptions()

    # Validate and process input with robust binary parsing
    try:
        if isinstance(input_data, (str, Path)):
            # Use binary file reading to avoid encoding assumptions
            with open(input_data, 'rb') as f:
                eml_msg = message_from_binary_file(f, policy=policy.default)
        elif isinstance(input_data, StringIO):
            # StringIO already contains text, use text parser
            eml_msg = message_from_file(input_data, policy=policy.default)
        elif hasattr(input_data, 'read'):
            # Handle IO[bytes] - read binary data and parse directly
            input_data.seek(0)  # Ensure we're at the beginning
            content = input_data.read()
            if isinstance(content, bytes):
                eml_msg = message_from_bytes(content, policy=policy.default)
            else:
                # If it's text, convert to string and parse
                eml_msg = message_from_file(StringIO(str(content)), policy=policy.default)
        else:
            raise InputError(
                f"Unsupported input type: {type(input_data).__name__}. Expected str, Path, or binary file object",
                parameter_name="input_data",
                parameter_value=input_data,
            )
    except Exception as e:
        if isinstance(e, (InputError, MarkdownConversionError)):
            raise
        else:
            raise MarkdownConversionError(
                f"Failed to parse email data: {str(e)}",
                conversion_stage="email_parsing",
                original_error=e
            ) from e

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_eml_metadata(eml_msg, options)

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

        # Sort messages chronologically based on sort_order option
        messages.sort(
            key=lambda m: m.get("date") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
            reverse=(options.sort_order == "desc")
        )

        # Use AST-based conversion path
        from all2md.parsers.eml import EmlToAstConverter
        from all2md.ast import MarkdownRenderer

        # Convert to AST
        ast_converter = EmlToAstConverter(options)
        ast_document = ast_converter.format_email_chain_as_ast(messages)

        # Render AST to markdown
        md_opts = options.markdown_options if options.markdown_options else MarkdownOptions()
        renderer = MarkdownRenderer(md_opts)
        result = renderer.render(ast_document)

        # Prepend metadata if enabled
        result = prepend_metadata_if_enabled(result.strip(), metadata, options.extract_metadata)

        return result

    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to process email content: {str(e)}",
            conversion_stage="content_processing",
            original_error=e
        ) from e


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
    ],
    converter_module="all2md.parsers.eml2markdown",
    converter_function="eml_to_markdown",
    required_packages=[],
    options_class="EmlOptions",
    description="Convert email messages to Markdown",
    priority=6
)
