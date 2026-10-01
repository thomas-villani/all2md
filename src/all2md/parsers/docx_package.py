#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/docx_package.py
"""Repair a DOCX package whose relationships name parts that are not there.

A relationship (``*.rels``) points a part at another: the document at its footer, its
font table, its numbering, an image. ``python-docx`` loads every part the
relationships reach as it opens the package, so a single relationship naming a file
missing from the archive -- a footer an editor never wrote, an image a tool dropped,
an internal bookmark written as if it were a file -- fails the whole document with a
``KeyError``. Word opens such a file and shows what is there. LibreOffice's Writer
regression corpus holds fifteen of them.

The repair rewrites the package in memory without those relationships, so the
missing part simply reads as absent: no footer, no font table, no numbering, an image
with nothing behind it. It runs only after an open has already failed, so a sound
package costs nothing, and a package it cannot improve reports the original error.
"""

from __future__ import annotations

import io
import logging
import posixpath
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

logger = logging.getLogger(__name__)

_RELATIONSHIPS_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


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
