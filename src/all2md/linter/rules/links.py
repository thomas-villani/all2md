"""Link rules (LNK001-LNK007).

Checks link structure (empty text, missing URLs), duplicated URLs, bare URLs
in plain text, low-quality link labels like "click here", insecure ``http://``
links, and links whose text is the raw URL.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterator

from all2md.ast import Document, Link, Node, NodeCollector, Text, extract_text
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

_GENERIC_LINK_TEXTS = frozenset(
    {
        "click here",
        "click",
        "here",
        "link",
        "this",
        "this link",
        "read more",
        "more",
    }
)

_URL_RE = re.compile(r"(?<![\w/@])https?://\S+", re.IGNORECASE)


def _collect_links(doc: Document) -> list[Link]:
    collector = NodeCollector(lambda n: isinstance(n, Link))
    doc.accept(collector)
    return [n for n in collector.collected if isinstance(n, Link)]


def _link_text(link: Link) -> str:
    return " ".join(extract_text(link.content, joiner="").split())


def _line(node: Node) -> int | None:
    return node.source_location.line if node.source_location else None


def _column(node: Node) -> int | None:
    return node.source_location.column if node.source_location else None


class EmptyLinkTextRule(LintRule):
    """LNK001: Flag links whose visible text is empty."""

    code = "LNK001"
    name = "empty-link-text"
    category = "links"
    description = "Links must have visible text describing their destination."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each link with empty text."""
        violations: list[Violation] = []
        for link in _collect_links(ctx.document):
            if _link_text(link):
                continue
            violations.append(
                self.build_violation(
                    message=f"Link to {link.url!r} has no visible text",
                    line=_line(link),
                    column=_column(link),
                    node_type="Link",
                    suggestion="Add descriptive text for the link",
                )
            )
        return violations


class MissingUrlRule(LintRule):
    """LNK002: Flag links with empty or whitespace-only URLs."""

    code = "LNK002"
    name = "missing-url"
    category = "links"
    description = "Links must have a non-empty URL."
    default_severity = Severity.ERROR

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each link with a blank URL."""
        violations: list[Violation] = []
        for link in _collect_links(ctx.document):
            if link.url and link.url.strip():
                continue
            text = _link_text(link) or "<empty>"
            violations.append(
                self.build_violation(
                    message=f"Link {text!r} has an empty URL",
                    line=_line(link),
                    column=_column(link),
                    node_type="Link",
                    suggestion="Set the link URL or remove the link",
                    context=text[:80],
                )
            )
        return violations


class DuplicateUrlsRule(LintRule):
    """LNK003: Flag URLs linked from more than one place in the document."""

    code = "LNK003"
    name = "duplicate-urls"
    category = "links"
    description = "The same URL should typically only be linked once."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each repeated link to the same URL."""
        buckets: dict[str, list[Link]] = defaultdict(list)
        for link in _collect_links(ctx.document):
            if link.url and link.url.strip():
                buckets[link.url.strip()].append(link)

        violations: list[Violation] = []
        for url, links in buckets.items():
            if len(links) < 2:
                continue
            for extra in links[1:]:
                text = _link_text(extra) or "<empty>"
                violations.append(
                    self.build_violation(
                        message=f"Duplicate link to {url!r} ({len(links)} total occurrences)",
                        line=_line(extra),
                        column=_column(extra),
                        node_type="Link",
                        suggestion="Consider reusing a reference-style link or consolidating references",
                        context=text[:80],
                    )
                )
        return violations


