#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Metadata extraction and YAML front matter utilities for all2md.

This module provides utilities for extracting document metadata and formatting it
as YAML front matter for prepending to Markdown output. It includes a simple
YAML formatter that doesn't require the PyYAML dependency.

The metadata extraction supports various document properties like title, author,
creation date, keywords, and format-specific metadata fields.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


@dataclass
class DocumentMetadata:
    """Container for extracted document metadata.

    Parameters
    ----------
    title : str | None
        Document title
    author : str | None
        Primary author or creator
    subject : str | None
        Document subject or description
    keywords : list[str] | None
        Document keywords or tags
    creation_date : datetime | str | None
        Document creation date
    modification_date : datetime | str | None
        Last modification date
    creator : str | None
        Software/tool that created the document
    producer : str | None
        Software/tool that produced the document
    category : str | None
        Document category or type
    language : str | None
        Document language
    custom : dict[str, Any]
        Custom metadata fields specific to document format
    """

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[List[str]] = None
    creation_date: Optional[Union[datetime, str]] = None
    modification_date: Optional[Union[datetime, str]] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary, excluding None values.

        Returns
        -------
        dict
            Dictionary containing only non-None metadata fields
        """
        result = {}

        # Standard fields
        if self.title:
            result['title'] = self.title
        if self.author:
            result['author'] = self.author
        if self.subject:
            result['description'] = self.subject
        if self.keywords:
            result['keywords'] = self.keywords
        if self.creation_date:
            if isinstance(self.creation_date, datetime):
                result['creation_date'] = self.creation_date.strftime('%Y-%m-%d')
            else:
                result['creation_date'] = str(self.creation_date)
        if self.modification_date:
            if isinstance(self.modification_date, datetime):
                result['modification_date'] = self.modification_date.strftime('%Y-%m-%d')
            else:
                result['modification_date'] = str(self.modification_date)
        if self.creator:
            result['creator'] = self.creator
        if self.producer:
            result['producer'] = self.producer
        if self.category:
            result['category'] = self.category
        if self.language:
            result['language'] = self.language

        # Add custom fields
        for key, value in self.custom.items():
            if value is not None:
                result[key] = value

        return result


def format_yaml_value(value: Any) -> str:
    """Format a single value for YAML output.

    Parameters
    ----------
    value : Any
        Value to format

    Returns
    -------
    str
        YAML-formatted string representation
    """
    if value is None:
        return 'null'
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, (list, tuple)):
        if not value:
            return '[]'
        # Check if we need to quote items
        items = []
        for item in value:
            if isinstance(item, str):
                # Quote if contains special YAML chars
                if any(c in str(item) for c in [':', '#', '"', "'", '|', '>', '\n', '[', ']', '{', '}', ',', '&', '*', '!', '%', '@', '`']):
                    escaped = str(item).replace('\\', '\\\\').replace('"', '\\"')
                    items.append(f'"{escaped}"')
                else:
                    items.append(str(item))
            else:
                items.append(str(item))
        return f"[{', '.join(items)}]"
    elif isinstance(value, dict):
        # For nested dicts, we'll use a simple inline format
        if not value:
            return '{}'
        items = []
        for k, v in value.items():
            formatted_value = format_yaml_value(v)
            items.append(f'{k}: {formatted_value}')
        return f"{{{', '.join(items)}}}"
    elif isinstance(value, str):
        # Check if string needs quoting
        needs_quote = (
            ':' in value or
            '#' in value or
            '"' in value or
            "'" in value or
            '\n' in value or
            value.startswith((' ', '\t')) or
            value.endswith((' ', '\t')) or
            value in ['true', 'false', 'null', 'yes', 'no', 'on', 'off'] or
            value.startswith(('|', '>', '-', '*', '&', '!', '%', '@', '`')) or
            (value and value[0].isdigit() and '.' in value)  # Might be confused with number
        )

        if needs_quote:
            # Escape backslashes and quotes
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        return value
    else:
        # Fallback for other types
        return str(value)


def format_yaml_frontmatter(metadata: Union[DocumentMetadata, Dict[str, Any]]) -> str:
    """Format metadata as YAML front matter.

    This function creates a simple YAML front matter block without requiring
    the PyYAML dependency. It handles basic types: strings, numbers, booleans,
    lists, and simple dictionaries.

    Parameters
    ----------
    metadata : DocumentMetadata or dict
        Metadata to format as YAML front matter

    Returns
    -------
    str
        YAML front matter string with --- delimiters, or empty string if no metadata

    Examples
    --------
    >>> metadata = DocumentMetadata(
    ...     title="My Document",
    ...     author="John Doe",
    ...     keywords=["python", "conversion"]
    ... )
    >>> print(format_yaml_frontmatter(metadata))
    ---
    title: My Document
    author: John Doe
    keywords: [python, conversion]
    ---

    """
    # Convert DocumentMetadata to dict if needed
    if isinstance(metadata, DocumentMetadata):
        data = metadata.to_dict()
    else:
        data = metadata

    # Skip if no metadata
    if not data:
        return ""

    lines = ["---"]

    # Process each field
    for key, value in data.items():
        if value is None:
            continue

        # Format the value
        formatted_value = format_yaml_value(value)

        # Handle multiline strings specially
        if isinstance(value, str) and '\n' in value:
            # Use literal block scalar for multiline strings
            lines.append(f'{key}: |')
            for line in value.split('\n'):
                lines.append(f'  {line}')
        else:
            lines.append(f'{key}: {formatted_value}')

    lines.append("---")
    return '\n'.join(lines) + '\n\n'


def prepend_metadata_if_enabled(content: str, metadata: Optional[DocumentMetadata], extract_metadata: bool) -> str:
    """Helper to prepend metadata to content if extraction is enabled.

    Parameters
    ----------
    content : str
        The markdown content
    metadata : DocumentMetadata | None
        The extracted metadata
    extract_metadata : bool
        Whether metadata extraction is enabled

    Returns
    -------
    str
        Content with metadata prepended if enabled, otherwise unchanged content
    """
    if extract_metadata and metadata:
        frontmatter = format_yaml_frontmatter(metadata)
        if frontmatter:
            return frontmatter + content
    return content
