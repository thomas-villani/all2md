"""Roundtrip fidelity oracles.

Each oracle takes a Markdown string and returns a :class:`CheckResult`. The two
oracles are deliberately independent so a loss has to slip past *both*:

``idempotency_check``
    ``once = md -> AST -> md``; ``twice = once -> AST -> md``. Passes iff
    ``once == twice`` (a fixed point). Purely syntactic and reference-free.

``html_equivalence_check``
    Renders both ``md`` and ``once`` to HTML with a *fixed reference renderer*
    (mistune's own HTML renderer, configured with the same plugin set all2md's
    parser enables) and compares a normalized form. Because the reference
    renderer is independent of all2md's AST model and Markdown renderer - the
    surfaces where roundtrip losses actually happen - it catches loss that
    already occurred on the first render and is therefore stable under
    idempotency.

Both oracles take a ``via`` format. With ``via="man"`` each pass goes through a
man page (``md -> AST -> man -> AST -> md``), which judges that format's renderer
and parser as a pair; the default ``"markdown"`` is the direct pass above.

Caveat worth stating plainly: all2md *parses* with mistune too, so the HTML
oracle is independent of the AST + render halves of the pipeline, not of the
parse half. That is the right scope for our failure surface (the recent
regressions all lived in the AST builder and the list renderer), but it is not a
fully third-party judge.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

import all2md

from .via import profile_for

if TYPE_CHECKING:
    from all2md.constants import DocumentFormat
    from all2md.options.markdown import MarkdownRendererOptions


@dataclass
class CheckResult:
    """Outcome of one oracle on one document.

    ``passed`` is the pass/fail verdict. ``skipped`` marks a case the oracle
    cannot fairly judge (e.g. HTML-equivalence on a raw-HTML doc, which is lossy
    by policy); a skipped result is neither a pass nor a failure. ``diff`` holds
    a human-readable unified diff when the check fails.
    """

    oracle: str
    passed: bool
    detail: str = ""
    diff: Optional[str] = None
    skipped: bool = False


def _roundtrip_once(md: str, renderer_options: Optional["MarkdownRendererOptions"], via: str = "markdown") -> str:
    """Run one ``Markdown -> AST -> Markdown`` pass, through ``via`` if it is another format.

    With ``via="man"`` the pass is ``Markdown -> AST -> man -> AST -> Markdown``:
    the document is written in that format and read back before the Markdown
    render, so the oracles judge the format's renderer and parser together.
    """
    if via != "markdown":
        fmt = cast("DocumentFormat", via)
        intermediate = all2md.convert(
            md,
            source_format="markdown",
            target_format=fmt,
            renderer_options=profile_for(via).renderer_options,
        )
        if isinstance(intermediate, str):
            intermediate = intermediate.encode("utf-8")
        assert intermediate is not None  # a target format always returns content
        result = all2md.convert(
            intermediate,
            source_format=fmt,
            target_format="markdown",
            renderer_options=renderer_options,
        )
    else:
        result = all2md.convert(
            md,
            source_format="markdown",
            target_format="markdown",
            renderer_options=renderer_options,
        )
    assert isinstance(result, str)  # markdown target is always text
    return result


def idempotency_check(
    md: str,
    *,
    renderer_options: Optional["MarkdownRendererOptions"] = None,
    via: str = "markdown",
) -> CheckResult:
    """Assert the roundtrip reaches a fixed point (``once == twice``).

    The first render may legitimately normalize the source (list markers, wrap
    width, blank-line policy); that is not a loss. A *second* render that
    differs from the first means the rendered Markdown re-parsed to a different
    AST - the signature of the list/footnote roundtrip bugs (#84/#85/#91).
    """
    try:
        once = _roundtrip_once(md, renderer_options, via)
    except Exception as exc:  # a construct that errors on roundtrip is itself a finding
        return CheckResult("idempotency", passed=False, detail=f"first render raised {type(exc).__name__}: {exc}")
    try:
        twice = _roundtrip_once(once, renderer_options, via)
    except Exception as exc:
        return CheckResult("idempotency", passed=False, detail=f"second render raised {type(exc).__name__}: {exc}")

    if once == twice:
        return CheckResult("idempotency", passed=True)
    return CheckResult(
        "idempotency",
        passed=False,
        detail="roundtrip is not a fixed point: rendering the output again changed it",
        diff=_unified_diff(once, twice, "once", "twice"),
    )


def html_equivalence_check(
    md: str,
    *,
    renderer_options: Optional["MarkdownRendererOptions"] = None,
    via: str = "markdown",
) -> CheckResult:
    """Assert the roundtrip preserves meaning, measured as reference HTML.

    ``normalize(ref_html(md)) == normalize(ref_html(md -> AST -> md))``. Catches
    semantic loss (a dropped paragraph, a mangled table cell) that idempotency
    misses when the loss happens on the first render and is then stable.
    """
    try:
        once = _roundtrip_once(md, renderer_options, via)
    except Exception as exc:
        return CheckResult("html_equivalence", passed=False, detail=f"render raised {type(exc).__name__}: {exc}")

    project = profile_for(via).project
    original_html = _normalize_html(_reference_html(md), project)
    roundtrip_html = _normalize_html(_reference_html(once), project)

    if original_html == roundtrip_html:
        return CheckResult("html_equivalence", passed=True)
    return CheckResult(
        "html_equivalence",
        passed=False,
        detail="reference HTML differs between the original and the roundtripped Markdown",
        diff=_unified_diff(original_html, roundtrip_html, "original.html", "roundtrip.html"),
    )


# --- reference HTML rendering -------------------------------------------------


@lru_cache(maxsize=1)
def _reference_markdown():  # type: ignore[no-untyped-def]
    """Build a mistune Markdown->HTML renderer matching all2md's default plugins.

    Mirrors the plugin set enabled in ``all2md.parsers.markdown`` so the oracle
    understands the same constructs (tables, footnotes, task lists, math, def
    lists, the pymdownx inline marks) rather than passing them through as literal
    text - which would blind it to corruption of those constructs. Admonitions
    are intentionally omitted: they use all2md's custom block token, which
    mistune's stock HTML renderer has no method for, so the HTML oracle is not
    authoritative for them (idempotency still is).
    """
    import mistune
    from mistune.plugins.table import table_in_list, table_in_quote

    plugins = [
        "strikethrough",
        "table",
        table_in_list,
        table_in_quote,
        "footnotes",
        "task_lists",
        "math",
        "def_list",
        "mark",
        "insert",
        "superscript",
        "subscript",
        "url",
    ]
    return mistune.create_markdown(escape=False, plugins=plugins)


def _reference_html(md: str) -> str:
    rendered = _reference_markdown()(md)
    return rendered if isinstance(rendered, str) else ""


# --- HTML normalization -------------------------------------------------------

_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)
_WS = re.compile(r"\s+")


def _normalize_html(html: str, project: Optional[Callable[[Any], None]] = None) -> str:
    """Serialize HTML to a canonical, diff-friendly form.

    Insignificant inter-tag whitespace is dropped and text runs are collapsed to
    single spaces, so two HTML fragments that differ only in incidental
    whitespace compare equal while genuine structural differences (a missing
    element, a changed cell) stand out line by line. ``project`` first rewrites
    the parsed tree to remove what a ``via`` format cannot express.
    """
    from bs4 import BeautifulSoup
    from bs4.element import NavigableString, Tag

    soup = BeautifulSoup(html, "html.parser")
    if project is not None:
        project(soup)
    lines: list[str] = []

    def walk(node: object, depth: int) -> None:
        indent = "  " * depth
        if isinstance(node, NavigableString):
            text = _WS.sub(" ", str(node)).strip()
            if text:
                lines.append(f"{indent}#text {text!r}")
            return
        if isinstance(node, Tag):
            attrs = " ".join(f'{k}="{_attr_value(node.get(k))}"' for k in sorted(node.attrs))
            head = f"{node.name} {attrs}".rstrip()
            if node.name in _VOID_TAGS:
                lines.append(f"{indent}<{head}/>")
                return
            lines.append(f"{indent}<{head}>")
            for child in node.children:
                walk(child, depth + 1)
            lines.append(f"{indent}</{node.name}>")

    for child in soup.children:
        walk(child, 0)
    return "\n".join(lines)


def _attr_value(value: object) -> str:
    """Render an attribute value, joining bs4's list-valued attrs (e.g. ``class``)."""
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    return str(value)


def _unified_diff(a: str, b: str, a_name: str, b_name: str) -> str:
    diff = difflib.unified_diff(
        a.splitlines(),
        b.splitlines(),
        fromfile=a_name,
        tofile=b_name,
        lineterm="",
    )
    return "\n".join(diff)
