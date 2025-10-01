#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/mhtml2markdown.py
"""MHTML single-file web archive to Markdown conversion module.

This module provides functionality to convert MHTML files (.mht, .mhtml)
to Markdown. It parses the multipart MIME structure of the MHTML archive,
extracts the main HTML document, and processes embedded assets like images.

The converter works by locating the root HTML content and all related assets
referenced via Content-ID (cid:) or Content-Location. It then pre-processes
the HTML to inline these assets as base64 data URIs, creating a self-contained
HTML document. This document is then passed to the existing html2markdown
converter for the final transformation.

Key Features
------------
- Parses MHTML/MHT single-file web archives.
- Extracts the primary HTML content.
- Handles embedded assets (images) referenced by 'cid:' or 'file://'.
- Inlines assets as base64 data URIs for robust conversion.
- Leverages the existing `html2markdown` module for final conversion.
- Integrates with the unified attachment handling options.

Dependencies
------------
- beautifulsoup4: For pre-processing the HTML content.
- Standard library modules: email, base64, re.

Examples
--------
Basic conversion from a file path:

    >>> from all2md.converters.mhtml2markdown import mhtml_to_markdown
    >>> markdown = mhtml_to_markdown('archive.mht')
    >>> print(markdown)

Convert with a file-like object:

    >>> with open('archive.mhtml', 'rb') as f:
    ...     markdown = mhtml_to_markdown(f)
    >>> print(markdown)
"""

import base64
import email
import os
import re
from email import policy
from pathlib import Path
from typing import IO, TYPE_CHECKING, Union

if TYPE_CHECKING:
    pass

from all2md.converter_metadata import ConverterMetadata
from all2md.converters.html2markdown import html_to_markdown
from all2md.exceptions import InputError, MarkdownConversionError
from all2md.options import HtmlOptions, MarkdownOptions, MhtmlOptions
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled
from all2md.utils.security import validate_local_file_access


