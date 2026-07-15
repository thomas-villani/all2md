"""Corpus loading for the roundtrip benchmark.

Phase 0/1 ships the *synthetic* corpus only: labeled Markdown files under
``corpus/synthetic/``, one construct family per file plus a ``kitchen-sink``
document that combines them. Each file's stem is its construct family; tags are
derived from content (e.g. ``has_raw_html`` marks a doc that is lossy by policy
under all2md's ``html_passthrough_mode="escape"`` posture, so the HTML oracle
skips it rather than flagging an expected loss).

The CommonMark / GFM spec suites (Phase 2) will land as an additional loader
here; the ``Case`` shape is already source-agnostic to accommodate them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYNTHETIC_DIR = HERE / "corpus" / "synthetic"

# A run of raw HTML: an open tag like <div ...>, </div>, or a self-closing tag.
# Deliberately loose - if a doc contains anything HTML-ish we treat it as
# raw-HTML and let the HTML oracle skip it (all2md escapes raw HTML by policy).
_RAW_HTML = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(\s[^<>]*)?/?>")


@dataclass
class Case:
    """One corpus document.

    ``source`` distinguishes the synthetic corpus from later spec suites.
    ``has_raw_html`` flags documents the HTML-equivalence oracle should skip
    because all2md intentionally escapes raw HTML (a policy loss, not a bug).
    """

    name: str
    markdown: str
    source: str = "synthetic"
    path: Path | None = None
    has_raw_html: bool = False
    tags: list[str] = field(default_factory=list)


def _strip_fenced_code(md: str) -> str:
    """Drop fenced code so HTML shown as an example isn't read as raw HTML."""
    return re.sub(r"```.*?```", "", md, flags=re.DOTALL)


def _looks_like_raw_html(md: str) -> bool:
    return bool(_RAW_HTML.search(_strip_fenced_code(md)))


def load_synthetic_corpus(directory: Path | None = None) -> list[Case]:
    """Load every ``*.md`` under the synthetic corpus dir, sorted by name."""
    directory = directory or SYNTHETIC_DIR
    cases: list[Case] = []
    for path in sorted(directory.glob("*.md")):
        md = path.read_text(encoding="utf-8")
        cases.append(
            Case(
                name=path.stem,
                markdown=md,
                source="synthetic",
                path=path,
                has_raw_html=_looks_like_raw_html(md),
                tags=[path.stem],
            )
        )
    return cases
