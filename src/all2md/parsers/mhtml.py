#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/mhtml.py
"""MHTML parser that converts MHTML files to AST representation.

This module provides the MhtmlToAstConverter class that parses MHTML
single-file web archives and builds an AST representation.
"""

from __future__ import annotations

import email
from email import policy
from pathlib import Path
from typing import IO, Any, Union

from all2md.ast import Document
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError, DependencyError
from all2md.options import MhtmlOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.html import HtmlToAstConverter
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata


class MhtmlToAstConverter(BaseParser):
    """Convert MHTML files to AST representation.

    This parser extracts HTML content from MHTML archives and converts
    it to AST using the HTML parser.

    Parameters
    ----------
    options : MhtmlOptions or None
        MHTML conversion options

    """

    def __init__(self, options: MhtmlOptions | None = None, progress_callback=None):
        options = options or MhtmlOptions()
        super().__init__(options, progress_callback)
        self.options: MhtmlOptions = options
        self._html_parser = HtmlToAstConverter(self.options)

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse MHTML file into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input MHTML file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed MHTML structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid MHTML format

        """
        try:
            import bs4
        except ImportError as e:
            raise DependencyError(
                converter_name="mhtml",
                missing_packages=[("bs4", "")],
            ) from e

        # Parse MHTML message
        try:
            doc_input, input_type = validate_and_convert_input(
                input_data, supported_types=["path-like", "file-like", "bytes"], require_binary=True
            )

            if input_type == "path":
                with open(doc_input, 'rb') as f:
                    msg = email.message_from_binary_file(f, policy=policy.default)
            elif input_type == "bytes":
                msg = email.message_from_bytes(doc_input, policy=policy.default)
            else:  # file-like
                msg = email.message_from_binary_file(doc_input, policy=policy.default)

        except Exception as e:
            raise ParsingError(
                f"Failed to parse MHTML file: {e}",
                parsing_stage="mhtml_parsing",
                original_error=e
            ) from e

        # Extract HTML content
        html_content = self._extract_html_from_mhtml(msg)

        if not html_content:
            raise ParsingError(
                "No HTML content found in MHTML file",
                parsing_stage="content_extraction"
            )

        # Convert HTML to AST
        doc = self._html_parser.convert_to_ast(html_content)

        # Extract and attach metadata
        metadata = self.extract_metadata(msg, html_content)
        doc.metadata = metadata.to_dict()

        return doc

    def _extract_html_from_mhtml(self, msg: email.message.EmailMessage) -> str:
        """Extract HTML content from MHTML message.

        Parameters
        ----------
        msg : email.message.EmailMessage
            Parsed MHTML message

        Returns
        -------
        str
            HTML content

        """
        html_content = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_content = payload.decode('utf-8', errors='ignore')
                        break
        else:
            if msg.get_content_type() == 'text/html':
                payload = msg.get_payload(decode=True)
                if payload:
                    html_content = payload.decode('utf-8', errors='ignore')

        return html_content

    def extract_metadata(self, document: Any, html_content: str = "") -> DocumentMetadata:
        """Extract metadata from MHTML message.

        Parameters
        ----------
        document : email.message.EmailMessage
            MHTML message object
        html_content : str, optional
            HTML content for additional metadata extraction

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract metadata from email headers
        subject = document.get('Subject')
        if subject:
            metadata.title = str(subject).strip()

        from_header = document.get('From')
        if from_header:
            metadata.author = str(from_header).strip()

        date_header = document.get('Date')
        if date_header:
            metadata.creation_date = str(date_header).strip()

        # Extract additional headers
        to_header = document.get('To')
        if to_header:
            metadata.custom['to'] = str(to_header).strip()

        message_id = document.get('Message-ID')
        if message_id:
            metadata.custom['message_id'] = str(message_id).strip()

        x_mailer = document.get('X-Mailer')
        if x_mailer:
            metadata.creator = str(x_mailer).strip()

        # Extract from HTML content if available
        if html_content:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # Get title from HTML if not already set
                if not metadata.title:
                    title_tag = soup.find('title')
                    if title_tag and title_tag.string:
                        metadata.title = str(title_tag.string).strip()

                # Extract meta keywords
                meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                if meta_keywords and meta_keywords.get('content'):
                    keywords_str = str(meta_keywords.get('content'))
                    metadata.keywords = [k.strip() for k in keywords_str.split(',')]

            except ImportError:
                pass  # BeautifulSoup not available

        return metadata


CONVERTER_METADATA = ConverterMetadata(
    format_name="mhtml",
    extensions=[".mhtml", ".mht"],
    mime_types=["multipart/related", "message/rfc822"],
    magic_bytes=[
        (b"MIME-Version:", 0),
    ],
    parser_class=MhtmlToAstConverter,
    renderer_class=None,
    parser_required_packages=[("beautifulsoup4", "bs4", "")],
    renderer_required_packages=[],
    import_error_message="MHTML conversion requires 'beautifulsoup4'. Install with: pip install beautifulsoup4",
    parser_options_class=MhtmlOptions,
    renderer_options_class=None,
    description="Convert MHTML web archives to Markdown",
    priority=5
)
