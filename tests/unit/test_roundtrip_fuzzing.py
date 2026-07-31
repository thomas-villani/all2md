"""Generative round-trip fuzzing across the renderer/parser matrix.

Why this file exists
-------------------

``all2md`` ships 24 formats that can be both rendered to and parsed back from,
and the interesting defects live in the *pairs*: a renderer writes something its
own parser cannot read, or reads back as a different shape. The existing fuzz
suites (``test_filename_fuzzing``, ``test_url_validation_fuzzing``,
``test_html_sanitizer_fuzzing``, ``test_pdf_html_edge_case_fuzzing``) all aim at
security surfaces. Nothing generated documents and pushed them through the
matrix, so the whole "renderer and parser disagree" class was only ever covered
by fixture documents somebody had already thought to write.

The AST is the natural input: :func:`all2md.roundtrip_report` accepts a
``Document`` directly and scores what survived, so one strategy drives every
format. ``tests/document_strategies.py`` builds those documents.

How the gates work
------------------

Three gates, in increasing tightness:

``test_ast_round_trip_is_lossless``
    The ``ast`` format must score exactly 100 on every generated document. This
    is the control. If it ever drops, the harness is measuring wrong and every
    other number in this file is suspect.

``test_no_unrecognised_crash``
    No format may raise an exception that is not already in
    :data:`KNOWN_CRASHES`. This is the ratchet that matters: a new renderer that
    emits output its parser rejects fails here on the next CI run, instead of
    surfacing as a user bug report months later.

``test_structural_invariant``
    Specific document shapes, each drawn from a defect this project has actually
    shipped a fix for, must survive a round trip. Known gaps are marked
    ``xfail(strict=True)`` rather than deleted, so fixing one turns it into an
    XPASS and CI tells the contributor to remove the marker. The allowlist can
    only shrink.

Adding to the allowlists
------------------------

Do not widen an allowlist to make a red suite green. A new entry means a new
defect, so it needs a comment saying what breaks and, once filed, the issue
number. If a fix removes the last entry for a format, delete the entry rather
than leaving it as documentation.
"""

import io

import pytest
from document_strategies import documents, documents_of, lists, tables
from hypothesis import HealthCheck, given, settings

from all2md import from_ast, roundtrip_report, roundtrippable_formats, to_ast
from all2md.ast.nodes import (
    CodeBlock,
    Document,
    Heading,
    List,
    ListItem,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)

#: Every gate in this file exercises parser and renderer logic, which does not
#: vary across interpreter versions, so CI runs the file on a single Python leg
#: and deselects it on the rest with ``-m "not matrix_single"``. The marker is
#: dedicated rather than reusing ``fuzzing``: four other suites carry that one
#: (filename, URL, HTML-sanitizer and PDF edge-case fuzzing), they are all
#: sub-second and security-relevant, and dropping them from four legs would save
#: nothing while thinning the security coverage.
#:
#: The gates that draw their corpus with Hypothesis carry a second marker,
#: ``generative``, and per-PR CI deselects it: those run on a schedule instead
#: (see .github/workflows/fuzz-corpus.yml). They are ``derandomize=True``, so a
#: PR run recomputes a fixed answer over a fixed corpus and can only change when
#: our code does -- the discovery value is in a seeded sweep, not in the 300th
#: identical replay. What stays per-PR is everything deterministic and cheap:
#: the classification check, the structural invariants, and the known-crash
#: repros, whose strict xfails are what fail the moment someone fixes a bug and
#: leaves the allowlist entry behind.
pytestmark = pytest.mark.matrix_single

# --------------------------------------------------------------------------- #
# Format groups
# --------------------------------------------------------------------------- #

#: Text formats, fast enough to round-trip inside a property test. Roughly
#: 3-30 ms each, so the whole group costs well under a second per example.
TEXT_FORMATS = (
    "ast",
    "markdown",
    "html",
    "rst",
    "org",
    "asciidoc",
    "textile",
    "mediawiki",
    "dokuwiki",
    "latex",
    "plaintext",
)

#: Container and binary formats. Each writes a real archive or document, so they
#: cost 4-90 ms and are exercised in a ``slow``-marked test rather than on every
#: run.
BINARY_FORMATS = ("docx", "odt", "odp", "pptx", "epub", "rtf", "ipynb", "pdf")

