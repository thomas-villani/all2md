#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/ini.py
"""INI rendering from AST.

This module provides the IniRenderer class which extracts section-based data
from AST documents and converts it to INI format. The primary use case is
extracting configuration from markdown documentation as INI files.

Examples
--------
Extract configuration from markdown:
    Input markdown:
        # server
        * **host**: localhost
        * **port**: 8080

        # database
        * **name**: mydb
        * **timeout**: 30

    Output INI:
        [server]
        host = localhost
        port = 8080

        [database]
        name = mydb
        timeout = 30

"""

from __future__ import annotations

import configparser
import io
import logging
from pathlib import Path
from typing import IO, Any, Union

from all2md.ast.nodes import Document, Heading, ListItem, Node, Paragraph, Strong, Text
from all2md.ast.nodes import List as AstList
from all2md.exceptions import RenderingError
from all2md.options.ini import IniRendererOptions
from all2md.renderers.base import BaseRenderer

logger = logging.getLogger(__name__)


class RawConfigParser(configparser.RawConfigParser):
    """Custom ConfigParser that preserves case."""

    def optionxform(self, optionstr: str) -> str:
        """Override to preserve case of option names."""
        return optionstr


class IniRenderer(BaseRenderer):
    """Render AST to INI format by extracting section-based data.

    This renderer extracts sections and key-value pairs from AST documents
    and converts them to INI format. Level-1 headings become sections, and
    definition lists (bold keys with values) become key-value pairs.

    Parameters
    ----------
    options : IniRendererOptions or None, default = None
        INI rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, List, ListItem, Paragraph, Strong, Text
        >>> from all2md.renderers.ini import IniRenderer
        >>> heading = Heading(level=1, content=[Text(content="server")])
        >>> list_item = ListItem(children=[
        ...     Paragraph(content=[
        ...         Strong(content=[Text(content="host")]),
        ...         Text(content=": localhost")
        ...     ])
        ... ])
        >>> list_node = List(items=[list_item], ordered=False)
        >>> doc = Document(children=[heading, list_node])
        >>> renderer = IniRenderer()
        >>> ini_text = renderer.render_to_string(doc)

    """

    def __init__(self, options: IniRendererOptions | None = None):
        """Initialize the INI renderer with options."""
        BaseRenderer._validate_options_type(options, IniRendererOptions, "ini")
        options = options or IniRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: IniRendererOptions = options

    def render(self, doc: Document, output: Union[str, Path, IO[bytes], IO[str]]) -> None:
        """Render AST document to INI file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, IO[bytes], or IO[str]
            Output destination

        """
        ini_str = self.render_to_string(doc)

        # Write to output
        if isinstance(output, (str, Path)):
            with open(output, "w", encoding="utf-8") as f:
                f.write(ini_str)
        elif hasattr(output, "write"):
            if hasattr(output, "mode") and "b" in getattr(output, "mode", ""):
                # Binary mode - encode to bytes
                output.write(ini_str.encode("utf-8"))  # type: ignore[arg-type]
            else:
                # Text mode
                output.write(ini_str)  # type: ignore[call-overload]
        else:
            raise RenderingError(f"Unsupported output type: {type(output)}")

    def render_to_string(self, doc: Document) -> str:
        """Render AST document to INI string.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        str
            INI string

        """
        try:
            # Extract structured data
            data = self._extract_data(doc)

            # Convert to INI using configparser
            config: RawConfigParser | configparser.ConfigParser
            if self.options.preserve_case:
                config = RawConfigParser(allow_no_value=self.options.allow_no_value)
            else:
                config = configparser.ConfigParser(allow_no_value=self.options.allow_no_value)

            # Add sections and values
            for section, values in data.items():
                config.add_section(section)
                for key, value in values.items():
                    if value is None or value == "":
                        if self.options.allow_no_value:
                            config.set(section, key)
                        else:
                            config.set(section, key, "")
                    else:
                        config.set(section, key, str(value))

            # Write to string
            output = io.StringIO()
            config.write(output)
            return output.getvalue()

        except Exception as e:
            raise RenderingError(f"Failed to render INI: {e}") from e

    def _extract_data(self, doc: Document) -> dict[str, dict[str, Any]]:
        """Extract structured data from document.

        Parameters
        ----------
        doc : Document
            Document to extract from

        Returns
        -------
        dict[str, dict[str, Any]]
            Extracted data as {section: {key: value}}

        """
        extractor = DataExtractor(self.options)
        return extractor.extract(doc)


