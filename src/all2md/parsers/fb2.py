# Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/fb2.py
"""FB2 (FictionBook 2.0) parser that converts FB2 ebooks to AST representation."""

from __future__ import annotations

import base64
import binascii
import io
import logging
import mimetypes
import re
import zipfile
from pathlib import Path
from typing import IO, Any, Iterable, Optional, Union

import defusedxml.ElementTree as ET

from all2md.ast import (
    BlockQuote,
    Code,
    Document,
    Emphasis,
    Heading,
    LineBreak,
    Link,
    Node,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Text,
    ThematicBreak,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError, ValidationError
from all2md.options.fb2 import Fb2Options
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import process_attachment
from all2md.utils.encoding import normalize_stream_to_bytes
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.parser_helpers import attachment_result_to_image_node

logger = logging.getLogger(__name__)

_FB2_NAMESPACE = "http://www.gribuser.ru/xml/fictionbook/2.0"
_XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"


class Fb2ToAstConverter(BaseParser):
    """Convert FB2 ebooks to AST representation."""

    def __init__(self, options: Optional[Fb2Options] = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the FB2 to AST converter.

        Parameters
        ----------
        options : Fb2Options or None, default = None
            Parser configuration options
        progress_callback : ProgressCallback or None, default = None
            Optional callback for progress updates

        """
        BaseParser._validate_options_type(options, Fb2Options, "fb2")
        options = options or Fb2Options()
        super().__init__(options, progress_callback)
        self.options: Fb2Options = options
        self._namespaces: dict[str, str] = {"fb2": _FB2_NAMESPACE, "xlink": _XLINK_NAMESPACE}
        self._binary_map: dict[str, dict[str, Any]] = {}
        self._attachment_cache: dict[str, dict[str, Any]] = {}
        self._attachment_footnotes: dict[str, str] = {}
        self._whitespace_pattern = re.compile(r"\s+")

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse FB2 document into an AST Document."""
        self._emit_progress("started", "Converting FB2 document", current=0, total=1)

        xml_bytes = self._load_fb2_bytes(input_data)
        root = self._parse_fb2_root(xml_bytes)

        doc = self.convert_to_ast(root)
        metadata = self.extract_metadata(root)
        doc.metadata = metadata.to_dict()

        self._emit_progress("finished", "FB2 conversion completed", current=1, total=1)
        return doc

    def convert_to_ast(self, root: ET.Element) -> Document:
        """Convert parsed FB2 XML tree to AST Document."""
        self._binary_map = self._collect_binaries(root)
        self._attachment_cache = {}
        self._attachment_footnotes = {}

        children: list[Node] = []
        note_children: list[Node] = []

        for body in self._iter_children(root, "body"):
            body_nodes = self._process_body(body, heading_level=1)
            if self._is_notes_body(body):
                if self.options.include_notes:
                    # Drop leading heading to avoid duplicate "Notes" headings later
                    filtered = body_nodes[1:] if body_nodes and isinstance(body_nodes[0], Heading) else body_nodes
                    note_children.extend(filtered)
            else:
                children.extend(body_nodes)

        if note_children and self.options.include_notes:
            if children:
                children.append(ThematicBreak())
            children.append(Heading(level=2, content=[Text(content=self.options.notes_section_title)]))
            children.extend(note_children)

        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        return Document(children=children)

    def extract_metadata(self, document: ET.Element) -> DocumentMetadata:
        """Extract metadata from FB2 XML tree."""
        metadata = DocumentMetadata()

        description = self._find_child(document, "description")
        if description is None:
            return metadata

        title_info = self._find_child(description, "title-info")
        if title_info is not None:
            title = self._find_text(title_info, "book-title")
            if title:
                metadata.title = title

            authors = [self._format_author(author) for author in self._iter_children(title_info, "author")]
            authors = [a for a in authors if a]
            if authors:
                metadata.author = ", ".join(authors)

            annotation = self._find_child(title_info, "annotation")
            if annotation is not None:
                annotation_text = self._collect_plain_text(annotation)
                if annotation_text:
                    metadata.subject = annotation_text

            keywords = self._find_text(title_info, "keywords")
            if keywords:
                metadata.keywords = [kw.strip() for kw in keywords.split(",") if kw.strip()]

            date_element = self._find_child(title_info, "date")
            if date_element is not None:
                date_value = date_element.attrib.get("value") or self._collect_plain_text(date_element)
                if date_value:
                    metadata.creation_date = date_value

            language = self._find_text(title_info, "lang")
            if language:
                metadata.language = language

            genres = [self._collect_plain_text(genre) for genre in self._iter_children(title_info, "genre")]
            genres = [g for g in genres if g]
            if genres:
                metadata.custom["genres"] = genres

        doc_info = self._find_child(description, "document-info")
        if doc_info is not None:
            doc_authors = [self._collect_plain_text(author) for author in self._iter_children(doc_info, "author")]
            doc_authors = [a for a in doc_authors if a]
            if doc_authors:
                metadata.creator = ", ".join(doc_authors)

            doc_id = self._find_text(doc_info, "id")
            if doc_id:
                metadata.custom["identifier"] = doc_id

            publisher = self._find_text(doc_info, "publisher")
            if publisher:
                metadata.custom["publisher"] = publisher

            doc_date = self._find_child(doc_info, "date")
            if doc_date is not None:
                doc_date_value = doc_date.attrib.get("value") or self._collect_plain_text(doc_date)
                if doc_date_value:
                    metadata.modification_date = doc_date_value

        return metadata

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    def _load_fb2_bytes(self, input_data: Union[str, Path, IO[bytes], bytes]) -> bytes:
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            if path.suffix.lower() == ".fb2":
                return path.read_bytes()
            if path.name.lower().endswith(".fb2.zip") or path.suffix.lower() == ".zip":
                with self._validated_zip_input(path, suffix=".zip") as validated:
                    return self._extract_fb2_from_zip(validated)

            return path.read_bytes()

        if isinstance(input_data, bytes):
            if input_data.startswith(b"PK\x03\x04"):
                with self._validated_zip_input(input_data, suffix=".zip") as validated:
                    return self._extract_fb2_from_zip(validated)
            return input_data

        if hasattr(input_data, "read"):
            original_position = input_data.tell() if hasattr(input_data, "tell") else None
            # Normalize stream to bytes (handles both binary and text mode)
            data = normalize_stream_to_bytes(input_data)
            if original_position is not None:
                input_data.seek(original_position)
            if data.startswith(b"PK\x03\x04"):
                with self._validated_zip_input(data, suffix=".zip") as validated:
                    return self._extract_fb2_from_zip(validated)
            return data

        raise ValidationError("Unsupported input type for FB2 parser")

    def _extract_fb2_from_zip(self, zip_source: Union[str, Path, IO[bytes]]) -> bytes:
        try:
            with zipfile.ZipFile(zip_source) as archive:
                fb2_names = [
                    info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith(".fb2")
                ]
                if not fb2_names:
                    raise ParsingError(
                        "FB2 archive does not contain an .fb2 file",
                        parsing_stage="archive_extraction",
                    )
                # Prefer the smallest name (heuristic for primary document)
                fb2_info = sorted(fb2_names, key=lambda info: len(info.filename))[0]
                return archive.read(fb2_info)
        except zipfile.BadZipFile as exc:
            raise ParsingError(
                "Failed to read FB2 ZIP archive",
                parsing_stage="archive_opening",
                original_error=exc,
            ) from exc

    def _parse_fb2_root(self, xml_bytes: bytes) -> ET.Element:
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as first_error:
            for encoding in self.options.fallback_encodings:
                try:
                    decoded = xml_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
                try:
                    root = ET.fromstring(decoded)
                    break
                except ET.ParseError:
                    continue
            else:
                raise ParsingError(
                    f"Failed to parse FB2 XML: {first_error}",
                    parsing_stage="xml_parsing",
                    original_error=first_error,
                ) from first_error
        namespace = self._extract_namespace(root.tag)
        if namespace:
            self._namespaces["fb2"] = namespace
        return root

    def _collect_binaries(self, root: ET.Element) -> dict[str, dict[str, Any]]:
        binaries: dict[str, dict[str, Any]] = {}
        for binary in root.findall(f".//{{{self._namespaces['fb2']}}}binary"):
            binary_id = binary.attrib.get("id")
            if not binary_id:
                continue
            data_str = "".join(binary.itertext()).strip()
            if not data_str:
                continue
            try:
                data = base64.b64decode(self._whitespace_pattern.sub("", data_str), validate=False)
            except (binascii.Error, ValueError) as exc:
                logger.warning("Failed to decode FB2 binary %s: %s", binary_id, exc)
                continue
            if not data:
                continue
            if len(data) > self.options.max_asset_size_bytes:
                logger.warning(
                    "Skipping FB2 binary %s: size %s exceeds limit %s",
                    binary_id,
                    len(data),
                    self.options.max_asset_size_bytes,
                )
                continue
            content_type = binary.attrib.get("content-type", "")
            guessed_ext = mimetypes.guess_extension(content_type) if content_type else None
            name = binary.attrib.get("id") or "attachment"
            if guessed_ext and not name.lower().endswith(guessed_ext):
                name = f"{name}{guessed_ext}"
            binaries[binary_id] = {
                "data": data,
                "content_type": content_type,
                "name": name,
            }
        return binaries

    def _process_body(self, body: ET.Element, heading_level: int) -> list[Node]:
        nodes: list[Node] = []
        title = self._find_child(body, "title")
        if title is not None:
            heading_nodes = self._title_to_heading(title, heading_level)
            nodes.extend(heading_nodes)
        for child in body:
            local = self._local_name(child.tag)
            if local == "title":
                continue
            if local == "section":
                nodes.extend(self._process_section(child, min(heading_level + 1, 6)))
            elif local == "p":
                paragraph = self._build_paragraph(child)
                if paragraph:
                    nodes.append(paragraph)
            elif local == "image":
                image_node = self._process_image(child, inline=False)
                if image_node:
                    nodes.append(image_node)
            elif local == "empty-line":
                nodes.append(Paragraph(content=[]))
            elif local == "poem":
                nodes.extend(self._process_poem(child))
            elif local == "epigraph":
                nodes.extend(self._process_epigraph(child))
            else:
                fallback = self._build_paragraph(child)
                if fallback:
                    nodes.append(fallback)
        return nodes

    def _process_section(self, section: ET.Element, heading_level: int) -> list[Node]:
        section_type = (section.attrib.get("type") or "").lower()
        if section_type and "notes" in section_type and not self.options.include_notes:
            return []

        nodes: list[Node] = []
        title = self._find_child(section, "title")
        if title is not None:
            nodes.extend(self._title_to_heading(title, heading_level))

        for child in section:
            local = self._local_name(child.tag)
            if local == "title":
                continue
            if local == "section":
                nodes.extend(self._process_section(child, min(heading_level + 1, 6)))
            elif local in {"p", "subtitle", "text-author", "cite"}:
                paragraph = self._build_paragraph(child)
                if paragraph:
                    if local == "subtitle":
                        nodes.append(Heading(level=min(heading_level + 1, 6), content=paragraph.content))
                    else:
                        nodes.append(paragraph)
            elif local == "poem":
                nodes.extend(self._process_poem(child))
            elif local == "epigraph":
                nodes.extend(self._process_epigraph(child))
            elif local == "image":
                image_node = self._process_image(child, inline=False)
                if image_node:
                    nodes.append(image_node)
            elif local == "empty-line":
                nodes.append(Paragraph(content=[]))
            else:
                fallback = self._build_paragraph(child)
                if fallback:
                    nodes.append(fallback)
        return nodes

    def _process_poem(self, poem: ET.Element) -> list[Node]:
        nodes: list[Node] = []
        for child in poem:
            local = self._local_name(child.tag)
            if local == "title":
                nodes.extend(self._title_to_heading(child, heading_level=3))
            elif local == "stanza":
                stanza_content: list[Node] = []
                first_line = True
                for line in child:
                    if self._local_name(line.tag) != "v":
                        continue
                    line_nodes = self._convert_inline(line)
                    if not line_nodes:
                        continue
                    if not first_line:
                        stanza_content.append(LineBreak())
                    stanza_content.extend(line_nodes)
                    first_line = False
                if stanza_content:
                    nodes.append(Paragraph(content=stanza_content))
            else:
                fallback = self._build_paragraph(child)
                if fallback:
                    nodes.append(fallback)
        return nodes

    def _process_epigraph(self, epigraph: ET.Element) -> list[Node]:
        quote_children: list[Node] = []
        for child in epigraph:
            paragraph = self._build_paragraph(child)
            if paragraph:
                quote_children.append(paragraph)
        if not quote_children:
            return []
        return [BlockQuote(children=quote_children)]

    def _build_paragraph(self, element: ET.Element) -> Optional[Paragraph]:
        content = self._convert_inline(element)
        if not content:
            text = self._collect_plain_text(element)
            if not text:
                return None
            content = [Text(content=text)]
        content = self._trim_trailing_whitespace(content)
        if not content:
            return None
        return Paragraph(content=content)

    def _convert_inline(self, element: ET.Element) -> list[Node]:
        nodes: list[Node] = []
        if element.text:
            self._append_text(nodes, element.text)
        for child in element:
            child_nodes = self._convert_inline_element(child)
            nodes.extend(child_nodes)
            if child.tail:
                self._append_text(nodes, child.tail)
        return nodes

    def _convert_inline_element(self, element: ET.Element) -> list[Node]:
        local = self._local_name(element.tag)
        if local == "emphasis":
            return [Emphasis(content=self._convert_inline(element))]
        if local == "strong":
            return [Strong(content=self._convert_inline(element))]
        if local == "strikethrough":
            return [Strikethrough(content=self._convert_inline(element))]
        if local in {"sub", "subscript"}:
            return [Subscript(content=self._convert_inline(element))]
        if local in {"sup", "superscript"}:
            return [Superscript(content=self._convert_inline(element))]
        if local == "code":
            code_text = self._collect_plain_text(element)
            if code_text:
                return [Code(content=code_text)]
            return []
        if local == "a":
            link_nodes = self._convert_link(element)
            if link_nodes:
                return link_nodes
            return self._convert_inline(element)
        if local == "image":
            image_node = self._process_image(element, inline=True)
            return [image_node] if image_node else []
        return self._convert_inline(element)

    def _convert_link(self, element: ET.Element) -> list[Node]:
        href = element.attrib.get(self._qname(self._namespaces.get("xlink", _XLINK_NAMESPACE), "href"))
        if not href:
            href = element.attrib.get("href")
        if not href:
            return []
        url = href.strip()
        content = self._convert_inline(element)
        title = element.attrib.get("title")
        return [Link(url=url, content=content, title=title)]

    def _process_image(self, element: ET.Element, inline: bool) -> Optional[Node]:
        href = element.attrib.get(self._qname(self._namespaces.get("xlink", _XLINK_NAMESPACE), "href"))
        if not href:
            href = element.attrib.get("href")
        if not href:
            return None
        binary_id = href.lstrip("#")
        binary = self._binary_map.get(binary_id)
        if not binary:
            logger.debug("Referenced FB2 binary missing: %s", binary_id)
            return None

        if binary_id not in self._attachment_cache:
            alt_text = element.attrib.get("alt") or binary.get("name", "image")
            result = process_attachment(
                attachment_data=binary["data"],
                attachment_name=binary.get("name", binary_id),
                alt_text=alt_text,
                attachment_mode=self.options.attachment_mode,
                attachment_output_dir=self.options.attachment_output_dir,
                attachment_base_url=self.options.attachment_base_url,
                is_image=True,
                alt_text_mode=self.options.alt_text_mode,
            )
            self._attachment_cache[binary_id] = result
            footnote_label = result.get("footnote_label")
            footnote_content = result.get("footnote_content")
            if footnote_label and footnote_content:
                self._attachment_footnotes[footnote_label] = footnote_content
        result = self._attachment_cache[binary_id]
        fallback_alt = element.attrib.get("alt") or binary.get("name", "image")
        image_node = attachment_result_to_image_node(result, fallback_alt_text=fallback_alt)
        if image_node and binary.get("content_type"):
            image_node.metadata["content_type"] = binary["content_type"]
        if not image_node:
            return None
        if inline:
            return image_node
        return Paragraph(content=[image_node])

    # ------------------------------------------------------------------
    # XML helpers
    # ------------------------------------------------------------------
    def _find_child(self, element: ET.Element, local_name: str) -> Optional[ET.Element]:
        for child in element:
            if self._local_name(child.tag) == local_name:
                return child
        return None

    def _find_text(self, element: ET.Element, local_name: str) -> Optional[str]:
        child = self._find_child(element, local_name)
        if child is None:
            return None
        text = self._collect_plain_text(child)
        return text or None

    def _iter_children(self, element: ET.Element, local_name: str) -> Iterable[ET.Element]:
        for child in element:
            if self._local_name(child.tag) == local_name:
                yield child

    def _local_name(self, tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _extract_namespace(self, tag: str) -> str:
        if tag.startswith("{") and "}" in tag:
            return tag[1:].split("}", 1)[0]
        return ""

    def _qname(self, namespace: str, local_name: str) -> str:
        return f"{{{namespace}}}{local_name}" if namespace else local_name

    def _collect_plain_text(self, element: ET.Element) -> str:
        text = "".join(element.itertext())
        return self._normalize_text(text)

    def _append_text(self, nodes: list[Node], text: str) -> None:
        normalized = self._normalize_text(text)
        if not normalized:
            return
        if nodes and isinstance(nodes[-1], Text):
            if nodes[-1].content and not nodes[-1].content.endswith(" "):
                nodes[-1].content += " "
            nodes[-1].content += normalized
        else:
            nodes.append(Text(content=normalized))

    def _normalize_text(self, text: str) -> str:
        normalized = self._whitespace_pattern.sub(" ", text or "")
        return normalized.strip()

    def _trim_trailing_whitespace(self, nodes: list[Node]) -> list[Node]:
        while nodes and isinstance(nodes[-1], Text):
            nodes[-1].content = nodes[-1].content.rstrip()
            if nodes[-1].content:
                break
            nodes.pop()
        return nodes

    def _format_author(self, author: ET.Element) -> str:
        parts = [
            self._find_text(author, "first-name"),
            self._find_text(author, "middle-name"),
            self._find_text(author, "last-name"),
        ]
        name = " ".join(part for part in parts if part)
        if name:
            return name
        nickname = self._find_text(author, "nickname")
        return nickname or ""

    def _title_to_heading(self, title_element: ET.Element, heading_level: int) -> list[Heading]:
        content: list[Node] = []
        if title_element.text:
            self._append_text(content, title_element.text)
        for child in title_element:
            if self._local_name(child.tag) == "p":
                content.extend(self._convert_inline(child))
            else:
                content.extend(self._convert_inline(child))
            if child.tail:
                self._append_text(content, child.tail)
        content = self._trim_trailing_whitespace(content)
        if not content:
            return []
        level = min(max(heading_level, 1), 6)
        return [Heading(level=level, content=content)]

    def _is_notes_body(self, body: ET.Element) -> bool:
        body_type = (body.attrib.get("type") or body.attrib.get("name") or "").lower()
        return "note" in body_type


def _is_fb2_content(data: bytes) -> bool:
    """Heuristic content detector for FB2 documents."""
    if not data:
        return False
    leading = data.lstrip()
    if leading.startswith(b"<?xml"):
        try:
            snippet = leading[:4096].decode("utf-8", errors="ignore")
        except UnicodeDecodeError:
            snippet = ""
        return "FictionBook" in snippet
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                return any(name.lower().endswith(".fb2") for name in archive.namelist())
        except zipfile.BadZipFile:
            return False
    return False


CONVERTER_METADATA = ConverterMetadata(
    format_name="fb2",
    extensions=[".fb2"],
    mime_types=["application/x-fictionbook+xml", "text/xml"],
    magic_bytes=[(b"<?xml", 0)],
    content_detector=_is_fb2_content,
    parser_class=Fb2ToAstConverter,
    parser_options_class=Fb2Options,
    description="FictionBook 2.0 ebook format",
    priority=6,
)
