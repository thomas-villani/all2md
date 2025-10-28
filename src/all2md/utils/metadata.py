#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/metadata

"""Metadata extraction and front matter utilities for all2md.

This module provides utilities for extracting document metadata and formatting it
as front matter for prepending to Markdown output. Serialization now relies on
PyYAML and tomli_w for robust YAML and TOML generation.

The metadata extraction supports various document properties like title, author,
creation date, keywords, and format-specific metadata fields.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Tuple, Union

import tomli_w
import yaml

MetadataVisibility = Literal["core", "standard", "extended", "all"]

# Standard property mappings for different document formats
PDF_FIELD_MAPPING = {
    "title": ["title", "Title"],
    "author": ["author", "Author"],
    "subject": ["subject", "Subject"],
    "creator": ["creator", "Creator"],
    "producer": ["producer", "Producer"],
    "keywords": ["keywords", "Keywords"],
}

OFFICE_FIELD_MAPPING = {
    "title": "title",
    "author": "author",
    "subject": "subject",
    "category": "category",
    "language": "language",
    "keywords": "keywords",
    "creation_date": "created",
    "modification_date": "modified",
}

SPREADSHEET_FIELD_MAPPING: Mapping[str, Union[str, List[str]]] = {
    "title": "title",
    "author": "creator",
    "subject": ["subject", "description"],
    "language": "language",
    "category": "category",
    "keywords": "keywords",
    "creation_date": "created",
    "modification_date": "modified",
}

CORE_METADATA_FIELDS: tuple[str, ...] = (
    "title",
    "author",
    "source",
    "creation_date",
    "modification_date",
    "accessed_date",
)

DESCRIPTIVE_METADATA_FIELDS: tuple[str, ...] = (
    "description",
    "keywords",
    "language",
    "category",
)

TECHNICAL_METADATA_FIELDS: tuple[str, ...] = (
    "creator",
    "producer",
    "page_count",
    "word_count",
)

INTERNAL_METADATA_FIELDS: tuple[str, ...] = (
    "source_path",
    "sha256",
    "extraction_date",
)

FIELD_NORMALIZATION_ALIASES: Mapping[str, str] = {
    "url": "source",
    "source_url": "source",
    "link": "source",
    "website": "source",
    "publication": "source",
    "accessed": "accessed_date",
    "accessed_on": "accessed_date",
    "date_accessed": "accessed_date",
    "date_published": "creation_date",
    "published_date": "creation_date",
    "created_at": "creation_date",
    "modified_at": "modification_date",
}

FIELD_VISIBILITY_MAP: Mapping[MetadataVisibility, tuple[str, ...]] = {
    "core": CORE_METADATA_FIELDS,
    "standard": CORE_METADATA_FIELDS + DESCRIPTIVE_METADATA_FIELDS,
    "extended": CORE_METADATA_FIELDS + DESCRIPTIVE_METADATA_FIELDS + TECHNICAL_METADATA_FIELDS,
    "all": CORE_METADATA_FIELDS + DESCRIPTIVE_METADATA_FIELDS + TECHNICAL_METADATA_FIELDS + INTERNAL_METADATA_FIELDS,
}

FIELD_OUTPUT_ORDER: tuple[str, ...] = (
    "title",
    "author",
    "source",
    "creation_date",
    "modification_date",
    "accessed_date",
    "description",
    "keywords",
    "language",
    "category",
    "creator",
    "producer",
    "page_count",
    "word_count",
    "source_path",
    "sha256",
    "extraction_date",
)


def _normalize_field_name(field: str) -> str:
    """Return canonical field name for metadata filtering."""
    return FIELD_NORMALIZATION_ALIASES.get(field, field)


ALL_KNOWN_FIELDS: tuple[str, ...] = (
    CORE_METADATA_FIELDS
    + DESCRIPTIVE_METADATA_FIELDS
    + TECHNICAL_METADATA_FIELDS
    + INTERNAL_METADATA_FIELDS
    + ("accessed_date", "source")
)


@dataclass(frozen=True)
class MetadataRenderPolicy:
    """Configuration describing how document metadata should be rendered."""

    visibility: MetadataVisibility = "extended"
    include_fields: Tuple[str, ...] = field(default_factory=tuple)
    exclude_fields: Tuple[str, ...] = field(default_factory=tuple)
    include_custom_fields: bool = True
    field_aliases: Dict[str, str] = field(default_factory=dict)


DEFAULT_METADATA_RENDER_POLICY = MetadataRenderPolicy()


def _value_is_meaningful(value: Any) -> bool:
    """Return True if the metadata value should be rendered."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _normalize_metadata_dict(metadata: Mapping[str, Any]) -> Tuple[Dict[str, Any], set[str]]:
    """Normalize metadata keys and collect custom fields."""
    normalized: Dict[str, Any] = {}
    custom_fields: set[str] = set()

    for key, value in metadata.items():
        if not _value_is_meaningful(value):
            continue

        canonical = _normalize_field_name(key)

        if canonical == "url":
            canonical = "source"
        elif canonical == "extraction_date":
            normalized["extraction_date"] = value
            if "accessed_date" not in normalized:
                normalized["accessed_date"] = value
            continue

        normalized[canonical] = value

        if canonical not in ALL_KNOWN_FIELDS:
            custom_fields.add(canonical)

    # Ensure source/accessed aliases are populated when only alternate keys exist
    if "source" not in normalized:
        for alias in ("url", "source_url", "link", "website", "publication"):
            if alias in metadata and _value_is_meaningful(metadata[alias]):
                normalized["source"] = metadata[alias]
                break

    if "accessed_date" not in normalized:
        for alias in ("accessed_date", "accessed", "accessed_on", "date_accessed", "extraction_date"):
            if alias in metadata and _value_is_meaningful(metadata[alias]):
                normalized["accessed_date"] = metadata[alias]
                break

    return normalized, custom_fields


