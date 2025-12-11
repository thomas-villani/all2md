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

import logging
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Union, cast
from urllib.parse import urlparse

from all2md.ast.nodes import Comment, CommentInline, Document, Heading, Image, Node, get_node_children
from all2md.ast.transforms import clone_node
from all2md.constants import DEPS_EPUB_RENDER
from all2md.exceptions import RenderingError
from all2md.options.epub import EpubRendererOptions
from all2md.options.html import HtmlRendererOptions
from all2md.renderers._split_utils import (
    auto_split_ast,
    extract_heading_text,
    split_ast_by_heading,
    split_ast_by_separator,
)
from all2md.renderers.base import BaseRenderer
from all2md.renderers.html import HtmlRenderer
from all2md.utils.decorators import requires_dependencies
from all2md.utils.images import decode_base64_image, detect_image_format_from_bytes
from all2md.utils.network_security import fetch_image_securely, is_network_disabled

logger = logging.getLogger(__name__)


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

        >>> from all2md.options.epub import EpubRendererOptions
        >>> from all2md.ast import Document, Heading, Paragraph, Text
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
        BaseRenderer._validate_options_type(options, EpubRendererOptions, "epub")
        options = options or EpubRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: EpubRendererOptions = options

        # Create HTML renderer for chapter content
        html_options = HtmlRendererOptions(standalone=False, css_style="embedded")  # Generate fragments, not full HTML
        self.html_renderer = HtmlRenderer(html_options)

        # Track temporary files for cleanup
        self._temp_files: list[str] = []

    @requires_dependencies("epub_render", DEPS_EPUB_RENDER)
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

        Notes
        -----
        The original AST document is preserved and not mutated during rendering.
        Image URL rewriting is performed on a deep copy of the document to ensure
        the input AST can be safely reused for multiple renderings.

        """
        from ebooklib import epub

        # Clone document to avoid mutating the original AST during image URL rewriting.
        # This ensures the input document can be reused for rendering to other formats.
        doc = cast(Document, clone_node(doc))

        # Create EPUB book
        book = epub.EpubBook()

        # Set metadata
        self._set_metadata(book, doc)

        # Collect all images from the document
        all_images = self._collect_images(doc)

        # Create URL mapping for image rewriting
        url_mapping = {}
        for idx, img_node in enumerate(all_images, start=1):
            internal_path = self._add_image_to_epub(book, img_node, idx)
            if internal_path:
                url_mapping[img_node.url] = internal_path

        # Rewrite image URLs in the document
        if url_mapping:
            self._rewrite_image_urls(doc, url_mapping)

        # Add cover image if requested
        if self.options.include_cover and self.options.cover_image_path:
            self._add_cover_image(book)

        # Split document into chapters
        chapters_data = self._split_into_chapters(doc)

        # Create EPUB chapters
        epub_chapters = []
        spine_items = ["nav"]

        for idx, (heading, content_nodes) in enumerate(chapters_data, start=1):
            chapter_title = self._get_chapter_title(heading, idx)
            chapter_filename = f"chapter_{idx}.xhtml"

            # Create chapter document for rendering
            # Include the heading in the chapter content so it appears in the rendered chapter
            chapter_children = [heading] + content_nodes if heading else content_nodes
            chapter_doc = Document(children=chapter_children, metadata=doc.metadata)

            # Render chapter content to HTML
            chapter_html = self.html_renderer.render_to_string(chapter_doc)

            # Create EPUB chapter
            epub_chapter = epub.EpubHtml(title=chapter_title, file_name=chapter_filename, lang=self.options.language)
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
                f"Failed to write EPUB file: {e!r}", rendering_stage="rendering", original_error=e
            ) from e
        finally:
            # Clean up temporary files

            for temp_file in self._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass  # Ignore cleanup errors

    @requires_dependencies("epub_render", DEPS_EPUB_RENDER)
    def render_to_bytes(self, doc: Document) -> bytes:
        """Render the AST to EPUB bytes.

        Returns
        -------
        bytes
            EPUB file content as bytes

        """
        buffer = BytesIO()
        self.render(doc, buffer)
        return buffer.getvalue()

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
        if not title and doc.metadata and "title" in doc.metadata:
            title = str(doc.metadata["title"])
        if not title:
            title = "Untitled"
        book.set_title(title)

        # Set author
        author = self.options.author
        if not author and doc.metadata and "author" in doc.metadata:
            author = str(doc.metadata["author"])
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
            if "subject" in doc.metadata:
                book.add_metadata("DC", "subject", str(doc.metadata["subject"]))
            if "date" in doc.metadata:
                book.add_metadata("DC", "date", str(doc.metadata["date"]))
            if "description" in doc.metadata:
                book.add_metadata("DC", "description", str(doc.metadata["description"]))

        # Set creator application metadata if configured
        if self.options.creator:
            # Add contributor with "bkp" (book producer) role for EPUB
            book.add_metadata("DC", "contributor", self.options.creator)

    def _split_into_chapters(self, doc: Document) -> list[tuple[Heading | None, list[Node]]]:
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
            return split_ast_by_heading(doc, heading_level=self.options.chapter_split_heading_level)

        else:  # "auto"
            # Auto-detect best strategy
            return auto_split_ast(doc, heading_level=self.options.chapter_split_heading_level)

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

    def _collect_images(self, node: Node, images: list[Image] | None = None) -> list[Image]:
        """Recursively collect all Image nodes from the AST.

        Parameters
        ----------
        node : Node
            Node to search for images
        images : list of Image or None, default = None
            Accumulator for found images

        Returns
        -------
        list of Image
            All Image nodes found in the tree

        """
        if images is None:
            images = []

        if isinstance(node, Image):
            images.append(node)

        # Recursively search children
        for child in get_node_children(node):
            self._collect_images(child, images)

        return images

    def _decode_data_uri(self, data_uri: str) -> tuple[bytes, str] | None:
        """Decode base64 data URI to image bytes and format.

        Parameters
        ----------
        data_uri : str
            Data URI with base64 encoded image

        Returns
        -------
        tuple of (bytes, str) or None
            (image_data, format) or None if decoding failed

        """
        # Use centralized image utility
        image_data, image_format = decode_base64_image(data_uri)
        if image_data and image_format:
            return (image_data, image_format)
        return None

    def _fetch_remote_image(self, url: str) -> tuple[bytes, str] | None:
        """Fetch remote image securely.

        Parameters
        ----------
        url : str
            Remote image URL

        Returns
        -------
        tuple of (bytes, str) or None
            (image_data, image_format) or None if fetch failed

        """
        # Check global network disable flag
        if is_network_disabled():
            logger.debug(f"Network disabled, skipping remote image: {url}")
            return None

        # Check if remote fetching is allowed
        if not self.options.network.allow_remote_fetch:
            logger.debug(f"Remote fetching disabled, skipping image: {url}")
            return None

        try:
            # Fetch image data securely
            image_data = fetch_image_securely(
                url=url,
                allowed_hosts=self.options.network.allowed_hosts,
                require_https=self.options.network.require_https,
                max_size_bytes=self.options.max_asset_size_bytes,
                timeout=self.options.network.network_timeout,
                require_head_success=self.options.network.require_head_success,
            )

            # Detect image format from URL or content
            detected_format = detect_image_format_from_bytes(image_data[:32])

            if detected_format:
                image_format = detected_format
            else:
                # Fall back to extension from URL
                parsed = urlparse(url)
                path_lower = parsed.path.lower()
                if path_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg")):
                    image_format = path_lower.split(".")[-1]
                else:
                    # Default to png
                    image_format = "png"
                    logger.debug(f"Could not detect format from content or URL, defaulting to png: {url}")

            logger.debug(f"Successfully fetched remote image: {url}")
            return (image_data, image_format)

        except Exception as e:
            logger.warning(f"Failed to fetch remote image {url}: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to fetch remote image {url}: {e!r}", rendering_stage="image_processing", original_error=e
                ) from e
            return None

    def _add_image_to_epub(self, book: Any, image_node: Image, index: int) -> str | None:
        """Add an image to the EPUB and return the internal path.

        Parameters
        ----------
        book : ebooklib.epub.EpubBook
            EPUB book object
        image_node : Image
            Image node to add
        index : int
            Image index for naming

        Returns
        -------
        str or None
            Internal EPUB path (e.g., "images/img_001.png") or None if failed

        """
        from ebooklib import epub

        try:
            image_url = image_node.url
            if not image_url:
                return None

            # Handle data URIs
            if image_url.startswith("data:"):
                decoded = self._decode_data_uri(image_url)
                if not decoded:
                    return None

                image_data, image_format = decoded
                internal_path = f"images/img_{index:03d}.{image_format}"

                # Create EPUB image item
                epub_image = epub.EpubImage()
                epub_image.file_name = internal_path
                epub_image.content = image_data

                # Add to book
                book.add_item(epub_image)

                return internal_path

            # Handle remote HTTP/HTTPS URLs
            elif image_url.startswith(("http://", "https://")):
                # Fetch remote image securely
                fetched = self._fetch_remote_image(image_url)
                if not fetched:
                    return None

                image_data, image_format = fetched
                internal_path = f"images/img_{index:03d}.{image_format}"

                # Create EPUB image item
                epub_image = epub.EpubImage()
                epub_image.file_name = internal_path
                epub_image.content = image_data

                # Add to book
                book.add_item(epub_image)

                return internal_path

            # Handle local file paths
            else:
                # Try to read local file
                image_path = Path(image_url)
                if image_path.exists() and image_path.is_file():
                    image_data = image_path.read_bytes()

                    # Detect format from file content (more reliable than extension)
                    detected_format = detect_image_format_from_bytes(image_data[:32])

                    # Fall back to extension if content detection fails
                    if detected_format:
                        image_format = detected_format
                    else:
                        image_format = image_path.suffix.lstrip(".")
                        if not image_format:
                            logger.debug("Could not detect format from content or extension")
                            return None
                        logger.debug(f"Could not detect format from content, using extension: {image_format}")

                    internal_path = f"images/img_{index:03d}.{image_format}"

                    # Create EPUB image item
                    epub_image = epub.EpubImage()
                    epub_image.file_name = internal_path
                    epub_image.content = image_data

                    # Add to book
                    book.add_item(epub_image)

                    return internal_path

                # Local file not found
                logger.debug(f"Local file not found: {image_url}")
                return None

        except Exception as e:
            # If anything fails, log and optionally raise
            logger.warning(f"Failed to add image to EPUB: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to add image to EPUB: {e!r}", rendering_stage="image_processing", original_error=e
                ) from e
            return None

    def _rewrite_image_urls(self, node: Node, url_mapping: dict[str, str]) -> None:
        """Recursively rewrite image URLs in the AST.

        Parameters
        ----------
        node : Node
            Node to search and update
        url_mapping : dict of str to str
            Mapping from original URLs to internal EPUB paths

        """
        if isinstance(node, Image):
            if node.url in url_mapping:
                # Update the URL in place
                node.url = url_mapping[node.url]

        # Recursively update children

        for child in get_node_children(node):
            self._rewrite_image_urls(child, url_mapping)

    def _add_cover_image(self, book: Any) -> None:
        """Add cover image to the EPUB.

        Parameters
        ----------
        book : ebooklib.epub.EpubBook
            EPUB book object

        """
        try:
            if not self.options.cover_image_path:
                return

            cover_path = Path(self.options.cover_image_path)
            if not cover_path.exists() or not cover_path.is_file():
                return

            # Read cover image
            cover_data = cover_path.read_bytes()
            cover_format = cover_path.suffix.lstrip(".")

            # Set cover image
            book.set_cover(f"cover.{cover_format}", cover_data)

        except Exception as e:
            # If cover image fails, log and optionally raise
            logger.warning(f"Failed to add cover image: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to add cover image: {e!r}", rendering_stage="cover_image", original_error=e
                ) from e

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (no-op, handled by HTML renderer).

        Parameters
        ----------
        node : Comment
            Comment to render

        Notes
        -----
        Comments are handled by the HtmlRenderer which is used to render
        EPUB chapter content. This method exists only to satisfy the visitor
        pattern but is never called during normal rendering flow.

        """
        pass

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (no-op, handled by HTML renderer).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        Inline comments are handled by the HtmlRenderer which is used to
        render EPUB chapter content. This method exists only to satisfy the
        visitor pattern but is never called during normal rendering flow.

        """
        pass