class BareUrlRule(LintRule):
    """LNK004: Flag raw URLs that appear in prose instead of being wrapped in a Link."""

    code = "LNK004"
    name = "bare-url"
    category = "links"
    description = "Raw URLs should be wrapped in link syntax."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each unwrapped URL found in Text content."""
        violations: list[Violation] = []
        for text_node, _parent_is_link in _iter_text_nodes(ctx.document):
            if _parent_is_link:
                continue
            content = text_node.content
            if not content:
                continue
            for match in _URL_RE.finditer(content):
                url = match.group(0).rstrip(".,;:)")
                violations.append(
                    self.build_violation(
                        message=f"Bare URL in text: {url!r}",
                        line=_line(text_node),
                        column=_column(text_node),
                        node_type="Text",
                        suggestion=f"Wrap the URL in a link: [text]({url})",
                        context=content[:80],
                    )
                )
        return violations


class LinkTextQualityRule(LintRule):
    """LNK005: Flag links whose text is a low-quality filler phrase like 'click here'."""

    code = "LNK005"
    name = "link-text-quality"
    category = "links"
    description = "Link text should describe the destination, not use generic phrases like 'click here'."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each link whose text is in the generic-phrases list."""
        violations: list[Violation] = []
        for link in _collect_links(ctx.document):
            text = _link_text(link).lower().strip()
            if not text:
                continue
            if text in _GENERIC_LINK_TEXTS:
                violations.append(
                    self.build_violation(
                        message=f"Low-quality link text: {text!r}",
                        line=_line(link),
                        column=_column(link),
                        node_type="Link",
                        suggestion="Use descriptive link text that names the destination",
                        context=text[:80],
                    )
                )
        return violations


def _iter_text_nodes(doc: Document) -> Iterator[tuple[Text, bool]]:
    """Yield ``(Text, parent_is_link)`` for every Text node in the document."""
    from all2md.ast import get_node_children

    def walk(node: Node, inside_link: bool) -> Iterator[tuple[Text, bool]]:
        if isinstance(node, Text):
            yield node, inside_link
            return
        is_link = inside_link or isinstance(node, Link)
        for child in get_node_children(node):
            yield from walk(child, is_link)

    yield from walk(doc, False)


class InsecureLinkRule(LintRule):
    """LNK006: Flag links that use ``http://`` instead of ``https://``.

    No auto-fix in v2.0 — blindly upgrading to HTTPS can break a fraction
    of legitimate hosts. The lint output points the user at the link;
    they decide whether to upgrade.
    """

    code = "LNK006"
    name = "insecure-link"
    category = "links"
    description = "Links should use HTTPS where possible."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each ``http://`` Link URL."""
        violations: list[Violation] = []
        for link in _collect_links(ctx.document):
            url = (link.url or "").strip()
            if not url.lower().startswith("http://"):
                continue
            text = _link_text(link) or url
            violations.append(
                self.build_violation(
                    message=f"Insecure HTTP link: {url!r}",
                    line=_line(link),
                    column=_column(link),
                    node_type="Link",
                    suggestion="Upgrade to HTTPS if the destination supports it",
                    context=text[:80],
                )
            )
        return violations


class LinkTextIsUrlRule(LintRule):
    """LNK007: Flag links whose visible text equals the URL itself.

    Distinct from :class:`BareUrlRule` (LNK004): LNK004 catches raw URLs in
    prose that aren't wrapped in link syntax at all; LNK007 catches links
    of the form ``[https://x](https://x)`` where the markup is correct but
    the visible text adds nothing.
    """

    code = "LNK007"
    name = "link-text-is-url"
    category = "links"
    description = "Link text should describe the destination, not duplicate the URL."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each link whose text equals its URL."""
        violations: list[Violation] = []
        for link in _collect_links(ctx.document):
            url = (link.url or "").strip()
            text = _link_text(link).strip()
            if not url or not text:
                continue
            if text.rstrip("/") == url.rstrip("/"):
                violations.append(
                    self.build_violation(
                        message=f"Link text duplicates URL: {url!r}",
                        line=_line(link),
                        column=_column(link),
                        node_type="Link",
                        suggestion="Replace the link text with a descriptive phrase",
                        context=text[:80],
                    )
                )
        return violations


for _rule_cls in (
    EmptyLinkTextRule,
    MissingUrlRule,
    DuplicateUrlsRule,
    BareUrlRule,
    LinkTextQualityRule,
    InsecureLinkRule,
    LinkTextIsUrlRule,
):
    rule_registry.register(_rule_cls)
