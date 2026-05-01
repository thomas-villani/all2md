"""Auto-fix framework for the linter.

A fix is a closure attached to a :class:`Violation`. The rule's ``check()``
captures the offending AST node and emits a :class:`Violation` whose
``fix`` field carries a :class:`LintFix` — the framework calls
``LintFix.apply`` to mutate the captured node in place. There is no second
``fix()`` method on :class:`LintRule`, so ``check`` and ``fix`` cannot drift.

Most fixes mutate ``Text.content`` and never touch :class:`FixContext`.
Structural fixes (e.g. removing an empty heading) call
``fctx.remove(node)`` to detach a node from its parent — the framework
handles the parent lookup lazily.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Callable, Optional

from all2md.ast import (
    BlockQuote,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    Heading,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Underline,
    get_node_children,
)

if TYPE_CHECKING:
    from all2md.linter.violations import Violation

logger = logging.getLogger(__name__)


class FixSafety(IntEnum):
    """Safety classification for an auto-fix.

    Lower numeric value means safer / less invasive. ``apply_fixes`` uses
    ``<= max_safety`` to decide which fixes to apply, so ``SAFE`` fixes
    run under both ``--fix`` and ``--fix-unsafe`` while ``SUGGESTED`` fixes
    run only under ``--fix-unsafe``.
    """

    SAFE = 1
    SUGGESTED = 2
    MANUAL = 3

    @property
    def label(self) -> str:
        """Lowercase label suitable for human output ('safe', 'suggested', 'manual')."""
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class LintFix:
    """A fix attached to a :class:`Violation`.

    Parameters
    ----------
    target : Node
        The AST node this fix mutates or removes. Used for conflict
        detection (two fixes targeting the same node — the first one wins).
    apply : Callable[[FixContext], None]
        In-place mutation of the AST. For text mutations the callback
        usually closes over ``target`` and rewrites ``target.content``.
        For structural fixes the callback uses ``ctx.remove(target)`` or
        ``ctx.replace(old, new)``.
    safety : FixSafety
        How aggressively to apply this fix.
    description : str
        Short human-readable description of what the fix does, for
        reporters and logs.

    """

    target: Node
    apply: Callable[["FixContext"], None]
    safety: FixSafety
    description: str = ""


@dataclass
class AppliedFix:
    """Record of a fix that was (or would have been) applied."""

    rule_code: str
    line: Optional[int]
    description: str
    safety: FixSafety

    def to_dict(self) -> dict:
        """Serialise to a plain dict for the JSON reporter."""
        return {
            "rule_code": self.rule_code,
            "line": self.line,
            "description": self.description,
            "safety": self.safety.label,
        }


class FixContext:
    """Mutation primitives passed to :class:`LintFix.apply`.

    The parent map is built lazily on first use, so fixes that only
    mutate ``Text.content`` never pay for it.
    """

    def __init__(self, document: Document) -> None:
        """Initialise a context for ``document``.

        The parent map is not built until the first call to
        :meth:`parent_of`, :meth:`remove`, or :meth:`replace`.
        """
        self.document = document
        self._parent_map: Optional[dict[int, Node]] = None

    def _ensure_parent_map(self) -> None:
        if self._parent_map is None:
            self._parent_map = _build_parent_map(self.document)

    def parent_of(self, node: Node) -> Optional[Node]:
        """Return the parent of ``node`` in this context's document, or ``None``."""
        self._ensure_parent_map()
        assert self._parent_map is not None
        return self._parent_map.get(id(node))

    def remove(self, node: Node) -> bool:
        """Detach ``node`` from its parent.

        Returns ``True`` on success, ``False`` if the node has no parent
        or the parent's container does not hold it (e.g. the node has
        already been detached by an earlier fix in the same run).
        """
        parent = self.parent_of(node)
        if parent is None:
            return False
        ok = _remove_child(parent, node)
        if ok and self._parent_map is not None:
            self._parent_map.pop(id(node), None)
        return ok

    def replace(self, old: Node, new: Node) -> bool:
        """Replace ``old`` with ``new`` in its parent's container.

        Returns ``True`` on success. Plumbed for future structural fixes;
        none of the v2.0 SAFE fixes use it.
        """
        parent = self.parent_of(old)
        if parent is None:
            return False
        ok = _replace_child(parent, old, new)
        if ok and self._parent_map is not None:
            self._parent_map.pop(id(old), None)
            self._parent_map[id(new)] = parent
        return ok


def _build_parent_map(doc: Document) -> dict[int, Node]:
    """Walk ``doc`` and return a map from ``id(child)`` to the child's parent."""
    pm: dict[int, Node] = {}

    def walk(node: Node) -> None:
        for child in get_node_children(node):
            pm[id(child)] = node
            walk(child)

    walk(doc)
    return pm


