#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/eml.py
"""Configuration options for EML (email) parsing.

This module defines options for parsing email files and message chains.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_CLEAN_QUOTES,
    DEFAULT_CLEAN_WRAPPED_URLS,
    DEFAULT_CONVERT_HTML_TO_MARKDOWN,
    DEFAULT_DATE_FORMAT_MODE,
    DEFAULT_DATE_STRFTIME_PATTERN,
    DEFAULT_DETECT_REPLY_SEPARATORS,
    DEFAULT_EMAIL_SORT_ORDER,
    DEFAULT_EML_ATTACH_SECTION_TITLE,
    DEFAULT_EML_INCLUDE_ATTACH_SECTION_HEADING,
    DEFAULT_EML_INCLUDE_HTML_PARTS,
    DEFAULT_EML_INCLUDE_PLAIN_PARTS,
    DEFAULT_EML_SUBJECT_AS_H1,
    DEFAULT_NORMALIZE_HEADERS,
    DEFAULT_PRESERVE_RAW_HEADERS,
    DEFAULT_URL_WRAPPERS,
    DateFormatMode,
    EmailSortOrder,
)
from all2md.options.base import BaseParserOptions
from all2md.options.common import AttachmentOptionsMixin, NetworkFetchOptions


@dataclass(frozen=True)
class EmlOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for EML-to-Markdown conversion.

    This dataclass contains settings specific to email message processing,
    including robust parsing, date handling, quote processing, and URL cleaning.
    Inherits attachment handling from AttachmentOptionsMixin for email attachments.

    Parameters
    ----------
    include_headers : bool, default True
        Whether to include email headers (From, To, Subject, Date) in output.
    preserve_thread_structure : bool, default True
        Whether to maintain email thread/reply chain structure.
    date_format_mode : {"iso8601", "locale", "strftime"}, default "strftime"
        How to format dates in output:
        - "iso8601": Use ISO 8601 format (2023-01-01T10:00:00Z)
        - "locale": Use system locale-aware formatting
        - "strftime": Use custom strftime pattern
    date_strftime_pattern : str, default "%m/%d/%y %H:%M"
        Custom strftime pattern when date_format_mode is "strftime".
    convert_html_to_markdown : bool, default False
        Whether to convert HTML content to Markdown
        When True, HTML parts are converted to Markdown; when False, HTML is preserved as-is.
    clean_quotes : bool, default True
        Whether to clean and normalize quoted content ("> " prefixes, etc.).
    detect_reply_separators : bool, default True
        Whether to detect common reply separators like "On <date>, <name> wrote:".
    normalize_headers : bool, default True
        Whether to normalize header casing and whitespace.
    preserve_raw_headers : bool, default False
        Whether to preserve both raw and decoded header values.
    clean_wrapped_urls : bool, default True
        Whether to clean URL defense/safety wrappers from links.
    url_wrappers : list[str], default from constants
        List of URL wrapper domains to clean (urldefense.com, safelinks, etc.).

    Examples
    --------
    Convert email with ISO 8601 date formatting:
        >>> options = EmlOptions(date_format_mode="iso8601")

    Convert with HTML-to-Markdown conversion enabled:
        >>> options = EmlOptions(convert_html_to_markdown=True)

    Disable quote cleaning and URL unwrapping:
        >>> options = EmlOptions(clean_quotes=False, clean_wrapped_urls=False)

    """

    include_headers: bool = field(
        default=True,
        metadata={
            "help": "Include email headers (From, To, Subject, Date) in output",
            "cli_name": "no-include-headers",
            "importance": "core",
        },
    )
    preserve_thread_structure: bool = field(
        default=True,
        metadata={
            "help": "Maintain email thread/reply chain structure",
            "cli_name": "no-preserve-thread-structure",
            "importance": "core",
        },
    )
    date_format_mode: DateFormatMode = field(
        default=DEFAULT_DATE_FORMAT_MODE,
        metadata={"help": "Date formatting mode: iso8601, locale, or strftime", "importance": "advanced"},
    )
    date_strftime_pattern: str = field(
        default=DEFAULT_DATE_STRFTIME_PATTERN,
        metadata={"help": "Custom strftime pattern for date formatting", "importance": "advanced"},
    )
    convert_html_to_markdown: bool = field(
        default=DEFAULT_CONVERT_HTML_TO_MARKDOWN,
        metadata={"help": "Convert HTML content to Markdown", "importance": "core"},
    )
    clean_quotes: bool = field(
        default=DEFAULT_CLEAN_QUOTES, metadata={"help": "Clean and normalize quoted content", "importance": "advanced"}
    )
    detect_reply_separators: bool = field(
        default=DEFAULT_DETECT_REPLY_SEPARATORS,
        metadata={"help": "Detect common reply separators", "importance": "advanced"},
    )
    normalize_headers: bool = field(
        default=DEFAULT_NORMALIZE_HEADERS,
        metadata={"help": "Normalize header casing and whitespace", "importance": "advanced"},
    )
    preserve_raw_headers: bool = field(
        default=DEFAULT_PRESERVE_RAW_HEADERS,
        metadata={"help": "Preserve both raw and decoded header values", "importance": "advanced"},
    )
    clean_wrapped_urls: bool = field(
        default=DEFAULT_CLEAN_WRAPPED_URLS,
        metadata={"help": "Clean URL defense/safety wrappers from links", "importance": "security"},
    )
    url_wrappers: list[str] | None = field(
        default_factory=lambda: DEFAULT_URL_WRAPPERS.copy(),
        metadata={"help": "URL wrappers (e.g. 'urldefense') to strip from links", "importance": "security"},
    )

    # Network security options for HTML conversion (when convert_html_to_markdown=True)
    html_network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for HTML part conversion",
            "cli_flatten": True,  # Nested, handled separately
        },
    )

    # Advanced EML options
    sort_order: EmailSortOrder = field(
        default=DEFAULT_EMAIL_SORT_ORDER,
        metadata={
            "help": "Email chain sort order: 'asc' (oldest first) or 'desc' (newest first)",
            "choices": ["asc", "desc"],
            "importance": "advanced",
        },
    )
    subject_as_h1: bool = field(
        default=DEFAULT_EML_SUBJECT_AS_H1,
        metadata={
            "help": "Include subject line as H1 heading",
            "cli_name": "no-subject-as-h1",
            "importance": "advanced",
        },
    )
    include_attach_section_heading: bool = field(
        default=DEFAULT_EML_INCLUDE_ATTACH_SECTION_HEADING,
        metadata={
            "help": "Include heading before attachments section",
            "cli_name": "no-include-attach-section-heading",
            "importance": "advanced",
        },
    )
    attach_section_title: str = field(
        default=DEFAULT_EML_ATTACH_SECTION_TITLE,
        metadata={"help": "Title for attachments section heading", "importance": "advanced"},
    )
    include_html_parts: bool = field(
        default=DEFAULT_EML_INCLUDE_HTML_PARTS,
        metadata={
            "help": "Include HTML content parts from emails",
            "cli_name": "no-include-html-parts",
            "importance": "advanced",
        },
    )
    include_plain_parts: bool = field(
        default=DEFAULT_EML_INCLUDE_PLAIN_PARTS,
        metadata={
            "help": "Include plain text content parts from emails",
            "cli_name": "no-include-plain-parts",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate and ensure immutability by defensively copying mutable collections.

        Calls parent class validation and adds defensive copying for url_wrappers.
        """
        # Call parent's __post_init__ for validation
        super().__post_init__()

        # Defensive copy of mutable collections to ensure immutability
        if self.url_wrappers is not None:
            object.__setattr__(self, "url_wrappers", list(self.url_wrappers))