def prepare_metadata_for_render(
    metadata: Union["DocumentMetadata", Mapping[str, Any], None], policy: MetadataRenderPolicy | None = None
) -> Dict[str, Any]:
    """Return metadata filtered for rendering according to the policy."""
    if not metadata:
        return {}

    policy = policy or DEFAULT_METADATA_RENDER_POLICY

    if isinstance(metadata, DocumentMetadata):
        metadata_dict = metadata.to_dict()
    else:
        metadata_dict = dict(metadata)

    normalized, custom_fields = _normalize_metadata_dict(metadata_dict)

    visibility_fields = set(FIELD_VISIBILITY_MAP.get(policy.visibility, FIELD_VISIBILITY_MAP["extended"]))
    include_fields = {_normalize_field_name(name) for name in policy.include_fields}
    exclude_fields = {_normalize_field_name(name) for name in policy.exclude_fields}

    output: list[tuple[str, Any]] = []
    added_fields: set[str] = set()

    def add_field(field_name: str) -> None:
        canonical = _normalize_field_name(field_name)
        if canonical in added_fields:
            return
        if canonical in exclude_fields:
            return

        value = normalized.get(canonical)
        if value is None:
            raw_value = metadata_dict.get(field_name)
            if raw_value is None and canonical != field_name:
                raw_value = metadata_dict.get(canonical)
            value = raw_value

        if not _value_is_meaningful(value):
            return

        output_key = policy.field_aliases.get(canonical, canonical)
        output.append((output_key, value))
        added_fields.add(canonical)

    for field_name in FIELD_OUTPUT_ORDER:
        if field_name not in normalized:
            continue
        if field_name not in visibility_fields and field_name not in include_fields:
            continue
        add_field(field_name)

    if policy.include_custom_fields:
        for field_name in sorted(custom_fields):
            if field_name in added_fields:
                continue
            if field_name in exclude_fields and field_name not in include_fields:
                continue
            add_field(field_name)

    for field_name in include_fields:
        add_field(field_name)

    return dict(output)


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
    version : str | None
        Document version (e.g., from AsciiDoc revnumber)
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
    version: Optional[str] = None
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
            result["title"] = self.title
        if self.author:
            result["author"] = self.author
        if self.subject:
            result["description"] = self.subject
        if self.keywords:
            result["keywords"] = self.keywords
        if self.creation_date:
            if isinstance(self.creation_date, datetime):
                result["creation_date"] = self.creation_date.strftime("%Y-%m-%d")
            else:
                result["creation_date"] = str(self.creation_date)
        if self.modification_date:
            if isinstance(self.modification_date, datetime):
                result["modification_date"] = self.modification_date.strftime("%Y-%m-%d")
            else:
                result["modification_date"] = str(self.modification_date)
        if self.creator:
            result["creator"] = self.creator
        if self.producer:
            result["producer"] = self.producer
        if self.category:
            result["category"] = self.category
        if self.language:
            result["language"] = self.language

        # New fields
        if self.url:
            result["url"] = self.url
        if self.source_path:
            result["source_path"] = self.source_path
        if self.page_count is not None:
            result["page_count"] = self.page_count
        if self.word_count is not None:
            result["word_count"] = self.word_count
        if self.sha256:
            result["sha256"] = self.sha256
        if self.extraction_date:
            result["extraction_date"] = self.extraction_date
        if self.version:
            result["version"] = self.version

        # Add custom fields
        for key, value in self.custom.items():
            if value is not None:
                result[key] = value

        return result


