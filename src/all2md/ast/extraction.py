#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/extraction.py
"""Typed ``--extract`` selectors: sections, tables, and figures.

This module backs the CLI ``--extract`` flag. It parses a single selector
string into a typed :class:`ExtractSelector`, resolves it against a document's
AST, and assembles one or more selectors into a combined :class:`Document`.

Selector grammar (one per ``--extract``)::

    <body>[::<word-limit>]

where ``<body>`` is one of:

- ``Introduction`` / ``Chapter*`` -- section by heading name or wildcard pattern
- ``#:1`` / ``#:1-3`` / ``#:1,3,5`` / ``#:3-`` -- section(s) by 1-based index
- ``table:2`` / ``table:1-3`` / ``table:*`` -- table(s) by 1-based position
- ``figure:1`` / ``image:1`` / ``figure:*`` -- figure(s)/image(s) by position

The optional ``::N`` suffix truncates the selector's output to roughly ``N``
words, cutting only at node boundaries so the result stays a valid AST.

``line:`` ranges are intentionally *not* handled here -- they select by rendered
output line and are resolved in the CLI layer where the Markdown rendering is
available.

Examples
--------
>>> doc = build_extracted_document(source, ["Introduction::500", "table:1"])

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Optional

from all2md.ast.nodes import (
    Document,
    Image,
    Node,
    Paragraph,
    Table,
    ThematicBreak,
    get_node_children,
)
from all2md.ast.sections import get_all_sections, parse_section_ranges, resolve_section_indices
from all2md.ast.utils import extract_text

# Separator between a selector body and its optional word limit (``Intro::500``).
WORD_LIMIT_SEP = "::"

# Reserved prefixes that switch a selector away from section name/index matching.
_TABLE_PREFIX = "table:"
_FIGURE_PREFIXES = ("figure:", "image:")

SelectorKind = Literal["section", "table", "figure"]


@dataclass(frozen=True)
class ExtractSelector:
    """A parsed ``--extract`` selector.

    Attributes
    ----------
    kind : {"section", "table", "figure"}
        What the selector targets.
    spec : str
        The selector body with any ``kind:`` prefix and ``::N`` suffix removed
        (e.g. ``"Introduction"``, ``"#:1-3"``, ``"2"``, ``"*"``).
    word_limit : int or None
        Optional cap on the number of words in the selector's output.
    raw : str
        The original, unparsed selector string (used in error messages).

    """

    kind: SelectorKind
    spec: str
    word_limit: Optional[int]
    raw: str


def parse_extract_selector(raw: str) -> ExtractSelector:
    """Parse a single ``--extract`` selector string.

    Parameters
    ----------
    raw : str
        Selector string, e.g. ``"Introduction::500"`` or ``"table:2"``.

    Returns
    -------
    ExtractSelector
        The parsed selector.

    Raises
    ------
    ValueError
        If the selector is empty or the ``::N`` word limit is not a positive
        integer.

    """
    text = raw.strip()

    word_limit: Optional[int] = None
    body = text
    if WORD_LIMIT_SEP in text:
        body, _, limit_str = text.rpartition(WORD_LIMIT_SEP)
        body = body.strip()
        limit_str = limit_str.strip()
        if not limit_str.isdigit() or int(limit_str) < 1:
            raise ValueError(
                f"Invalid word limit in --extract '{raw}': expected a positive integer after '{WORD_LIMIT_SEP}'."
            )
        word_limit = int(limit_str)

    if not body:
        raise ValueError(f"Empty --extract selector: '{raw}'.")

    lower = body.lower()
    if lower.startswith(_TABLE_PREFIX):
        return ExtractSelector("table", body[len(_TABLE_PREFIX) :].strip(), word_limit, raw)
    for prefix in _FIGURE_PREFIXES:
        if lower.startswith(prefix):
            return ExtractSelector("figure", body[len(prefix) :].strip(), word_limit, raw)

    return ExtractSelector("section", body, word_limit, raw)


def _walk(nodes: list[Node]) -> Iterator[Node]:
    """Yield every node in ``nodes`` and all of their descendants (pre-order)."""
    for node in nodes:
        yield node
        yield from _walk(get_node_children(node))


def collect_tables(doc: Document) -> list[Table]:
    """Return every :class:`Table` in the document, in document order."""
    return [node for node in _walk(doc.children) if isinstance(node, Table)]


def collect_figures(doc: Document) -> list[Image]:
    """Return every :class:`Image` in the document, in document order."""
    return [node for node in _walk(doc.children) if isinstance(node, Image)]


def _resolve_indexed(count: int, spec: str, what: str) -> list[int]:
    """Resolve a 1-based positional spec (``2``, ``1-3``, ``*``) to 0-based indices."""
    if count == 0:
        raise ValueError(f"Document contains no {what}s to extract")

    normalized = spec.strip().lower()
    if normalized in ("", "*", "all"):
        return list(range(count))

    indices = parse_section_ranges(spec, count)
    if not indices:
        raise ValueError(f"No {what}s selected by '{spec}' (document has {count} {what}{'s' if count != 1 else ''})")
    return indices


def _join_groups(groups: list[list[Node]]) -> list[Node]:
    """Flatten node groups, inserting a :class:`ThematicBreak` between groups."""
    out: list[Node] = []
    for i, group in enumerate(groups):
        if i:
            out.append(ThematicBreak())
        out.extend(group)
    return out


def _section_nodes(doc: Document, spec: str) -> list[Node]:
    """Resolve a section selector to a node sequence (matching ``extract_sections``)."""
    sections = get_all_sections(doc)
    if not sections:
        raise ValueError("Document contains no sections (headings)")

    indices = resolve_section_indices(sections, spec, case_sensitive=False)
    groups = [[sections[i].heading, *sections[i].content] for i in indices]
    return _join_groups(groups)


def _figure_groups(figures: list[Image], indices: list[int]) -> list[list[Node]]:
    """Wrap selected inline images in paragraphs so they render at block level."""
    return [[Paragraph(content=[figures[i]])] for i in indices]


def _truncate_words(nodes: list[Node], limit: int) -> list[Node]:
    """Keep whole nodes until ``limit`` words are reached (never splits a node).

    Always returns at least the first node so a selector never yields nothing
    just because its opening node already exceeds the budget.
    """
    kept: list[Node] = []
    used = 0
    for node in nodes:
        if used >= limit:
            break
        kept.append(node)
        used += len(extract_text(node).split())
    return kept or nodes[:1]


def selector_nodes(doc: Document, selector: ExtractSelector) -> list[Node]:
    """Resolve a single selector to its node sequence (before word-limit trimming)."""
    if selector.kind == "section":
        return _section_nodes(doc, selector.spec)

    if selector.kind == "table":
        tables = collect_tables(doc)
        indices = _resolve_indexed(len(tables), selector.spec, "table")
        return _join_groups([[tables[i]] for i in indices])

    figures = collect_figures(doc)
    indices = _resolve_indexed(len(figures), selector.spec, "figure")
    return _join_groups(_figure_groups(figures, indices))


def build_extracted_document(doc: Document, raw_specs: list[str]) -> Document:
    """Build a document from one or more ``--extract`` selectors, in spec order.

    Each selector's output is appended in the order the selectors were given,
    separated by a :class:`ThematicBreak`. Word limits are applied per selector.

    Parameters
    ----------
    doc : Document
        Source document.
    raw_specs : list of str
        Raw ``--extract`` selector strings (excluding ``line:`` ranges).

    Returns
    -------
    Document
        New document containing the selected content.

    Raises
    ------
    ValueError
        If a selector is malformed or matches nothing.

    """
    selectors = [parse_extract_selector(raw) for raw in raw_specs]

    parts: list[list[Node]] = []
    for selector in selectors:
        nodes = selector_nodes(doc, selector)
        if selector.word_limit is not None:
            nodes = _truncate_words(nodes, selector.word_limit)
        if nodes:
            parts.append(nodes)

    if not parts:
        raise ValueError("No content matched the --extract selector(s)")

    children = _join_groups(parts)
    return Document(children=children, metadata=doc.metadata.copy(), source_location=doc.source_location)


__all__ = [
    "ExtractSelector",
    "WORD_LIMIT_SEP",
    "parse_extract_selector",
    "collect_tables",
    "collect_figures",
    "selector_nodes",
    "build_extracted_document",
]
