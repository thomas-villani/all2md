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

Five gates, in increasing tightness:

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

``test_footnotes_survive``
    Footnote references and definitions, generated in matched pairs, keep their
    count and their definition paragraphs across a round trip. Same strict-xfail
    ratchet. This is the first gate aimed at a node class the strategies could
    not previously build at all: they reached 19 of the AST's 34 concrete node
    types, and a defect in the other 15 was invisible at any example budget --
    which is why "expand the fuzz tests" was answered with more coverage rather
    than more examples.

``test_definition_lists_survive``
    The second such gate, covering ``DefinitionList``/``Term``/``Description``.
    It runs only over the five formats whose *parser* can build a definition
    list: sixteen renderers emit one, and a round trip through the other eleven
    would fill the allowlist with entries saying nothing but "this format has no
    syntax we read back".

    Its descriptions hold plain text rather than arbitrary inline content, on
    purpose. Drawing full paragraphs found a real crash on the first run --- and
    the crash was an inline defect (#353) reachable from a bare paragraph, which
    an entry in this gate's allowlist would have misattributed to definition
    lists. A gate should fail for the reason it is named after.

Adding to the allowlists
------------------------

Do not widen an allowlist to make a red suite green. A new entry means a new
defect, so it needs a comment saying what breaks and, once filed, the issue
number. If a fix removes the last entry for a format, delete the entry rather
than leaving it as documentation.
"""

import io
import os

import pytest
from document_strategies import (
    documents,
    documents_of,
    documents_with_definition_lists,
    documents_with_footnotes,
    figures,
    lists,
    tables,
)
from hypothesis import HealthCheck, given, settings

from all2md import from_ast, roundtrip_report, roundtrippable_formats, to_ast
from all2md.ast.nodes import (
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Figure,
    FootnoteDefinition,
    FootnoteReference,
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
#: ``generative``. They run per PR on the same single leg: they are
#: ``derandomize=True``, so a PR replays a fixed corpus to recompute an answer
#: that only moves when our code does, which is what a ratchet is for. They were
#: briefly moved to a nightly schedule when they took over three hours, but that
#: was a verbose Hypothesis profile leaking into CI (#341), not the gates; they
#: cost ~20s.
pytestmark = pytest.mark.matrix_single

#: Draw a fresh corpus instead of replaying the fixed one. This is the *discovery*
#: mode, run nightly by .github/workflows/fuzz-corpus.yml, and anything it finds
#: belongs in :data:`KNOWN_CRASHES` with a reproduction.
#:
#: It needs an environment variable because ``--hypothesis-seed=random`` cannot do
#: it: an explicit ``derandomize=True`` in ``@settings`` beats the flag, so that
#: sweep silently replays the same documents. Measured, by fingerprinting the
#: drawn corpus -- with and without the flag the fingerprints are identical. Do
#: not put ``--hypothesis-seed=random`` in a workflow and call it discovery.
DISCOVERY = os.environ.get("ALL2MD_FUZZ_DISCOVERY") == "1"

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
#:
#: Empty since #343 closed the asciidoc one. That entry read as a hard-break
#: rendering problem; it was the parser never joining an item's run-on lines,
#: which both leaked the text out of the item and ended the list. The regression
#: tests live with the parser, in tests/unit/parsers/test_asciidoc_parser.py.
KNOWN_CRASHES: dict[tuple[str, str], str] = {}


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
    @settings(deadline=None, derandomize=not DISCOVERY, suppress_health_check=[HealthCheck.too_slow])
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
    fixed. Discovery is a separate activity, run nightly and on purpose rather
    than on every commit::

        ALL2MD_FUZZ_DISCOVERY=1 python -m pytest -m generative

    Anything that finds belongs in :data:`KNOWN_CRASHES` with a reproduction.

    Use that variable, not ``--hypothesis-seed=random``: the flag loses to the
    explicit ``derandomize`` here and quietly replays the same corpus, so a
    sweep built on it is vacuous. See :data:`DISCOVERY`.

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
        derandomize=not DISCOVERY,
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
        derandomize=not DISCOVERY,
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


#: An empty list item nested one level down, carrying a task status. The RTF
#: repros that shared this shape moved to tests/unit/renderers/test_rtf_nested_lists.py
#: when #209 and #210 were fixed.
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
        [],
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
    """Return every descendant of ``node`` that is an instance of ``cls``.

    Tuples and lists inside a child attribute are walked through rather than
    treated as leaves. ``DefinitionList.items`` is a list of
    ``(term, [description, ...])`` tuples, and without this a search for a
    `DefinitionTerm` finds nothing at all -- which made the first version of the
    definition-list gate compare 0 against 0 and pass while measuring nothing.
    """
    found = [] if found is None else found
    if isinstance(node, (tuple, list)):
        for element in node:
            _collect(element, cls, found)
        return found
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
#: Everything here is a real asymmetry, and every entry is now filed. Entries are
#: marked strict-xfail, so fixing one fails CI until the entry is deleted.
#:
#: The reasons below were re-measured against ``main`` when the issues were
#: filed, and four of them had blamed the wrong side of the trip: a renderer that
#: does emit the right syntax, with a parser that will not read it back, is a
#: different fix from a renderer that emits nothing. Prefer measuring the
#: rendered output before trusting a reason in this table.
#:
#: Empty since #237 closed the last table-caption entry. Markdown has no caption
#: syntax, so the renderer emits the caption twice over -- an italic paragraph for
#: readers, a marker comment for the parser -- and the invariant holds without
#: making the caption invisible in the file.
KNOWN_INVARIANT_GAPS: dict[tuple[str, str], str] = {}

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

    @settings(
        deadline=None,
        max_examples=25,
        derandomize=not DISCOVERY,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(documents_of(tables()))
    def test_table_documents_round_trip_through_html(self, doc: Document) -> None:
        """Property: HTML preserves every table's declared dimensions.

        HTML has explicit ``colspan``/``rowspan`` and a ``<caption>``, so it is
        the one text format with no excuse for changing a table's shape. That
        makes it the right place to assert dimensions rather than allowlist them.
        """
        source_widths = _header_widths(doc)
        assert _header_widths(_round_trip(doc, "html")) == source_widths

    @settings(
        deadline=None,
        max_examples=25,
        derandomize=not DISCOVERY,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(documents_of(lists()))
    def test_list_documents_keep_their_item_count_in_html(self, doc: Document) -> None:
        """Property: HTML keeps every list item, including the empty ones.

        ``<li></li>`` is legal and unambiguous, so an item that disappears here
        was dropped by the renderer rather than squeezed out by the syntax.
        """
        assert _list_item_count(_round_trip(doc, "html")) == _list_item_count(doc)


# --------------------------------------------------------------------------- #
# Footnotes
# --------------------------------------------------------------------------- #
#
# The first node class added after measuring that the strategies could only
# build 19 of the AST's 34 concrete node types. Raising ``max_examples`` could
# never have found any of the gaps below, because nothing in the generator drew
# a footnote -- which is why the answer to "expand the fuzz tests" was more
# coverage rather than more examples.


def _footnote_counts(doc: Document) -> tuple[int, int]:
    """Return ``(references, definitions)`` in *doc*."""
    return len(_collect(doc, FootnoteReference)), len(_collect(doc, FootnoteDefinition))


def _definition_paragraphs(doc: Document) -> int:
    """Return the total number of paragraphs across every footnote definition."""
    return sum(len(_collect(definition, Paragraph)) for definition in _collect(doc, FootnoteDefinition))


#: Formats the footnote gate covers: the text formats whose renderer emits
#: footnotes at all. The container formats are excluded for the same reason they
#: are excluded from the structural invariants -- every one would need an
#: allowlist line saying "this format has no footnotes", which teaches nothing.
FOOTNOTE_FORMATS = ("ast", "markdown", "html", "rst", "org", "asciidoc", "dokuwiki")

#: Known footnote round-trip gaps, keyed by ``(format, property)``. Same ratchet
#: as the other allowlists in this file: fixing one makes its test XPASS, which
#: fails CI until the entry is deleted, so a fix cannot silently leave a stale
#: reason behind.
#:
#: Every reason below was read off the rendered output, not inferred from the
#: count that failed. That distinction has bitten this file before -- four
#: earlier entries named the wrong side of the trip -- and it mattered again
#: here: "asciidoc loses every footnote" reads like a renderer that drops them,
#: and the renderer is in fact correct.
KNOWN_FOOTNOTE_GAPS: dict[tuple[str, str], str] = {
    # ("asciidoc", "markers") is gone: the parser reads the named inline form
    # `footnote:a1[text]` (#346), degrades a hard break inside the macro's brackets to a
    # space instead of an unparseable embedded newline, and synthesizes an empty
    # definition for an id referenced but never defined -- the spelling the renderer
    # itself emits when a definition's content flattens to nothing.
    ("asciidoc", "definition_paragraphs"): (
        "The AsciiDoc renderer flattens a multi-paragraph definition into one inline argument: "
        "two paragraphs render as `footnote:a1[note one note two]`. Lost at render time, before "
        "the parser gap above is even reached."
    ),
    ("html", "markers"): (
        "The HTML renderer emits a real footnote section -- `<sup id=fnref-a1><a href=#fn-a1>` and "
        "a `<section id=footnotes>` -- but the HTML parser has no rule for reading it back, so "
        "html->html keeps the text and loses the structure. HTML has no native footnote element, "
        "so this is recovering our own convention rather than a standard one."
    ),
    (
        "html",
        "definition_paragraphs",
    ): "Follows from the markers gap: there is no definition left to count paragraphs in.",
    ("rst", "markers"): (
        "The reST renderer emits `body[a1]_` and `.. [a1] text`. With an alphanumeric label that is "
        "reST *citation* syntax, not footnote syntax (which wants `[#name]_` or a number), so the "
        "identifiers the generator draws do not survive as footnotes."
    ),
    ("rst", "definition_paragraphs"): (
        "A multi-paragraph definition renders as indented continuation lines under `.. [a1]`, which "
        "reads back as one paragraph rather than two. #347"
    ),
    # ("markdown", "definition_paragraphs") is gone: what looked like #347's collapse was
    # three defects wearing one reason -- consecutive hard breaks splitting the definition's
    # paragraph (#384), and nested/empty strikethrough opening a tilde fence that ate the
    # definition (#391). With both fixed, the canonical two-paragraph markdown footnote
    # round-trips whole.
    # ("org", "definition_paragraphs") is gone: Org continues a footnote definition
    # across a single blank line and ends it at two, so the renderer now separates a
    # definition's paragraphs with a blank line (and follows a definition with two
    # before ordinary content), and the parser's block splitter counts the blank
    # lines between blocks instead of discarding them.
    ("dokuwiki", "definition_paragraphs"): "Multi-paragraph definitions collapse toward a single paragraph. #347",
}

#: The properties the gate asserts, and how to measure each.
FOOTNOTE_PROPERTIES = {
    "markers": _footnote_counts,
    "definition_paragraphs": _definition_paragraphs,
}


def _footnote_params() -> list:
    """Build one parametrization per (format, property), xfailing known gaps."""
    params = []
    for fmt in FOOTNOTE_FORMATS:
        for name in FOOTNOTE_PROPERTIES:
            reason = KNOWN_FOOTNOTE_GAPS.get((fmt, name))
            marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
            params.append(pytest.param(fmt, name, id=f"{fmt}-{name}", marks=marks))
    return params


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.generative
class TestGeneratedFootnotes:
    """Footnotes survive a round trip, or the gap is written down and attributed."""

    @pytest.mark.parametrize(("fmt", "prop"), _footnote_params())
    def test_footnotes_survive(self, fmt: str, prop: str) -> None:
        """Property: a document's footnotes come back with the same shape.

        References and definitions are generated in matched pairs. An unmatched
        reference is a different property with a different answer per format --
        drop it, keep it as text, synthesise an empty note -- and mixing the two
        would make every failure ambiguous about which one it was.
        """
        measure = FOOTNOTE_PROPERTIES[prop]

        @settings(
            deadline=None,
            max_examples=25,
            derandomize=not DISCOVERY,
            suppress_health_check=[HealthCheck.too_slow],
        )
        @given(documents_with_footnotes())
        def property_holds(doc: Document) -> None:
            assert measure(_round_trip(doc, fmt)) == measure(doc)

        property_holds()


def _definition_shape(doc: Document) -> tuple[int, int, int]:
    """Return ``(lists, terms, descriptions)`` in *doc*."""
    return (
        len(_collect(doc, DefinitionList)),
        len(_collect(doc, DefinitionTerm)),
        len(_collect(doc, DefinitionDescription)),
    )


def _description_paragraphs(doc: Document) -> int:
    """Return the total number of paragraphs across every description."""
    return sum(len(_collect(description, Paragraph)) for description in _collect(doc, DefinitionDescription))


#: Formats the definition-list gate covers: the ones whose *parser* can produce a
#: `DefinitionList` at all. Sixteen renderers emit one, but only five read one
#: back, and a round trip through the other eleven measures a documented absence
#: rather than a defect -- it would fill the allowlist with entries that say
#: nothing except "this format has no definition-list syntax we parse".
DEFINITION_FORMATS = ("ast", "markdown", "html", "rst", "org", "asciidoc")

#: Known definition-list round-trip gaps, keyed by ``(format, property)``. Same
#: ratchet as the other allowlists here: fixing one makes its test XPASS, which
#: fails CI until the entry is deleted.
#: Markdown and HTML round-trip all three shapes here correctly, so none of these
#: is a spec ambiguity about what a definition list means -- two formats get it
#: right and three do not.
KNOWN_DEFINITION_GAPS: dict[tuple[str, str], str] = {
    ("asciidoc", "shape"): (
        "AsciiDoc attaches one description to each `term::`, so a term's several "
        "descriptions flatten into it -- as continuation lines since #351's fix bound "
        "descriptions to their terms at all, so the words survive; the description count "
        "cannot. The same inherent expressibility gap as reST and Org."
    ),
    ("asciidoc", "description_paragraphs"): (
        "A description's paragraph boundary degrades to a continuation line, so two "
        "paragraphs come back as one -- words intact since the renderer stopped fusing "
        "them ('only'+'extra' -> 'onlyextra'). Asciidoctor proper spells the boundary "
        "with a `+` continuation line, which this parser does not read yet; teaching it "
        "`+` would close this."
    ),
    # ("rst", "description_paragraphs") is gone: the word-fusing concatenation (#352) is
    # fixed -- blocks now render as same-indent paragraphs separated by blank lines, and
    # the parser reads the paragraph count back exactly.
    ("rst", "shape"): (
        "reST's own syntax holds ONE definition per term (docutils: (term, classifier*, "
        "definition)), so a term's several descriptions flatten into that one definition -- "
        "as separate paragraphs since #352's fix, so the words survive; the description "
        "count cannot. An inherent expressibility gap, not a renderer defect."
    ),
    ("org", "shape"): (
        "Org has one `::` definition per item, so a term's several descriptions flatten "
        "into it -- as continuation lines since #352's fix, words intact, count lost. "
        "Inherent to the syntax, like ('rst', 'shape')."
    ),
    ("org", "description_paragraphs"): (
        "A description's paragraph boundary degrades to a continuation line, so two "
        "paragraphs come back as one -- with their words intact since #352's fix (they "
        "used to fuse: 'alpha'+'beta' -> 'alphabeta'). Org proper spells the boundary as "
        "a blank line plus indent, which the org parser's block splitter cannot see "
        "across yet; parser-side continuation support would close this."
    ),
}

DEFINITION_PROPERTIES = {
    "shape": _definition_shape,
    "description_paragraphs": _description_paragraphs,
}


def _definition_params() -> list:
    """Build one parametrization per (format, property), xfailing known gaps."""
    params = []
    for fmt in DEFINITION_FORMATS:
        for name in DEFINITION_PROPERTIES:
            reason = KNOWN_DEFINITION_GAPS.get((fmt, name))
            marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
            params.append(pytest.param(fmt, name, id=f"{fmt}-{name}", marks=marks))
    return params


@pytest.mark.unit
@pytest.mark.generative
@pytest.mark.fuzzing
class TestGeneratedDefinitionLists:
    """Definition lists survive a round trip, or the gap is written down and attributed."""

    @pytest.mark.parametrize(("fmt", "prop"), _definition_params())
    def test_definition_lists_survive(self, fmt: str, prop: str) -> None:
        """Property: a document's definition lists come back with the same shape."""
        measure = DEFINITION_PROPERTIES[prop]

        @settings(
            deadline=None,
            max_examples=25,
            derandomize=not DISCOVERY,
            suppress_health_check=[HealthCheck.too_slow],
        )
        @given(documents_with_definition_lists())
        def property_holds(doc: Document) -> None:
            assert measure(_round_trip(doc, fmt)) == measure(doc)

        property_holds()


def _figure_shape(doc: Document) -> tuple[int, list[str | None]]:
    """Return ``(figure count, captions in order)`` in *doc*."""
    figure_nodes = _collect(doc, Figure)
    return (len(figure_nodes), [node.caption for node in figure_nodes])


def _figure_child_blocks(doc: Document) -> int:
    """Return the total number of direct child blocks across every figure."""
    return sum(len(node.children) for node in _collect(doc, Figure))


#: Formats the figure gate covers: the ones whose *parser* reconstructs the
#: Figure container (#338). Every renderer emits the content -- most degrade the
#: container to its children plus a caption line -- but only the ast, markdown,
#: and html parsers read it back today (html since ``figures_parsing`` defaulted
#: to ``"figure"``, which is what this harness runs).
FIGURE_FORMATS = ("ast", "markdown", "html")

#: Known figure round-trip gaps, same ratchet as the other allowlists here.
KNOWN_FIGURE_GAPS: dict[tuple[str, str], str] = {}

FIGURE_PROPERTIES = {
    "shape": _figure_shape,
    "child_blocks": _figure_child_blocks,
}


def _figure_params() -> list:
    """Build one parametrization per (format, property), xfailing known gaps."""
    params = []
    for fmt in FIGURE_FORMATS:
        for name in FIGURE_PROPERTIES:
            reason = KNOWN_FIGURE_GAPS.get((fmt, name))
            marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
            params.append(pytest.param(fmt, name, id=f"{fmt}-{name}", marks=marks))
    return params


@pytest.mark.unit
@pytest.mark.generative
@pytest.mark.fuzzing
class TestGeneratedFigures:
    """Figure containers survive a round trip, or the gap is written down and attributed."""

    @pytest.mark.parametrize(("fmt", "prop"), _figure_params())
    def test_figures_survive(self, fmt: str, prop: str) -> None:
        """Property: a document's figures come back with the same shape.

        Empty-children figures are generated on purpose: a vector-drawn PDF
        figure has a caption and no extractable content, and "a figure was
        here" must survive the trip rather than collapse to nothing (#338).
        """
        measure = FIGURE_PROPERTIES[prop]

        @settings(
            deadline=None,
            max_examples=25,
            derandomize=not DISCOVERY,
            suppress_health_check=[HealthCheck.too_slow],
        )
        @given(documents_of(figures()))
        def property_holds(doc: Document) -> None:
            assert measure(_round_trip(doc, fmt)) == measure(doc)

        property_holds()
