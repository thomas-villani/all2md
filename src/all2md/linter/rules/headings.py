"""Heading content rules (HDG001-HDG007).

Checks the text of each heading: punctuation, length, duplication,
capitalization consistency, emphasis-wrapped headings, sentence-shaped
headings, and URLs in heading text.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from all2md.ast import Document, Emphasis, Heading, NodeCollector, Strong, extract_text
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

_DEFAULT_MAX_HEADING_LENGTH = 80
_DEFAULT_HEADING_SENTENCE_MAX_WORDS = 12
_TRAILING_PUNCTUATION = ".,;:"
_HEADING_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _collect_headings(doc: Document) -> list[Heading]:
    collector = NodeCollector(lambda n: isinstance(n, Heading))
    doc.accept(collector)
    return [n for n in collector.collected if isinstance(n, Heading)]


def _heading_text(heading: Heading) -> str:
    raw = extract_text(heading, joiner="")
    return " ".join(raw.split())


def _line(h: Heading) -> int | None:
    return h.source_location.line if h.source_location else None


def _column(h: Heading) -> int | None:
    return h.source_location.column if h.source_location else None


def _classify_capitalization(text: str) -> str:
    """Return 'all-caps', 'title-case', 'sentence', or 'other'.

    Single-word headings cannot reliably distinguish title-case from
    sentence case, so they are classified as 'other' and do not
    contribute to the majority vote in :class:`HeadingCapitalizationRule`.
    """
    words = [w for w in text.split() if any(c.isalpha() for c in w)]
    if not words:
        return "other"
    letters = [c for c in text if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len([c for c in text if c.isalpha()]) >= 2:
        return "all-caps"
    significant = [w for w in words if len(w) > 1]
    if len(significant) < 2:
        return "other"
    first_cap = significant[0][0].isupper()
    if first_cap and all(w[0].islower() for w in significant[1:]):
        return "sentence"
    title_count = sum(1 for w in significant if w[0].isupper())
    if title_count >= max(2, len(significant) - 1):
        return "title-case"
    return "other"


class HeadingTrailingPunctuationRule(LintRule):
    """HDG001: Flag headings that end with sentence-style punctuation."""

    code = "HDG001"
    name = "heading-trailing-punctuation"
    category = "headings"
    description = "Headings should not end with sentence-ending punctuation."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each heading ending in '.', ',', ';', or ':'."""
        violations: list[Violation] = []
        for heading in _collect_headings(ctx.document):
            text = _heading_text(heading)
            if text and text[-1] in _TRAILING_PUNCTUATION:
                violations.append(
                    self.build_violation(
                        message=f"Heading ends with {text[-1]!r}: {text!r}",
                        line=_line(heading),
                        column=_column(heading),
                        node_type="Heading",
                        suggestion=f"Remove the trailing {text[-1]!r}",
                        context=text[:80] or None,
                    )
                )
        return violations


class HeadingLengthRule(LintRule):
    """HDG002: Flag headings longer than a configurable character limit (default 80)."""

    code = "HDG002"
    name = "heading-length"
    category = "headings"
    description = "Headings should not exceed a configurable maximum length."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each heading exceeding ``max_length``."""
        max_length = _coerce_positive_int(
            ctx.config.get("max_length", _DEFAULT_MAX_HEADING_LENGTH),
            default=_DEFAULT_MAX_HEADING_LENGTH,
        )
        violations: list[Violation] = []
        for heading in _collect_headings(ctx.document):
            text = _heading_text(heading)
            if len(text) > max_length:
                violations.append(
                    self.build_violation(
                        message=f"Heading is {len(text)} characters (max {max_length})",
                        line=_line(heading),
                        column=_column(heading),
                        node_type="Heading",
                        suggestion="Shorten the heading or split it into sub-sections",
                        context=text[:80],
                    )
                )
        return violations


class DuplicateHeadingsRule(LintRule):
    """HDG003: Flag same-level headings with identical (case-insensitive) text."""

    code = "HDG003"
    name = "duplicate-headings"
    category = "headings"
    description = "Headings at the same level should not have duplicate text."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each duplicate occurrence after the first."""
        seen: dict[tuple[int, str], Heading] = {}
        violations: list[Violation] = []
        for heading in _collect_headings(ctx.document):
            text = _heading_text(heading).lower()
            if not text:
                continue
            key = (heading.level, text)
            if key in seen:
                violations.append(
                    self.build_violation(
                        message=f"Duplicate H{heading.level} heading: {text!r}",
                        line=_line(heading),
                        column=_column(heading),
                        node_type="Heading",
                        suggestion="Rename one of the duplicates to disambiguate",
                        context=text[:80] or None,
                    )
                )
            else:
                seen[key] = heading
        return violations


