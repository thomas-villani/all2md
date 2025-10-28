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


def create_org_enhanced_features() -> str:
    """Return an Org-mode document showcasing enhanced parsing features.

    This includes:
    - SCHEDULED timestamps with time ranges
    - Repeating tasks
    - CLOSED timestamps
    - Properties drawer
    - Tags
    - LOGBOOK drawer with state changes (when properly positioned)
    """
    return (
        "#+TITLE: Enhanced Org Features\n"
        "#+AUTHOR: Test User\n"
        "#+DATE: 2025-10-27\n\n"
        "* TODO Weekly meeting :work:team:\n"
        "  :PROPERTIES:\n"
        "  :ID: meeting-001\n"
        "  :LOCATION: Conference Room A\n"
        "  :END:\n"
        "  SCHEDULED: <2025-11-04 Mon 10:00-11:00>\n\n"
        "  Meeting agenda items.\n\n"
        "* TODO Recurring task :personal:\n"
        "  SCHEDULED: <2025-11-02 Sun +1w>\n\n"
        "  Weekly review task that repeats.\n\n"
        "* DONE Completed project :work:archived:\n"
        "  :PROPERTIES:\n"
        "  :ID: project-123\n"
        "  :END:\n"
        "  CLOSED: [2024-12-01 Sun]\n"
        "  SCHEDULED: <2024-11-15 Fri>\n"
        "  DEADLINE: <2024-12-01 Sun>\n\n"
        "  Final deliverables completed.\n\n"
        "* TODO Task with notes :work:\n"
        "  :PROPERTIES:\n"
        "  :CREATED: [2025-10-27 Mon]\n"
        "  :END:\n"
        "  :LOGBOOK:\n"
        '  - Note "Started work" [2025-10-27 Mon 14:30]\n'
        "  :END:\n\n"
        "  Task with detailed notes.\n"
    )


def org_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode Org-mode content to bytes."""
    return text.encode(encoding)


def org_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream containing Org-mode text."""
    return BytesIO(org_to_bytes(text, encoding=encoding))
