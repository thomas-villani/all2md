#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/epub.py
"""EPUB parser that converts EPUB files to AST representation.

This module provides the EpubToAstConverter class that parses EPUB files,
extracts HTML content from chapters, and builds an AST representation.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import Document, Heading, Node, Text, ThematicBreak
from all2md.constants import DEPS_EPUB
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError, ValidationError, ZipFileSecurityError
from all2md.options.epub import EpubOptions
from all2md.options.html import HtmlOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.html import HtmlToAstConverter
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.metadata import DocumentMetadata


class EpubToAstConverter(BaseParser):
    """Convert EPUB files to AST representation.

    This parser extracts content from EPUB files, processes each chapter's
    HTML content, and builds a unified AST document.

    Parameters
    ----------
    options : EpubOptions or None
        EPUB conversion options

    """

    def __init__(self, options: EpubOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the EPUB parser with options and progress callback."""
        BaseParser._validate_options_type(options, EpubOptions, "epub")
        options = options or EpubOptions()
        super().__init__(options, progress_callback)
        self.options: EpubOptions = options

        # Create HtmlOptions with attachment settings forwarded from EPUB options
        html_opts = self.options.html_options or HtmlOptions()
        html_opts = replace(
            html_opts,
            attachment_mode=self.options.attachment_mode,
            attachment_output_dir=self.options.attachment_output_dir,
            attachment_base_url=self.options.attachment_base_url,
            alt_text_mode=self.options.alt_text_mode,
            max_asset_size_bytes=self.options.max_asset_size_bytes,
        )
        self.html_parser = HtmlToAstConverter(html_opts)

    @requires_dependencies("epub", DEPS_EPUB)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse EPUB file into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input EPUB file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed EPUB structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid EPUB format

        """
        from ebooklib import epub

        # Handle file-like objects by creating a temporary file
        temp_file = None
        book = None

        # Validate ZIP archive and get path for ebooklib
        # Use validated_zip_input context manager to avoid double-reading
        temp_file = None
        if isinstance(input_data, (str, Path)):
            # Path inputs - validate directly
            self._validate_zip_security(input_data, suffix=".epub")
            epub_path = str(input_data)
        elif isinstance(input_data, bytes):
            # Bytes inputs - create temp file and validate
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".epub")
            temp_file.write(input_data)
            temp_file.close()
            self._validate_zip_security(temp_file.name, suffix=".epub")
            epub_path = temp_file.name
        elif hasattr(input_data, "read"):
            # File-like inputs - read and create temp file
            original_position = input_data.tell() if hasattr(input_data, "tell") else 0
            input_data.seek(0)
            data = input_data.read()
            input_data.seek(original_position)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".epub")
            temp_file.write(data)
            temp_file.close()
            self._validate_zip_security(temp_file.name, suffix=".epub")
            epub_path = temp_file.name
        else:
            # Fallback - should not reach here with proper type hints
            epub_path = str(input_data)

        try:
            book = epub.read_epub(epub_path)
        except (ParsingError, ZipFileSecurityError, ValidationError):
            raise
        except Exception as e:
            raise ParsingError(
                f"Failed to read or parse EPUB file: {e!r}",
                parsing_stage="document_opening",
                original_error=e,
            ) from e
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass

        if book:
            # Convert to AST
            doc = self.convert_to_ast(book)
            # Extract and attach metadata
            metadata = self.extract_metadata(book)
            doc.metadata = metadata.to_dict()
            return doc
        else:
            raise ParsingError(
                "Failed to read or parse EPUB file: no file read.",
                parsing_stage="document_opening",
            )

    def convert_to_ast(self, book: Any) -> Document:
        """Convert EPUB book to AST Document.

        Parameters
        ----------
        book : ebooklib.epub.EpubBook
            EPUB book object

        Returns
        -------
        Document
            AST document node

        """
        # Emit started event
        self._emit_progress("started", "Converting EPUB document", current=0, total=1)
        from ebooklib import ITEM_DOCUMENT

        children: list[Node] = []

        # Add table of contents if requested
        if self.options.include_toc:
            toc_nodes = self._build_toc(book)
            if toc_nodes:
                children.extend(toc_nodes)
                children.append(ThematicBreak())

        # Process spine items (chapters in reading order)
        for item in book.get_items_of_type(ITEM_DOCUMENT):  # 9 = ITEM_DOCUMENT
            if item.get_type() == ITEM_DOCUMENT:  # Document type
                html_content = item.get_content().decode("utf-8", errors="ignore")
                chapter_doc = self.html_parser.convert_to_ast(html_content)
                if chapter_doc.children:
                    children.extend(chapter_doc.children)
                    # Add chapter separator only when not merging chapters
                    if not self.options.merge_chapters:
                        children.append(ThematicBreak())

        # Emit finished event
        self._emit_progress("finished", "EPUB conversion completed", current=1, total=1)

        return Document(children=children)

    def _build_toc(self, book: Any) -> list[Node]:
        """Build table of contents from EPUB.

        Parameters
        ----------
        book : ebooklib.epub.EpubBook
            EPUB book object

        Returns
        -------
        list of Node
            TOC nodes

        """
        nodes: list[Node] = []
        toc = book.toc

        if not toc:
            return nodes

        # Add TOC heading
        nodes.append(Heading(level=1, content=[Text(content="Table of Contents")]))

        # Process TOC items
        for item in toc:
            if hasattr(item, "title"):
                nodes.append(Heading(level=2, content=[Text(content=item.title)]))

        return nodes

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from EPUB book.

        Parameters
        ----------
        document : ebooklib.epub.EpubBook
            EPUB book object

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract metadata from EPUB
        if hasattr(document, "get_metadata"):
            # Title
            title_meta = document.get_metadata("DC", "title")
            if title_meta and title_meta[0]:
                metadata.title = str(title_meta[0][0])

            # Author/Creator
            creator_meta = document.get_metadata("DC", "creator")
            if creator_meta and creator_meta[0]:
                metadata.author = str(creator_meta[0][0])

            # Subject/Description
            subject_meta = document.get_metadata("DC", "subject")
            if subject_meta and subject_meta[0]:
                metadata.subject = str(subject_meta[0][0])

            # Language
            language_meta = document.get_metadata("DC", "language")
            if language_meta and language_meta[0]:
                metadata.language = str(language_meta[0][0])

            # Publisher
            publisher_meta = document.get_metadata("DC", "publisher")
            if publisher_meta and publisher_meta[0]:
                metadata.custom["publisher"] = str(publisher_meta[0][0])

            # Date
            date_meta = document.get_metadata("DC", "date")
            if date_meta and date_meta[0]:
                metadata.creation_date = str(date_meta[0][0])

        return metadata


# Converter metadata for registry
CONVERTER_METADATA = ConverterMetadata(
    format_name="epub",
    extensions=[".epub"],
    mime_types=["application/epub+zip"],
    description="Electronic Publication (EPUB) format",
    parser_class=EpubToAstConverter,
    renderer_class="all2md.renderers.epub.EpubRenderer",
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    parser_required_packages=[("ebooklib", "ebooklib", "")],
    renderer_required_packages=[("ebooklib", "ebooklib", ">=0.17")],
    optional_packages=[],
    import_error_message=("ePub conversion requires 'ebooklib'. " "Install with: pip install ebooklib"),
    parser_options_class=EpubOptions,
    renderer_options_class="all2md.options.epub.EpubRendererOptions",
    priority=8,
)