class HeadingCapitalizationRule(LintRule):
    """HDG004: Flag headings at the same level that diverge from the dominant capitalization style."""

    code = "HDG004"
    name = "heading-capitalization"
    category = "headings"
    description = "Headings at the same level should share a capitalization style."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each heading whose style doesn't match the majority at its level."""
        per_level: dict[int, list[tuple[Heading, str, str]]] = defaultdict(list)
        for heading in _collect_headings(ctx.document):
            text = _heading_text(heading)
            if not text:
                continue
            per_level[heading.level].append((heading, text, _classify_capitalization(text)))

        violations: list[Violation] = []
        for level, entries in per_level.items():
            styles = {style for _, _, style in entries if style != "other"}
            if len(styles) <= 1:
                continue
            # Majority style wins; flag outliers.
            counts: dict[str, int] = defaultdict(int)
            for _, _, style in entries:
                counts[style] += 1
            majority = max(counts.items(), key=lambda kv: kv[1])[0]
            for heading, text, style in entries:
                if style == majority or style == "other":
                    continue
                violations.append(
                    self.build_violation(
                        message=(
                            f"H{level} heading uses {style!r} but the dominant style at this level is "
                            f"{majority!r}: {text!r}"
                        ),
                        line=_line(heading),
                        column=_column(heading),
                        node_type="Heading",
                        suggestion=f"Rewrite to match {majority} style",
                        context=text[:80],
                    )
                )
        return violations


class HeadingEmphasisRule(LintRule):
    """HDG005: Flag headings whose content is a single Strong or Emphasis node."""

    code = "HDG005"
    name = "heading-emphasis"
    category = "headings"
    description = "Headings should not be wrapped entirely in emphasis or strong markup."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each heading wrapped entirely in emphasis."""
        violations: list[Violation] = []
        for heading in _collect_headings(ctx.document):
            if len(heading.content) != 1:
                continue
            only = heading.content[0]
            if isinstance(only, (Strong, Emphasis)):
                wrapper = type(only).__name__
                text = _heading_text(heading)
                violations.append(
                    self.build_violation(
                        message=f"Heading is wrapped entirely in {wrapper}",
                        line=_line(heading),
                        column=_column(heading),
                        node_type="Heading",
                        suggestion="Remove the wrapping emphasis — the heading level already conveys importance",
                        context=text[:80] or None,
                    )
                )
        return violations


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


class HeadingAsSentenceRule(LintRule):
    """HDG006: Flag headings that read like a full sentence.

    A heading is sentence-shaped if it both (a) has more words than the
    configured threshold (default 12), and (b) ends with a sentence-final
    punctuation mark (``.``, ``!``, ``?``). Either alone is unreliable —
    short imperative headings sometimes end with ``!``, and long noun
    phrases without punctuation are perfectly valid headings.
    """

    code = "HDG006"
    name = "heading-as-sentence"
    category = "headings"
    description = "Headings should not read like full sentences."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each heading that looks like a sentence."""
        max_words = _coerce_positive_int(
            ctx.config.get("max_words", _DEFAULT_HEADING_SENTENCE_MAX_WORDS),
            default=_DEFAULT_HEADING_SENTENCE_MAX_WORDS,
        )
        violations: list[Violation] = []
        for heading in _collect_headings(ctx.document):
            text = _heading_text(heading)
            if not text:
                continue
            words = text.split()
            ends_in_sentence_punct = text[-1] in ".!?"
            if len(words) > max_words and ends_in_sentence_punct:
                violations.append(
                    self.build_violation(
                        message=(
                            f"Heading reads like a sentence ({len(words)} words ending in {text[-1]!r}): {text!r}"
                        ),
                        line=_line(heading),
                        column=_column(heading),
                        node_type="Heading",
                        suggestion="Rewrite as a noun phrase or split into multiple headings",
                        context=text[:80] or None,
                    )
                )
        return violations


class HeadingUrlRule(LintRule):
    """HDG007: Flag headings whose text contains a URL."""

    code = "HDG007"
    name = "heading-url"
    category = "headings"
    description = "Headings should not contain raw URLs."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each heading whose plain text contains a URL."""
        violations: list[Violation] = []
        for heading in _collect_headings(ctx.document):
            text = _heading_text(heading)
            match = _HEADING_URL_RE.search(text)
            if match:
                violations.append(
                    self.build_violation(
                        message=f"Heading contains a URL: {match.group(0)!r}",
                        line=_line(heading),
                        column=_column(heading),
                        node_type="Heading",
                        suggestion="Move the URL out of the heading and into the section body",
                        context=text[:80] or None,
                    )
                )
        return violations


for _rule_cls in (
    HeadingTrailingPunctuationRule,
    HeadingLengthRule,
    DuplicateHeadingsRule,
    HeadingCapitalizationRule,
    HeadingEmphasisRule,
    HeadingAsSentenceRule,
    HeadingUrlRule,
):
    rule_registry.register(_rule_cls)
