#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/outlook.py
"""Outlook (MSG/PST/OST) to AST converter.

This module provides conversion from Microsoft Outlook format files to AST representation.
It supports:
- MSG files (single message) via extract-msg
- PST/OST files (archives) via pypff (optional dependency)

For large PST/OST files, streaming processing is used to minimize memory usage.

"""

from __future__ import annotations

import datetime
import logging
import re
import tempfile
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import Document, Heading, Node, Paragraph, Text, ThematicBreak
from all2md.constants import DEPS_OUTLOOK
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, MalformedFileError, ParsingError, ValidationError
from all2md.options.outlook import OutlookOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.eml import (
    clean_message,
    convert_eml_html_to_markdown,
    format_eml_date,
    parse_single_message,
    process_email_attachments,
)
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def _detect_outlook_format(input_data: Union[str, Path, IO[bytes], bytes]) -> str:
    """Detect Outlook format from input data.

    Parameters
    ----------
    input_data : str, Path, IO[bytes], or bytes
        Input data to detect

    Returns
    -------
    str
        Detected format: "msg", "pst", or "ost"

    """
    # Read magic bytes
    if isinstance(input_data, bytes):
        magic = input_data[:8]
    elif isinstance(input_data, (str, Path)):
        path = Path(input_data)
        ext = path.suffix.lower()
        # Quick check by extension
        if ext == ".msg":
            return "msg"
        elif ext == ".pst":
            return "pst"
        elif ext == ".ost":
            return "ost"

        # Fallback to magic bytes
        try:
            with open(path, "rb") as f:
                magic = f.read(8)
        except Exception:
            return "msg"  # Default fallback
    elif hasattr(input_data, "read"):
        pos = input_data.tell() if hasattr(input_data, "tell") else 0
        magic = input_data.read(8)
        if hasattr(input_data, "seek"):
            input_data.seek(pos)  # Reset position
    else:
        return "msg"  # Default fallback

    # Check magic bytes
    # MSG files are OLE/CFBF format
    if magic.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "msg"
    # PST/OST files have "!BDN" signature
    elif magic.startswith(b"!BDN"):
        # Distinguish PST from OST by extension if available
        if isinstance(input_data, (str, Path)):
            ext = Path(input_data).suffix.lower()
            if ext == ".ost":
                return "ost"
        return "pst"
    else:
        return "msg"  # Default fallback


def _convert_msg_to_email_message(msg_obj: Any) -> EmailMessage:
    """Convert extract-msg Message to stdlib EmailMessage.

    Parameters
    ----------
    msg_obj : extract_msg.Message
        Message object from extract-msg library

    Returns
    -------
    EmailMessage
        Converted email message

    """
    # Create EmailMessage
    email_msg = EmailMessage(policy=policy.default)

    # Set headers
    if msg_obj.sender:
        email_msg["From"] = msg_obj.sender
    if msg_obj.to:
        email_msg["To"] = msg_obj.to
    if msg_obj.cc:
        email_msg["Cc"] = msg_obj.cc
    if msg_obj.subject:
        email_msg["Subject"] = msg_obj.subject
    if msg_obj.date:
        # msg_obj.date is a datetime object
        email_msg["Date"] = msg_obj.date.strftime("%a, %d %b %Y %H:%M:%S %z")
    if msg_obj.message_id:
        email_msg["Message-ID"] = msg_obj.message_id

    # Set body content
    if msg_obj.body:
        email_msg.set_content(msg_obj.body, subtype="plain")
    elif msg_obj.htmlBody:
        email_msg.set_content(msg_obj.htmlBody, subtype="html")

    # Add attachments
    if msg_obj.attachments:
        for attachment in msg_obj.attachments:
            # Initialize att_name before try block to avoid UnboundLocalError
            # in exception handler if early operations fail
            att_name = "unknown_attachment"
            try:
                # Get attachment data
                att_data = attachment.data
                att_name = attachment.longFilename or attachment.shortFilename or "attachment"

                # Add as attachment
                email_msg.add_attachment(
                    att_data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=att_name,
                )
            except Exception as e:
                logger.warning(f"Failed to process attachment {att_name}: {e}")
                continue

    return email_msg


