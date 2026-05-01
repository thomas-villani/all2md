"""Typography rules (TYP001-TYP008).

Low-level text hygiene: trailing spaces, multiple spaces, straight quotes,
double-hyphens that should be em-dashes, inconsistent list marker styles
(adjacent sibling lists with mismatched ordered/unordered types), ellipsis
character, space-before-punctuation, and consecutive punctuation.

Most TYP rules carry a SAFE auto-fix that mutates ``Text.content``
in place — see :mod:`all2md.linter.fixes`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable, Iterator

from all2md.ast import Document, List, Node, NodeCollector, Text, get_node_children
from all2md.linter.fixes import FixSafety, LintFix
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

if TYPE_CHECKING:
    from all2md.linter.fixes import FixContext

_MULTIPLE_SPACES_RE = re.compile(r"\S[ \t]{2,}\S")
_MULTIPLE_SPACES_FIX_RE = re.compile(r"[ \t]{2,}")
_STRAIGHT_QUOTE_WORD_RE = re.compile(r"[\"']([A-Za-z][^\"']*)[\"']")
_STRAIGHT_QUOTE_DOUBLE_FIX_RE = re.compile(r"\"([A-Za-z][^\"]*)\"")
_STRAIGHT_QUOTE_SINGLE_FIX_RE = re.compile(r"(?<![A-Za-z])'([A-Za-z][^']*)'(?![A-Za-z])")
_DOUBLE_HYPHEN_RE = re.compile(r"(?<!-)--(?!-)")
_ELLIPSIS_RE = re.compile(r"(?<!\.)\.{3}(?!\.)")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([,.;:!?])")
_CONSECUTIVE_PUNCT_RE = re.compile(r"([,!?])\1+")


def _line(node: Node) -> int | None:
    return node.source_location.line if node.source_location else None


def _column(node: Node) -> int | None:
    return node.source_location.column if node.source_location else None


def _collect_text_nodes(doc: Document) -> list[Text]:
    collector = NodeCollector(lambda n: isinstance(n, Text))
    doc.accept(collector)
    return [n for n in collector.collected if isinstance(n, Text)]


# ---------------------------------------------------------------------------
# Pure-string fix helpers (idempotent: applying twice is the same as once).
# ---------------------------------------------------------------------------


def _strip_trailing(s: str) -> str:
    return s.rstrip(" \t")


def _collapse_spaces(s: str) -> str:
    return _MULTIPLE_SPACES_FIX_RE.sub(" ", s)


def _curly_quotes(s: str) -> str:
    s = _STRAIGHT_QUOTE_DOUBLE_FIX_RE.sub("“\\1”", s)
    s = _STRAIGHT_QUOTE_SINGLE_FIX_RE.sub("‘\\1’", s)
    return s


def _double_hyphens(s: str) -> str:
    return _DOUBLE_HYPHEN_RE.sub("—", s)


def _ellipsis(s: str) -> str:
    return _ELLIPSIS_RE.sub("…", s)


def _strip_space_before_punct(s: str) -> str:
    return _SPACE_BEFORE_PUNCT_RE.sub(r"\1", s)


def _safe_text_fix(node: Text, transform: Callable[[str], str]) -> Callable[["FixContext"], None]:
    """Build a SAFE LintFix apply-callback that rewrites ``node.content`` via ``transform``."""

    def _apply(_fctx: "FixContext", n: Text = node, t: Callable[[str], str] = transform) -> None:
        n.content = t(n.content)

    return _apply


class TrailingSpacesRule(LintRule):
    """TYP001: Flag Text nodes that end with whitespace when they're the last child of their parent."""

    code = "TYP001"
    name = "trailing-spaces"
    category = "typography"
    description = "Text should not end with trailing whitespace."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each trailing-whitespace Text at the end of a container."""
        violations: list[Violation] = []
        for text in _iter_last_text_children(ctx.document):
            content = text.content
            if content and (content.endswith(" ") or content.endswith("\t")):
                stripped = content.rstrip(" \t")
                violations.append(
                    self.build_violation(
                        message="Text content has trailing whitespace",
                        line=_line(text),
                        column=_column(text),
                        node_type="Text",
                        suggestion="Strip trailing whitespace",
                        context=stripped[-80:] or None,
                        fix=LintFix(
                            target=text,
                            apply=_safe_text_fix(text, _strip_trailing),
                            safety=FixSafety.SAFE,
                            description="Strip trailing whitespace",
                        ),
                    )
                )
        return violations


def _iter_last_text_children(doc: Document) -> Iterator[Text]:
    """Yield every :class:`Text` node that is the last child of its parent.

    A Text that precedes another inline element (``"Read the "`` before a
    link) naturally contains a trailing space — flagging those is noise.
    Only Text nodes at the end of their container reliably indicate a
    trailing-whitespace issue the author can act on.
    """
    from all2md.ast import Node as _Node

    def walk(node: _Node) -> Iterator[Text]:
        children = get_node_children(node)
        if children:
            last = children[-1]
            if isinstance(last, Text):
                yield last
            for child in children:
                yield from walk(child)

    yield from walk(doc)


class MultipleSpacesRule(LintRule):
    """TYP002: Flag Text nodes containing runs of consecutive spaces."""

    code = "TYP002"
    name = "multiple-spaces"
    category = "typography"
    description = "Text should not contain multiple consecutive spaces."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each Text containing two or more consecutive spaces."""
        violations: list[Violation] = []
        for text in _collect_text_nodes(ctx.document):
            content = text.content
            if not content:
                continue
            if _MULTIPLE_SPACES_RE.search(content):
                violations.append(
                    self.build_violation(
                        message="Text contains multiple consecutive spaces",
                        line=_line(text),
                        column=_column(text),
                        node_type="Text",
                        suggestion="Collapse runs of spaces to a single space",
                        context=content[:80],
                        fix=LintFix(
                            target=text,
                            apply=_safe_text_fix(text, _collapse_spaces),
                            safety=FixSafety.SAFE,
                            description="Collapse runs of spaces",
                        ),
                    )
                )
        return violations