# Containers whose children live in ``.children``.
_CHILDREN_CONTAINERS = (Document, BlockQuote, ListItem)
# Containers whose children live in ``.content`` (a list of inline/block nodes).
_CONTENT_CONTAINERS = (
    Heading,
    Paragraph,
    Emphasis,
    Strong,
    Strikethrough,
    Underline,
    Superscript,
    Subscript,
    Link,
    TableCell,
    DefinitionTerm,
    DefinitionDescription,
    FootnoteDefinition,
)


def _remove_child(parent: Node, child: Node) -> bool:
    """Detach ``child`` from ``parent`` by mirroring :func:`get_node_children`.

    Returns ``True`` on success.
    """
    if isinstance(parent, _CHILDREN_CONTAINERS):
        return _list_remove_identity(parent.children, child)
    if isinstance(parent, _CONTENT_CONTAINERS):
        return _list_remove_identity(parent.content, child)
    if isinstance(parent, List):
        return _list_remove_identity(parent.items, child)
    if isinstance(parent, Table):
        if parent.header is child:
            parent.header = None
            return True
        return _list_remove_identity(parent.rows, child)
    if isinstance(parent, TableRow):
        return _list_remove_identity(parent.cells, child)
    if isinstance(parent, DefinitionList):
        for idx, (term, descs) in enumerate(parent.items):
            if term is child:
                del parent.items[idx]
                return True
            if any(d is child for d in descs):
                parent.items[idx] = (term, [d for d in descs if d is not child])
                return True
        return False
    return False


def _replace_child(parent: Node, old: Node, new: Node) -> bool:
    """Replace ``old`` with ``new`` in ``parent``'s container."""
    if isinstance(parent, _CHILDREN_CONTAINERS):
        return _list_replace_identity(parent.children, old, new)
    if isinstance(parent, _CONTENT_CONTAINERS):
        return _list_replace_identity(parent.content, old, new)
    if isinstance(parent, List) and isinstance(new, ListItem):
        return _list_replace_identity(parent.items, old, new)
    if isinstance(parent, Table):
        if parent.header is old and isinstance(new, TableRow):
            parent.header = new
            return True
        if isinstance(new, TableRow):
            return _list_replace_identity(parent.rows, old, new)
        return False
    if isinstance(parent, TableRow) and isinstance(new, TableCell):
        return _list_replace_identity(parent.cells, old, new)
    return False


def _list_remove_identity(seq: list, target: Node) -> bool:
    """Remove the first element ``x`` of ``seq`` for which ``x is target``."""
    for idx, item in enumerate(seq):
        if item is target:
            del seq[idx]
            return True
    return False


def _list_replace_identity(seq: list, old: Node, new: Node) -> bool:
    """Replace the first element ``x`` of ``seq`` for which ``x is old`` with ``new``."""
    for idx, item in enumerate(seq):
        if item is old:
            seq[idx] = new
            return True
    return False


def _node_depth(parent_map: dict[int, Node], node: Node) -> int:
    """Return the depth of ``node`` in the document tree (root is 0)."""
    depth = 0
    cursor: Optional[Node] = parent_map.get(id(node))
    while cursor is not None:
        depth += 1
        cursor = parent_map.get(id(cursor))
    return depth


def apply_fixes(
    doc: Document,
    violations: list["Violation"],
    max_safety: FixSafety,
) -> tuple[list[AppliedFix], list[AppliedFix]]:
    """Apply every fix attached to ``violations`` whose safety is ``<= max_safety``.

    Conflict policy: when two fixes target the same node (by ``id()``),
    the first one (in deterministic outer-to-inner, top-to-bottom order)
    is applied; subsequent fixes targeting that node are deferred and
    returned in ``skipped_conflicts``. Users re-run ``--fix`` to converge.

    Returns
    -------
    (applied, skipped_conflicts)
        Two lists of :class:`AppliedFix` records — the first describes
        fixes that ran, the second describes fixes that were deferred
        because an earlier fix already touched their target.

    """
    fctx = FixContext(doc)
    parent_map = _build_parent_map(doc)
    fctx._parent_map = parent_map  # share the eagerly-built map; saves rebuilds

    candidates = [v for v in violations if v.fix is not None and v.fix.safety <= max_safety]
    candidates.sort(
        key=lambda v: (
            _node_depth(parent_map, v.fix.target) if v.fix else 0,
            v.line if v.line is not None else 0,
            v.column if v.column is not None else 0,
            v.rule_code,
        )
    )

    touched: set[int] = set()
    applied: list[AppliedFix] = []
    skipped: list[AppliedFix] = []
    for v in candidates:
        fix = v.fix
        assert fix is not None  # filtered above
        record = AppliedFix(
            rule_code=v.rule_code,
            line=v.line,
            description=fix.description,
            safety=fix.safety,
        )
        if id(fix.target) in touched:
            skipped.append(record)
            continue
        try:
            fix.apply(fctx)
        except Exception:
            logger.exception("Fix for %s failed", v.rule_code)
            continue
        touched.add(id(fix.target))
        applied.append(record)
    return applied, skipped