#: Data-serialization formats, deliberately excluded from the matrix. They carry
#: key-value data, not document structure, so "the heading did not survive" is
#: their designed behaviour and not a defect. ``csv`` goes further and raises
#: outright on a document with no table, which is also correct.
DATA_FORMATS = ("csv", "ini", "json", "toml", "yaml")

#: Formats whose round trip is expected to be exactly lossless.
LOSSLESS_FORMATS = ("ast",)


# --------------------------------------------------------------------------- #
# Known crashes
# --------------------------------------------------------------------------- #

#: Exceptions the matrix currently raises, as ``(format, substring)``.
#:
#: Each entry is a live defect, not an accepted behaviour: a renderer emitting
#: output its own parser rejects is always a bug. They are listed so the gate can
#: distinguish "already known" from "newly introduced". Minimal reproductions for
#: every entry are pinned in :class:`TestKnownCrashRepros` below.
KNOWN_CRASHES: dict[tuple[str, str], str] = {
    # An empty list item nested inside another list leaves the RTF renderer
    # emitting a group the RTF parser walks off the end of.
    ("rtf", "IndexError"): "rtf round trip of a nested empty list item indexes out of range",
    # Same shape carrying a task status takes a different path and raises a
    # KeyError from pyth. It is now wrapped in RenderingError (#212), so the
    # needle matches the original error inside the wrapper's message; the crash
    # itself is still live.
    ("rtf", "KeyError"): "rtf round trip of a nested task list item raises a KeyError",
}


def is_known(fmt: str, exc: BaseException) -> bool:
    """Return whether ``exc`` from ``fmt`` is already on the allowlist."""
    text = f"{type(exc).__name__}: {exc}"
    return any(needle in text for (known_fmt, needle) in KNOWN_CRASHES if known_fmt == fmt)


# --------------------------------------------------------------------------- #
# Gate 0: coverage of the matrix itself
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.fuzzing
class TestMatrixCoverage:
    """The format groups above must account for every round-trippable format."""

    def test_every_roundtrippable_format_is_classified(self) -> None:
        """Every format is in exactly one group, so none escapes the fuzzer.

        Without this, adding a 25th format silently opts it out of every gate in
        this file: the groups are hand-written tuples, and nothing else would
        notice the omission. Failing here forces a deliberate choice, either
        "fuzz it" or "it is data, not documents, and here is why".
        """
        classified = TEXT_FORMATS + BINARY_FORMATS + DATA_FORMATS
        assert len(classified) == len(set(classified)), "a format appears in more than one group"
        assert set(classified) == set(roundtrippable_formats())


# --------------------------------------------------------------------------- #
# Gate 1: the control
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.generative
class TestLosslessFormatsAreLossless:
    """The formats that claim exactness are the harness's control."""

    @pytest.mark.parametrize("fmt", LOSSLESS_FORMATS)
    @settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(doc=documents())
    def test_round_trip_scores_exactly_100(self, fmt: str, doc: Document) -> None:
        """Property: a lossless format round trip loses nothing, ever.

        ``ast`` is a direct JSON encoding of the node tree, so any loss is a bug
        in the encoder, the decoder, or the scorer. This test is what makes the
        other numbers in this file trustworthy: if it fails, a low score
        elsewhere might be measurement error rather than a real asymmetry.
        """
        report = roundtrip_report(doc, via=fmt)
        assert report.score == 100, f"{fmt} round trip lost structure: {[d.to_dict() for d in report.deltas]}"


