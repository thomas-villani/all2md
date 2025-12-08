#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/mbox.py
"""MBOX mailbox archive to AST converter.

This module provides conversion from Unix mailbox format files (mbox, maildir, etc.)
to AST representation. It supports streaming processing for large mailboxes and
reuses the EML parser for individual message processing.

"""

from __future__ import annotations

import datetime
import logging
import mailbox
import re
from email.message import Message
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import Document, Heading, Node, Paragraph, Text, ThematicBreak
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError, ParsingError, ValidationError
from all2md.options.mbox import MboxOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.eml import (
    clean_message,
    format_eml_date,
    parse_single_message,
    process_email_attachments,
)
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def _detect_mailbox_format(path: Path) -> str:
    """Detect mailbox format from file/directory structure.

    Parameters
    ----------
    path : Path
        Path to mailbox file or directory

    Returns
    -------
    str
        Detected format: "mbox", "maildir", "mh", "babyl", or "mmdf"

    """
    if path.is_dir():
        # Directory-based formats
        if (path / "cur").is_dir() and (path / "new").is_dir() and (path / "tmp").is_dir():
            return "maildir"
        elif any(f.name.isdigit() for f in path.iterdir() if f.is_file()):
            return "mh"
        else:
            return "maildir"  # Default for unknown directory
    else:
        # File-based formats - check magic bytes
        try:
            with open(path, "rb") as f:
                header = f.read(1024)
                if header.startswith(b"From "):
                    return "mbox"
                elif header.startswith(b"*** MESSAG"):
                    return "mmdf"
                else:
                    # Try to read as babyl
                    try:
                        f.seek(0)
                        first_line = f.readline()
                        if b"BABYL OPTIONS" in first_line:
                            return "babyl"
                    except Exception:
                        pass
                    return "mbox"  # Default fallback
        except Exception:
            return "mbox"  # Default fallback


def _get_mailbox_class(format_name: str) -> type:
    """Get mailbox class for the specified format.

    Parameters
    ----------
    format_name : str
        Mailbox format name

    Returns
    -------
    type
        Mailbox class from stdlib mailbox module

    """
    format_map = {
        "mbox": mailbox.mbox,
        "maildir": mailbox.Maildir,
        "mh": mailbox.MH,
        "babyl": mailbox.Babyl,
        "mmdf": mailbox.MMDF,
    }
    return format_map.get(format_name, mailbox.mbox)


def _filter_message(msg_data: dict[str, Any], options: MboxOptions) -> bool:
    """Check if message passes filtering criteria.

    Parameters
    ----------
    msg_data : dict
        Parsed message data
    options : MboxOptions
        Filtering options

    Returns
    -------
    bool
        True if message should be included

    """
    # Date range filtering
    if options.date_range_start or options.date_range_end:
        msg_date = msg_data.get("date")
        if msg_date is None:
            return False  # Skip messages without dates when filtering by date

        if options.date_range_start and msg_date < options.date_range_start:
            return False

        if options.date_range_end and msg_date > options.date_range_end:
            return False

    return True


