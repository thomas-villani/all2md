#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/epub.py
"""EPUB rendering from AST.

This module provides the EpubRenderer class which converts AST nodes
to EPUB format. The renderer uses ebooklib to generate EPUB3 packages
with proper metadata, chapters, and navigation.

The rendering process splits the AST into chapters using configurable
strategies (separator-based or heading-based), converts each chapter
to XHTML, and assembles a complete EPUB package.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Union

from all2md.ast.nodes import Document, Heading, Node
from all2md.exceptions import RenderingError
from all2md.options import EpubRendererOptions, HtmlRendererOptions
from all2md.renderers._split_utils import (
    auto_split_ast,
    extract_heading_text,
    split_ast_by_heading,
    split_ast_by_separator,
)
from all2md.renderers.base import BaseRenderer
from all2md.renderers.html import HtmlRenderer
from all2md.utils.decorators import requires_dependencies


class EpubRenderer(BaseRenderer):
    """Render AST nodes to EPUB format.

    This class converts an AST document into an EPUB3 package using
    ebooklib. It splits the document into chapters based on configured
    strategy and generates proper EPUB metadata and navigation.

    Parameters
    ----------
    options : EpubRendererOptions or None, default = None
        EPUB rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Paragraph, Text
        >>> from all2md.options import EpubRendererOptions
        >>> from all2md.renderers.epub import EpubRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Chapter 1")]),
        ...     Paragraph(content=[Text(content="Content here")])
        ... ])
        >>> options = EpubRendererOptions(title="My Book")
        >>> renderer = EpubRenderer(options)
        >>> renderer.render(doc, "output.epub")

    """

    def __init__(self, options: EpubRendererOptions | None = None):
        """Initialize the EPUB renderer with options."""
        options = options or EpubRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: EpubRendererOptions = options

        # Create HTML renderer for chapter content
        html_options = HtmlRendererOptions(
            standalone=False,  # Generate fragments, not full HTML
            css_style="embedded"
        )
        self.html_renderer = HtmlRenderer(html_options)

    @requires_dependencies("epub_render", [("ebooklib", "ebooklib", ">=0.17")])
    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to an EPUB file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        Raises
        ------
        DependencyError
            If ebooklib is not installed
        RenderingError
            If EPUB generation fails

        """
        from ebooklib import epub

        # Create EPUB book
        book = epub.EpubBook()

        # Set metadata
        self._set_metadata(book, doc)

        # Split document into chapters
        chapters_data = self._split_into_chapters(doc)

        # Create EPUB chapters
        epub_chapters = []
        spine_items = ['nav']

        for idx, (heading, content_nodes) in enumerate(chapters_data, start=1):
            chapter_title = self._get_chapter_title(heading, idx)
            chapter_filename = f"chapter_{idx}.xhtml"

            # Create chapter document for rendering
            chapter_doc = Document(children=content_nodes, metadata=doc.metadata)

            # Render chapter content to HTML
            chapter_html = self.html_renderer.render_to_string(chapter_doc)

            # Create EPUB chapter
            epub_chapter = epub.EpubHtml(
                title=chapter_title,
                file_name=chapter_filename,
                lang=self.options.language
            )
            epub_chapter.content = chapter_html

            # Add chapter to book
            book.add_item(epub_chapter)
            epub_chapters.append(epub_chapter)
            spine_items.append(epub_chapter)

        # Define table of contents
        if self.options.generate_toc:
            book.toc = tuple(epub_chapters)

        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Define spine (reading order)
        book.spine = spine_items

        # Write EPUB file
        try:
            if isinstance(output, (str, Path)):
                epub.write_epub(str(output), book, {})
            else:
                # For file-like objects, write to BytesIO first
                buffer = BytesIO()
                epub.write_epub(buffer, book, {})
                buffer.seek(0)
                output.write(buffer.read())
        except Exception as e:
            raise RenderingError(
                f"Failed to write EPUB file: {e!r}",
                rendering_stage="rendering",
                original_error=e
            ) from e

    # render_to_bytes() is inherited from BaseRenderer

    def _set_metadata(self, book: Any, doc: Document) -> None:
        """Set EPUB metadata from options and document metadata.

        Parameters
        ----------
        book : ebooklib.epub.EpubBook
            EPUB book object
        doc : Document
            AST document with metadata

        """
        # Set title
        title = self.options.title
        if not title and doc.metadata and 'title' in doc.metadata:
            title = str(doc.metadata['title'])
        if not title:
            title = "Untitled"
        book.set_title(title)

        # Set author
        author = self.options.author
        if not author and doc.metadata and 'author' in doc.metadata:
            author = str(doc.metadata['author'])
        if author:
            book.add_author(author)

        # Set language
        book.set_language(self.options.language)

        # Set identifier (generate UUID if not provided)
        identifier = self.options.identifier
        if not identifier:
            identifier = f"urn:uuid:{uuid.uuid4()}"
        book.set_identifier(identifier)

        # Add other metadata from document
        if doc.metadata:
            if 'subject' in doc.metadata:
                book.add_metadata('DC', 'subject', str(doc.metadata['subject']))
            if 'date' in doc.metadata:
                book.add_metadata('DC', 'date', str(doc.metadata['date']))
            if 'description' in doc.metadata:
                book.add_metadata('DC', 'description', str(doc.metadata['description']))

    def _split_into_chapters(
        self,
        doc: Document
    ) -> list[tuple[Heading | None, list[Node]]]:
        """Split AST document into chapters based on configured strategy.

        Parameters
        ----------
        doc : Document
            AST document to split

        Returns
        -------
        list of tuple[Heading or None, list of Node]
            List of (heading, content_nodes) tuples

        """
        split_mode = self.options.chapter_split_mode

        if split_mode == "separator":
            # Split on ThematicBreak nodes
            separator_chunks = split_ast_by_separator(doc)
            return [(None, chunk) for chunk in separator_chunks]

        elif split_mode == "heading":
            # Split on heading level
            return split_ast_by_heading(
                doc,
                heading_level=self.options.chapter_split_heading_level
            )

        else:  # "auto"
            # Auto-detect best strategy
            return auto_split_ast(
                doc,
                heading_level=self.options.chapter_split_heading_level
            )

    def _get_chapter_title(self, heading: Heading | None, chapter_num: int) -> str:
        """Get chapter title from heading or generate one.

        Parameters
        ----------
        heading : Heading or None
            Chapter heading node
        chapter_num : int
            Chapter number (1-based)

        Returns
        -------
        str
            Chapter title

        """
        if heading and self.options.use_heading_as_chapter_title:
            title = extract_heading_text(heading)
            if title:
                return title

        # Fall back to template
        return self.options.chapter_title_template.format(num=chapter_num)