# --------------------------------------------------------------------------- #
# Gate 2: the crash ratchet
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.generative
class TestNoUnrecognisedCrash:
    """No format may fail in a way that is not already documented.

    Both gates run ``derandomize=True``, so the examples are a fixed function of
    the strategy rather than a fresh random draw each run. That is deliberate.
    A ratchet has to fail only when someone breaks something, and a randomised
    gate fails the first time it happens to draw a shape that was always broken,
    which reads as a flaky test and trains people to re-run CI until it passes.

    The cost is that these gates stop discovering new defects once the seed is
    fixed. Discovery is a separate activity, run on purpose rather than on every
    commit::

        HYPOTHESIS_PROFILE=ci python -m pytest -m fuzzing --hypothesis-seed=random

    Anything that finds belongs in :data:`KNOWN_CRASHES` with a reproduction.

    The format comes from ``parametrize`` rather than from ``sampled_from``
    inside the strategy, so ``max_examples`` is a budget *per format* instead of
    a budget shared across all of them. Drawing the format made the gate much
    less sensitive than it looks: 25 examples spread over 11 text formats is
    about two documents per format, so a shape has to be common to be seen at
    all. Measured, by breaking the mediawiki renderer for level-6 headings only
    — a shape present in **12.8%** of generated documents (51/400): the
    drawn-format gate passed green with the break live, this one fails on it.
    Parametrizing also puts the format in the test id, so a failure names the
    format without reading the Hypothesis output.
    """

    @pytest.mark.parametrize("fmt", TEXT_FORMATS)
    @settings(
        deadline=None,
        max_examples=25,
        derandomize=True,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(documents())
    def test_text_formats_raise_nothing_new(self, fmt: str, doc: Document) -> None:
        """Property: a text-format round trip either works or fails a known way.

        Locks the current crash surface in place. A renderer change that makes
        output its own parser cannot read fails here, which is the whole point:
        that class of defect is invisible to fixture-based tests because nobody
        writes a fixture for a shape they did not know was broken.
        """
        try:
            roundtrip_report(doc, via=fmt)
        except Exception as exc:  # noqa: BLE001 - the assertion is about the class
            if not is_known(fmt, exc):
                pytest.fail(f"new crash class for {fmt!r}: {type(exc).__name__}: {exc}")

    @pytest.mark.slow
    @pytest.mark.parametrize("fmt", BINARY_FORMATS)
    @settings(
        deadline=None,
        max_examples=10,
        derandomize=True,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(documents(max_blocks=3))
    def test_binary_formats_raise_nothing_new(self, fmt: str, doc: Document) -> None:
        """Property: the same guarantee for container and binary formats.

        Split out and marked ``slow`` because each example writes a real archive
        or PDF. Same gate, fewer examples, so a full run stays usable locally.

        The shared-budget problem was worse here than for text: 10 examples over
        8 formats meant most formats saw one document, and some saw none at all.
        """
        try:
            roundtrip_report(doc, via=fmt)
        except Exception as exc:  # noqa: BLE001 - the assertion is about the class
            if not is_known(fmt, exc):
                pytest.fail(f"new crash class for {fmt!r}: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- #
# Known-crash reproductions
# --------------------------------------------------------------------------- #


def _cell(text: str = "", **kwargs: object) -> TableCell:
    """Build a table cell, empty when ``text`` is empty."""
    return TableCell(content=[Text(content=text)] if text else [], **kwargs)  # type: ignore[arg-type]


#: An empty list item nested one level down, alongside an empty sibling.
NESTED_EMPTY_ITEM = Document(
    children=[
        Paragraph(content=[Text(content="0")]),
        List(
            ordered=False,
            tight=False,
            items=[
                ListItem(children=[List(ordered=False, tight=False, items=[ListItem(children=[])])]),
                ListItem(children=[]),
            ],
        ),
    ]
)

#: The same shape, carrying a task status.
NESTED_TASK_ITEM = Document(
    children=[
        List(
            ordered=False,
            tight=False,
            items=[
                ListItem(
                    task_status="checked",
                    children=[
                        List(
                            ordered=False,
                            tight=False,
                            items=[ListItem(children=[], task_status="checked")],
                        )
                    ],
                )
            ],
        )
    ]
)


@pytest.mark.unit
@pytest.mark.fuzzing
class TestKnownCrashRepros:
    """Minimal reproductions for every :data:`KNOWN_CRASHES` entry.

    Marked ``xfail(strict=True)`` rather than asserting the crash, because a test
    that asserts broken behaviour defends the bug. Strict xfail does the
    opposite: the day someone fixes the renderer the test XPASSes, CI fails, and
    the contributor is told to delete the marker and the allowlist entry.
    """

    @pytest.mark.parametrize(
        ("doc", "fmt"),
        [
            pytest.param(
                NESTED_EMPTY_ITEM,
                "rtf",
                id="rtf-nested-empty-list-item",
                marks=pytest.mark.xfail(strict=True, reason="parser indexes past the end of a group"),
            ),
            pytest.param(
                NESTED_TASK_ITEM,
                "rtf",
                id="rtf-nested-task-list-item",
                marks=pytest.mark.xfail(strict=True, reason="pyth raises KeyError on the task status"),
            ),
        ],
    )
    def test_known_crash_still_reproduces(self, doc: Document, fmt: str) -> None:
        """Each known crash reproduces from a minimal document.

        Every reproduction here was shrunk by Hypothesis from a generated
        document, so it is the smallest shape that triggers the defect rather
        than the first one found.
        """
        roundtrip_report(doc, via=fmt)


# --------------------------------------------------------------------------- #
# Gate 3: structural invariants
# --------------------------------------------------------------------------- #


def _round_trip(doc: Document, fmt: str) -> Document:
    """Render ``doc`` to ``fmt`` and parse it straight back."""
    rendered = from_ast(doc, fmt)
    data = rendered.encode("utf-8") if isinstance(rendered, str) else rendered
    return to_ast(io.BytesIO(data), source_format=fmt)


def _collect(node: object, cls: type, found: list | None = None) -> list:
    """Return every descendant of ``node`` that is an instance of ``cls``."""
    found = [] if found is None else found
    if isinstance(node, cls):
        found.append(node)
    for attr in ("children", "content", "items", "rows", "cells"):
        for child in getattr(node, attr, None) or []:
            _collect(child, cls, found)
    header = getattr(node, "header", None)
    if header is not None:
        _collect(header, cls, found)
    return found


def _list_item_count(doc: Document) -> int:
    return sum(len(node.items) for node in _collect(doc, List))


def _list_starts(doc: Document) -> list[int]:
    return [node.start for node in _collect(doc, List) if node.ordered]


def _captions(doc: Document) -> list[str | None]:
    return [node.caption for node in _collect(doc, Table)]


def _header_widths(doc: Document) -> list[int]:
    return [len(node.header.cells) for node in _collect(doc, Table) if node.header]


def _heading_levels(doc: Document) -> list[int]:
    return [node.level for node in _collect(doc, Heading)]


def _code_languages(doc: Document) -> list[str | None]:
    return [node.language for node in _collect(doc, CodeBlock)]


#: One entry per invariant: a document, a probe, and the value the probe must
#: return after a round trip. Each is drawn from a defect class this project has
#: shipped a fix for, so the invariant is not hypothetical.
INVARIANTS: dict[str, tuple[Document, object, object]] = {
    # PRs #160 (bbcode), #159 (mediawiki), #119 (dokuwiki) all fixed a renderer
    # that silently dropped an empty list item.
    "empty-list-item-survives": (
        Document(
            children=[
                List(
                    ordered=False,
                    items=[ListItem(children=[]), ListItem(children=[Paragraph(content=[Text(content="x")])])],
                )
            ]
        ),
        _list_item_count,
        2,
    ),
    # PR #87 fixed HTML resetting `<ol start="N">` to 1.
    "ordered-list-start-survives": (
        Document(
            children=[List(ordered=True, start=5, items=[ListItem(children=[Paragraph(content=[Text(content="a")])])])]
        ),
        _list_starts,
        [5],
    ),
    # PRs #157, #129, #132 fixed mediawiki `|+` caption handling.
    "table-caption-survives": (
        Document(
            children=[
                Table(
                    header=TableRow(is_header=True, cells=[_cell("a"), _cell("b")]),
                    rows=[TableRow(cells=[_cell("1"), _cell("2")])],
                    caption="cap",
                )
            ]
        ),
        _captions,
        ["cap"],
    ),
    # PRs #153 (yaml) and #137 (json) fixed duplicate column values collapsing.
    "duplicate-header-labels-survive": (
        Document(
            children=[
                Table(
                    header=TableRow(is_header=True, cells=[_cell("d"), _cell("d")]),
                    rows=[TableRow(cells=[_cell("1"), _cell("2")])],
                )
            ]
        ),
        _header_widths,
        [2],
    ),
    # PR #155 fixed org emitting heading levels above the AST maximum.
    "heading-levels-survive": (
        Document(children=[Heading(level=level, content=[Text(content=f"h{level}")]) for level in range(1, 7)]),
        _heading_levels,
        [1, 2, 3, 4, 5, 6],
    ),
    "code-block-language-survives": (
        Document(children=[CodeBlock(content="x = 1", language="python")]),
        _code_languages,
        ["python"],
    ),
}

#: Invariants that do not hold yet, as ``(format, invariant)`` with the reason.
#:
#: Everything here is a real asymmetry. Two of them are arguably by design and
#: are called out as such; the rest are defects worth fixing. Entries are marked
#: strict-xfail, so fixing one fails CI until the entry is deleted.
KNOWN_INVARIANT_GAPS: dict[tuple[str, str], str] = {
    # Markdown and reStructuredText have no table-caption syntax, so the caption
    # has nowhere to go. Arguably by design, though both could round-trip it
    # through a comment or a `.. table::` directive.
    ("markdown", "table-caption-survives"): "markdown has no caption syntax",
    ("rst", "table-caption-survives"): "rst renderer does not emit a table directive",
    ("org", "table-caption-survives"): "org renderer does not emit #+CAPTION",
    ("asciidoc", "table-caption-survives"): "asciidoc renderer does not emit a .caption line",
    # rst derives heading level from the underline character, and the renderer
    # reuses characters, so distinct levels collapse into each other.
    ("rst", "heading-levels-survive"): "rst underline characters repeat, collapsing levels",
    # asciidoc drops the first heading: the renderer treats a leading level-1 as
    # the document title and the parser does not map it back.
    ("asciidoc", "heading-levels-survive"): "leading h1 becomes the document title and is lost",
    # asciidoc writes a trailing pipe after the last cell, which its parser reads
    # as an extra empty column, so every table gains a phantom column.
    ("asciidoc", "duplicate-header-labels-survive"): "trailing pipe parses as an extra empty cell",
    # asciidoc and org both drop the ordered-list start attribute.
    ("asciidoc", "ordered-list-start-survives"): "renderer does not emit the start attribute",
    ("org", "ordered-list-start-survives"): "renderer does not emit [@N]",
    # org loses an empty list item and the source-block language.
    ("org", "empty-list-item-survives"): "renderer drops the empty item's bullet",
    ("org", "code-block-language-survives"): "renderer does not emit the #+BEGIN_SRC language",
}

#: Formats the invariant gate covers. Text formats only: the invariants probe
#: specific node attributes, and the container formats lose so much structure
#: that every entry would need an allowlist line, which teaches nothing.
INVARIANT_FORMATS = ("ast", "markdown", "html", "rst", "org", "asciidoc")


def _invariant_params() -> list:
    """Build one parametrization per (format, invariant), xfailing known gaps."""
    params = []
    for fmt in INVARIANT_FORMATS:
        for name in INVARIANTS:
            reason = KNOWN_INVARIANT_GAPS.get((fmt, name))
            marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
            params.append(pytest.param(fmt, name, id=f"{fmt}-{name}", marks=marks))
    return params


@pytest.mark.unit
@pytest.mark.fuzzing
class TestStructuralInvariants:
    """Document shapes drawn from real shipped fixes must survive a round trip."""

    @pytest.mark.parametrize(("fmt", "invariant"), _invariant_params())
    def test_structural_invariant(self, fmt: str, invariant: str) -> None:
        """Each invariant holds for each format, or is a documented gap.

        These are the shapes this project has already had to fix once. Asserting
        them per format is what turns 39 one-format bug fixes into a matrix: a
        renderer that regresses "empty list items survive" fails here even if the
        format that originally broke is untouched.
        """
        doc, probe, expected = INVARIANTS[invariant]
        actual = probe(_round_trip(doc, fmt))  # type: ignore[operator]
        assert actual == expected, f"{fmt}: {invariant} gave {actual!r}, expected {expected!r}"


# --------------------------------------------------------------------------- #
# Targeted generative properties
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.generative
class TestGeneratedTablesAndLists:
    """Aim the generator at the two node classes that break most often."""

    @settings(deadline=None, max_examples=25, suppress_health_check=[HealthCheck.too_slow])
    @given(documents_of(tables()))
    def test_table_documents_round_trip_through_html(self, doc: Document) -> None:
        """Property: HTML preserves every table's declared dimensions.

        HTML has explicit ``colspan``/``rowspan`` and a ``<caption>``, so it is
        the one text format with no excuse for changing a table's shape. That
        makes it the right place to assert dimensions rather than allowlist them.
        """
        source_widths = _header_widths(doc)
        assert _header_widths(_round_trip(doc, "html")) == source_widths

    @settings(deadline=None, max_examples=25, suppress_health_check=[HealthCheck.too_slow])
    @given(documents_of(lists()))
    def test_list_documents_keep_their_item_count_in_html(self, doc: Document) -> None:
        """Property: HTML keeps every list item, including the empty ones.

        ``<li></li>`` is legal and unambiguous, so an item that disappears here
        was dropped by the renderer rather than squeezed out by the syntax.
        """
        assert _list_item_count(_round_trip(doc, "html")) == _list_item_count(doc)
