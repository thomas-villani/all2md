#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/ini.py
"""INI to AST converter.

This module provides intelligent conversion from INI structures to readable
document format. By default, it transforms the structure into a hierarchical
document with headings and definition lists. Alternatively, it can render INI
as a literal code block (via the `literal_block` option).

Examples
--------
**Smart Conversion (default):**

Input INI::

    [server]
    host = localhost
    port = 8080

    [database]
    name = mydb
    timeout = 30

Output (as markdown):

.. code-block:: markdown

    # server
    * **host**: localhost
    * **port**: 8,080

    # database
    * **name**: mydb
    * **timeout**: 30

**Literal Block Mode:**

Input INI (same as above)

Output (as markdown):

.. code-block:: ini

    [server]
    host = localhost
    port = 8080

    [database]
    name = mydb
    timeout = 30

"""

from __future__ import annotations

import configparser
import logging
from pathlib import Path
from typing import IO, Optional, Union

from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    List,
    ListItem,
    Node,
    Paragraph,
    Strong,
    Text,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.ini import IniParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class RawConfigParser(configparser.RawConfigParser):
    """Custom ConfigParser that preserves case."""

    def optionxform(self, optionstr: str) -> str:
        """Override to preserve case of option names."""
        return optionstr


class IniParser(BaseParser):
    r"""Convert INI structures to AST representation.

    This parser creates a readable document from INI by converting:
    - Sections → headings
    - Key-value pairs → definition lists (bullet lists with bold keys)
    - Comments → preserved as paragraphs (if supported)

    Parameters
    ----------
    options : IniParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = IniParser()
        >>> doc = parser.parse('[server]\\nhost = localhost\\nport = 8080')

    With options:

        >>> options = IniParserOptions(preserve_case=True, allow_no_value=True)
        >>> parser = IniParser(options)
        >>> doc = parser.parse(ini_file_path)

    """

    def __init__(self, options: IniParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the INI parser with options and progress callback."""
        BaseParser._validate_options_type(options, IniParserOptions, "ini")
        options = options or IniParserOptions()
        super().__init__(options, progress_callback)
        self.options: IniParserOptions = options

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse INI input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            INI input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw INI bytes
            - INI string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        ParsingError
            If parsing fails

        """
        self._emit_progress("started", "Parsing INI", current=0, total=100)

        try:
            # Load content using BaseParser helper
            content = self._load_text_content(input_data)

            # Check if we should render as literal code block
            if self.options.literal_block:
                self._emit_progress("completed", "INI wrapped as code block", current=100, total=100)

                # Create code block
                code_block = CodeBlock(content=content, language="ini")
                metadata = DocumentMetadata()
                return Document(children=[code_block], metadata=metadata.to_dict())

            self._emit_progress("parsing", "Parsing INI structure", current=30, total=100)

            # Parse INI
            try:
                # Create parser with appropriate options
                parser: RawConfigParser | configparser.ConfigParser
                if self.options.preserve_case:
                    parser = RawConfigParser(allow_no_value=self.options.allow_no_value)
                else:
                    parser = configparser.ConfigParser(allow_no_value=self.options.allow_no_value)

                parser.read_string(content)
            except configparser.Error as e:
                raise ParsingError(f"Invalid INI: {e}") from e

            self._emit_progress("converting", "Converting to document structure", current=60, total=100)

            # Convert to AST
            children: list[Node] = []

            # Convert each section
            for section in parser.sections():
                # Add section heading
                children.append(Heading(level=1, content=[Text(content=section)]))

                # Convert section items to definition list
                items = list(parser.items(section))
                if items:
                    list_items: list[ListItem] = []
                    for key, value in items:
                        # Format value
                        if value is None or value == "":
                            value_text = ""
                        elif self.options.pretty_format_numbers:
                            # Try to format as number
                            try:
                                num_value = int(value)
                                if abs(num_value) >= 1000:
                                    value_text = f"{num_value:,}"
                                else:
                                    value_text = value
                            except ValueError:
                                value_text = value
                        else:
                            value_text = value

                        # Create list item with bold key
                        if value_text:
                            item_content: list[Node] = [
                                Paragraph(
                                    content=[
                                        Strong(content=[Text(content=key)]),
                                        Text(content=f": {value_text}"),
                                    ]
                                )
                            ]
                        else:
                            # No value - just show key
                            item_content = [
                                Paragraph(
                                    content=[
                                        Strong(content=[Text(content=key)]),
                                    ]
                                )
                            ]

                        list_items.append(ListItem(children=item_content))

                    if list_items:
                        children.append(List(items=list_items, ordered=False))

            self._emit_progress("completed", "INI parsing completed", current=100, total=100)

            # Create document
            metadata = self.extract_metadata(parser)
            return Document(children=children, metadata=metadata.to_dict())

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(f"Failed to parse INI: {e}") from e

    def extract_metadata(self, parser: RawConfigParser | configparser.ConfigParser) -> DocumentMetadata:
        """Extract metadata from INI structure.

        Parameters
        ----------
        parser : RawConfigParser or ConfigParser
            Parsed INI configuration

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Try to extract title from common section/key combinations
        for section in ["metadata", "info", "config"]:
            if parser.has_section(section):
                for key in ["title", "name"]:
                    if parser.has_option(section, key):
                        metadata.title = parser.get(section, key)
                        break
                if metadata.title:
                    break

        return metadata


def _detect_ini_content(content: bytes) -> bool:
    """Detect if content is INI.

    Parameters
    ----------
    content : bytes
        File content to analyze

    Returns
    -------
    bool
        True if content appears to be INI

    """
    try:
        content_str = content.decode("utf-8", errors="ignore").strip()
        if not content_str:
            return False

        # Try to parse as INI
        parser = configparser.ConfigParser()
        parser.read_string(content_str)

        # Must have at least one section to be valid INI
        return len(parser.sections()) > 0
    except Exception:
        return False


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="ini",
    extensions=[".ini", ".cfg", ".conf"],
    mime_types=["text/plain"],  # INI doesn't have a standard MIME type
    magic_bytes=[],
    content_detector=_detect_ini_content,
    parser_class=IniParser,
    renderer_class="all2md.renderers.ini.IniRenderer",
    renders_as_string=True,
    parser_required_packages=[],  # stdlib only
    renderer_required_packages=[],
    import_error_message="INI conversion uses Python standard library (no dependencies)",
    parser_options_class=IniParserOptions,
    renderer_options_class="all2md.options.ini.IniRendererOptions",
    description="Convert INI configuration files to/from readable documents with sections and key-value pairs",
    priority=10,
)
