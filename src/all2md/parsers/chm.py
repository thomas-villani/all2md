#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/chm.py
"""CHM (Microsoft Compiled HTML Help) parser that converts CHM files to AST representation.

This module provides the ChmParser class that parses CHM files, extracts HTML content
from pages, and builds an AST representation. CHM files are compressed archives of HTML
pages with a table of contents structure, commonly used for software documentation.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import Document, Heading, Node, Text, ThematicBreak
from all2md.constants import DEPS_CHM
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError, ValidationError
from all2md.options.chm import ChmOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.html import HtmlToAstConverter
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class ChmParser(BaseParser):
    """Convert CHM files to AST representation.

    This parser extracts content from Microsoft Compiled HTML Help (CHM) files,
    processes each page's HTML content, and builds a unified AST document.

    Parameters
    ----------
    options : ChmOptions or None
        CHM conversion options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates during parsing

    """

    def __init__(self, options: ChmOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the CHM parser with options and progress callback."""
        BaseParser._validate_options_type(options, ChmOptions, "chm")
        options = options or ChmOptions()
        super().__init__(options, progress_callback)
        self.options: ChmOptions = options
        # Create HTML parser with nested options, forwarding attachment settings from CHM options
        html_options = self.options.html_options
        if html_options is None:
            # Create new HtmlOptions with attachment settings from CHM options
            from all2md.options.html import HtmlOptions

            html_options = HtmlOptions(
                attachment_mode=self.options.attachment_mode,
                attachment_output_dir=self.options.attachment_output_dir,
                attachment_base_url=self.options.attachment_base_url,
                attachment_filename_template=self.options.attachment_filename_template,
                alt_text_mode=self.options.alt_text_mode,
                attachments_footnotes_section=self.options.attachments_footnotes_section,
            )
        self.html_parser = HtmlToAstConverter(html_options)

    @requires_dependencies("chm", DEPS_CHM)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse CHM file into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input CHM file to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw CHM bytes

        Returns
        -------
        Document
            AST Document node representing the parsed CHM structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid CHM format
        ValidationError
            If input data is invalid

        """
        from chm.chm import CHMFile

        # Handle file-like objects or bytes by creating a temporary file
        temp_file = None
        chm_path = None

        try:
            if hasattr(input_data, "read") and hasattr(input_data, "seek"):
                # File-like object - write to temp file
                input_data.seek(0)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".chm")
                temp_file.write(input_data.read())
                temp_file.close()
                chm_path = temp_file.name
            elif isinstance(input_data, bytes):
                # Raw bytes - write to temp file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".chm")
                temp_file.write(input_data)
                temp_file.close()
                chm_path = temp_file.name
            else:
                # Should be a path
                chm_path = str(input_data)

            # Open CHM file
            chm_file = CHMFile()
            result = chm_file.LoadCHM(chm_path)

            if result != 1:
                raise ParsingError(
                    "Failed to load CHM file. File may be corrupted or not a valid CHM format.",
                    parsing_stage="document_opening",
                )

            # Convert to AST
            doc = self.convert_to_ast(chm_file)

            # Extract and attach metadata
            metadata = self.extract_metadata(chm_file)
            doc.metadata = metadata.to_dict()

            return doc

        except (ParsingError, ValidationError):
            raise
        except Exception as e:
            raise ParsingError(
                f"Failed to read or parse CHM file: {e!r}",
                parsing_stage="document_opening",
                original_error=e,
            ) from e
        finally:
            # Clean up temp file if created
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass

    def convert_to_ast(self, chm_file: Any) -> Document:
        """Convert CHM file to AST Document.

        Parameters
        ----------
        chm_file : chm.chm.CHMFile
            CHM file object

        Returns
        -------
        Document
            AST document node

        """
        # Emit started event
        self._emit_progress("started", "Converting CHM document", current=0, total=1)

        children: list[Node] = []

        # Add table of contents if requested
        if self.options.include_toc:
            toc_nodes = self._build_toc(chm_file)
            if toc_nodes:
                children.extend(toc_nodes)
                children.append(ThematicBreak())

        # Get all topics/pages from CHM
        pages = self._enumerate_pages(chm_file)

        total_pages = len(pages)
        logger.info(f"Found {total_pages} pages in CHM file")

        # Process each page
        for idx, page_path in enumerate(pages, 1):
            try:
                # Emit progress for each page
                self._emit_progress(
                    "item_done",
                    f"Processing page {idx}/{total_pages}",
                    current=idx,
                    total=total_pages,
                    item_type="page",
                    page=idx,
                )

                # Extract HTML content from page
                html_content = self._get_page_content(chm_file, page_path)

                if html_content:
                    # Parse HTML with HtmlToAstConverter
                    page_doc = self.html_parser.convert_to_ast(html_content)

                    if page_doc.children:
                        children.extend(page_doc.children)

                        # Add page separator if not merging
                        if not self.options.merge_pages:
                            children.append(ThematicBreak())
            except Exception as e:
                logger.warning(f"Failed to process page {page_path}: {e}")
                # Continue with next page

        # Emit finished event
        self._emit_progress("finished", "CHM conversion completed", current=total_pages, total=total_pages)

        return Document(children=children)

    def _enumerate_pages(self, chm_file: Any) -> list[str]:
        """Enumerate all HTML pages in the CHM file.

        Parameters
        ----------
        chm_file : chm.chm.CHMFile
            CHM file object

        Returns
        -------
        list[str]
            List of page paths in the CHM file

        """
        pages: list[str] = []

        # Try to get topics from TOC
        try:
            topics = chm_file.GetTopicsTree()
            if topics:
                self._collect_topics_recursive(topics, pages)
        except Exception as e:
            logger.debug(f"Failed to get topics from TOC: {e}")

        # If no pages found via TOC, try to enumerate files
        if not pages:
            try:
                # Enumerate all items in CHM
                def enum_callback(chm_file: Any, ui: Any, context: Any) -> int:
                    """Collect HTML files from CHM."""
                    path = ui.path
                    # Check if it's an HTML file
                    if path and (path.endswith(".html") or path.endswith(".htm")):
                        context.append(path)
                    return 1  # Continue enumeration

                pages = []
                chm_file.Enumerate(0x00000000, enum_callback, pages)  # ENUMERATE_ALL
            except Exception as e:
                logger.warning(f"Failed to enumerate CHM contents: {e}")

        # If still no pages, try to get home page at least
        if not pages and hasattr(chm_file, "home") and chm_file.home:
            pages.append(chm_file.home)

        return pages

    def _collect_topics_recursive(self, node: Any, pages: list[str]) -> None:
        """Recursively collect topic paths from TOC tree.

        Parameters
        ----------
        node : Any
            TOC tree node
        pages : list[str]
            List to append page paths to

        """
        try:
            # Check if node has a Local property (page path)
            if hasattr(node, "Local") and node.Local:
                pages.append(node.Local)

            # Recursively process children
            if hasattr(node, "children"):
                for child in node.children:
                    self._collect_topics_recursive(child, pages)
        except Exception as e:
            logger.debug(f"Error collecting topics: {e}")

    def _get_page_content(self, chm_file: Any, page_path: str) -> str:
        """Retrieve HTML content from a CHM page.

        Parameters
        ----------
        chm_file : chm.chm.CHMFile
            CHM file object
        page_path : str
            Path to the page in the CHM archive

        Returns
        -------
        str
            HTML content of the page

        """
        try:
            # Resolve object
            obj = chm_file.ResolveObject(page_path)
            if obj[0] != 0:
                logger.warning(f"Failed to resolve CHM object: {page_path}")
                return ""

            # Retrieve content
            result = chm_file.RetrieveObject(obj[1])
            if result[0] != 0:
                logger.warning(f"Failed to retrieve CHM object: {page_path}")
                return ""

            # Decode bytes to string
            content_bytes = result[1]

            # Try to decode with common encodings
            for encoding in ["utf-8", "windows-1252", "iso-8859-1"]:
                try:
                    return content_bytes.decode(encoding)
                except (UnicodeDecodeError, AttributeError):
                    continue

            # Fallback: decode with errors='ignore'
            logger.warning(f"Unable to decode page {page_path} with common encodings, using fallback")
            return content_bytes.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.warning(f"Error retrieving page content for {page_path}: {e}")
            return ""

    def _build_toc(self, chm_file: Any) -> list[Node]:
        """Build table of contents from CHM.

        Parameters
        ----------
        chm_file : chm.chm.CHMFile
            CHM file object

        Returns
        -------
        list[Node]
            TOC nodes

        """
        nodes: list[Node] = []

        try:
            topics = chm_file.GetTopicsTree()
            if not topics:
                return nodes

            # Add TOC heading
            nodes.append(Heading(level=1, content=[Text(content="Table of Contents")]))

            # Process TOC items
            self._build_toc_recursive(topics, nodes, level=2)

        except Exception as e:
            logger.debug(f"Failed to build TOC: {e}")

        return nodes

    def _build_toc_recursive(self, node: Any, nodes: list[Node], level: int = 2) -> None:
        """Recursively build TOC from tree structure.

        Parameters
        ----------
        node : Any
            TOC tree node
        nodes : list[Node]
            List to append TOC nodes to
        level : int
            Heading level for this TOC item

        """
        try:
            # Add this node's title if it has one
            if hasattr(node, "title") and node.title:
                # Cap level at 6 (max heading level)
                actual_level = min(level, 6)
                nodes.append(Heading(level=actual_level, content=[Text(content=node.title)]))

            # Recursively process children
            if hasattr(node, "children"):
                for child in node.children:
                    self._build_toc_recursive(child, nodes, level + 1)
        except Exception as e:
            logger.debug(f"Error building TOC: {e}")

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from CHM file.

        Parameters
        ----------
        document : chm.chm.CHMFile
            CHM file object

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        Notes
        -----
        CHM files have limited metadata support. This method attempts to extract
        what's available, primarily from the title and home page.

        """
        metadata = DocumentMetadata()

        try:
            # Try to get title from CHM metadata
            if hasattr(document, "title") and document.title:
                metadata.title = document.title

            # If no title, try to extract from home page
            if not metadata.title and hasattr(document, "home") and document.home:
                try:
                    home_content = self._get_page_content(document, document.home)
                    if home_content:
                        # Parse home page to extract title
                        from bs4 import BeautifulSoup
                        from bs4.element import Tag

                        soup = BeautifulSoup(home_content, "html.parser")
                        title_tag = soup.find("title")
                        if isinstance(title_tag, Tag) and title_tag.string:
                            metadata.title = title_tag.string.strip()
                except Exception as e:
                    logger.debug(f"Failed to extract title from home page: {e}")

            # CHM files typically don't have author or other metadata
            # Could potentially extract from HTML meta tags if needed

        except Exception as e:
            logger.debug(f"Error extracting CHM metadata: {e}")

        return metadata


# Converter metadata for registry
CONVERTER_METADATA = ConverterMetadata(
    format_name="chm",
    extensions=[".chm"],
    mime_types=["application/vnd.ms-htmlhelp"],
    magic_bytes=[
        (b"ITSF", 0),  # CHM file signature
    ],
    parser_class=ChmParser,
    renderer_class=None,  # No renderer for CHM (parse-only format)
    parser_required_packages=[("pychm", "chm", "")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message=(
        "CHM conversion requires 'pychm'. "
        "Note: pychm also requires the CHMLib C library to be installed. "
        "Install with: pip install pychm"
    ),
    parser_options_class=ChmOptions,
    renderer_options_class=None,
    description="Convert Microsoft Compiled HTML Help (CHM) files to AST",
    priority=5,
)
