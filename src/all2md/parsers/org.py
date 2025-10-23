#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/org.py
"""Org-Mode to AST converter.

This module provides conversion from Org-Mode documents to AST representation
using the orgparse parser. It enables bidirectional transformation by parsing
Org files into the same AST structure used for other formats.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.org import OrgParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.encoding import read_text_with_encoding_detection
from all2md.utils.html_sanitizer import sanitize_url
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class OrgParser(BaseParser):
    r"""Convert Org-Mode to AST representation.

    This converter uses orgparse to parse Org-Mode files and builds an AST that
    matches the structure used throughout all2md, enabling bidirectional
    conversion and transformation pipelines.

    Parameters
    ----------
    options : OrgParserOptions or None, default = None
        Parser configuration options

    Examples
    --------
    Basic parsing:

        >>> parser = OrgParser()
        >>> doc = parser.parse("* Heading\n\nThis is **bold**.")

    With options:

        >>> options = OrgParserOptions(
        ...     todo_keywords=["TODO", "IN-PROGRESS", "DONE"],
        ...     parse_tags=True
        ... )
        >>> parser = OrgParser(options)
        >>> doc = parser.parse(org_text)

    """

    def __init__(self, options: OrgParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the Org parser with options and progress callback."""
        options = options or OrgParserOptions()
        super().__init__(options, progress_callback)
        self.options: OrgParserOptions = options

    @requires_dependencies("org", [("orgparse", "orgparse", "")])
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse Org-Mode input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Org-Mode input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw Org bytes
            - Org string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        DependencyError
            If orgparse is not installed
        ParsingError
            If parsing fails

        """
        # Load Org content from various input types
        org_content = self._load_org_content(input_data)

        import orgparse

        # Parse Org to orgparse tree
        try:
            root = orgparse.loads(org_content)
        except Exception as e:
            raise ParsingError(f"Failed to parse Org-Mode: {e}") from e

        # Extract metadata
        metadata = self.extract_metadata(root)

        # Convert orgparse tree to AST
        children = []

        # Process root node body first (plain text without headings)
        # Use format='raw' to preserve link syntax
        root_body = (
            root.get_body(format="raw").strip()
            if hasattr(root, "get_body")
            else (root.body.strip() if root.body else "")
        )
        if root_body:
            body_nodes = self._process_body(root_body)
            children.extend(body_nodes)

        # Process child nodes (headings and their content)
        for node in root.children:
            ast_nodes = self._process_node(node)
            if ast_nodes is not None:
                if isinstance(ast_nodes, list):
                    children.extend(ast_nodes)
                else:
                    children.append(ast_nodes)

        return Document(children=children, metadata=metadata.to_dict())

    @staticmethod
    def _load_org_content(input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Load Org content from various input types with encoding detection.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        str
            Org content as string

        """
        if isinstance(input_data, bytes):
            return read_text_with_encoding_detection(input_data)
        elif isinstance(input_data, Path):
            with open(input_data, "rb") as f:
                return read_text_with_encoding_detection(f.read())
        elif isinstance(input_data, str):
            # Could be file path or Org content
            path = Path(input_data)
            if path.exists() and path.is_file():
                with open(path, "rb") as f:
                    return read_text_with_encoding_detection(f.read())
            else:
                # Assume it's Org content
                return input_data
        else:
            # File-like object - IO[bytes] returns bytes
            input_data.seek(0)
            content_bytes = input_data.read()
            return read_text_with_encoding_detection(content_bytes)

    def _process_node(self, node: Any) -> Node | list[Node] | None:
        """Process an orgparse node into an AST node.

        Parameters
        ----------
        node : orgparse.OrgNode
            Orgparse node to process

        Returns
        -------
        Node, list[Node], or None
            Resulting AST node(s)

        """
        result: list[Node] = []

        # Process headline as Heading
        heading_ast = self._process_headline(node)
        if heading_ast:
            result.append(heading_ast)

        # Process body content
        # Use format='raw' to preserve link syntax
        body_text = (
            node.get_body(format="raw").strip()
            if hasattr(node, "get_body")
            else (node.body.strip() if node.body else "")
        )
        if body_text:
            body_nodes = self._process_body(body_text)
            result.extend(body_nodes)

        # Process children recursively
        for child in node.children:
            child_nodes = self._process_node(child)
            if child_nodes is not None:
                if isinstance(child_nodes, list):
                    result.extend(child_nodes)
                else:
                    result.append(child_nodes)

        return result if result else None

    def _process_headline(self, node: Any) -> Heading | None:
        """Process an orgparse headline node.

        Parameters
        ----------
        node : orgparse.OrgNode
            Orgparse node representing a headline

        Returns
        -------
        Heading or None
            Heading AST node with metadata for TODO state, priority, and tags

        """
        if not node.heading:
            return None

        # Extract heading level (number of stars)
        level = node.level

        # Extract TODO state (independent of parse_tags)
        # First try orgparse's detection, then manually parse if needed
        todo_state = None
        manually_extracted_todo = False
        if node.todo and node.todo in self.options.todo_keywords:
            todo_state = node.todo
        elif not node.todo:
            # Manually check if heading starts with a TODO keyword
            # that orgparse didn't recognize
            heading_parts = node.heading.split(None, 1)
            if heading_parts and heading_parts[0] in self.options.todo_keywords:
                todo_state = heading_parts[0]
                manually_extracted_todo = True

        # Extract priority
        priority = None
        if hasattr(node, "priority") and node.priority:
            priority = node.priority

        # Extract tags (controlled by parse_tags option)
        tags = []
        if self.options.parse_tags and hasattr(node, "tags") and node.tags:
            tags = list(node.tags)

        # Parse inline content from heading text
        # If we manually extracted TODO, remove it from the heading text
        heading_text = node.heading
        if manually_extracted_todo and todo_state:
            # Remove the TODO keyword from heading text
            heading_text = heading_text[len(todo_state) :].lstrip()
        content = self._parse_inline(heading_text)

        # Build metadata
        heading_metadata: dict[str, Any] = {}
        if todo_state:
            heading_metadata["org_todo_state"] = todo_state
        if priority:
            heading_metadata["org_priority"] = priority
        if tags:
            heading_metadata["org_tags"] = tags

        # Extract properties if enabled
        if self.options.parse_properties and hasattr(node, "properties") and node.properties:
            heading_metadata["org_properties"] = dict(node.properties)

        # Extract scheduling information if enabled (SCHEDULED/DEADLINE)
        if self.options.parse_scheduling:
            if hasattr(node, "scheduled") and node.scheduled:
                heading_metadata["org_scheduled"] = str(node.scheduled)
            if hasattr(node, "deadline") and node.deadline:
                heading_metadata["org_deadline"] = str(node.deadline)

        return Heading(level=level, content=content, metadata=heading_metadata)

    def _process_body(self, body_text: str) -> list[Node]:
        """Process body text into AST nodes.

        Parameters
        ----------
        body_text : str
            Body text content

        Returns
        -------
        list[Node]
            List of AST nodes (paragraphs, code blocks, lists, tables, etc.)

        """
        result: list[Node] = []

        # Split into blocks (separated by blank lines)
        blocks = re.split(r"\n\n+", body_text)

        # Track footnote definitions for later
        footnote_defs: list[FootnoteDefinition] = []

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Check for horizontal rules (5+ dashes)
            if re.match(r"^-{5,}$", block):
                result.append(ThematicBreak())
                continue

            # Check for footnote definitions [fn:id] content
            footnote_match = re.match(r"^\[fn:([^\]]+)\]\s+(.+)$", block, re.DOTALL)
            if footnote_match:
                footnote_id = footnote_match.group(1)
                footnote_content_text = footnote_match.group(2)
                # Parse footnote content as inline
                footnote_content = [Paragraph(content=self._parse_inline(footnote_content_text))]
                footnote_defs.append(FootnoteDefinition(identifier=footnote_id, content=footnote_content))
                continue

            # Check for math blocks \[...\]
            math_block_match = re.match(r"^\\\[(.+?)\\\]$", block, re.DOTALL)
            if math_block_match:
                math_content = math_block_match.group(1).strip()
                result.append(MathBlock(content=math_content, notation="latex"))
                continue

            # Check for code blocks (#+BEGIN_SRC / #+END_SRC)
            if block.startswith("#+BEGIN_SRC") or block.startswith("#+begin_src"):
                code_block = self._parse_code_block(block)
                if code_block:
                    result.append(code_block)
                continue

            # Check for tables (lines starting with |)
            if block.startswith("|"):
                table = self._parse_table(block)
                if table:
                    result.append(table)
                continue

            # Check for definition lists (- term :: definition)
            if re.search(r"^-\s+.+?\s+::\s+", block, re.MULTILINE):
                def_list = self._parse_definition_list(block)
                if def_list:
                    result.append(def_list)
                    continue

            # Check for lists (lines starting with -, +, *, or numbers)
            if re.match(r"^[\-\+\*]|\d+[\.\)]", block):
                list_node = self._parse_list(block)
                if list_node:
                    result.append(list_node)
                continue

            # Check for block quotes (lines starting with :)
            if all(line.strip().startswith(":") or not line.strip() for line in block.split("\n")):
                quote = self._parse_block_quote(block)
                if quote:
                    result.append(quote)
                continue

            # Default: treat as paragraph
            para = self._parse_paragraph(block)
            if para:
                result.append(para)

        # Append footnote definitions at the end
        result.extend(footnote_defs)

        return result

    def _parse_paragraph(self, text: str) -> Paragraph:
        """Parse a paragraph of text.

        Parameters
        ----------
        text : str
            Paragraph text

        Returns
        -------
        Paragraph
            Paragraph AST node

        """
        content = self._parse_inline(text)
        return Paragraph(content=content)

    def _parse_inline(self, text: str) -> list[Node]:
        """Parse inline formatting in text.

        Handles Org-Mode inline formatting:
        - *bold* -> Strong
        - /italic/ -> Emphasis
        - =code= or ~verbatim~ -> Code
        - _underline_ -> Underline (note: conflicts with subscript)
        - +strikethrough+ -> Strikethrough
        - [[url][description]] -> Link
        - [[file:path]] -> Image (if it's an image file)
        - [fn:id] -> FootnoteReference
        - \\(...\\) or $...$ -> MathInline
        - ^{text} -> Superscript
        - _{text} -> Subscript
        - \\\\ -> LineBreak

        Parameters
        ----------
        text : str
            Text with inline formatting

        Returns
        -------
        list[Node]
            List of inline AST nodes

        """
        result: list[Node] = []
        pos = 0

        # Pattern for Org inline formatting
        # Extended to include footnotes, math, superscript, subscript, line breaks
        pattern = re.compile(
            r"\\\\\s*$|"  # Line break at end of line
            r"\[fn:([^\]]+)\]|"  # [fn:id] footnote reference
            r"\\\(([^)]+)\\\)|"  # \(...\) inline math - note single backslash in pattern
            r"\$([^$]+)\$|"  # $...$ inline math (alternative)
            r"\^{([^}]+)}|"  # ^{super} superscript
            r"_{([^}]+)}|"  # _{sub} subscript
            r"\*([^*]+)\*|"  # *bold*
            r"/([^/]+)/|"  # /italic/
            r"=([^=]+)=|"  # =code=
            r"~([^~]+)~|"  # ~verbatim~
            r"_([^_\s]{1}[^_]*[^_\s]{1}|[^_\s])_(?=\s|[,\.;:!?\)]|$)|"  # _underline_ (with word boundaries)
            r"\+([^+]+)\+|"  # +strikethrough+
            r"\[\[([^\]]+?)(?:\]\[([^\]]+))?\]\]|"  # [[url]] or [[url][desc]]
            r'(?:https?|ftp)://[^\s<>"{}|\\^`\[\]]+'  # Plain URLs
        )

        for match in pattern.finditer(text):
            # Add any text before this match
            if match.start() > pos:
                result.append(Text(content=text[pos : match.start()]))

            # Process the match based on which group matched
            matched_groups = match.groups()

            if match.group(0).strip() == "\\\\":  # Line break
                result.append(LineBreak(soft=False))
            elif matched_groups[0]:  # [fn:id] footnote reference
                footnote_id = matched_groups[0]
                result.append(FootnoteReference(identifier=footnote_id))
            elif matched_groups[1]:  # \(...\) inline math
                math_content = matched_groups[1]
                result.append(MathInline(content=math_content, notation="latex"))
            elif matched_groups[2]:  # $...$ inline math
                math_content = matched_groups[2]
                result.append(MathInline(content=math_content, notation="latex"))
            elif matched_groups[3]:  # ^{super} superscript
                super_content = matched_groups[3]
                result.append(Superscript(content=[Text(content=super_content)]))
            elif matched_groups[4]:  # _{sub} subscript
                sub_content = matched_groups[4]
                result.append(Subscript(content=[Text(content=sub_content)]))
            elif matched_groups[5]:  # *bold*
                result.append(Strong(content=[Text(content=matched_groups[5])]))
            elif matched_groups[6]:  # /italic/
                result.append(Emphasis(content=[Text(content=matched_groups[6])]))
            elif matched_groups[7]:  # =code=
                result.append(Code(content=matched_groups[7]))
            elif matched_groups[8]:  # ~verbatim~
                result.append(Code(content=matched_groups[8]))
            elif matched_groups[9]:  # _underline_
                result.append(Underline(content=[Text(content=matched_groups[9])]))
            elif matched_groups[10]:  # +strikethrough+
                result.append(Strikethrough(content=[Text(content=matched_groups[10])]))
            elif matched_groups[11]:  # [[link]] with optional description
                url = matched_groups[11]
                description = matched_groups[12] if matched_groups[12] else url

                # Check if it's an image link
                if url.startswith("file:") or any(
                    url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg"]
                ):
                    # Remove 'file:' prefix if present
                    image_url = url[5:] if url.startswith("file:") else url
                    # Sanitize URL to prevent XSS attacks
                    image_url = sanitize_url(image_url)
                    result.append(Image(url=image_url, alt_text=description))
                else:
                    # Regular link
                    # Sanitize URL to prevent XSS attacks
                    url = sanitize_url(url)
                    result.append(Link(url=url, content=[Text(content=description)]))
            else:  # Plain URL
                url = match.group(0)
                # Check if it's an image URL
                if any(url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg"]):
                    # Sanitize URL to prevent XSS attacks
                    url = sanitize_url(url)
                    result.append(Image(url=url, alt_text=url))
                else:
                    # Regular link
                    # Sanitize URL to prevent XSS attacks
                    url = sanitize_url(url)
                    result.append(Link(url=url, content=[Text(content=url)]))

            pos = match.end()

        # Add any remaining text
        if pos < len(text):
            result.append(Text(content=text[pos:]))

        return result if result else [Text(content=text)]

    def _parse_code_block(self, block: str) -> CodeBlock | None:
        """Parse a code block.

        Parameters
        ----------
        block : str
            Code block text

        Returns
        -------
        CodeBlock or None
            Code block AST node with optional header args in metadata

        """
        lines = block.split("\n")
        if len(lines) < 2:
            return None

        # Extract language and header args from first line
        # Format: #+BEGIN_SRC language :arg1 value1 :arg2 value2
        first_line = lines[0].strip()
        language = None
        header_args = None

        if " " in first_line:
            # Split to get everything after #+BEGIN_SRC
            parts = first_line.split(None, 1)
            if len(parts) > 1:
                rest = parts[1].strip()
                # Split on first space to separate language from args
                if " " in rest:
                    lang_part, args_part = rest.split(None, 1)
                    language = lang_part.strip()
                    # Store header args if they start with : (Org-mode convention)
                    if args_part.strip().startswith(":"):
                        header_args = args_part.strip()
                else:
                    # No args, just language
                    language = rest

        # Extract code content (between BEGIN_SRC and END_SRC)
        code_lines = []
        in_code = False
        for line in lines:
            if line.strip().lower().startswith("#+begin_src"):
                in_code = True
                continue
            if line.strip().lower().startswith("#+end_src"):
                break
            if in_code:
                code_lines.append(line)

        code_content = "\n".join(code_lines)

        # Build metadata with header args if present
        if header_args:
            return CodeBlock(content=code_content, language=language, metadata={"org_header_args": header_args})
        else:
            return CodeBlock(content=code_content, language=language)

    def _parse_table(self, block: str) -> Table | None:
        """Parse an Org table.

        Parameters
        ----------
        block : str
            Table block text

        Returns
        -------
        Table or None
            Table AST node

        """
        lines = block.split("\n")
        rows: list[TableRow] = []
        header: Optional[TableRow] = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith("|---") or line.startswith("|==="):
                # Separator line - indicates header row above it
                if rows and not header:
                    header = rows.pop()
                    header = TableRow(cells=header.cells, is_header=True)
                continue

            if line.startswith("|"):
                # Parse table row
                cells_text = [cell.strip() for cell in line.split("|")[1:-1]]
                cells = [TableCell(content=self._parse_inline(cell_text)) for cell_text in cells_text]
                rows.append(TableRow(cells=cells, is_header=False))

        return Table(header=header, rows=rows)

    def _parse_list(self, block: str) -> List | None:
        """Parse an Org list.

        Parameters
        ----------
        block : str
            List block text

        Returns
        -------
        List or None
            List AST node

        """
        lines = block.split("\n")
        items: list[ListItem] = []
        ordered = False

        # Check if ordered or unordered
        first_line = lines[0].strip()
        if re.match(r"^\d+[\.\)]", first_line):
            ordered = True

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Match list item
            if ordered:
                match = re.match(r"^\d+[\.\)]\s+(.+)$", line_stripped)
            else:
                match = re.match(r"^[\-\+\*]\s+(.+)$", line_stripped)

            if match:
                item_text = match.group(1)
                content = self._parse_inline(item_text)
                items.append(ListItem(children=[Paragraph(content=content)]))

        return List(ordered=ordered, items=items)

    def _parse_definition_list(self, block: str) -> DefinitionList | None:
        """Parse an Org definition list.

        Org syntax: - term :: definition

        Parameters
        ----------
        block : str
            Definition list block text

        Returns
        -------
        DefinitionList or None
            Definition list AST node

        """
        lines = block.split("\n")
        items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Match definition list item: - term :: definition
            match = re.match(r"^-\s+(.+?)\s+::\s+(.+)$", line_stripped)
            if match:
                term_text = match.group(1)
                definition_text = match.group(2)

                # Parse term and definition content
                term_content = self._parse_inline(term_text)
                term = DefinitionTerm(content=term_content)

                def_content = self._parse_inline(definition_text)
                definition = DefinitionDescription(content=[Paragraph(content=def_content)])

                items.append((term, [definition]))

        if not items:
            return None

        return DefinitionList(items=items)

    def _parse_block_quote(self, block: str) -> BlockQuote:
        """Parse a block quote (lines starting with :).

        Parameters
        ----------
        block : str
            Block quote text

        Returns
        -------
        BlockQuote
            Block quote AST node

        """
        lines = block.split("\n")
        # Remove leading : from each line
        clean_lines = []
        for line in lines:
            if line.strip().startswith(":"):
                clean_lines.append(line.strip()[1:].strip())
            else:
                clean_lines.append(line)

        quote_text = "\n".join(clean_lines)
        content = self._parse_inline(quote_text)
        return BlockQuote(children=[Paragraph(content=content)])

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from orgparse document.

        Parameters
        ----------
        document : orgparse.OrgNode
            Parsed orgparse document

        Returns
        -------
        DocumentMetadata
            Extracted metadata from document

        Notes
        -----
        Org-Mode documents can have metadata in several places:
        - File-level properties (#+TITLE:, #+AUTHOR:, etc.) via env
        - Top-level heading as title
        - Properties drawer in first heading

        """
        metadata = DocumentMetadata()

        # Extract file-level properties (#+TITLE:, #+AUTHOR:, etc.)
        if hasattr(document, "get_file_property"):
            title = document.get_file_property("TITLE")
            if title:
                metadata.title = title

            author = document.get_file_property("AUTHOR")
            if author:
                metadata.author = author

            date = document.get_file_property("DATE")
            if date:
                metadata.creation_date = date

        # Also check properties (drawer-style properties)
        if hasattr(document, "properties") and document.properties:
            props = document.properties
            if "TITLE" in props and not metadata.title:
                metadata.title = props["TITLE"]
            if "AUTHOR" in props and not metadata.author:
                metadata.author = props["AUTHOR"]
            if "DATE" in props and not metadata.creation_date:
                metadata.creation_date = props["DATE"]

            # Store other properties in custom
            for key, value in props.items():
                if key.upper() not in ["TITLE", "AUTHOR", "DATE"]:
                    metadata.custom[key.lower()] = value

        # If no title from properties, try to get from first heading
        if not metadata.title and document.children:
            first_child = document.children[0]
            if hasattr(first_child, "heading") and first_child.heading:
                metadata.title = first_child.heading

        # Extract scheduling info from first heading into custom metadata if enabled
        if self.options.parse_scheduling and document.children:
            first_child = document.children[0]
            if hasattr(first_child, "scheduled") and first_child.scheduled:
                metadata.custom["org_scheduled"] = str(first_child.scheduled)
            if hasattr(first_child, "deadline") and first_child.deadline:
                metadata.custom["org_deadline"] = str(first_child.deadline)

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="org",
    extensions=[".org"],
    mime_types=["text/org", "text/x-org"],
    magic_bytes=[],
    parser_class=OrgParser,
    renderer_class="all2md.renderers.org.OrgRenderer",
    renders_as_string=True,
    parser_required_packages=[("orgparse", "orgparse", "")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="Org-Mode parsing requires 'orgparse'. Install with: pip install 'all2md[org]'",
    parser_options_class=OrgParserOptions,
    renderer_options_class="all2md.options.org.OrgRendererOptions",
    description="Parse Org-Mode to AST and render AST to Org-Mode",
    priority=10,
)
