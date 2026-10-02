#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/docx_package.py
"""Repair a DOCX package that Word opens and ``python-docx`` refuses.

Two kinds are repaired: a Strict Open XML package, and one whose relationships name
parts that are not there.

Strict Open XML (ISO/IEC 29500 Strict, "Strict Open XML Document" in Word's Save As)
uses the same elements as the Transitional format every reader expects, under
different names: ``http://purl.oclc.org/ooxml/wordprocessingml/main`` for
``http://schemas.openxmlformats.org/wordprocessingml/2006/main``, and likewise for
every namespace and relationship type. ``python-docx`` finds no main document under
the Strict relationship type and refuses the package. Renaming them is enough for the
seven Strict files in LibreOffice's Writer regression corpus that Word opens.

A relationship (``*.rels``) points a part at another: the document at its footer, its
font table, its numbering, an image. ``python-docx`` loads every part the
relationships reach as it opens the package, so a single relationship naming a file
missing from the archive -- a footer an editor never wrote, an image a tool dropped,
an internal bookmark written as if it were a file -- fails the whole document with a
``KeyError``. Word opens such a file and shows what is there. LibreOffice's Writer
regression corpus holds fifteen of them.

The second repair rewrites the package in memory without those relationships, so
the missing part simply reads as absent: no footer, no font table, no numbering, an
image with nothing behind it. Both run only after an open has already failed, so a
sound package costs nothing, and a package they cannot improve reports the original
error.
"""

from __future__ import annotations

import io
import logging
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

logger = logging.getLogger(__name__)

_RELATIONSHIPS_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Strict Open XML (ISO/IEC 29500 Strict) names every namespace and relationship type
# under purl.oclc.org instead of schemas.openxmlformats.org; the elements inside are
# the same. Translating the names lets the Transitional reader open the package.
_STRICT_PREFIX = b"http://purl.oclc.org/ooxml/"
_STRICT_URI = re.compile(rb"http://purl\.oclc\.org/ooxml/[A-Za-z0-9/_\-]+")
_TRANSITIONAL = "http://schemas.openxmlformats.org/"
_STRICT_NAMESPACES = {
    "wordprocessingml/main": "wordprocessingml/2006/main",
    "spreadsheetml/main": "spreadsheetml/2006/main",
    "presentationml/main": "presentationml/2006/main",
    "officeDocument/math": "officeDocument/2006/math",
    "officeDocument/sharedTypes": "officeDocument/2006/sharedTypes",
    "officeDocument/bibliography": "officeDocument/2006/bibliography",
    "officeDocument/customXml": "officeDocument/2006/customXml",
    "officeDocument/docPropsVTypes": "officeDocument/2006/docPropsVTypes",
    "officeDocument/extendedProperties": "officeDocument/2006/extended-properties",
    "officeDocument/customProperties": "officeDocument/2006/custom-properties",
    "officeDocument/relationships": "officeDocument/2006/relationships",
    "drawingml/main": "drawingml/2006/main",
    "drawingml/wordprocessingDrawing": "drawingml/2006/wordprocessingDrawing",
    "drawingml/picture": "drawingml/2006/picture",
    "drawingml/chart": "drawingml/2006/chart",
    "drawingml/chartDrawing": "drawingml/2006/chartDrawing",
    "drawingml/diagram": "drawingml/2006/diagram",
    "drawingml/lockedCanvas": "drawingml/2006/lockedCanvas",
    "drawingml/compatibility": "drawingml/2006/compatibility",
}
# Relationship types whose last segment Transitional spells differently, or keeps in
# the package namespace rather than the office document one.
_STRICT_RELATIONSHIP_TYPES = {
    "extendedProperties": "officeDocument/2006/relationships/extended-properties",
    "customProperties": "officeDocument/2006/relationships/custom-properties",
    "metadata/thumbnail": "package/2006/relationships/metadata/thumbnail",
}