def extract_mhtml_metadata(msg: email.message.EmailMessage, html_content: str) -> DocumentMetadata:
    """Extract metadata from MHTML file.

    Parameters
    ----------
    msg : email.message.EmailMessage
        Parsed MHTML message
    html_content : str
        HTML content from the MHTML file

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Extract metadata from email headers
    subject = msg.get('Subject')
    if subject:
        metadata.title = str(subject).strip()

    from_header = msg.get('From')
    if from_header:
        metadata.author = str(from_header).strip()

    date_header = msg.get('Date')
    if date_header:
        metadata.creation_date = str(date_header).strip()

    # Extract additional email headers
    to_header = msg.get('To')
    if to_header:
        metadata.custom['to'] = str(to_header).strip()

    cc_header = msg.get('CC')
    if cc_header:
        metadata.custom['cc'] = str(cc_header).strip()

    message_id = msg.get('Message-ID')
    if message_id:
        metadata.custom['message_id'] = str(message_id).strip()

    x_mailer = msg.get('X-Mailer')
    if x_mailer:
        metadata.creator = str(x_mailer).strip()
    else:
        user_agent = msg.get('User-Agent')
        if user_agent:
            metadata.creator = str(user_agent).strip()

    # Extract metadata from HTML content using BeautifulSoup
    try:
        # Import BeautifulSoup here to handle dependencies gracefully
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # If BeautifulSoup is not available, skip HTML parsing
            return metadata

        soup = BeautifulSoup(html_content, 'html.parser')

        # Get title from HTML if not already set
        if not metadata.title:
            title_tag = soup.find('title')
            if title_tag and hasattr(title_tag, 'string') and title_tag.string:
                metadata.title = str(title_tag.string).strip()

        # Extract meta tags
        meta_tags = soup.find_all('meta')
        keywords_list = []

        for meta in meta_tags:
            # meta_tags are from find_all, need to check if they have get method
            if not hasattr(meta, 'get'):
                continue
            name_attr = meta.get('name')
            property_attr = meta.get('property')
            content_attr = meta.get('content')

            name = str(name_attr).lower() if name_attr else ''
            property_name = str(property_attr).lower() if property_attr else ''
            content = str(content_attr) if content_attr else ''

            if not content:
                continue

            # Standard meta tags
            if name == 'author' and not metadata.author:
                metadata.author = content.strip()
            elif name == 'description':
                metadata.subject = content.strip()
            elif name == 'keywords':
                # Split keywords by comma and add to list
                keywords_list.extend([k.strip() for k in content.split(',') if k.strip()])
            elif name == 'generator' and not metadata.creator:
                metadata.creator = content.strip()
            elif name == 'language':
                metadata.language = content.strip()
            elif name == 'created' or name == 'date-created':
                if not metadata.creation_date:
                    metadata.creation_date = content.strip()

            # Open Graph meta tags
            elif property_name == 'og:title' and not metadata.title:
                metadata.title = content.strip()
            elif property_name == 'og:description' and not metadata.subject:
                metadata.subject = content.strip()
            elif property_name == 'og:type':
                metadata.custom['og_type'] = content.strip()
            elif property_name == 'og:url':
                metadata.custom['og_url'] = content.strip()
            elif property_name == 'og:site_name':
                metadata.custom['site_name'] = content.strip()

            # Additional meta tags
            elif name == 'viewport':
                metadata.custom['viewport'] = content.strip()
            elif name == 'robots':
                metadata.custom['robots'] = content.strip()
            elif name == 'canonical':
                metadata.custom['canonical_url'] = content.strip()

        # Set keywords if any were found
        if keywords_list:
            metadata.keywords = keywords_list

        # Count assets and get basic document statistics
        images = soup.find_all('img')
        if images:
            metadata.custom['image_count'] = len(images)

        links = soup.find_all('a', href=True)
        if links:
            metadata.custom['link_count'] = len(links)

        # Get text content length (approximate)
        text_content = soup.get_text()
        if text_content:
            word_count = len(text_content.split())
            if word_count > 0:
                metadata.custom['word_count'] = word_count

    except Exception:
        # If HTML parsing fails, continue with email-only metadata
        pass

    return metadata


def mhtml_to_markdown(
        input_data: Union[str, Path, IO[bytes]], options: MhtmlOptions | None = None
) -> str:
    """Convert an MHTML single-file web archive to Markdown format.

    Processes MHTML files (.mht, .mhtml) by parsing the multipart MIME
    structure, extracting the main HTML document and its embedded assets
    (like images). It then converts the HTML content to Markdown.

    Parameters
    ----------
    input_data : str, os.PathLike, or file-like object
        MHTML file to convert. Can be:
        - String path to an MHTML file
        - pathlib.Path object pointing to an MHTML file
        - File-like object opened in binary mode (e.g., BytesIO)
    options : MhtmlOptions or None, default None
        Configuration options for MHTML conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown representation of the MHTML file's content.

    Raises
    ------
    InputError
        If input type is not supported or file cannot be read.
    MarkdownConversionError
        If the MHTML file is malformed or contains no HTML content.
    """
    # Import dependencies inside function to avoid import-time failures
    try:
        from bs4 import BeautifulSoup
    except ImportError as e:
        from all2md.exceptions import DependencyError
        raise DependencyError(
            converter_name="mhtml",
            missing_packages=[("beautifulsoup4", "")],
            install_command="pip install beautifulsoup4"
        ) from e

    if options is None:
        options = MhtmlOptions()

    try:
        doc_input, input_type = validate_and_convert_input(
            input_data, supported_types=["path-like", "file-like"], require_binary=True
        )

        if input_type == "path":
            with open(doc_input, "rb") as f:
                raw_data = f.read()
        elif input_type in ("file", "bytes"):
            raw_data = doc_input.read()
        else:
            raise InputError(f"Unsupported input type for MHTML conversion: {type(input_data).__name__}")

        msg = email.message_from_bytes(raw_data, policy=policy.default)
    except InputError:
        # Let InputError propagate directly
        raise
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to read or parse MHTML file: {e}", conversion_stage="mhtml_parsing", original_error=e
        ) from e

    # --- Extract HTML and assets ---
    html_string = None
    assets = {}  # Maps Content-ID and Content-Location to (data, filename, mime_type)

    # Find the root HTML part
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            # Payload could be bytes, Message, or Any - need to check
            if isinstance(payload, bytes):
                html_string = payload.decode(charset, errors="replace")
            elif payload is not None:
                html_string = str(payload)
            break  # Assume the first HTML part is the main document

    if not html_string:
        raise MarkdownConversionError(
            "No HTML content found in the MHTML file.",
            conversion_stage="mhtml_parsing"
        )

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_mhtml_metadata(msg, html_string)

    # Gather all assets
    for part in msg.walk():
        cid = part.get("Content-ID")
        location = part.get("Content-Location")
        filename = part.get_filename()

        if cid or location:
            asset_data = part.get_payload(decode=True)
            asset_info = (asset_data, filename, part.get_content_type())
            if cid:
                assets[cid.strip().lstrip("<").rstrip(">")] = asset_info
            if location:
                assets[location.strip()] = asset_info

    # --- Pre-process HTML to inline assets as data URIs and clean up MS Word artifacts ---
    soup = BeautifulSoup(html_string, "html.parser")

    # Handle asset inlining
    for tag in soup.find_all(src=re.compile(r"^(cid:|file://)")):
        # Tag from find_all could be various types, need to check if it has get method
        if not hasattr(tag, 'get'):
            continue
        src_attr = tag.get("src")
        if not src_attr:
            continue

        src = str(src_attr)
        asset_id = None

        if src.startswith("cid:"):
            asset_id = src[4:]
        elif src.startswith("file://"):
            # Security check for local file access
            if not validate_local_file_access(
                    src,
                    allow_local_files=options.local_files.allow_local_files,
                    local_file_allowlist=options.local_files.local_file_allowlist,
                    local_file_denylist=options.local_files.local_file_denylist,
                    allow_cwd_files=options.local_files.allow_cwd_files
            ):
                # Remove the tag if access is not allowed
                if hasattr(tag, 'decompose'):
                    tag.decompose()
                continue

            # Some browsers save MHTML with file:// based locations
            asset_id = os.path.basename(src)

        if asset_id and asset_id in assets:
            data, _, mime_type = assets[asset_id]
            if data and mime_type and mime_type.startswith("image/"):
                if isinstance(data, bytes):
                    b64_data = base64.b64encode(data).decode("utf-8")
                    if hasattr(tag, '__setitem__'):
                        tag["src"] = f"data:{mime_type};base64,{b64_data}"

    processed_html = str(soup)

    # Clean up Microsoft Word conditional comments and formatting artifacts while preserving list structure

    # Extract and replace list markers before removing conditional comments
    def replace_list_markers(match: re.Match[str]) -> str:
        content = match.group(0)
        # Look for bullet patterns: -, ·, o, ▪, etc.
        if re.search(r'[-·o▪•]', content):
            return '- '
        # Look for numbered patterns: 1., 2., etc.
        number_match = re.search(r'(\d+)\.', content)
        if number_match:
            return f"{number_match.group(1)}. "
        # Fallback to generic bullet
        return '- '

    # Replace MS Word list conditional comments with proper list markers
    processed_html = re.sub(r'<!--\[if !supportLists\]-->(.*?)<!--\[endif\]-->', replace_list_markers, processed_html,
                            flags=re.DOTALL)

    # Clean up remaining MS Word artifacts
    processed_html = re.sub(r'<!--\[if[^>]*\]-->.*?<!--\[endif\]-->', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<o:p[^>]*>.*?</o:p>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<v:[^>]*>.*?</v:[^>]*>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<w:[^>]*>.*?</w:[^>]*>', '', processed_html, flags=re.DOTALL)

    # Convert MS Word list paragraph classes to proper HTML list structure
    processed_html = re.sub(r'<p class="MsoListParagraph[^"]*"[^>]*>', '<li>', processed_html)
    processed_html = re.sub(r'<p[^>]*class="MsoListParagraph[^"]*"[^>]*>', '<li>', processed_html)

    # --- Convert the processed HTML to Markdown ---
    html_options = HtmlOptions(
        attachment_mode=options.attachment_mode,
        attachment_output_dir=options.attachment_output_dir,
        attachment_base_url=options.attachment_base_url,
        markdown_options=options.markdown_options or MarkdownOptions(),
        # Pass through HTML processing options
        strip_comments=options.strip_comments,
        links_as=options.links_as,
        collapse_whitespace=options.collapse_whitespace,
        br_handling=options.br_handling,
        allowed_elements=options.allowed_elements,
        allowed_attributes=options.allowed_attributes,
    )

    markdown_content = html_to_markdown(processed_html, options=html_options)

    # Prepend metadata if enabled
    result = prepend_metadata_if_enabled(markdown_content, metadata, options.extract_metadata)

    return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="mhtml",
    extensions=[".mhtml", ".mht"],
    mime_types=["multipart/related", "message/rfc822"],
    magic_bytes=[
        (b"MIME-Version:", 0),
    ],
    converter_module="all2md.converters.mhtml2markdown",
    converter_function="mhtml_to_markdown",
    required_packages=[("beautifulsoup4", "")],
    import_error_message="MHTML conversion requires 'beautifulsoup4'. Install with: pip install beautifulsoup4",
    options_class="MhtmlOptions",
    description="Convert MHTML web archives to Markdown",
    priority=5
)