class StraightQuotesRule(LintRule):
    """TYP003: Flag Text that uses straight ASCII quotes around a word."""

    code = "TYP003"
    name = "straight-quotes"
    category = "typography"
    description = "Prefer curly quotes (“”‘’) over straight quotes."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each Text containing quoted words using straight quotes."""
        violations: list[Violation] = []
        for text in _collect_text_nodes(ctx.document):
            content = text.content
            if not content:
                continue
            if _STRAIGHT_QUOTE_WORD_RE.search(content):
                violations.append(
                    self.build_violation(
                        message="Text uses straight quotes around a word",
                        line=_line(text),
                        column=_column(text),
                        node_type="Text",
                        suggestion="Replace with curly quotes (“” or ‘’)",
                        context=content[:80],
                        fix=LintFix(
                            target=text,
                            apply=_safe_text_fix(text, _curly_quotes),
                            safety=FixSafety.SAFE,
                            description="Replace straight quotes with curly quotes",
                        ),
                    )
                )
        return violations


class DoubleHyphensRule(LintRule):
    """TYP004: Flag Text containing ``--`` that should be an em-dash."""

    code = "TYP004"
    name = "double-hyphens"
    category = "typography"
    description = "Prefer em-dashes (—) over double hyphens."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each Text containing a double-hyphen sequence."""
        violations: list[Violation] = []
        for text in _collect_text_nodes(ctx.document):
            content = text.content
            if not content:
                continue
            if _DOUBLE_HYPHEN_RE.search(content):
                violations.append(
                    self.build_violation(
                        message="Text contains '--' (should be em-dash)",
                        line=_line(text),
                        column=_column(text),
                        node_type="Text",
                        suggestion="Replace '--' with an em-dash (—)",
                        context=content[:80],
                        fix=LintFix(
                            target=text,
                            apply=_safe_text_fix(text, _double_hyphens),
                            safety=FixSafety.SAFE,
                            description="Replace -- with em-dash",
                        ),
                    )
                )
        return violations


