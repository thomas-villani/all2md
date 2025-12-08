#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/enex.py
"""Evernote Export (ENEX) to AST converter.

This module provides conversion from Evernote Export files (.enex) to AST representation.
ENEX files are XML-based exports containing one or more notes with embedded HTML content
and base64-encoded attachments.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import logging
import re
from pathlib import Path
from typing import IO, Any, Optional, Union

import defusedxml.ElementTree as ET

from all2md.ast import Document, Heading, Node, Paragraph, Text, ThematicBreak
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError, ParsingError, ValidationError
from all2md.options.enex import EnexOptions
from all2md.options.html import HtmlOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.html import HtmlToAstConverter
from all2md.progress import ProgressCallback
from all2md.utils.attachments import process_attachment
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def _parse_enex_date(date_str: str | None) -> datetime.datetime | None:
    """Parse Evernote date string to datetime.

    Evernote dates are in format: YYYYMMDDTHHmmssZ

    Parameters
    ----------
    date_str : str | None
        Date string from ENEX file

    Returns
    -------
    datetime.datetime | None
        Parsed datetime in UTC, or None if parsing fails

    """
    if not date_str:
        return None

    try:
        # Format: 20230115T143000Z
        return datetime.datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        return None


def _format_enex_date(dt: datetime.datetime | None, options: EnexOptions) -> str:
    """Format datetime according to EnexOptions configuration.

    Parameters
    ----------
    dt : datetime.datetime | None
        Datetime to format
    options : EnexOptions
        Configuration options for date formatting

    Returns
    -------
    str
        Formatted date string, or empty string if dt is None

    """
    if dt is None:
        return ""

    if options.date_format_mode == "iso8601":
        return dt.isoformat()
    elif options.date_format_mode == "locale":
        return dt.strftime("%c")
    else:  # strftime mode
        return dt.strftime(options.date_strftime_pattern)


class EnexToAstConverter(BaseParser):
    """Convert Evernote Export (ENEX) files to AST representation.

    This converter processes ENEX XML files and builds an AST that can be
    rendered to various markdown flavors. It handles multiple notes, embedded
    HTML content, and base64-encoded attachments.

    Parameters
    ----------
    options : EnexOptions or None
        Conversion options
    progress_callback : ProgressCallback or None
        Optional callback for progress updates during parsing

    """

    def __init__(self, options: EnexOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the ENEX parser with options and progress callback."""
        BaseParser._validate_options_type(options, EnexOptions, "enex")
        options = options or EnexOptions()
        super().__init__(options, progress_callback)
        self.options: EnexOptions = options
        self._resource_map: dict[str, dict[str, Any]] = {}
        self._attachment_footnotes: dict[str, str] = {}
        self._html_converter: HtmlToAstConverter | None = None

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse ENEX file into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input ENEX document to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw ENEX bytes

        Returns
        -------
        Document
            AST Document node representing the parsed ENEX structure

        Raises
        ------
        MalformedFileError
            If parsing fails due to invalid ENEX format
        ParsingError
            If content processing fails
        ValidationError
            If input type is not supported

        """
        # Reset parser state to prevent leakage across parse calls
        self._resource_map = {}
        self._attachment_footnotes = {}
        self._html_converter = None

        # Load XML bytes
        try:
            xml_bytes = self._load_bytes_content(input_data)
        except Exception as e:
            raise MalformedFileError(
                f"Failed to load ENEX data: {e!r}",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=e,
            ) from e

        # Parse XML
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            raise MalformedFileError(
                f"Failed to parse ENEX XML: {e!r}",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=e,
            ) from e

        # Validate root element
        if root.tag != "en-export":
            raise MalformedFileError(
                f"Invalid ENEX format: expected <en-export> root element, got <{root.tag}>",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=None,
            )

        # Extract notes
        notes = list(root.findall("note"))
        if not notes:
            logger.warning("ENEX file contains no notes")

        self._emit_progress("started", "Converting ENEX document", current=0, total=len(notes))

        # Process each note
        try:
            note_data_list = []
            for i, note_elem in enumerate(notes, 1):
                note_data = self._process_note(note_elem)
                if note_data:
                    note_data_list.append(note_data)

                self._emit_progress("item_done", f"Note {i}/{len(notes)}", current=i, total=len(notes))

            # Sort notes if requested
            if self.options.sort_notes_by != "none":
                note_data_list = self._sort_notes(note_data_list)

            # Convert to AST
            doc = self._format_notes_as_ast(note_data_list)

            # Extract metadata
            metadata = self.extract_metadata(root)
            doc.metadata = metadata.to_dict()

            self._emit_progress("finished", "ENEX conversion completed", current=len(notes), total=len(notes))

            return doc

        except Exception as e:
            if isinstance(e, (ParsingError, ValidationError)):
                raise
            raise ParsingError(
                f"Failed to process ENEX content: {str(e)}",
                parsing_stage="content_processing",
                original_error=e,
            ) from e

    def _process_note(self, note_elem: ET.Element) -> dict[str, Any] | None:
        """Process a single note element.

        Parameters
        ----------
        note_elem : ET.Element
            Note XML element

        Returns
        -------
        dict[str, Any] | None
            Parsed note data or None if processing failed

        """
        try:
            note_data: dict[str, Any] = {}

            # Extract title
            title_elem = note_elem.find("title")
            note_data["title"] = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"

            # Extract dates
            created_elem = note_elem.find("created")
            if created_elem is not None and created_elem.text:
                note_data["created"] = _parse_enex_date(created_elem.text)

            updated_elem = note_elem.find("updated")
            if updated_elem is not None and updated_elem.text:
                note_data["updated"] = _parse_enex_date(updated_elem.text)

            # Extract tags
            tags = []
            for tag_elem in note_elem.findall("tag"):
                if tag_elem.text:
                    tags.append(tag_elem.text.strip())
            note_data["tags"] = tags

            # Extract attributes (notebook, source-url, etc.)
            note_attrs_elem = note_elem.find("note-attributes")
            if note_attrs_elem is not None:
                source_url = note_attrs_elem.find("source-url")
                if source_url is not None and source_url.text:
                    note_data["source_url"] = source_url.text.strip()

                source = note_attrs_elem.find("source")
                if source is not None and source.text:
                    note_data["source"] = source.text.strip()

                # Notebook name (if present)
                notebook = note_elem.find("notebook")
                if notebook is not None and notebook.text:
                    note_data["notebook"] = notebook.text.strip()

            # Build resource map for this note
            note_resources = {}
            for resource_elem in note_elem.findall("resource"):
                resource_data = self._process_resource(resource_elem)
                if resource_data and "hash" in resource_data:
                    note_resources[resource_data["hash"]] = resource_data

            # Store resources in instance map
            self._resource_map.update(note_resources)

            # Extract and process content
            content_elem = note_elem.find("content")
            if content_elem is not None and content_elem.text:
                note_data["content_nodes"] = self._convert_note_content(content_elem.text, note_resources)
            else:
                note_data["content_nodes"] = []

            return note_data

        except Exception as e:
            logger.warning(f"Failed to process note: {e}")
            return None

    def _process_resource(self, resource_elem: ET.Element) -> dict[str, Any] | None:
        """Process a resource (attachment) element.

        Parameters
        ----------
        resource_elem : ET.Element
            Resource XML element

        Returns
        -------
        dict[str, Any] | None
            Resource data including hash, mime type, and decoded data

        """
        try:
            resource_data: dict[str, Any] = {}

            # Extract data
            data_elem = resource_elem.find("data")
            if data_elem is not None and data_elem.text:
                # Data is base64 encoded
                try:
                    decoded_data = base64.b64decode(data_elem.text)
                    resource_data["data"] = decoded_data
                    resource_data["size"] = len(decoded_data)

                    # Check size limits
                    if len(decoded_data) > self.options.max_asset_size_bytes:
                        logger.warning(
                            f"Resource exceeds size limit ({len(decoded_data)} > {self.options.max_asset_size_bytes})"
                        )
                        return None

                except Exception as e:
                    logger.warning(f"Failed to decode resource data: {e}")
                    return None

            # Extract mime type
            mime_elem = resource_elem.find("mime")
            if mime_elem is not None and mime_elem.text:
                resource_data["mime_type"] = mime_elem.text.strip()

            # Extract resource attributes
            resource_attrs_elem = resource_elem.find("resource-attributes")
            if resource_attrs_elem is not None:
                filename_elem = resource_attrs_elem.find("file-name")
                if filename_elem is not None and filename_elem.text:
                    resource_data["filename"] = filename_elem.text.strip()

            # Compute hash for lookup (Evernote uses MD5 of the binary data)
            if "data" in resource_data:
                md5_hash = hashlib.md5(resource_data["data"], usedforsecurity=False).hexdigest()
                resource_data["hash"] = md5_hash

            return resource_data

        except Exception as e:
            logger.warning(f"Failed to process resource: {e}")
            return None

    def _convert_note_content(self, content_cdata: str, note_resources: dict[str, Any]) -> list[Node]:
        """Convert note HTML content to AST nodes.

        Parameters
        ----------
        content_cdata : str
            CDATA content containing en-note HTML
        note_resources : dict[str, Any]
            Resource map for this note

        Returns
        -------
        list[Node]
            List of AST nodes

        """
        try:
            # Parse the en-note content (it's nested XML/HTML inside CDATA)
            # Remove CDATA wrapper if present
            content_html = content_cdata.strip()

            # Pre-process: replace <en-media> tags with proper img/a tags
            content_html = self._replace_en_media_tags(content_html, note_resources)

            # Use HTML parser to convert to AST
            if self._html_converter is None:
                # Create HTML options based on ENEX options
                html_options = HtmlOptions(
                    extract_title=False,
                    attachment_mode=self.options.attachment_mode,
                    attachment_output_dir=self.options.attachment_output_dir,
                    attachment_base_url=self.options.attachment_base_url,
                    max_asset_size_bytes=self.options.max_asset_size_bytes,
                    alt_text_mode=self.options.alt_text_mode,
                )
                self._html_converter = HtmlToAstConverter(options=html_options)

            # Convert HTML to AST
            doc = self._html_converter.convert_to_ast(content_html)

            # Extract children nodes (skip Document wrapper)
            return doc.children if doc.children else []

        except Exception as e:
            logger.warning(f"Failed to convert note content: {e}")
            # Return content as plain text paragraph
            return [Paragraph(content=[Text(content=content_cdata)])]

    def _replace_en_media_tags(self, html_content: str, note_resources: dict[str, Any]) -> str:
        """Replace <en-media> tags with proper HTML img/a tags.

        Parameters
        ----------
        html_content : str
            HTML content with en-media tags
        note_resources : dict[str, Any]
            Resource map for this note

        Returns
        -------
        str
            HTML with en-media tags replaced

        """
        # Find all en-media tags
        en_media_pattern = re.compile(r"<en-media\s+([^>]+)/>")

        def replace_media(match: re.Match[str]) -> str:
            attrs_str = match.group(1)

            # Extract hash attribute
            hash_match = re.search(r'hash="([^"]+)"', attrs_str)
            if not hash_match:
                return match.group(0)  # Keep original if no hash

            media_hash = hash_match.group(1)

            # Look up resource
            resource = note_resources.get(media_hash)
            if not resource or "data" not in resource:
                # Resource not found, create placeholder
                return f'<div>[Attachment: {resource.get("filename", media_hash) if resource else media_hash}]</div>'

            # Determine if it's an image
            mime_type = resource.get("mime_type", "")
            is_image = mime_type.startswith("image/")

            # Process attachment
            filename = resource.get("filename", f"attachment_{media_hash[:8]}")
            result = process_attachment(
                attachment_data=resource["data"],
                attachment_name=filename,
                alt_text=filename,
                attachment_mode=self.options.attachment_mode,
                attachment_output_dir=self.options.attachment_output_dir,
                attachment_base_url=self.options.attachment_base_url,
                is_image=is_image,
                alt_text_mode=self.options.alt_text_mode,
            )

            # Collect footnotes if present
            if result.get("footnote_label") and result.get("footnote_content"):
                self._attachment_footnotes[result["footnote_label"]] = result["footnote_content"]

            # Generate appropriate HTML
            if result.get("url"):
                if is_image:
                    return f'<img src="{result["url"]}" alt="{filename}" />'
                else:
                    return f'<a href="{result["url"]}">{filename}</a>'
            elif result.get("markdown"):
                # For base64, return as HTML comment (will be handled by HTML parser)
                return f'<!-- {result["markdown"]} -->'
            else:
                return f"<div>[Attachment: {filename}]</div>"

        return en_media_pattern.sub(replace_media, html_content)

    def _sort_notes(self, note_data_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort notes according to options.

        Parameters
        ----------
        note_data_list : list[dict[str, Any]]
            List of note data dictionaries

        Returns
        -------
        list[dict[str, Any]]
            Sorted list of notes

        """
        if self.options.sort_notes_by == "created":
            return sorted(
                note_data_list,
                key=lambda n: n.get("created") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
            )
        elif self.options.sort_notes_by == "updated":
            return sorted(
                note_data_list,
                key=lambda n: n.get("updated") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                reverse=True,
            )
        elif self.options.sort_notes_by == "title":
            return sorted(note_data_list, key=lambda n: n.get("title", "").lower())
        else:
            return note_data_list

    def _format_notes_as_ast(self, note_data_list: list[dict[str, Any]]) -> Document:
        """Convert notes to AST Document.

        Parameters
        ----------
        note_data_list : list[dict[str, Any]]
            List of note data dictionaries

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        # Group by notebook if needed
        if self.options.notebook_as_heading:
            notebooks: dict[str, list[dict[str, Any]]] = {}
            for note in note_data_list:
                notebook = note.get("notebook", "Notes")
                if notebook not in notebooks:
                    notebooks[notebook] = []
                notebooks[notebook].append(note)

            # Build hierarchical structure
            for notebook_name, notebook_notes in notebooks.items():
                # Notebook heading (H1 or configurable)
                children.append(Heading(level=1, content=[Text(content=notebook_name)]))

                # Add notes
                for note in notebook_notes:
                    self._add_note_nodes(children, note)

        else:
            # Flat structure - all notes sequentially
            for note in note_data_list:
                self._add_note_nodes(children, note)

        # Append attachment footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        return Document(children=children)

    def _add_note_nodes(self, children: list[Node], note_data: dict[str, Any]) -> None:
        """Add note nodes to children list.

        Parameters
        ----------
        children : list[Node]
            List to append nodes to
        note_data : dict[str, Any]
            Note data

        """
        # Add note title as heading
        title = note_data.get("title", "Untitled")
        children.append(Heading(level=self.options.note_title_level, content=[Text(content=title)]))

        # Add metadata if requested
        if self.options.include_note_metadata:
            metadata_lines = []

            if "created" in note_data and note_data["created"]:
                created_str = _format_enex_date(note_data["created"], self.options)
                metadata_lines.append(f"Created: {created_str}")

            if "updated" in note_data and note_data["updated"]:
                updated_str = _format_enex_date(note_data["updated"], self.options)
                metadata_lines.append(f"Updated: {updated_str}")

            if "source_url" in note_data:
                metadata_lines.append(f"Source: {note_data['source_url']}")

            if metadata_lines:
                metadata_text = "\n".join(metadata_lines)
                children.append(Paragraph(content=[Text(content=metadata_text)]))

        # Add tags if requested
        if self.options.include_tags and self.options.tags_format != "skip" and note_data.get("tags"):
            tags = note_data["tags"]
            if self.options.tags_format == "frontmatter":
                # Add as YAML frontmatter (just include in metadata)
                # This would need special handling in renderer
                tags_yaml = "tags: [" + ", ".join(tags) + "]"
                children.append(Paragraph(content=[Text(content=tags_yaml)]))
            elif self.options.tags_format == "inline":
                tags_str = "Tags: " + ", ".join(tags)
                children.append(Paragraph(content=[Text(content=tags_str)]))
            elif self.options.tags_format == "heading":
                children.append(Heading(level=self.options.note_title_level + 1, content=[Text(content="Tags")]))
                tags_str = ", ".join(tags)
                children.append(Paragraph(content=[Text(content=tags_str)]))

        # Add content nodes
        content_nodes = note_data.get("content_nodes", [])
        children.extend(content_nodes)

        # Add separator between notes
        children.append(ThematicBreak())

    def extract_metadata(self, document: ET.Element) -> DocumentMetadata:
        """Extract metadata from ENEX document.

        Parameters
        ----------
        document : ET.Element
            ENEX root element

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract export metadata from root attributes
        export_date = document.get("export-date")
        if export_date:
            metadata.custom["export_date"] = export_date

        application = document.get("application")
        if application:
            metadata.creator = application

        version = document.get("version")
        if version:
            metadata.custom["enex_version"] = version

        # Count notes
        notes = list(document.findall("note"))
        metadata.custom["note_count"] = len(notes)

        # Extract title from first note if available
        if notes:
            first_note = notes[0]
            title_elem = first_note.find("title")
            if title_elem is not None and title_elem.text:
                metadata.title = title_elem.text.strip()

        # Aggregate tags from all notes
        all_tags = set()
        for note in notes:
            for tag_elem in note.findall("tag"):
                if tag_elem.text:
                    all_tags.add(tag_elem.text.strip())

        if all_tags:
            metadata.keywords = sorted(all_tags)

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="enex",
    extensions=[".enex"],
    mime_types=["application/enex+xml"],
    magic_bytes=[
        (b"<?xml", 0),
        (b"<en-export", 0),
    ],
    parser_class=EnexToAstConverter,
    renderer_class=None,
    parser_required_packages=[],  # Uses stdlib xml.etree
    renderer_required_packages=[],
    parser_options_class=EnexOptions,
    renderer_options_class=None,
    description="Convert Evernote ENEX exports to Markdown",
    priority=6,
)
