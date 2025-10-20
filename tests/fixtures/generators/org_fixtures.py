"""Org-mode fixture generators for Emacs Org document tests."""

from __future__ import annotations

from io import BytesIO


def create_org_agenda_document() -> str:
    """Return an Org-mode document with headings, lists, and tables."""
    return (
        "#+TITLE: Sprint Notes\n"
        "#+AUTHOR: Test User\n\n"
        "* TODO Implement feature A\n"
        "  DEADLINE: <2025-03-15 Fri>\n"
        "  - [ ] Write design\n"
        "  - [ ] Implement\n"
        "  - [ ] Review\n\n"
        "* DONE Ship bug fixes\n"
        "  CLOSED: [2025-02-28 Fri]\n\n"
        "* Notes\n"
        "  Some inline =code= and *bold* text.\n\n"
        "| Task       | Owner | Status |\n"
        "|------------+-------+--------|\n"
        "| Feature A  | Alex  | TODO   |\n"
        "| Bug fixes  | Blair | DONE   |\n"
    )


def org_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode Org-mode content to bytes."""
    return text.encode(encoding)


def org_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream containing Org-mode text."""
    return BytesIO(org_to_bytes(text, encoding=encoding))