def format_yaml_frontmatter(
    metadata: Union[DocumentMetadata, Dict[str, Any]], policy: MetadataRenderPolicy | None = None
) -> str:
    """Format metadata as YAML front matter.

    This function creates a YAML front matter block using PyYAML for robust
    serialization of metadata structures.

    Parameters
    ----------
    metadata : DocumentMetadata or dict
        Metadata to format as YAML front matter
    policy : MetadataRenderPolicy or None, optional
        Filtering policy describing which metadata fields to include

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
    data = prepare_metadata_for_render(metadata, policy)

    # Skip if no metadata after policy filtering
    if not data:
        return ""

    yaml_content = yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )

    if not yaml_content.endswith("\n"):
        yaml_content += "\n"

    return f"---\n{yaml_content}---\n\n"


def format_toml_frontmatter(
    metadata: Union[DocumentMetadata, Dict[str, Any]], policy: MetadataRenderPolicy | None = None
) -> str:
    """Format metadata as TOML front matter.

    This function creates TOML front matter using tomli_w for standards-compliant
    serialization.

    Parameters
    ----------
    metadata : DocumentMetadata or dict
        Metadata to format as TOML front matter
    policy : MetadataRenderPolicy or None, optional
        Filtering policy describing which metadata fields to include

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
    data = prepare_metadata_for_render(metadata, policy)

    if not data:
        return ""

    toml_content = tomli_w.dumps(data)

    if not toml_content.endswith("\n"):
        toml_content += "\n"

    return f"+++\n{toml_content}+++\n\n"


def format_json_frontmatter(
    metadata: Union[DocumentMetadata, Dict[str, Any]], policy: MetadataRenderPolicy | None = None
) -> str:
    r"""Format metadata as JSON front matter.

    This function creates JSON front matter with proper escaping and formatting.

    Parameters
    ----------
    metadata : DocumentMetadata or dict
        Metadata to format as JSON front matter
    policy : MetadataRenderPolicy or None, optional
        Filtering policy describing which metadata fields to include

    Returns
    -------
    str
        JSON front matter string with \`\`\`json delimiters, or empty string if no metadata

    Examples
    --------
    >>> metadata = DocumentMetadata(
    ...     title="My Document",
    ...     author="John Doe",
    ...     keywords=["python", "conversion"]
    ... )
    >>> print(format_json_frontmatter(metadata))
    \`\`\`json
    {
      "title": "My Document",
      "author": "John Doe",
      "keywords": ["python", "conversion"]
    }
    \`\`\`

    """
    data = prepare_metadata_for_render(metadata, policy)

    if not data:
        return ""

    # Format as JSON with indentation
    json_content = json.dumps(data, indent=2, ensure_ascii=False)

    return f"```json\n{json_content}\n```\n\n"


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

    keywords = [k.strip() for k in re.split("[,;]", keywords_str) if k.strip()]
    return keywords


def map_properties_to_metadata(
    props_obj: Any, field_mapping: Mapping[str, Union[str, List[str]]], custom_handlers: Optional[Dict[str, Any]] = None
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
        if metadata_field == "keywords" and value:
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

    dict_obj = DictWrapper(metadata_dict)
    return map_properties_to_metadata(dict_obj, field_mapping)


def prepend_metadata_if_enabled(
    content: str,
    metadata: Optional[DocumentMetadata],
    extract_metadata: bool,
    policy: MetadataRenderPolicy | None = None,
) -> str:
    """Prepend metadata to content if extraction is enabled.

    Parameters
    ----------
    content : str
        The markdown content
    metadata : DocumentMetadata | None
        The extracted metadata
    extract_metadata : bool
        Whether metadata extraction is enabled
    policy : MetadataRenderPolicy or None, optional
        Policy controlling which metadata fields are prepended

    Returns
    -------
    str
        Content with metadata prepended if enabled, otherwise unchanged content

    """
    if extract_metadata and metadata:
        frontmatter = format_yaml_frontmatter(metadata, policy=policy)
        if frontmatter:
            return frontmatter + content
    return content


def enrich_metadata_with_conversion_info(
    metadata: DocumentMetadata, input_data: Any, content: str = "", page_count: Optional[int] = None
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
    metadata.extraction_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Try to extract source_path from input
    if isinstance(input_data, (str, Path)):
        metadata.source_path = str(input_data)

    # Calculate SHA256 hash using chunked reading to avoid memory issues with large files
    # Use 1MB chunks for efficient memory usage
    chunk_size = 1024 * 1024  # 1MB
    try:
        if isinstance(input_data, bytes):
            metadata.sha256 = hashlib.sha256(input_data).hexdigest()
        elif isinstance(input_data, (str, Path)):
            # Hash file content if it's a path using chunked reading
            try:
                hash_obj = hashlib.sha256()
                with open(str(input_data), "rb") as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        hash_obj.update(chunk)
                metadata.sha256 = hash_obj.hexdigest()
            except Exception:
                pass  # Skip if file can't be read
        elif hasattr(input_data, "read"):
            # For file-like objects, use chunked reading
            try:
                # Save position if seekable
                current_pos = input_data.tell() if hasattr(input_data, "tell") else None

                # Hash in chunks
                hash_obj = hashlib.sha256()
                while True:
                    chunk = input_data.read(chunk_size)
                    if not chunk:
                        break
                    hash_obj.update(chunk)
                metadata.sha256 = hash_obj.hexdigest()

                # Try to restore position if seekable
                if current_pos is not None and hasattr(input_data, "seek"):
                    try:
                        input_data.seek(current_pos)
                    except Exception:
                        pass  # If seek fails, continue without restoring position
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
