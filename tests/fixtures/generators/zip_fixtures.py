"""ZIP archive fixture generators for container format tests."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from utils import MINIMAL_PNG_BYTES


def create_simple_zip() -> bytes:
    """Create a ZIP archive containing a couple of text files."""
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "Sample ZIP archive for testing\n")
        archive.writestr("docs/notes.txt", "Nested directory entry\n")
    return buffer.getvalue()


def create_zip_with_binary_assets() -> bytes:
    """Create a ZIP archive that mixes text and binary content."""
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("data/report.csv", "id,value\n1,42\n2,99\n")
        archive.writestr("images/thumbnail.png", MINIMAL_PNG_BYTES)
        archive.writestr("scripts/run.sh", "#!/bin/sh\n echo 'ZIP fixture'\n")
    return buffer.getvalue()


def create_zip_with_subarchives() -> bytes:
    """Create a ZIP archive containing another nested ZIP file."""
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        inner_zip = BytesIO()
        with ZipFile(inner_zip, mode="w", compression=ZIP_DEFLATED) as inner:
            inner.writestr("inner.txt", "Nested archive content\n")
        archive.writestr("archives/inner.zip", inner_zip.getvalue())
        archive.writestr("README.md", "# Zip Fixture\n\nContains a nested archive.\n")
    return buffer.getvalue()


def zip_bytes_io(zip_bytes: bytes) -> BytesIO:
    """Return a BytesIO handle for ZIP bytes."""
    return BytesIO(zip_bytes)
