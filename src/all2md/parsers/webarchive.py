#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/webarchive.py
"""Safari WebArchive parser that converts .webarchive files to AST representation.

This module provides the WebArchiveToAstConverter class that parses Safari WebArchive
files (binary plist format) and builds an AST representation.
"""

from __future__ import annotations

import logging
import plistlib
from pathlib import Path
from typing import IO, Any, Optional, Union
from urllib.parse import urlparse

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.constants import DEPS_WEBARCHIVE
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError, ParsingError
from all2md.options.webarchive import WebArchiveOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.html import HtmlToAstConverter
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class WebArchiveToAstConverter(BaseParser):
    """Convert Safari WebArchive files to AST representation.

    This parser extracts HTML content from Safari WebArchive files (binary plist
    format) and converts it to AST using the HTML parser.

    Parameters
    ----------
    options : WebArchiveOptions or None
        WebArchive conversion options

    Examples
    --------
    Basic usage:
        >>> from all2md.parsers.webarchive import WebArchiveToAstConverter
        >>> from all2md.options.webarchive import WebArchiveOptions
        >>> parser = WebArchiveToAstConverter()
        >>> doc = parser.parse("example.webarchive")

    Extract embedded resources:
        >>> options = WebArchiveOptions(
        ...     extract_subresources=True,
        ...     attachment_output_dir="./resources"
        ... )
        >>> parser = WebArchiveToAstConverter(options)
        >>> doc = parser.parse("example.webarchive")

    """

    def __init__(self, options: WebArchiveOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the WebArchive parser with options and progress callback."""
        BaseParser._validate_options_type(options, WebArchiveOptions, "webarchive")
        options = options or WebArchiveOptions()
        super().__init__(options, progress_callback)
        self.options: WebArchiveOptions = options
        self._html_parser = HtmlToAstConverter(self.options)

    @requires_dependencies("webarchive", DEPS_WEBARCHIVE)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse WebArchive file into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input WebArchive file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed WebArchive structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid WebArchive format
        MalformedFileError
            If the plist structure is invalid or corrupted

        """
        self._emit_progress("started", "Parsing WebArchive", current=0, total=1)

        # Parse WebArchive plist
        try:
            doc_input, input_type = validate_and_convert_input(
                input_data, supported_types=["path-like", "file-like", "bytes"], require_binary=True
            )

            if input_type == "path":
                with open(doc_input, "rb") as f:
                    archive_data = plistlib.load(f)
            else:  # file-like or bytes (both are file-like after validate_and_convert_input)
                archive_data = plistlib.load(doc_input)

        except plistlib.InvalidFileException as e:
            raise MalformedFileError(f"Invalid WebArchive plist format: {e}", file_path=None, original_error=e) from e
        except Exception as e:
            raise ParsingError(
                f"Failed to parse WebArchive file: {e}", parsing_stage="plist_parsing", original_error=e
            ) from e

        # Extract main HTML content
        html_content = self._extract_main_html(archive_data)

        if not html_content:
            raise ParsingError("No HTML content found in WebArchive", parsing_stage="content_extraction")

        # Extract subresources if requested
        if self.options.extract_subresources and self.options.attachment_output_dir:
            self._extract_subresources(archive_data)

        # Convert HTML to AST
        doc = self._html_parser.convert_to_ast(html_content)

        # Handle subframes if requested
        if self.options.handle_subframes:
            self._process_subframes(archive_data, doc)

        # Extract and attach metadata
        metadata = self.extract_metadata(archive_data, html_content)
        doc.metadata = metadata.to_dict()

        self._emit_progress("finished", "WebArchive parsing completed", current=1, total=1)

        return doc

    def _extract_main_html(self, archive_data: dict[str, Any]) -> str:
        """Extract main HTML content from WebArchive plist.

        Parameters
        ----------
        archive_data : dict
            Parsed WebArchive plist data

        Returns
        -------
        str
            HTML content

        Raises
        ------
        ParsingError
            If WebMainResource is missing or invalid

        """
        main_resource = archive_data.get("WebMainResource")
        if not main_resource:
            raise ParsingError("WebMainResource not found in WebArchive", parsing_stage="content_extraction")

        # Extract the resource data
        html_data = main_resource.get("WebResourceData")
        if not html_data:
            raise ParsingError("WebResourceData not found in WebMainResource", parsing_stage="content_extraction")

        # Get encoding (default to UTF-8)
        encoding = main_resource.get("WebResourceTextEncodingName", "UTF-8")

        # Decode HTML content
        try:
            if isinstance(html_data, bytes):
                html_content = html_data.decode(encoding, errors="replace")
            else:
                html_content = str(html_data)
        except Exception as e:
            logger.warning(f"Failed to decode HTML with encoding {encoding}, using UTF-8: {e}")
            try:
                html_content = html_data.decode("utf-8", errors="replace")
            except Exception as e2:
                raise ParsingError(
                    f"Failed to decode HTML content: {e2}", parsing_stage="content_decoding", original_error=e2
                ) from e2

        return html_content

    def _extract_subresources(self, archive_data: dict[str, Any]) -> None:
        """Extract embedded resources from WebSubresources.

        Parameters
        ----------
        archive_data : dict
            Parsed WebArchive plist data

        """
        subresources = archive_data.get("WebSubresources", [])
        if not subresources:
            logger.debug("No WebSubresources found in WebArchive")
            return

        if not self.options.attachment_output_dir:
            logger.warning("extract_subresources=True but attachment_output_dir not set")
            return

        output_dir = Path(self.options.attachment_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for resource in subresources:
            try:
                # Get resource data and metadata
                resource_data = resource.get("WebResourceData")
                resource_url = resource.get("WebResourceURL", "")
                mime_type = resource.get("WebResourceMIMEType", "")

                if not resource_data:
                    continue

                # Extract filename from URL
                if resource_url:
                    filename = Path(resource_url).name
                else:
                    # Generate filename from MIME type
                    ext = self._mime_to_extension(mime_type)
                    filename = f"resource_{id(resource)}{ext}"

                # Write resource to file
                output_file = output_dir / filename
                if isinstance(resource_data, bytes):
                    output_file.write_bytes(resource_data)
                else:
                    output_file.write_text(str(resource_data))

                logger.debug(f"Extracted resource: {filename} ({mime_type})")

            except Exception as e:
                logger.warning(f"Failed to extract resource: {e}")
                continue

    def _process_subframes(self, archive_data: dict[str, Any], doc: Document) -> None:
        """Process nested iframe content from WebSubframeArchives.

        Parameters
        ----------
        archive_data : dict
            Parsed WebArchive plist data
        doc : Document
            Main document to append subframe content to

        """
        subframes = archive_data.get("WebSubframeArchives", [])
        if not subframes:
            return

        for idx, subframe in enumerate(subframes):
            try:
                # Extract HTML from subframe
                html_content = self._extract_main_html(subframe)

                if not html_content:
                    continue

                # Get frame name/title if available
                frame_resource = subframe.get("WebMainResource", {})
                frame_name = frame_resource.get("WebResourceFrameName", f"Frame {idx + 1}")

                # Add section heading for frame
                doc.children.append(Heading(level=2, content=[Text(content=f"Nested Frame: {frame_name}")]))

                # Convert frame HTML to AST
                frame_doc = self._html_parser.convert_to_ast(html_content)

                # Append frame content to main document
                doc.children.extend(frame_doc.children)

            except Exception as e:
                logger.warning(f"Failed to process subframe {idx}: {e}")
                doc.children.append(Paragraph(content=[Text(content=f"(Error processing nested frame: {e})")]))
                continue

    def _mime_to_extension(self, mime_type: str) -> str:
        """Convert MIME type to file extension.

        Parameters
        ----------
        mime_type : str
            MIME type string

        Returns
        -------
        str
            File extension (with leading dot)

        """
        mime_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/svg+xml": ".svg",
            "image/webp": ".webp",
            "text/css": ".css",
            "text/javascript": ".js",
            "application/javascript": ".js",
            "application/json": ".json",
            "text/html": ".html",
        }
        return mime_map.get(mime_type.lower(), ".bin")

    def extract_metadata(self, archive_data: dict[str, Any], html_content: str = "") -> DocumentMetadata:
        """Extract metadata from WebArchive plist.

        Parameters
        ----------
        archive_data : dict
            Parsed WebArchive plist data
        html_content : str, optional
            HTML content for additional metadata extraction

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        main_resource = archive_data.get("WebMainResource", {})

        # Extract URL as title
        url = main_resource.get("WebResourceURL")
        if url:
            metadata.custom["url"] = str(url)
            # Use domain/path as title if no better title found

            parsed = urlparse(str(url))
            if parsed.netloc:
                metadata.title = f"{parsed.netloc}{parsed.path}"

        # Extract MIME type
        mime_type = main_resource.get("WebResourceMIMEType")
        if mime_type:
            metadata.custom["mime_type"] = str(mime_type)

        # Extract encoding
        encoding = main_resource.get("WebResourceTextEncodingName")
        if encoding:
            metadata.custom["encoding"] = str(encoding)

        # Extract frame name if present
        frame_name = main_resource.get("WebResourceFrameName")
        if frame_name:
            metadata.custom["frame_name"] = str(frame_name)

        # Count subresources and subframes
        subresources = archive_data.get("WebSubresources", [])
        subframes = archive_data.get("WebSubframeArchives", [])

        if subresources:
            metadata.custom["subresource_count"] = len(subresources)
        if subframes:
            metadata.custom["subframe_count"] = len(subframes)

        # Extract title from HTML if available
        if html_content:
            try:
                from bs4 import BeautifulSoup
                from bs4.element import Tag

                soup = BeautifulSoup(html_content, "html.parser")

                # Get title from HTML
                title_tag = soup.find("title")
                if isinstance(title_tag, Tag) and title_tag.string:
                    metadata.title = str(title_tag.string).strip()

            except ImportError:
                pass  # BeautifulSoup not available

        return metadata


CONVERTER_METADATA = ConverterMetadata(
    format_name="webarchive",
    extensions=[".webarchive"],
    mime_types=["application/x-webarchive"],
    magic_bytes=[
        (b"bplist00", 0),  # Binary plist header
    ],
    parser_class=WebArchiveToAstConverter,
    renderer_class=None,
    parser_required_packages=[("beautifulsoup4", "bs4", "")],
    renderer_required_packages=[],
    import_error_message="WebArchive conversion requires 'beautifulsoup4'. Install with: pip install beautifulsoup4",
    parser_options_class=WebArchiveOptions,
    renderer_options_class=None,
    description="Convert Safari WebArchive files to Markdown",
    priority=5,
)
