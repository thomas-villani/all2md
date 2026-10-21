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
from typing import IO, Any, cast

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
from all2md.constants import DEPS_ORG
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.org import OrgParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.html_sanitizer import sanitize_url
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)

#: Keywords that describe the document rather than the block beneath them. These are
#: read into the metadata, so they are dropped from the body above the first heading
#: instead of being printed twice. Affiliated keywords such as ``#+CAPTION:`` are
#: deliberately absent: they belong to the block that follows.
_FILE_PROPERTY_KEYWORDS = frozenset(
    {
        "AUTHOR",
        "DATE",
        "DESCRIPTION",
        "EMAIL",
        "FILETAGS",
        "KEYWORDS",
        "LANGUAGE",
        "OPTIONS",
        "PROPERTY",
        "SETUPFILE",
        "STARTUP",
        "SUBTITLE",
        "TITLE",
    }
)


def _trim_body(text: str) -> str:
    """Drop a body's surrounding blank lines, keeping its first line's indentation.

    ``str.strip`` took the first line's indent alone, and a list read by its
    indentation then saw that line's siblings as nested under it (#570).
    """
    lines = text.rstrip().split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines)


class OrgParser(BaseParser):
    r"""Convert Org-Mode to AST representation.

    This converter uses orgparse to parse Org-Mode files and builds an AST that
    matches the structure used throughout all2md, enabling bidirectional
    conversion and transformation pipelines.

    Parameters
    ----------
    options : OrgParserOptions or None, default = None
        Parser configuration options

    Notes
    -----
    **orgparse Limitations:**

    The parser relies on the orgparse library which has some known limitations:

    - **LOGBOOK drawer content**: When SCHEDULED/DEADLINE lines are placed after
      a PROPERTIES drawer (non-standard position), orgparse may strip the LOGBOOK
      drawer content. This is an orgparse limitation, not a bug in all2md.

    - **Drawer positioning**: Org-mode spec requires planning lines (SCHEDULED,
      DEADLINE, CLOSED) to come right after the heading. Some documents place them
      after PROPERTIES, which can cause parsing issues.

    - **CLOCK entries**: CLOCK entries within LOGBOOK drawers may or may not be
      available depending on document structure. The parser attempts to extract
      them from both ``node.clock`` and LOGBOOK drawer content.

    **What IS Supported:**

    - ✓ SCHEDULED timestamps with time ranges and repeaters
    - ✓ DEADLINE timestamps
    - ✓ CLOSED timestamps (when properly positioned)
    - ✓ Properties drawer (well-supported)
    - ✓ Tags and TODO keywords
    - ✓ LOGBOOK drawer (when content is available)
    - ✓ CLOCK entries (via node.clock)
    - ✓ Full timestamp metadata preservation

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

    Enhanced features:

        >>> options = OrgParserOptions(
        ...     parse_closed=True,
        ...     parse_logbook=True,
        ...     preserve_timestamp_metadata=True
        ... )
        >>> parser = OrgParser(options)
        >>> doc = parser.parse(org_file)
        >>> # Access enhanced metadata
        >>> heading = doc.children[0]
        >>> if "org_closed" in heading.metadata:
        ...     print(f"Closed: {heading.metadata['org_closed']}")

    """

    def __init__(self, options: OrgParserOptions | None = None, progress_callback: ProgressCallback | None = None):
        """Initialize the Org parser with options and progress callback."""
        BaseParser._validate_options_type(options, OrgParserOptions, "org")
        options = options or OrgParserOptions()
        super().__init__(options, progress_callback)
        self.options: OrgParserOptions = options

    @requires_dependencies("org", DEPS_ORG)
    def parse(self, input_data: str | Path | IO[bytes] | bytes) -> Document:
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
        org_content = self._load_text_content(input_data)

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
        root_body = _trim_body(root.get_body(format="raw") if hasattr(root, "get_body") else (root.body or ""))
        if root_body:
            filtered_body = self._strip_file_properties(root_body)

            if filtered_body:
                body_nodes = self._process_body(filtered_body)
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
    def _strip_file_properties(body: str) -> str:
        """Drop file-level keyword lines from the text above the first heading.

        ``#+TITLE:``, ``#+AUTHOR:`` and friends are already read into the document
        metadata, so leaving them in the body would print them twice.

        Only ``#+KEYWORD:`` lines qualify. Org spells block delimiters with the same
        ``#+`` prefix but no colon, and dropping every ``#+`` line deleted the
        ``#+BEGIN_SRC``/``#+END_SRC`` pair around a source block that appeared before
        the first heading -- the code then re-flowed as a paragraph, so a file opening
        with a code block silently lost it. The same block parsed correctly one line
        lower, under a heading, because only this preamble path filtered.

        Only keywords that really are file-level qualify. Org spells affiliated
        keywords such as ``#+CAPTION:`` the same way, and those belong to the block
        underneath them rather than to the document.

        Lines inside a block are left exactly as they are: a ``#+TITLE:`` written
        inside a source block is code, not a document property.
        """
        filtered_lines = []
        in_block = False
        for line in body.split("\n"):
            stripped = line.strip()
            if in_block:
                filtered_lines.append(line)
                if re.match(r"^#\+END_\w+", stripped, re.IGNORECASE):
                    in_block = False
                continue
            if re.match(r"^#\+BEGIN_\w+", stripped, re.IGNORECASE):
                in_block = True
                filtered_lines.append(line)
                continue
            keyword = re.match(r"^#\+([\w-]+):", stripped)
            if keyword and keyword.group(1).upper() in _FILE_PROPERTY_KEYWORDS:
                continue
            filtered_lines.append(line)
        return _trim_body("\n".join(filtered_lines))

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
        body_text = _trim_body(node.get_body(format="raw") if hasattr(node, "get_body") else (node.body or ""))
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

    def _extract_timestamp_metadata(self, timestamp_obj: Any) -> dict[str, Any] | None:
        """Extract full timestamp metadata from orgparse timestamp object.

        Parameters
        ----------
        timestamp_obj : orgparse timestamp object
            Timestamp object from orgparse (OrgDate, OrgDateScheduled, etc.)

        Returns
        -------
        dict or None
            Dictionary with timestamp metadata or None if no timestamp

        """
        if not timestamp_obj:
            return None

        metadata: dict[str, Any] = {}

        # Always store the string representation
        try:
            metadata["string"] = str(timestamp_obj)
        except Exception:
            # Handle orgparse bug where str() fails on some timestamps
            metadata["string"] = repr(timestamp_obj)

        # Store start date/time
        if hasattr(timestamp_obj, "start") and timestamp_obj.start:
            metadata["start"] = str(timestamp_obj.start)

        # Store end date/time (for time ranges)
        if hasattr(timestamp_obj, "end") and timestamp_obj.end:
            metadata["end"] = str(timestamp_obj.end)

        # Store active/inactive status
        if hasattr(timestamp_obj, "_active"):
            metadata["active"] = timestamp_obj._active

        # Store repeater information
        if hasattr(timestamp_obj, "_repeater") and timestamp_obj._repeater:
            rep_type, amount, unit = timestamp_obj._repeater
            metadata["repeater"] = {
                "type": rep_type,
                "amount": amount,
                "unit": unit,
                "string": f"{rep_type}{amount}{unit}",
            }

        # Store warning information
        if hasattr(timestamp_obj, "_warning") and timestamp_obj._warning:
            metadata["warning"] = timestamp_obj._warning

        return metadata

    def _parse_logbook_drawer(self, body_text: str) -> dict[str, Any] | None:
        """Parse LOGBOOK drawer from body text.

        Parameters
        ----------
        body_text : str
            Body text that may contain LOGBOOK drawer

        Returns
        -------
        dict or None
            Dictionary with logbook entries and raw content, or None if no logbook

        """
        # Match :LOGBOOK: ... :END:
        pattern = r":LOGBOOK:\s*\n(.*?)\n:END:"
        match = re.search(pattern, body_text, re.DOTALL)

        if not match:
            return None

        logbook_content = match.group(1).strip()
        entries: list[dict[str, Any]] = []

        for line in logbook_content.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Parse state changes: - State "NEW" from "OLD" [timestamp]
            state_match = re.match(r'-\s+State\s+"([^"]+)"\s+from\s+"([^"]+)"\s+\[(.+?)\]', line)
            if state_match:
                entries.append(
                    {
                        "type": "state_change",
                        "new_state": state_match.group(1),
                        "old_state": state_match.group(2),
                        "timestamp": state_match.group(3),
                    }
                )
                continue

            # Parse CLOCK entries: CLOCK: [start]--[end] => duration
            clock_match = re.match(r"CLOCK:\s+\[(.+?)\](?:--\[(.+?)\])?\s*(?:=>\s+(.+))?", line)
            if clock_match:
                entries.append(
                    {
                        "type": "clock",
                        "start": clock_match.group(1),
                        "end": clock_match.group(2) if clock_match.group(2) else None,
                        "duration": clock_match.group(3) if clock_match.group(3) else None,
                    }
                )
                continue

            # Parse notes: - Note text [timestamp]
            note_match = re.match(r"-\s+(.+?)\s+\[(.+?)\]", line)
            if note_match:
                entries.append({"type": "note", "content": note_match.group(1), "timestamp": note_match.group(2)})
                continue

        if not entries:
            return None

        return {"entries": entries, "raw": logbook_content}

    def _extract_todo_state(self, node: Any) -> tuple[str | None, bool]:
        """Extract TODO state from headline node.

        Parameters
        ----------
        node : orgparse.OrgNode
            Orgparse node representing a headline

        Returns
        -------
        tuple[str | None, bool]
            Tuple of (todo_state, manually_extracted) where manually_extracted
            indicates if the TODO keyword was manually parsed from heading text

        """
        # First try orgparse's detection
        if node.todo and node.todo in self.options.todo_keywords:
            return node.todo, False

        # Manually check if heading starts with a TODO keyword that orgparse didn't recognize
        if not node.todo:
            heading_parts = node.heading.split(None, 1)
            if heading_parts and heading_parts[0] in self.options.todo_keywords:
                return heading_parts[0], True

        return None, False

    def _extract_scheduling_to_metadata(self, node: Any, heading_metadata: dict[str, Any]) -> None:
        """Extract scheduling information (SCHEDULED/DEADLINE) into heading metadata.

        Parameters
        ----------
        node : orgparse.OrgNode
            Orgparse node with potential scheduling info
        heading_metadata : dict[str, Any]
            Metadata dictionary to update in-place

        """
        if not self.options.parse_scheduling:
            return

        if hasattr(node, "scheduled") and node.scheduled:
            if self.options.preserve_timestamp_metadata:
                sched_metadata = self._extract_timestamp_metadata(node.scheduled)
                if sched_metadata:
                    heading_metadata["org_scheduled"] = sched_metadata
            else:
                # Legacy: just store string
                try:
                    heading_metadata["org_scheduled"] = str(node.scheduled)
                except Exception:
                    heading_metadata["org_scheduled"] = repr(node.scheduled)

        if hasattr(node, "deadline") and node.deadline:
            if self.options.preserve_timestamp_metadata:
                deadline_metadata = self._extract_timestamp_metadata(node.deadline)
                if deadline_metadata:
                    heading_metadata["org_deadline"] = deadline_metadata
            else:
                # Legacy: just store string
                try:
                    heading_metadata["org_deadline"] = str(node.deadline)
                except Exception:
                    heading_metadata["org_deadline"] = repr(node.deadline)

    def _extract_closed_to_metadata(self, node: Any, heading_metadata: dict[str, Any]) -> None:
        """Extract CLOSED timestamp into heading metadata.

        Parameters
        ----------
        node : orgparse.OrgNode
            Orgparse node with potential closed timestamp
        heading_metadata : dict[str, Any]
            Metadata dictionary to update in-place

        """
        if not self.options.parse_closed:
            return

        if not (hasattr(node, "closed") and node.closed):
            return

        if self.options.preserve_timestamp_metadata:
            closed_metadata = self._extract_timestamp_metadata(node.closed)
            if closed_metadata:
                heading_metadata["org_closed"] = closed_metadata
        else:
            # Legacy: just store string
            try:
                heading_metadata["org_closed"] = str(node.closed)
            except Exception:
                heading_metadata["org_closed"] = repr(node.closed)

    def _extract_clock_to_metadata(self, node: Any, heading_metadata: dict[str, Any]) -> None:
        """Extract CLOCK entries into heading metadata.

        Parameters
        ----------
        node : orgparse.OrgNode
            Orgparse node with potential clock entries
        heading_metadata : dict[str, Any]
            Metadata dictionary to update in-place

        """
        if not self.options.parse_clock:
            return

        if not (hasattr(node, "clock") and node.clock):
            return

        clock_entries = []
        for clock in node.clock:
            entry: dict[str, Any] = {}
            if hasattr(clock, "start") and clock.start:
                entry["start"] = str(clock.start)
            if hasattr(clock, "end") and clock.end:
                entry["end"] = str(clock.end)
            # Try to get duration if available
            if hasattr(clock, "duration"):
                try:
                    entry["duration"] = str(clock.duration)
                except Exception:
                    # orgparse may raise computing duration for malformed
                    # clock entries; omit the duration field.
                    pass
            if entry:
                clock_entries.append(entry)

        if clock_entries:
            heading_metadata["org_clock"] = clock_entries

    def _extract_logbook_to_metadata(self, node: Any, heading_metadata: dict[str, Any]) -> None:
        """Extract LOGBOOK drawer into heading metadata.

        Parameters
        ----------
        node : orgparse.OrgNode
            Orgparse node with potential logbook drawer
        heading_metadata : dict[str, Any]
            Metadata dictionary to update in-place

        """
        if not self.options.parse_logbook:
            return

        body_text = node.get_body(format="raw") if hasattr(node, "get_body") else (node.body if node.body else "")
        if body_text:
            logbook_data = self._parse_logbook_drawer(body_text)
            if logbook_data:
                heading_metadata["org_logbook"] = logbook_data

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
        # Extract TODO / priority / tags first: orgparse sets heading='' for ``* TODO``.
        todo_state, manually_extracted_todo = self._extract_todo_state(node)
        priority = node.priority if hasattr(node, "priority") and node.priority else None
        tags = list(node.tags) if self.options.parse_tags and hasattr(node, "tags") and node.tags else []

        if not node.heading and not todo_state and not priority and not tags:
            return None

        # Extract heading level (number of stars). Org allows >6 stars; AST caps at 6.
        level = min(node.level, 6)

        # Parse inline content from heading text
        # If we manually extracted TODO, remove it from the heading text
        heading_text = node.heading
        if manually_extracted_todo and todo_state:
            heading_text = heading_text[len(todo_state) :].lstrip()
        # Empty title + TODO/priority: put marker in content so markdown keeps it
        content: list[Node]
        if not heading_text and todo_state:
            content = [Text(content=todo_state)]
        elif not heading_text and priority:
            content = [Text(content=f"[#{priority}]")]
        else:
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

        # Extract scheduling, closed, clock, and logbook metadata
        self._extract_scheduling_to_metadata(node, heading_metadata)
        self._extract_closed_to_metadata(node, heading_metadata)
        self._extract_clock_to_metadata(node, heading_metadata)
        self._extract_logbook_to_metadata(node, heading_metadata)

        return Heading(level=level, content=content, metadata=heading_metadata)

    @staticmethod
    def _split_body_blocks(body_text: str) -> list[tuple[int, str]]:
        """Split body text into blocks, keeping each greater block in one piece.

        Blank lines separate Org elements, but not inside a greater block: a
        ``#+BEGIN_SRC``/``#+END_SRC`` pair runs to its own delimiter no matter how many
        blank lines the code between them contains. Splitting on blank lines first cut
        such a block into fragments -- the one holding ``#+BEGIN_SRC`` had no end, the
        middle ones re-parsed as prose, and the last printed ``#+END_SRC`` verbatim as
        body text. So the segmentation has to know where a block is open, the same way
        the file-property filter above already does.

        A greater block also starts and ends an element of its own, so a delimiter that
        follows or precedes ordinary text without a blank line between them still marks
        a boundary. The one exception is an affiliated keyword such as ``#+CAPTION:``,
        which belongs to the block written underneath it and therefore stays attached.

        Each block is returned with the number of blank lines that preceded it,
        because Org gives that count meaning: one blank line after a footnote
        definition continues the definition, two end it.
        """
        blocks: list[tuple[int, str]] = []
        current: list[str] = []
        open_kind: str | None = None
        gap = 0
        gap_before_current = 0

        def flush() -> None:
            if current:
                blocks.append((gap_before_current, "\n".join(current)))
                current.clear()

        def append_line(text: str) -> None:
            nonlocal gap, gap_before_current
            if not current:
                gap_before_current = gap
            gap = 0
            current.append(text)

        for line in body_text.split("\n"):
            stripped = line.strip()

            if open_kind is not None:
                current.append(line)
                if re.match(rf"^#\+END_{re.escape(open_kind)}\b", stripped, re.IGNORECASE):
                    open_kind = None
                    flush()
                continue

            begin = re.match(r"^#\+BEGIN_(\w+)", stripped, re.IGNORECASE)
            if begin:
                # Affiliated keywords belong to the block below them; anything else is a
                # separate element that the block must not swallow.
                if not all(re.match(r"^#\+[\w-]+:", pending.strip()) for pending in current):
                    flush()
                open_kind = begin.group(1)
                append_line(line)
                continue

            if not stripped:
                flush()
                gap += 1
                continue

            append_line(line)

        flush()
        return blocks

    @staticmethod
    def _is_paragraph_content_block(block: str) -> bool:
        """Whether *block* would parse as a plain paragraph.

        Used to decide if a block continues a footnote definition. Anything
        that would parse as a structural element -- another definition, a
        thematic break, a table, a list, a greater block, a block quote --
        ends the definition instead of joining it.
        """
        if not block or re.match(r"^-{5,}$", block) or re.match(r"^\[fn:[^\]]+\]", block):
            return False
        if block.startswith(("#+", "|", "\\[")):
            return False
        if re.search(r"^-\s+.+?\s+::\s+", block, re.MULTILINE):
            return False
        if re.match(r"^([\-\+\*]\s+|\d+[\.\)]\s*)", block):
            return False
        if all(line.strip().startswith(":") for line in block.split("\n") if line.strip()):
            return False
        return True

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

        Notes
        -----
        Drawer content (e.g., :LOGBOOK:, :CLOCK:) is not supported as the orgparse
        library strips this content before we can access it.

        """
        result: list[Node] = []

        # Split into blocks (separated by blank lines), keeping greater blocks whole
        blocks = self._split_body_blocks(body_text)

        # Track footnote definitions for later
        footnote_defs: list[FootnoteDefinition] = []

        index = 0
        while index < len(blocks):
            raw_block = blocks[index][1]
            block = raw_block.strip()
            index += 1
            if not block:
                continue

            # `#+CAPTION:` is an affiliated keyword: it belongs to the block written
            # under it, and no blank line separates the two, so it arrives at the head
            # of this block rather than as one of its own.
            caption = None
            caption_match = re.match(r"^#\+CAPTION:\s*(.*)$", block.split("\n", 1)[0], re.IGNORECASE)
            if caption_match:
                caption = caption_match.group(1).strip() or None
                block = block.split("\n", 1)[1].strip() if "\n" in block else ""
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
                # Org continues a definition across a single blank line; two
                # consecutive blank lines (or the next definition) end it. Each
                # single-gap paragraph block that follows is another paragraph
                # of this definition, not document content. Structural blocks
                # (lists, tables, greater blocks...) end the definition here --
                # a conservative reading of the spec, which would keep them too.
                while index < len(blocks):
                    next_gap, next_block = blocks[index]
                    next_block = next_block.strip()
                    if next_gap != 1 or not self._is_paragraph_content_block(next_block):
                        break
                    continuation = self._parse_paragraph(next_block)
                    if continuation:
                        footnote_content.append(continuation)
                    index += 1
                footnote_def = FootnoteDefinition(identifier=footnote_id, content=cast(list[Node], footnote_content))
                footnote_defs.append(footnote_def)
                continue

            # Check for math blocks \[...\]
            math_block_match = re.match(r"^\\\[(.+?)\\\]$", block, re.DOTALL)
            if math_block_match:
                math_content = math_block_match.group(1).strip()
                result.append(MathBlock(content=math_content, notation="latex"))
                continue

            # Check for greater blocks (#+BEGIN_X / #+END_X)
            greater_block = re.match(r"^#\+BEGIN_(\w+)", block, re.IGNORECASE)
            if greater_block:
                result.extend(self._parse_greater_block(greater_block.group(1).upper(), block))
                continue

            # Check for tables (lines starting with |)
            if block.startswith("|"):
                table = self._parse_table(block)
                if table:
                    if caption:
                        table.caption = caption
                    result.append(table)
                continue

            # Check for definition lists (- term :: definition)
            if re.search(r"^-\s+.+?\s+::\s+", block, re.MULTILINE):
                def_list = self._parse_definition_list(block)
                if def_list:
                    result.append(def_list)
                    continue

            # Lists require a space after the marker (+gone+ is strikethrough, not a list)
            if re.match(r"^([\-\+\*]\s+|\d+[\.\)]\s*)", block):
                # The list parser reads indentation, so it gets the block as written:
                # stripping takes the first item's indent alone, and its siblings then
                # read as nested under it. A caption line was cut from the head already.
                result.extend(self._parse_lists(block if caption else raw_block))
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
        r"""Parse inline formatting in text.

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

    def _parse_greater_block(self, kind: str, block: str) -> list[Node]:
        """Parse an Org greater block into AST nodes.

        ``#+BEGIN_SRC`` was the only one recognized, so ``#+BEGIN_QUOTE`` and
        ``#+BEGIN_EXAMPLE`` fell through to the paragraph branch and their delimiter
        lines were rendered as body text -- and mangled on the way, since ``+...+``
        is Org's strikethrough syntax, so ``#+BEGIN_QUOTE`` came out as ``#~~BEGIN_QUOTE``.

        A block kind that is still unrecognized contributes its contents and drops its
        delimiters, which is what the rest of the pipeline can represent.
        """
        if kind == "SRC":
            code_block = self._parse_code_block(block)
            return [code_block] if code_block else []

        content = self._greater_block_content(block, kind)
        if not content.strip():
            return []
        if kind == "EXAMPLE":
            # An example block is verbatim text with no language, which is exactly a
            # fenced code block with none set.
            return [CodeBlock(content=content)]
        if kind == "QUOTE":
            return [BlockQuote(children=self._process_body(content))]
        return self._process_body(content)

    @staticmethod
    def _greater_block_content(block: str, kind: str) -> str:
        """Return the lines between a greater block's ``#+BEGIN_``/``#+END_`` delimiters."""
        lines = block.split("\n")
        end_marker = f"#+end_{kind.lower()}"
        content_lines = []
        started = False
        for line in lines:
            stripped = line.strip().lower()
            if not started:
                started = stripped.startswith(f"#+begin_{kind.lower()}")
                continue
            if stripped.startswith(end_marker):
                break
            content_lines.append(line)
        return "\n".join(content_lines)

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
        header: TableRow | None = None

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

    #: An Org list item's marker: a bullet, or a number closed by ``.`` or ``)``. The
    #: content group is optional -- a bullet with nothing after it is still an item.
    _BULLET_MARKER = re.compile(r"^[\-\+\*](?:\s+(.*))?$")
    _ORDERED_MARKER = re.compile(r"^(\d+)[\.\)](?:\s+(.*))?$")

    def _parse_lists(self, block: str) -> list[List]:
        """Parse an Org list block, nested lists included.

        Parameters
        ----------
        block : str
            List block text

        Returns
        -------
        list of List
            One List per run of same-kind items at the block's outer indentation;
            bullets followed by numbered items at the same level are two lists

        Notes
        -----
        Indentation is what marks a sub-item, so every line is read as
        ``(indent, text)``. A line indented past an item's marker belongs to that
        item: a marker there opens a nested list of either kind, and an unmarked line
        continues the item's text. The loop used to strip each line before matching
        it and choose one marker kind for the whole block, so a nested bullet came
        back as a sibling and a nested numbered item folded into its parent's text
        (#570). The result is the ``ListItem > [Paragraph, List]`` shape the Markdown
        and AsciiDoc parsers already build.

        """
        lines = [(len(line) - len(line.lstrip()), line.strip()) for line in block.split("\n") if line.strip()]
        lists: list[List] = []
        index = 0
        while index < len(lines):
            list_node, next_index = self._parse_list_lines(lines, index)
            if list_node is None or next_index == index:
                break
            lists.append(list_node)
            index = next_index
        return lists

    def _parse_list(self, block: str) -> List | None:
        """Parse an Org list block and return its first list.

        Parameters
        ----------
        block : str
            List block text

        Returns
        -------
        List or None
            List AST node

        """
        lists = self._parse_lists(block)
        return lists[0] if lists else None

    def _match_list_marker(self, text: str) -> tuple[bool, int, str] | None:
        """Match a list marker, returning ``(ordered, number, rest)`` or None."""
        ordered_match = self._ORDERED_MARKER.match(text)
        if ordered_match:
            return True, int(ordered_match.group(1)), (ordered_match.group(2) or "").strip()
        bullet_match = self._BULLET_MARKER.match(text)
        if bullet_match:
            return False, 1, (bullet_match.group(1) or "").strip()
        return None

    def _parse_list_lines(self, lines: list[tuple[int, str]], index: int) -> tuple[List | None, int]:
        """Parse one list starting at ``lines[index]``.

        Parameters
        ----------
        lines : list of (int, str)
            The block's non-blank lines as ``(indent, stripped text)``
        index : int
            Position of the list's first item

        Returns
        -------
        tuple of (List or None, int)
            The list, and the position of the first line it did not consume: a line
            indented less than the list, or a marker of the other kind at its level

        """
        first = self._match_list_marker(lines[index][1])
        if first is None:
            return None, index
        base_indent = lines[index][0]
        ordered = first[0]
        # The list's own first number is its start. Taking it is what the Markdown
        # parser already does, and without it a list written `5.` came back at 1 --
        # the number was present in the document and discarded on the way in.
        start = first[1] if ordered else 1
        items: list[ListItem] = []

        while index < len(lines):
            indent, text = lines[index]
            marker = self._match_list_marker(text)
            # Only a same-kind marker at the list's own indentation opens an item.
            if marker is None or indent != base_indent or marker[0] != ordered:
                break
            index += 1

            # An item owns every line indented past its marker. A marker there opens a
            # nested list; any other line continues the item's text. In a nested list, an
            # unmarked line back at the marker's own column ends the item, as in Org, and
            # goes to the parent. At the outermost level there is no parent, so such a
            # line is read as a lazy wrap rather than dropped. Run-on lines join with a
            # single space, as the AsciiDoc parser joins them (#343).
            texts = [marker[2]]
            children: list[Node] = []
            while index < len(lines):
                child_indent, child_text = lines[index]
                child_marker = self._match_list_marker(child_text)
                if child_marker is not None and child_indent > base_indent:
                    self._flush_item_text(texts, children)
                    texts = []
                    nested, index = self._parse_list_lines(lines, index)
                    if nested is not None:
                        children.append(nested)
                    continue
                if child_marker is None and (child_indent > base_indent or base_indent == 0):
                    texts.append(child_text)
                    index += 1
                    continue
                break
            counter = self._flush_item_text(texts, children)
            if counter is not None and not items:
                start = counter
            items.append(ListItem(children=children))

        return List(ordered=ordered, start=start, items=items), index

    def _flush_item_text(self, texts: list[str], children: list[Node]) -> int | None:
        """Append an item's pending run-on lines to ``children`` as one Paragraph.

        Returns the item's ``[@N]`` counter when the text opens with one. That is
        Org's own counter set, and it wins over the literal number it follows -- that
        is the whole point of writing it. Only the item's first text can carry it.

        """
        item_text = " ".join(t for t in texts if t).strip()
        counter = None
        if not children:
            counter_match = re.match(r"^\[@(\d+)\]\s*(.*)$", item_text, re.DOTALL)
            if counter_match:
                counter = int(counter_match.group(1))
                item_text = counter_match.group(2).strip()
        if item_text:
            children.append(Paragraph(content=self._parse_inline(item_text)))
        return counter

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
        entries: list[tuple[str, list[str]]] = []  # (term text, definition lines)

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Match definition list item: - term :: definition
            match = re.match(r"^-\s+(.+?)\s+::\s+(.+)$", line_stripped)
            if match:
                entries.append((match.group(1), [match.group(2)]))
            elif entries:
                # A line that does not open a new item continues the previous item's
                # definition -- an indented wrap, which is how Org (and this module's
                # own renderer) spells a definition longer than one line. These lines
                # used to be skipped outright, silently DELETING every line of a
                # definition after its first (#352). Within one block there are no
                # blank lines, so a continuation is the same paragraph by Org's rules
                # and joins with a space.
                entries[-1][1].append(line_stripped)

        items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = []
        for term_text, definition_lines in entries:
            term = DefinitionTerm(content=self._parse_inline(term_text))
            def_content = self._parse_inline(" ".join(definition_lines))
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
