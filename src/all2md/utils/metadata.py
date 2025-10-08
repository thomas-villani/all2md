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

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

# Standard property mappings for different document formats
PDF_FIELD_MAPPING = {
    'title': ['title', 'Title'],
    'author': ['author', 'Author'],
    'subject': ['subject', 'Subject'],
    'creator': ['creator', 'Creator'],
    'producer': ['producer', 'Producer'],
    'keywords': ['keywords', 'Keywords'],
}

OFFICE_FIELD_MAPPING = {
    'title': 'title',
    'author': 'author',
    'subject': 'subject',
    'category': 'category',
    'language': 'language',
    'keywords': 'keywords',
    'creation_date': 'created',
    'modification_date': 'modified',
}

SPREADSHEET_FIELD_MAPPING: Mapping[str, Union[str, List[str]]] = {
    'title': 'title',
    'author': 'creator',
    'subject': ['subject', 'description'],
    'language': 'language',
    'category': 'category',
    'keywords': 'keywords',
    'creation_date': 'created',
    'modification_date': 'modified',
}


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
    url : str | None
        Source URL of the document
    source_path : str | None
        Original file path of the document
    page_count : int | None
        Total number of pages (for paginated formats)
    word_count : int | None
        Total word count in the document
    sha256 : str | None
        SHA-256 hash of the source document
    extraction_date : str | None
        Date and time when the document was converted
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
    url: Optional[str] = None
    source_path: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    sha256: Optional[str] = None
    extraction_date: Optional[str] = None
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary, excluding None values.

        Returns
        -------
        dict
            Dictionary containing only non-None metadata fields

        """
        result: Dict[str, Any] = {}

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

        # New fields
        if self.url:
            result['url'] = self.url
        if self.source_path:
            result['source_path'] = self.source_path
        if self.page_count is not None:
            result['page_count'] = self.page_count
        if self.word_count is not None:
            result['word_count'] = self.word_count
        if self.sha256:
            result['sha256'] = self.sha256
        if self.extraction_date:
            result['extraction_date'] = self.extraction_date

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
                if any(c in str(item) for c in
                       [':', '#', '"', "'", '|', '>', '\n', '[', ']', '{', '}', ',', '&', '*', '!', '%', '@', '`']):
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


def format_toml_frontmatter(metadata: Union[DocumentMetadata, Dict[str, Any]]) -> str:
    """Format metadata as TOML front matter.

    This function creates TOML front matter using standard library json module
    (TOML can be represented as JSON-compatible structures).

    Parameters
    ----------
    metadata : DocumentMetadata or dict
        Metadata to format as TOML front matter

    Returns
    -------
    str
        TOML front matter string with +++ delimiters, or empty string if no metadata

    Examples
    --------
    >>> metadata = DocumentMetadata(
    ...     title="My Document",
    ...     author="John Doe",
    ...     keywords=["python", "conversion"]
    ... )
    >>> print(format_toml_frontmatter(metadata))
    +++
    title = "My Document"
    author = "John Doe"
    keywords = ["python", "conversion"]
    +++

    """
    # Convert DocumentMetadata to dict if needed
    if isinstance(metadata, DocumentMetadata):
        data = metadata.to_dict()
    else:
        data = metadata

    # Skip if no metadata
    if not data:
        return ""

    lines = ["+++"]

    # Process each field
    for key, value in data.items():
        if value is None:
            continue

        # Format the value for TOML
        if isinstance(value, bool):
            formatted_value = "true" if value else "false"
        elif isinstance(value, (int, float)):
            formatted_value = str(value)
        elif isinstance(value, str):
            # Escape quotes and backslashes
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            formatted_value = f'"{escaped}"'
        elif isinstance(value, list):
            # Format as TOML array
            items = []
            for item in value:
                if isinstance(item, str):
                    escaped = item.replace('\\', '\\\\').replace('"', '\\"')
                    items.append(f'"{escaped}"')
                else:
                    items.append(str(item))
            formatted_value = f"[{', '.join(items)}]"
        elif isinstance(value, dict):
            # Skip nested dicts for now (TOML tables are complex)
            continue
        else:
            formatted_value = f'"{str(value)}"'

        lines.append(f'{key} = {formatted_value}')

    lines.append("+++")
    return '\n'.join(lines) + '\n\n'


def format_json_frontmatter(metadata: Union[DocumentMetadata, Dict[str, Any]]) -> str:
    """Format metadata as JSON front matter.

    This function creates JSON front matter with proper escaping and formatting.

    Parameters
    ----------
    metadata : DocumentMetadata or dict
        Metadata to format as JSON front matter

    Returns
    -------
    str
        JSON front matter string with ```json delimiters, or empty string if no metadata

    Examples
    --------
    >>> metadata = DocumentMetadata(
    ...     title="My Document",
    ...     author="John Doe",
    ...     keywords=["python", "conversion"]
    ... )
    >>> print(format_json_frontmatter(metadata))
    ```json
    {
      "title": "My Document",
      "author": "John Doe",
      "keywords": ["python", "conversion"]
    }
    ```

    """
    import json

    # Convert DocumentMetadata to dict if needed
    if isinstance(metadata, DocumentMetadata):
        data = metadata.to_dict()
    else:
        data = metadata

    # Skip if no metadata
    if not data:
        return ""

    # Format as JSON with indentation
    json_content = json.dumps(data, indent=2, ensure_ascii=False)

    return f'```json\n{json_content}\n```\n\n'


def safe_extract_property(obj: Any, primary_attr: str, fallback_attr: Optional[str] = None) -> Optional[str]:
    """Safely extract a string property from an object with optional fallback.

    Parameters
    ----------
    obj : Any
        Object to extract property from
    primary_attr : str
        Primary attribute name to check
    fallback_attr : str | None
        Optional fallback attribute name if primary is not found or empty

    Returns
    -------
    str | None
        Non-empty string value, or None if not found or empty

    """
    def get_non_empty_value(attr_name: str) -> Optional[str]:
        if hasattr(obj, attr_name):
            value = getattr(obj, attr_name)
            if value and str(value).strip():
                return str(value).strip()
        return None

    # Try primary attribute first
    result = get_non_empty_value(primary_attr)
    if result:
        return result

    # Try fallback if provided
    if fallback_attr:
        return get_non_empty_value(fallback_attr)

    return None


def extract_keywords_from_string(keywords_str: str) -> List[str]:
    """Extract and clean keywords from a delimited string.

    Parameters
    ----------
    keywords_str : str
        String containing keywords separated by commas or semicolons

    Returns
    -------
    list[str]
        List of cleaned keyword strings

    """
    if not keywords_str or not keywords_str.strip():
        return []

    import re
    keywords = [k.strip() for k in re.split('[,;]', keywords_str) if k.strip()]
    return keywords


def map_properties_to_metadata(
    props_obj: Any,
    field_mapping: Mapping[str, Union[str, List[str]]],
    custom_handlers: Optional[Dict[str, Any]] = None
) -> DocumentMetadata:
    """Map properties from a document object to DocumentMetadata using field mappings.

    Parameters
    ----------
    props_obj : Any
        Object containing document properties (e.g., core_properties, metadata dict)
    field_mapping : dict[str, str | list[str]]
        Mapping from DocumentMetadata fields to property names.
        Values can be single strings or lists of fallback names.
    custom_handlers : dict[str, Any] | None
        Optional custom handling functions for specific fields

    Returns
    -------
    DocumentMetadata
        Populated metadata object

    Examples
    --------
    >>> # For DOCX/PPTX core_properties
    >>> mapping = {
    ...     'title': 'title',
    ...     'author': 'author',
    ...     'subject': 'subject',
    ...     'keywords': 'keywords'
    ... }
    >>> metadata = map_properties_to_metadata(props, mapping)

    >>> # For PDF with fallbacks
    >>> mapping = {
    ...     'title': ['title', 'Title'],
    ...     'author': ['author', 'Author']
    ... }
    >>> metadata = map_properties_to_metadata(pdf_meta, mapping)

    """
    metadata = DocumentMetadata()
    custom_handlers = custom_handlers or {}

    # Handle standard fields with mapping
    for metadata_field, prop_names in field_mapping.items():
        if not hasattr(metadata, metadata_field):
            continue

        # Handle custom processing for this field
        if metadata_field in custom_handlers:
            handler = custom_handlers[metadata_field]
            if callable(handler):
                value = handler(props_obj, prop_names)
                setattr(metadata, metadata_field, value)
            continue

        # Extract value using property names
        value = None
        if isinstance(prop_names, list):
            # Try each name in the list until we find a non-empty value
            for prop_name in prop_names:
                value = safe_extract_property(props_obj, prop_name)
                if value:
                    break
        else:
            value = safe_extract_property(props_obj, prop_names)

        # Special handling for keywords field
        if metadata_field == 'keywords' and value:
            if isinstance(value, str):
                value = extract_keywords_from_string(value)
            elif not isinstance(value, list):
                value = [str(value)] if value else []

        setattr(metadata, metadata_field, value)

    return metadata


def extract_dict_metadata(
    metadata_dict: Dict[str, Any], field_mapping: Mapping[str, Union[str, List[str]]]
) -> DocumentMetadata:
    """Extract metadata from a dictionary (useful for PDF and similar formats).

    Parameters
    ----------
    metadata_dict : dict[str, Any]
        Dictionary containing metadata key-value pairs
    field_mapping : dict[str, str | list[str]]
        Mapping from DocumentMetadata fields to dictionary keys

    Returns
    -------
    DocumentMetadata
        Populated metadata object

    """
    # Create a simple object wrapper for the dictionary to work with existing functions
    class DictWrapper:
        def __init__(self, data: Dict[str, Any]):
            self._data = data

        def __getattr__(self, name: str) -> Any:
            return self._data.get(name)

        def __hasattr__(self, name: str) -> bool:
            return name in self._data

    dict_obj = DictWrapper(metadata_dict)
    return map_properties_to_metadata(dict_obj, field_mapping)


def prepend_metadata_if_enabled(content: str, metadata: Optional[DocumentMetadata], extract_metadata: bool) -> str:
    """Prepend metadata to content if extraction is enabled.

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


def enrich_metadata_with_conversion_info(
    metadata: DocumentMetadata,
    input_data: Any,
    content: str = "",
    page_count: Optional[int] = None
) -> DocumentMetadata:
    """Enrich metadata with conversion-specific information.

    Adds fields like extraction_date, source_path, sha256, word_count, and page_count
    to the metadata based on the input and content.

    Parameters
    ----------
    metadata : DocumentMetadata
        The metadata object to enrich
    input_data : Any
        The input data (file path, bytes, or file object)
    content : str, default ""
        The extracted text content for word count calculation
    page_count : int | None, default None
        Number of pages (for paginated formats)

    Returns
    -------
    DocumentMetadata
        The enriched metadata object

    """
    # Set extraction date
    from datetime import datetime as dt
    metadata.extraction_date = dt.now().strftime('%Y-%m-%d %H:%M:%S')

    # Try to extract source_path from input
    if isinstance(input_data, (str, Path)):
        metadata.source_path = str(input_data)

    # Calculate SHA256 hash
    try:
        if isinstance(input_data, bytes):
            metadata.sha256 = hashlib.sha256(input_data).hexdigest()
        elif isinstance(input_data, (str, Path)):
            # Hash file content if it's a path
            try:
                with open(str(input_data), 'rb') as f:
                    metadata.sha256 = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                pass  # Skip if file can't be read
        elif hasattr(input_data, 'read'):
            # For file-like objects
            try:
                current_pos = input_data.tell() if hasattr(input_data, 'tell') else None
                data = input_data.read()
                metadata.sha256 = hashlib.sha256(data).hexdigest()
                # Try to restore position
                if current_pos is not None and hasattr(input_data, 'seek'):
                    input_data.seek(current_pos)
            except Exception:
                pass  # Skip if reading fails
    except Exception:
        pass  # Skip hash calculation on any error

    # Calculate word count from content
    if content:
        # Simple word count: split on whitespace
        metadata.word_count = len(content.split())

    # Set page count if provided
    if page_count is not None:
        metadata.page_count = page_count

    return metadata
