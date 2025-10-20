# Copyright (c) 2025 All2md Contributors
"""SimpleDoc format parser.

This module implements the SimpleDoc to AST converter, demonstrating how to
build a parser plugin for the all2md library.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, Optional, Union

from all2md.ast import CodeBlock, Document, Heading, List, ListItem, Node, Paragraph, Text
from all2md.exceptions import ParsingError
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata

from .options import SimpleDocOptions

logger = logging.getLogger(__name__)


class SimpleDocParser(BaseParser):
    """Convert SimpleDoc documents to AST representation.

    SimpleDoc is a lightweight markup format with:
    - Frontmatter metadata (between --- delimiters)
    - Headings (lines starting with @@)
    - Lists (lines starting with -)
    - Code blocks (triple backticks)
    - Paragraphs (separated by blank lines)

    Parameters
    ----------
    options : SimpleDocOptions or None
        Conversion options
    progress_callback : ProgressCallback or None
        Optional callback for progress updates during parsing

    """

    def __init__(
        self, options: SimpleDocOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the SimpleDoc parser with options and progress callback."""
        super().__init__(options or SimpleDocOptions(), progress_callback)
        self.options: SimpleDocOptions = options or SimpleDocOptions()

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse SimpleDoc input into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input SimpleDoc document to parse

        Returns
        -------
        Document
            AST Document node representing the parsed document structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid format or corruption

        """
        self._emit_progress("started", "Converting SimpleDoc document", current=0, total=1)

        try:
            content = self._read_content(input_data)
        except Exception as e:
            raise ParsingError(f"Failed to read SimpleDoc file: {e}") from e

        try:
            # Parse metadata and content
            metadata, content_text = self._extract_frontmatter(content)

            # Parse content into AST nodes
            children = self._parse_content(content_text)

            self._emit_progress("finished", "SimpleDoc conversion completed", current=1, total=1)

            return Document(children=children, metadata=metadata.to_dict())

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(
                f"Failed to parse SimpleDoc content: {e}", parsing_stage="content_parsing", original_error=e
            ) from e

    def _read_content(self, input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Read content from various input types.

        Parameters
        ----------
        input_data : various types
            Input data in different formats

        Returns
        -------
        str
            Text content

        """
        if isinstance(input_data, (str, Path)):
            # Read from file path
            with open(input_data, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        elif isinstance(input_data, bytes):
            # Decode bytes directly
            return input_data.decode("utf-8", errors="replace")
        elif hasattr(input_data, "read"):
            # Handle file-like object (IO[bytes])
            raw_content = input_data.read()
            if isinstance(raw_content, bytes):
                return raw_content.decode("utf-8", errors="replace")
            return str(raw_content)
        else:
            raise ValueError(f"Unsupported input type: {type(input_data)}")

    def _extract_frontmatter(self, content: str) -> tuple[DocumentMetadata, str]:
        """Extract frontmatter metadata from content.

        Parameters
        ----------
        content : str
            Full document content

        Returns
        -------
        tuple[DocumentMetadata, str]
            Extracted metadata and remaining content

        """
        metadata = DocumentMetadata()

        if not self.options.include_frontmatter:
            return metadata, content

        # Check for frontmatter block
        if not content.startswith("---\n") and not content.startswith("---\r\n"):
            return metadata, content

        # Find end of frontmatter
        lines = content.split("\n")
        end_index = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_index = i
                break

        if end_index == -1:
            # No closing ---, treat as regular content
            if self.options.strict_mode:
                raise ParsingError("Frontmatter block not closed (missing closing '---')")
            logger.warning("Frontmatter block not closed, treating as regular content")
            return metadata, content

        # Parse frontmatter
        frontmatter_lines = lines[1:end_index]
        for line in frontmatter_lines:
            line = line.strip()
            if not line or ":" not in line:
                continue

            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            # Map to DocumentMetadata fields
            if key == "title":
                metadata.title = value
            elif key == "author":
                metadata.author = value
            elif key == "date":
                metadata.date = value
            elif key == "tags":
                # Split comma-separated tags
                metadata.keywords = [tag.strip() for tag in value.split(",") if tag.strip()]
            else:
                # Store custom metadata
                if not metadata.custom:
                    metadata.custom = {}
                metadata.custom[key] = value

        # Return remaining content (after frontmatter)
        remaining_content = "\n".join(lines[end_index + 1 :])
        return metadata, remaining_content

    def _parse_content(self, content: str) -> list[Node]:
        """Parse SimpleDoc content into AST nodes.

        Parameters
        ----------
        content : str
            Content to parse (without frontmatter)

        Returns
        -------
        list[Node]
            List of AST nodes

        """
        children: list[Node] = []
        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Skip empty lines at document level
            if not line.strip():
                i += 1
                continue

            # Check for heading
            if line.strip().startswith("@@"):
                heading_text = line.strip()[2:].strip()
                children.append(Heading(level=1, content=[Text(content=heading_text)]))
                i += 1
                continue

            # Check for code block
            if self.options.parse_code_blocks and line.strip().startswith("```"):
                code_content, lines_consumed = self._parse_code_block(lines[i:])
                if code_content is not None:
                    children.append(code_content)
                    i += lines_consumed
                    continue

            # Check for list item
            if self.options.parse_lists and line.strip().startswith("-"):
                list_node, lines_consumed = self._parse_list(lines[i:])
                children.append(list_node)
                i += lines_consumed
                continue

            # Parse paragraph
            para_node, lines_consumed = self._parse_paragraph(lines[i:])
            if para_node:
                children.append(para_node)
            i += lines_consumed

        return children

    def _parse_code_block(self, lines: list[str]) -> tuple[CodeBlock | None, int]:
        """Parse a code block starting from the given lines.

        Parameters
        ----------
        lines : list[str]
            Lines starting with the code block

        Returns
        -------
        tuple[CodeBlock | None, int]
            Parsed code block and number of lines consumed

        """
        if not lines or not lines[0].strip().startswith("```"):
            return None, 1

        # Extract language from first line
        first_line = lines[0].strip()
        language = first_line[3:].strip() if len(first_line) > 3 else ""

        # Find closing backticks
        code_lines = []
        i = 1
        while i < len(lines):
            if lines[i].strip().startswith("```"):
                # Found closing backticks
                code_content = "\n".join(code_lines)
                return CodeBlock(language=language, content=code_content), i + 1
            code_lines.append(lines[i])
            i += 1

        # No closing backticks found
        if self.options.strict_mode:
            raise ParsingError("Code block not closed (missing closing '```')")

        logger.warning("Code block not closed, including remaining content")
        code_content = "\n".join(code_lines)
        return CodeBlock(language=language, content=code_content), len(lines)

    def _parse_list(self, lines: list[str]) -> tuple[List, int]:
        """Parse a list starting from the given lines.

        Parameters
        ----------
        lines : list[str]
            Lines starting with the list

        Returns
        -------
        tuple[List, int]
            Parsed list and number of lines consumed

        """
        items: list[ListItem] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Check if this is a list item
            if not line.startswith("-"):
                break

            # Extract item text (remove leading '- ')
            item_text = line[1:].strip()

            # Create list item
            items.append(ListItem(children=[Paragraph(content=[Text(content=item_text)])]))
            i += 1

        return List(ordered=False, items=items), i

    def _parse_paragraph(self, lines: list[str]) -> tuple[Paragraph | None, int]:
        """Parse a paragraph starting from the given lines.

        Parameters
        ----------
        lines : list[str]
            Lines starting with the paragraph

        Returns
        -------
        tuple[Paragraph | None, int]
            Parsed paragraph and number of lines consumed

        """
        para_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Stop at empty line
            if not line.strip():
                break

            # Stop at heading, list, or code block
            stripped = line.strip()
            if stripped.startswith("@@") or stripped.startswith("-") or stripped.startswith("```"):
                break

            para_lines.append(line.strip())
            i += 1

        if not para_lines:
            return None, i if i > 0 else 1

        # Join lines with spaces
        para_text = " ".join(para_lines)
        return Paragraph(content=[Text(content=para_text)]), i

    def extract_metadata(self, input_data: Union[str, Path, IO[bytes], bytes]) -> DocumentMetadata:
        """Extract metadata from SimpleDoc file.

        Parameters
        ----------
        input_data : various types
            Input data

        Returns
        -------
        DocumentMetadata
            Extracted metadata from frontmatter

        """
        try:
            content = self._read_content(input_data)
            metadata, _ = self._extract_frontmatter(content)
            return metadata
        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")
            return DocumentMetadata()