class MixedListMarkersRule(LintRule):
    """TYP005: Flag adjacent sibling lists that disagree on ordered vs unordered style."""

    code = "TYP005"
    name = "mixed-list-markers"
    category = "typography"
    description = "Adjacent sibling lists should share the same ordered/unordered style."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each list immediately following a sibling list of the opposite kind."""
        violations: list[Violation] = []
        self._walk(ctx.document, violations)
        return violations

    def _walk(self, node: Node, violations: list[Violation]) -> None:
        children = get_node_children(node)
        prev_list: List | None = None
        for child in children:
            if isinstance(child, List):
                if prev_list is not None and prev_list.ordered != child.ordered:
                    kind = "ordered" if child.ordered else "unordered"
                    prev_kind = "ordered" if prev_list.ordered else "unordered"
                    violations.append(
                        self.build_violation(
                            message=(f"Adjacent {kind} list follows {prev_kind} list — mixed marker styles"),
                            line=_line(child),
                            column=_column(child),
                            node_type="List",
                            suggestion="Use the same list type for adjacent lists or separate them with content",
                        )
                    )
                prev_list = child
            else:
                prev_list = None
            self._walk(child, violations)


class EllipsisCharacterRule(LintRule):
    """TYP006: Flag Text containing ``...`` instead of the ellipsis character."""

    code = "TYP006"
    name = "ellipsis-character"
    category = "typography"
    description = "Prefer the ellipsis character (…) over three periods."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each Text containing ``...`` (but not ``....``)."""
        violations: list[Violation] = []
        for text in _collect_text_nodes(ctx.document):
            content = text.content
            if not content:
                continue
            if _ELLIPSIS_RE.search(content):
                violations.append(
                    self.build_violation(
                        message="Text contains '...' (should be ellipsis character)",
                        line=_line(text),
                        column=_column(text),
                        node_type="Text",
                        suggestion="Replace '...' with '…'",
                        context=content[:80],
                        fix=LintFix(
                            target=text,
                            apply=_safe_text_fix(text, _ellipsis),
                            safety=FixSafety.SAFE,
                            description="Replace ... with ellipsis character",
                        ),
                    )
                )
        return violations


class SpaceBeforePunctuationRule(LintRule):
    """TYP007: Flag Text containing whitespace immediately before sentence punctuation."""

    code = "TYP007"
    name = "space-before-punctuation"
    category = "typography"
    description = "Punctuation should not be preceded by whitespace."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each Text where ``,.;:!?`` is preceded by a space."""
        violations: list[Violation] = []
        for text in _collect_text_nodes(ctx.document):
            content = text.content
            if not content:
                continue
            if _SPACE_BEFORE_PUNCT_RE.search(content):
                violations.append(
                    self.build_violation(
                        message="Text has whitespace before punctuation",
                        line=_line(text),
                        column=_column(text),
                        node_type="Text",
                        suggestion="Remove the space before the punctuation",
                        context=content[:80],
                        fix=LintFix(
                            target=text,
                            apply=_safe_text_fix(text, _strip_space_before_punct),
                            safety=FixSafety.SAFE,
                            description="Remove space before punctuation",
                        ),
                    )
                )
        return violations


class ConsecutivePunctuationRule(LintRule):
    """TYP008: Flag Text containing repeated punctuation like ``,,`` or ``!!``.

    Detects only ``,``, ``!``, and ``?`` repeats. ``..``/``...`` overlap with
    TYP006 (ellipsis) and are intentionally excluded — TYP006 already covers
    them. Repeats are not auto-fixed because the right replacement (collapse
    to one character vs. ellipsis vs. interrobang ``?!``) is reader judgement.
    """

    code = "TYP008"
    name = "consecutive-punctuation"
    category = "typography"
    description = "Punctuation should not be repeated (',,', '!!', '??', etc.)."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each Text containing a repeated punctuation mark."""
        violations: list[Violation] = []
        for text in _collect_text_nodes(ctx.document):
            content = text.content
            if not content:
                continue
            match = _CONSECUTIVE_PUNCT_RE.search(content)
            if match:
                violations.append(
                    self.build_violation(
                        message=f"Text contains repeated punctuation: {match.group(0)!r}",
                        line=_line(text),
                        column=_column(text),
                        node_type="Text",
                        suggestion="Reduce to a single punctuation mark or rewrite",
                        context=content[:80],
                    )
                )
        return violations


for _rule_cls in (
    TrailingSpacesRule,
    MultipleSpacesRule,
    StraightQuotesRule,
    DoubleHyphensRule,
    MixedListMarkersRule,
    EllipsisCharacterRule,
    SpaceBeforePunctuationRule,
    ConsecutivePunctuationRule,
):
    rule_registry.register(_rule_cls)