class MboxToAstConverter(BaseParser):
    """Convert Unix mailbox archives to AST representation.

    This converter processes mailbox format files (mbox, maildir, etc.) and builds
    an AST that can be rendered to various markdown flavors. It supports streaming
    processing for large mailboxes and reuses the EML parser for individual messages.

    Parameters
    ----------
    options : MboxOptions or None
        Conversion options
    progress_callback : ProgressCallback or None
        Optional callback for progress updates during parsing

    """

    def __init__(self, options: MboxOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the MBOX parser with options and progress callback."""
        BaseParser._validate_options_type(options, MboxOptions, "mbox")
        options = options or MboxOptions()
        super().__init__(options, progress_callback)
        self.options: MboxOptions = options
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse MBOX mailbox into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input mailbox to parse. Can be:
            - File path (str or Path) - for file-based formats (mbox, mmdf, babyl)
            - Directory path (str or Path) - for directory-based formats (maildir, mh)
            - Not supported: IO[bytes] or bytes (mailbox requires file access)

        Returns
        -------
        Document
            AST Document node representing the parsed mailbox structure

        Raises
        ------
        MalformedFileError
            If parsing fails due to invalid mailbox format
        ParsingError
            If content processing fails
        ValidationError
            If input type is not supported

        """
        # Reset parser state to prevent leakage across parse calls
        self._attachment_footnotes = {}

        # Validate input - mailbox module requires file/directory access
        if isinstance(input_data, bytes) or hasattr(input_data, "read"):
            raise ValidationError(
                "MBOX parser requires file or directory path. IO streams and bytes are not supported.",
                parameter_name="input_data",
                parameter_value="<IO or bytes>",
            )

        path = Path(input_data) if isinstance(input_data, str) else input_data

        if not path.exists():
            raise ValidationError(
                f"Mailbox path does not exist: {path}",
                parameter_name="input_data",
                parameter_value=str(path),
            )

        try:
            # Detect format if auto
            mailbox_format = self.options.mailbox_format
            if mailbox_format == "auto":
                detected_format = _detect_mailbox_format(path)
                mailbox_format = detected_format  # type: ignore[assignment]
            format_name = str(mailbox_format)  # Convert to str for use in error messages

            # Get appropriate mailbox class
            mbox_class = _get_mailbox_class(format_name)

            # Open mailbox
            mbox = None  # Initialize for finally block
            try:
                mbox = mbox_class(str(path))
            except Exception as e:
                raise MalformedFileError(
                    f"Failed to open mailbox as {format_name}: {e!r}",
                    file_path=str(path),
                    original_error=e,
                ) from e

            try:
                # Get total message count for progress reporting
                try:
                    total_messages = len(mbox)
                except Exception:
                    total_messages = 0  # Some mailbox types don't support len()

                self._emit_progress(
                    "started",
                    f"Processing {format_name} mailbox",
                    total=min(total_messages, self.options.max_messages or total_messages),
                )

                # Process messages with streaming
                messages = self._process_messages(mbox, format_name)

                # Extract metadata from the mailbox
                metadata = self.extract_metadata({"format": format_name, "message_count": len(messages)})

                # Convert to AST
                doc = self._format_mailbox_as_ast(messages)
                doc.metadata = metadata.to_dict()

                self._emit_progress(
                    "finished", f"Processed {len(messages)} messages", current=len(messages), total=len(messages)
                )

                return doc
            finally:
                # Ensure mailbox is closed to release file locks and descriptors
                if mbox is not None:
                    try:
                        mbox.close()
                    except Exception:
                        pass  # Ignore errors during cleanup

        except Exception as e:
            if isinstance(e, (ValidationError, MalformedFileError, ParsingError)):
                raise
            raise ParsingError(
                f"Failed to process mailbox: {str(e)}",
                parsing_stage="mailbox_processing",
                original_error=e,
            ) from e

    def _process_messages(self, mbox: mailbox.Mailbox, format_name: str) -> list[dict[str, Any]]:
        """Process messages from mailbox with streaming and filtering.

        Parameters
        ----------
        mbox : mailbox.Mailbox
            Opened mailbox object
        format_name : str
            Mailbox format name for metadata

        Returns
        -------
        list[dict[str, Any]]
            List of processed message dictionaries

        """
        messages = []
        processed_count = 0

        # For maildir format with folder filtering
        if format_name == "maildir" and self.options.folder_filter and isinstance(mbox, mailbox.Maildir):
            # Maildir supports folder iteration
            for folder_name in self.options.folder_filter:
                try:
                    folder = mbox.get_folder(folder_name)
                    # Type ignore: Maildir.get_folder returns Maildir but we accept it as Mailbox
                    messages.extend(
                        self._process_folder_messages(folder, folder_name, processed_count)  # type: ignore[arg-type]
                    )
                    processed_count = len(messages)
                except (KeyError, mailbox.NoSuchMailboxError):
                    # Folder doesn't exist, skip
                    continue
        else:
            # Process all messages
            messages = self._process_all_messages(mbox, processed_count)

        # Sort messages chronologically based on parent class sort_order option
        messages.sort(
            key=lambda m: m.get("date") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
            reverse=(self.options.sort_order == "desc"),
        )

        return messages

    def _process_all_messages(self, mbox: mailbox.Mailbox, start_count: int = 0) -> list[dict[str, Any]]:
        """Process all messages from mailbox.

        Parameters
        ----------
        mbox : mailbox.Mailbox
            Mailbox to process
        start_count : int
            Starting count for progress reporting

        Returns
        -------
        list[dict[str, Any]]
            List of processed messages

        """
        messages = []
        for i, key in enumerate(mbox.keys(), start=start_count + 1):
            # Check message limit
            if self.options.max_messages and i > self.options.max_messages:
                break

            try:
                msg = mbox[key]
                msg_data = self._process_single_message(msg, folder=None)

                if msg_data and _filter_message(msg_data, self.options):
                    messages.append(msg_data)

                self._emit_progress(
                    "message_done", f"Message {i}", current=i, total=len(mbox) if hasattr(mbox, "__len__") else 0
                )

            except Exception as e:
                # Log error but continue processing
                logger.warning(f"Failed to process message {key}: {e}")
                continue

        return messages

    def _process_folder_messages(
        self, folder: mailbox.Mailbox[Message[str, str]], folder_name: str, start_count: int = 0
    ) -> list[dict[str, Any]]:
        """Process messages from a specific folder.

        Parameters
        ----------
        folder : mailbox.Mailbox
            Folder mailbox to process
        folder_name : str
            Name of the folder
        start_count : int
            Starting count for progress reporting

        Returns
        -------
        list[dict[str, Any]]
            List of processed messages

        """
        messages = []
        for i, key in enumerate(folder.keys(), start=start_count + 1):
            # Check message limit
            if self.options.max_messages and i > self.options.max_messages:
                break

            try:
                msg = folder[key]
                msg_data = self._process_single_message(msg, folder=folder_name)

                if msg_data and _filter_message(msg_data, self.options):
                    messages.append(msg_data)

                self._emit_progress("message_done", f"Folder: {folder_name}, Message {i}", current=i)

            except Exception as e:
                # Log error but continue processing
                logger.warning(f"Failed to process message {key} in folder {folder_name}: {e}")
                continue

        return messages

    def _process_single_message(self, msg: Message, folder: str | None) -> dict[str, Any] | None:
        """Process a single message using EML parsing logic.

        Parameters
        ----------
        msg : Message
            Email message object
        folder : str or None
            Folder name for metadata

        Returns
        -------
        dict[str, Any] or None
            Processed message data or None if processing failed

        """
        try:
            # Parse using EML logic
            msg_data = parse_single_message(msg, self.options)

            # Add folder metadata if requested
            if folder and self.options.preserve_folder_metadata:
                msg_data["folder"] = folder

            # Process attachments if needed
            if self.options.attachment_mode != "skip":
                attachment_content, attachment_footnotes = process_email_attachments(msg, self.options)
                # Merge footnotes
                self._attachment_footnotes.update(attachment_footnotes)
                if attachment_content and "content" in msg_data:
                    msg_data["content"] += attachment_content

            # Clean message content
            if "content" in msg_data:
                msg_data["content"] = clean_message(msg_data["content"], self.options)

            return msg_data

        except Exception as e:
            logger.warning(f"Failed to parse message: {e}")
            return None

    def _format_mailbox_as_ast(self, messages: list[dict[str, Any]]) -> Document:
        """Convert mailbox messages to AST Document.

        Parameters
        ----------
        messages : list[dict[str, Any]]
            List of message dictionaries

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        if self.options.output_structure == "hierarchical":
            # Group by folder
            folders: dict[str, list[dict[str, Any]]] = {}
            for msg in messages:
                folder = msg.get("folder", "Inbox")
                if folder not in folders:
                    folders[folder] = []
                folders[folder].append(msg)

            # Build hierarchical structure
            for folder_name, folder_messages in folders.items():
                # Folder heading (H1)
                children.append(Heading(level=1, content=[Text(content=folder_name)]))

                # Add messages
                for msg in folder_messages:
                    self._add_message_nodes(children, msg, heading_level=2)

        else:
            # Flat structure - all messages sequentially
            for msg in messages:
                self._add_message_nodes(children, msg, heading_level=1)

        # Append attachment footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        return Document(children=children)

    def _add_message_nodes(self, children: list[Node], msg: dict[str, Any], heading_level: int) -> None:
        """Add message nodes to children list.

        Parameters
        ----------
        children : list[Node]
            List to append nodes to
        msg : dict[str, Any]
            Message data
        heading_level : int
            Heading level for subject

        """
        # Add subject as heading if requested
        if self.options.subject_as_h1 and "subject" in msg and msg["subject"]:
            children.append(Heading(level=heading_level, content=[Text(content=msg["subject"])]))

        # Add email headers as paragraphs if requested
        if self.options.include_headers:
            header_lines = []

            # Add folder metadata if present and using flat structure
            if self.options.output_structure == "flat" and "folder" in msg:
                header_lines.append(f"Folder: {msg['folder']}")

            header_lines.append(f"From: {msg.get('from', '')}")
            header_lines.append(f"To: {msg.get('to', '')}")

            if msg.get("cc"):
                header_lines.append(f"CC: {msg['cc']}")

            if "date" in msg and msg["date"] is not None:

                formatted_date = format_eml_date(msg["date"], self.options)
                if formatted_date:
                    header_lines.append(f"Date: {formatted_date}")

            # Only include subject in headers if not already shown as heading
            if not self.options.subject_as_h1 and "subject" in msg:
                header_lines.append(f"Subject: {msg.get('subject', '')}")

            # Create a single paragraph with all headers
            header_text = "\n".join(header_lines)
            children.append(Paragraph(content=[Text(content=header_text)]))

        # Add content
        content = msg.get("content", "")
        if content.strip():
            # Split content into paragraphs

            paragraphs = re.split(r"\n\n+", content.strip())
            for para_text in paragraphs:
                para_text = para_text.strip()
                if para_text:
                    children.append(Paragraph(content=[Text(content=para_text)]))

        # Add separator
        children.append(ThematicBreak())

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from mailbox.

        Parameters
        ----------
        document : Any
            Dictionary with mailbox information

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract format information
        if isinstance(document, dict):
            if "format" in document:
                metadata.custom["mailbox_format"] = document["format"]
            if "message_count" in document:
                metadata.custom["message_count"] = document["message_count"]

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="mbox",
    extensions=[".mbox", ".mbx"],
    mime_types=["application/mbox"],
    magic_bytes=[(b"From ", 0)],
    parser_class=MboxToAstConverter,
    renderer_class=None,
    parser_required_packages=[],  # Uses stdlib mailbox module
    renderer_required_packages=[],
    parser_options_class=MboxOptions,
    renderer_options_class=None,
    description="Convert Unix mailbox archives (mbox, maildir, etc.) to Markdown",
    priority=5,
)