class DataExtractor:
    """Extractor that walks AST and extracts section-based data.

    This class walks the AST and extracts sections (from headings) and
    key-value pairs (from definition lists).

    Parameters
    ----------
    options : IniRendererOptions
        Rendering options

    """

    def __init__(self, options: IniRendererOptions):
        """Initialize the data extractor."""
        self.options = options
        self.data: dict[str, dict[str, Any]] = {}
        self.current_section: str | None = None

    def extract(self, doc: Document) -> dict[str, dict[str, Any]]:
        """Extract data from document.

        Parameters
        ----------
        doc : Document
            Document to extract from

        Returns
        -------
        dict[str, dict[str, Any]]
            Extracted data as {section: {key: value}}

        """
        # Walk through document children
        for child in doc.children:
            self._process_node(child)
        return self.data

    def _process_node(self, node: Node) -> None:
        """Process a single node.

        Parameters
        ----------
        node : Node
            Node to process

        """
        if isinstance(node, Heading):
            if self.options.section_from_headings and node.level == 1:
                self._process_heading(node)
        elif isinstance(node, AstList):
            self._process_list(node)
        # For other nodes, recursively process children
        elif hasattr(node, "children") and isinstance(node.children, list):
            for child in node.children:
                self._process_node(child)

    def _process_heading(self, node: Heading) -> None:
        """Process heading node and create new section.

        Parameters
        ----------
        node : Heading
            Heading node to process

        """
        # Extract text from heading
        text_parts: list[str] = []
        for child in node.content:
            if isinstance(child, Text):
                text_parts.append(child.content)
        section_name = "".join(text_parts).strip()

        # Create new section
        self.current_section = section_name
        if section_name not in self.data:
            self.data[section_name] = {}

    def _process_list(self, node: AstList) -> None:
        """Process list node and extract key-value pairs.

        Parameters
        ----------
        node : AstList
            List node to process

        """
        # Only process if we have a current section
        if not self.current_section:
            # Create default section
            self.current_section = "DEFAULT"
            self.data[self.current_section] = {}

        # Extract key-value pairs from definition list items
        for item in node.items:
            key, value = self._extract_key_value(item)
            if key:
                # Type inference
                if self.options.type_inference and value:
                    value = self._infer_type(value)

                self.data[self.current_section][key] = value

    def _extract_key_value(self, item: ListItem) -> tuple[str | None, str | None]:
        """Extract key and value from list item.

        Expected format: **key**: value

        Parameters
        ----------
        item : ListItem
            List item to process

        Returns
        -------
        tuple[str | None, str | None]
            (key, value) tuple

        """
        # Look for pattern: Strong(key) + Text(": value")
        for child in item.children:
            if isinstance(child, Paragraph):
                key = None
                value_parts: list[str] = []
                found_separator = False

                for inline in child.content:
                    if isinstance(inline, Strong):
                        # Extract key from Strong
                        key_parts: list[str] = []
                        for key_child in inline.content:
                            if isinstance(key_child, Text):
                                key_parts.append(key_child.content)
                        key = "".join(key_parts).strip()
                    elif isinstance(inline, Text):
                        text = inline.content
                        # Check if this is the separator
                        if text.startswith(":"):
                            found_separator = True
                            # Add everything after the colon
                            text = text[1:].strip()
                            if text:
                                value_parts.append(text)
                        elif found_separator:
                            value_parts.append(text)

                if key:
                    value = "".join(value_parts).strip() if value_parts else None
                    return (key, value)

        return (None, None)

    def _infer_type(self, value: str) -> Any:
        """Infer and convert type from string.

        Parameters
        ----------
        value : str
            String value to convert

        Returns
        -------
        Any
            Converted value (Note: INI stores all as strings, but this helps with consistency)

        """
        # Empty string
        if not value or value.strip() == "":
            return ""

        stripped = value.strip().lower()

        # Boolean
        if stripped in ("true", "yes", "on", "1"):
            return "true"
        if stripped in ("false", "no", "off", "0"):
            return "false"

        # Number - keep as string with formatting removed
        try:
            # Remove thousand separators if present
            if "," in value:
                return value.replace(",", "")
        except Exception:
            pass

        # Return as string
        return value