def package_bytes(input_data: Any) -> bytes | None:
    """Read the raw package from a path, bytes or a seekable stream, or None if it cannot be."""
    try:
        if isinstance(input_data, (str, Path)):
            return Path(input_data).read_bytes()
        if isinstance(input_data, (bytes, bytearray)):
            return bytes(input_data)
        if hasattr(input_data, "read") and hasattr(input_data, "seek"):
            input_data.seek(0)
            data = input_data.read()
            return data if isinstance(data, bytes) else None
    except OSError:
        return None
    return None


def _source_directory(rels_name: str) -> str:
    """Return the directory a ``.rels`` part resolves relative targets against.

    ``word/_rels/document.xml.rels`` describes ``word/document.xml``, so its targets are
    relative to ``word``; the package's own ``_rels/.rels`` is relative to the root.
    """
    return posixpath.dirname(posixpath.dirname(rels_name))


def _target_exists(target: str, source_dir: str, names: set[str]) -> bool:
    for candidate in (target, unquote(target)):
        if candidate.startswith("/"):
            path = candidate.lstrip("/")
        else:
            path = posixpath.normpath(posixpath.join(source_dir, candidate))
        if path in names:
            return True
    return False


def drop_dangling_relationships(data: bytes) -> tuple[bytes, list[str]] | None:
    """Rewrite a package without its relationships to parts the archive lacks.

    Returns the rewritten package and the targets dropped, or None when the package
    is not a readable archive or has no such relationship to drop. External targets
    (a hyperlink's URL, a linked file) are never touched: they were never parts.
    """
    from lxml import etree

    try:
        source = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None

    names = set(source.namelist())
    dropped: list[str] = []
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename.endswith(".rels"):
                try:
                    root = etree.fromstring(content)
                except etree.XMLSyntaxError:
                    target.writestr(item, content)
                    continue
                source_dir = _source_directory(item.filename)
                removed = False
                for relationship in list(root.iterchildren(f"{_RELATIONSHIPS_NS}Relationship")):
                    if relationship.get("TargetMode") == "External":
                        continue
                    target_ref = relationship.get("Target", "")
                    if not _target_exists(target_ref, source_dir, names):
                        root.remove(relationship)
                        dropped.append(posixpath.join(source_dir, target_ref) if source_dir else target_ref)
                        removed = True
                if removed:
                    content = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            target.writestr(item, content)

    if not dropped:
        return None
    logger.warning("DOCX package names parts it does not contain; reading without them: %s", ", ".join(dropped))
    return output.getvalue(), dropped


def _transitional_uri(match: re.Match[bytes]) -> bytes:
    name = match.group(0)[len(_STRICT_PREFIX) :].decode("ascii")
    if name in _STRICT_NAMESPACES:
        return (_TRANSITIONAL + _STRICT_NAMESPACES[name]).encode("ascii")
    relationships = "officeDocument/relationships/"
    if name.startswith(relationships):
        kind = name[len(relationships) :]
        mapped = _STRICT_RELATIONSHIP_TYPES.get(kind, f"officeDocument/2006/relationships/{kind}")
        return (_TRANSITIONAL + mapped).encode("ascii")
    return match.group(0)


def strict_to_transitional(data: bytes) -> bytes | None:
    """Rewrite a Strict Open XML package with Transitional names, or None if it is not Strict.

    The package is Strict when its main relationship has the Strict type. Every XML
    part and relationship part has its Strict namespace URIs and relationship types
    replaced by the Transitional ones; names this table does not know are left alone.
    """
    try:
        source = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None

    with source:
        try:
            package_rels = source.read("_rels/.rels")
        except KeyError:
            return None
        if _STRICT_PREFIX + b"officeDocument/relationships/officeDocument" not in package_rels:
            return None
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                content = source.read(item.filename)
                if item.filename.endswith((".xml", ".rels")) and _STRICT_PREFIX in content:
                    content = _STRICT_URI.sub(_transitional_uri, content)
                target.writestr(item, content)

    logger.info("Reading a Strict Open XML package as Transitional")
    return output.getvalue()