def _filter_message(msg_data: dict[str, Any], options: OutlookOptions) -> bool:
    """Check if message passes filtering criteria.

    Parameters
    ----------
    msg_data : dict
        Parsed message data
    options : OutlookOptions
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


class OutlookToAstConverter(BaseParser):
    """Convert Microsoft Outlook files to AST representation.

    This converter processes Outlook format files (MSG, PST, OST) and builds an AST
    that can be rendered to various markdown flavors. It supports:
    - MSG: Single message files via extract-msg
    - PST/OST: Archive files via pypff (optional dependency)

    For large PST/OST files, streaming processing minimizes memory usage.

    Parameters
    ----------
    options : OutlookOptions or None
        Conversion options
    progress_callback : ProgressCallback or None
        Optional callback for progress updates during parsing

    """

    def __init__(self, options: OutlookOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the Outlook parser with options and progress callback."""
        BaseParser._validate_options_type(options, OutlookOptions, "outlook")
        options = options or OutlookOptions()
        super().__init__(options, progress_callback)
        self.options: OutlookOptions = options
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    @requires_dependencies("outlook", DEPS_OUTLOOK)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse Outlook file into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input Outlook file to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw file bytes

        Returns
        -------
        Document
            AST Document node representing the parsed Outlook file structure

        Raises
        ------
        MalformedFileError
            If parsing fails due to invalid file format
        ParsingError
            If content processing fails
        ValidationError
            If input type is not supported
        DependencyError
            If required dependencies are not installed

        """
        # Reset parser state to prevent leakage across parse calls
        self._attachment_footnotes = {}

        try:
            # Detect format
            format_type = _detect_outlook_format(input_data)

            # Route to appropriate parser
            if format_type == "msg":
                return self._parse_msg(input_data)
            elif format_type in ("pst", "ost"):
                return self._parse_pst(input_data)
            else:
                raise ValidationError(
                    f"Unknown Outlook format: {format_type}",
                    parameter_name="input_data",
                    parameter_value=str(type(input_data)),
                )

        except Exception as e:
            if isinstance(e, (ValidationError, MalformedFileError, ParsingError, DependencyError)):
                raise
            raise ParsingError(
                f"Failed to process Outlook file: {str(e)}",
                parsing_stage="outlook_processing",
                original_error=e,
            ) from e

    def _parse_msg(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse MSG file using extract-msg.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            MSG file data

        Returns
        -------
        Document
            AST document

        """
        import extract_msg

        try:
            # Load MSG file
            if isinstance(input_data, (str, Path)):
                msg_obj = extract_msg.Message(str(input_data))  # type: ignore[no-untyped-call]
            elif isinstance(input_data, bytes):
                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=".msg", delete=False) as tmp:
                    tmp.write(input_data)
                    tmp_path = tmp.name
                try:
                    msg_obj = extract_msg.Message(tmp_path)  # type: ignore[no-untyped-call]
                finally:
                    # Clean up temp file
                    try:
                        Path(tmp_path).unlink()
                    except Exception:
                        pass
            elif hasattr(input_data, "read"):
                # Read to bytes first
                if hasattr(input_data, "seek"):
                    input_data.seek(0)
                data = input_data.read()
                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=".msg", delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name
                try:
                    msg_obj = extract_msg.Message(tmp_path)  # type: ignore[no-untyped-call]
                finally:
                    # Clean up temp file
                    try:
                        Path(tmp_path).unlink()
                    except Exception:
                        pass
            else:
                raise ValidationError(
                    f"Unsupported input type: {type(input_data)}",
                    parameter_name="input_data",
                    parameter_value=str(type(input_data)),
                )

            self._emit_progress("started", "Processing MSG file", total=1)

            # Convert to EmailMessage
            email_msg = _convert_msg_to_email_message(msg_obj)

            # Parse using EML logic
            msg_data = parse_single_message(email_msg, self.options)

            # Process attachments if needed
            if self.options.attachment_mode != "skip":
                attachment_content, attachment_footnotes = process_email_attachments(email_msg, self.options)
                # Merge footnotes
                self._attachment_footnotes.update(attachment_footnotes)
                if attachment_content and "content" in msg_data:
                    msg_data["content"] += attachment_content

            # Clean message content
            if "content" in msg_data:
                msg_data["content"] = clean_message(msg_data["content"], self.options)

            # Extract metadata
            metadata = self.extract_metadata({"format": "msg", "message_count": 1})

            # Convert to AST
            doc = self._format_messages_as_ast([msg_data])
            doc.metadata = metadata.to_dict()

            self._emit_progress("finished", "Processed MSG file", current=1, total=1)

            return doc

        except Exception as e:
            if isinstance(e, (ValidationError, MalformedFileError, ParsingError)):
                raise
            raise MalformedFileError(
                f"Failed to parse MSG file: {e!r}",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=e,
            ) from e

    def _parse_pst(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse PST/OST file using pypff.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            PST/OST file data

        Returns
        -------
        Document
            AST document

        Raises
        ------
        DependencyError
            If pypff is not installed

        """
        # Check for pypff
        try:
            import pypff
        except ImportError as e:
            raise DependencyError(
                converter_name="outlook",
                missing_packages=[("libpff-python", "")],
                original_import_error=e,
            ) from e

        # Validate input - pypff requires file path
        if not isinstance(input_data, (str, Path)):
            raise ValidationError(
                "PST/OST parser requires file path. IO streams and bytes are not supported for PST/OST.",
                parameter_name="input_data",
                parameter_value=str(type(input_data)),
            )

        path = Path(input_data)
        if not path.exists():
            raise ValidationError(
                f"PST/OST file does not exist: {path}",
                parameter_name="input_data",
                parameter_value=str(path),
            )

        try:
            # Open PST file
            pst_file = pypff.file()
            pst_file.open(str(path))

            # Get root folder
            root = pst_file.get_root_folder()

            self._emit_progress("started", "Processing PST/OST file")

            # Process messages from folders
            messages = self._process_pst_folders(root)

            # Sort messages chronologically
            messages.sort(
                key=lambda m: m.get("date") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
                reverse=(self.options.sort_order == "desc"),
            )

            # Extract metadata
            metadata = self.extract_metadata({"format": "pst", "message_count": len(messages)})

            # Convert to AST
            doc = self._format_messages_as_ast(messages)
            doc.metadata = metadata.to_dict()

            self._emit_progress(
                "finished", f"Processed {len(messages)} messages", current=len(messages), total=len(messages)
            )

            # Close PST file
            pst_file.close()

            return doc

        except Exception as e:
            if isinstance(e, (ValidationError, DependencyError, ParsingError)):
                raise
            raise MalformedFileError(
                f"Failed to parse PST/OST file: {e!r}",
                file_path=str(path),
                original_error=e,
            ) from e

    def _process_pst_folders(self, folder: Any, parent_path: str = "") -> list[dict[str, Any]]:
        """Recursively process folders in PST file.

        Parameters
        ----------
        folder : pypff.folder
            Folder to process
        parent_path : str
            Parent folder path for hierarchical tracking

        Returns
        -------
        list[dict[str, Any]]
            List of processed messages

        """
        messages = []
        folder_name = folder.get_name() or "Root"
        folder_path = f"{parent_path}/{folder_name}" if parent_path else folder_name

        # Check if folder should be processed
        if self.options.folder_filter:
            # Only process if in filter list
            if folder_name not in self.options.folder_filter:
                # Check subfolders if enabled
                if self.options.include_subfolders:
                    for subfolder in folder.sub_folders:
                        messages.extend(self._process_pst_folders(subfolder, folder_path))
                return messages
        elif self.options.skip_folders:
            # Skip if in skip list
            if folder_name in self.options.skip_folders:
                return messages

        # Process messages in this folder
        message_count = folder.get_number_of_sub_messages()
        for i in range(message_count):
            # Check message limit
            if self.options.max_messages and len(messages) >= self.options.max_messages:
                break

            try:
                pst_msg = folder.get_sub_message(i)
                msg_data = self._process_pst_message(pst_msg, folder_name)

                if msg_data and _filter_message(msg_data, self.options):
                    messages.append(msg_data)

                self._emit_progress(
                    "message_done",
                    f"Folder: {folder_name}, Message {i + 1}/{message_count}",
                    current=len(messages),
                )

            except Exception as e:
                logger.warning(f"Failed to process message {i} in folder {folder_name}: {e}")
                continue

        # Process subfolders if enabled
        if self.options.include_subfolders:
            for subfolder in folder.sub_folders:
                sub_messages = self._process_pst_folders(subfolder, folder_path)
                messages.extend(sub_messages)

                # Check message limit
                if self.options.max_messages and len(messages) >= self.options.max_messages:
                    break

        return messages

    def _process_pst_message(self, pst_msg: Any, folder_name: str) -> dict[str, Any] | None:
        """Process a single PST message.

        Parameters
        ----------
        pst_msg : pypff.message
            PST message object
        folder_name : str
            Folder name for metadata

        Returns
        -------
        dict[str, Any] or None
            Processed message data

        """
        try:
            # Extract message data
            msg_data: dict[str, Any] = {}

            # Get headers
            msg_data["from"] = pst_msg.get_sender_name() or ""
            msg_data["to"] = pst_msg.get_display_to() or ""
            msg_data["cc"] = pst_msg.get_display_cc() or ""
            msg_data["subject"] = pst_msg.get_subject() or ""

            # Get date
            try:
                delivery_time = pst_msg.get_delivery_time()
                if delivery_time:
                    # Convert to datetime
                    msg_data["date"] = delivery_time
            except Exception:
                msg_data["date"] = None

            # Get content
            try:
                # Prefer plain text
                plain_body = pst_msg.get_plain_text_body()
                if plain_body:
                    msg_data["content"] = plain_body
                else:
                    # Fallback to HTML
                    html_body = pst_msg.get_html_body()
                    if html_body:
                        # Convert HTML to markdown if option enabled
                        if self.options.convert_html_to_markdown:
                            msg_data["content"] = convert_eml_html_to_markdown(html_body, self.options)
                        else:
                            msg_data["content"] = html_body
                    else:
                        msg_data["content"] = ""
            except Exception as e:
                logger.warning(f"Failed to extract message content: {e}")
                msg_data["content"] = ""

            # Add folder metadata if requested
            if self.options.preserve_folder_metadata:
                msg_data["folder"] = folder_name

            # Clean message content
            if msg_data.get("content"):
                msg_data["content"] = clean_message(msg_data["content"], self.options)

            return msg_data

        except Exception as e:
            logger.warning(f"Failed to parse PST message: {e}")
            return None

    def _format_messages_as_ast(self, messages: list[dict[str, Any]]) -> Document:
        """Convert messages to AST Document.

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

        if self.options.output_structure == "hierarchical" and any("folder" in m for m in messages):
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
        """Extract metadata from Outlook file.

        Parameters
        ----------
        document : Any
            Dictionary with file information

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract format information
        if isinstance(document, dict):
            if "format" in document:
                metadata.custom["outlook_format"] = document["format"]
            if "message_count" in document:
                metadata.custom["message_count"] = document["message_count"]

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="outlook",
    extensions=[".msg", ".pst", ".ost"],
    mime_types=["application/vnd.ms-outlook"],
    magic_bytes=[
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0),  # MSG (OLE/CFBF)
        (b"!BDN", 0),  # PST/OST
    ],
    parser_class=OutlookToAstConverter,
    renderer_class=None,
    parser_required_packages=[
        ("extract-msg", "extract_msg", ""),
        # Note: pypff is NOT listed here - it's checked at runtime for PST/OST files only
    ],
    renderer_required_packages=[],
    parser_options_class=OutlookOptions,
    renderer_options_class=None,
    description="Convert Microsoft Outlook MSG, PST, and OST files to Markdown",
    priority=5,
)
