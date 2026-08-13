"""Hypothesis strategies that build ``Document`` ASTs.

The round-trip scorer in :mod:`all2md.roundtrip` takes a ``Document`` directly,
so generating ASTs lets a property test drive every renderer/parser pair from a
single source of truth. That is the gap these strategies fill: the AST is the
one input shape shared by all 24 round-trippable formats, and the fixture
documents under ``tests/fixtures/`` only ever cover the shapes somebody thought
to write down.

Using it
--------

Compose ``documents()`` into a ``@given`` and round-trip the result::

    from hypothesis import given
    from document_strategies import documents

    @given(documents())
    def test_markdown_round_trips(doc):
        assert roundtrip_report(doc, via="markdown").score == 100

Every strategy takes a bound on how deep it may recurse, because an unbounded
list-inside-list-inside-table generates documents that take longer to render
than they do to shrink, and a slow shrink is what makes a property test
unpleasant to own.

Why the text alphabet is so narrow
----------------------------------

``safe_words()`` emits letters, digits and single spaces, and nothing else. It
is tempting to generate ``|``, ``*`` and ``#`` too, on the theory that more
adversarial text finds more bugs. It does, but they are all the *same* bug:
"format X did not escape metacharacter Y". That class swamps the structural
signal these strategies exist to measure, and it needs a different oracle
anyway, one that knows each format's escaping rules rather than comparing block
skeletons.

So metacharacters live in their own opt-in strategy, :func:`metacharacter_text`.
Use it when you are specifically testing escaping. Do not wire it into
:func:`documents`, or the structural properties start failing for reasons that
have nothing to do with structure.
"""

from hypothesis import strategies as st

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    Paragraph,
    Strikethrough,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)

#: Characters that carry no special meaning in any format we render to, so a
#: round trip that loses them lost structure rather than an escape.
SAFE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

#: Metacharacters that at least one target format treats as syntax. Kept out of
#: the default strategies on purpose -- see the module docstring.
METACHARACTERS = "|*_#`~[]()<>&\\\"'{}$%^=+!?:;,.@/"


def safe_words(min_words: int = 1, max_words: int = 4) -> st.SearchStrategy[str]:
    """Return a strategy for plain text with no format metacharacters.

    Words are joined by single spaces and never lead or trail with whitespace,
    because leading and trailing whitespace is normalised by most renderers and
    would make every property test fail for an uninteresting reason.
    """
    word = st.text(alphabet=SAFE_ALPHABET, min_size=1, max_size=8)
    return st.lists(word, min_size=min_words, max_size=max_words).map(" ".join)


def metacharacter_text() -> st.SearchStrategy[str]:
    """Return a strategy for text that mixes safe words with format syntax.

    Opt in to this only when the property under test is about escaping. It will
    fail structural round-trip properties by design.
    """
    return st.text(alphabet=SAFE_ALPHABET + METACHARACTERS, min_size=1, max_size=24)


def urls() -> st.SearchStrategy[str]:
    """Return a strategy for absolute http(s) URLs.

    Absolute only: relative URLs get resolved against a base by some renderers
    and left alone by others, which is a real asymmetry but not one a structural
    property should be asserting about.
    """
    host = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10)
    path = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=0, max_size=10)
    return st.builds(lambda s, h, p: f"{s}://{h}.example.com/{p}", st.sampled_from(["http", "https"]), host, path)


def text_nodes() -> st.SearchStrategy[Text]:
    """Return a strategy for :class:`Text` leaves."""
    return st.builds(Text, content=safe_words())


def inline_nodes(max_depth: int = 2) -> st.SearchStrategy[object]:
    """Return a strategy for inline nodes, nesting at most ``max_depth`` deep.

    Depth matters here: ``Strong(Emphasis(Text))`` is the shape that PR #158
    (bbcode dropping nested inlines when stripping colour) regressed on, so the
    default allows one level of wrapping rather than none.
    """
    leaves = st.one_of(
        text_nodes(),
        st.builds(Code, content=safe_words(max_words=2)),
        st.builds(Image, url=urls(), alt_text=safe_words(max_words=2)),
        st.just(LineBreak()),
    )
    if max_depth <= 0:
        return leaves

    child = st.lists(inline_nodes(max_depth - 1), min_size=1, max_size=3)
    return st.one_of(
        leaves,
        st.builds(Emphasis, content=child),
        st.builds(Strong, content=child),
        st.builds(Strikethrough, content=child),
        st.builds(Link, url=urls(), content=child),
    )


def inline_content(min_size: int = 1, max_size: int = 4) -> st.SearchStrategy[list]:
    """Return a strategy for a list of inline nodes, suitable as block content."""
    return st.lists(inline_nodes(), min_size=min_size, max_size=max_size)


def headings() -> st.SearchStrategy[Heading]:
    """Return a strategy for headings at every legal level.

    Levels run the full 1 to 6 because clamping above the AST maximum is its own
    defect class: PR #155 fixed org emitting levels above six.
    """
    return st.builds(Heading, level=st.integers(min_value=1, max_value=6), content=inline_content())


def paragraphs() -> st.SearchStrategy[Paragraph]:
    """Return a strategy for paragraphs."""
    return st.builds(Paragraph, content=inline_content())


def code_blocks() -> st.SearchStrategy[CodeBlock]:
    """Return a strategy for fenced code blocks, with and without a language."""
    return st.builds(
        CodeBlock,
        content=st.lists(safe_words(), min_size=1, max_size=3).map("\n".join),
        language=st.one_of(st.none(), st.sampled_from(["python", "rust", "text"])),
    )


def list_items(max_depth: int = 1) -> st.SearchStrategy[ListItem]:
    """Return a strategy for list items, including deliberately empty ones.

    ``children=[]`` is generated on purpose. An empty list item is the single
    most-regressed shape in this project's history: PRs #160 (bbcode), #159
    (mediawiki) and #119 (dokuwiki) all fixed a renderer that silently dropped
    it. A strategy that only builds non-empty items cannot see that class.
    """
    body = st.lists(st.one_of(paragraphs(), code_blocks()), min_size=1, max_size=2)
    if max_depth > 0:
        body = st.lists(
            st.one_of(paragraphs(), lists(max_depth - 1)),
            min_size=1,
            max_size=2,
        )
    return st.builds(
        ListItem,
        children=st.one_of(st.just([]), body),
        task_status=st.one_of(st.none(), st.sampled_from(["checked", "unchecked"])),
    )


def lists(max_depth: int = 1) -> st.SearchStrategy[List]:
    """Return a strategy for ordered and unordered lists.

    ``start`` varies because an ordered list that does not begin at 1 is a
    distinct defect class (PR #87 fixed HTML resetting ``<ol start="N">``), and
    ``tight`` varies because loose lists collapse differently (PR #85).
    """
    return st.builds(
        List,
        ordered=st.booleans(),
        items=st.lists(list_items(max_depth), min_size=1, max_size=3),
        start=st.integers(min_value=1, max_value=5),
        tight=st.booleans(),
    )


def table_cells(allow_span: bool = True) -> st.SearchStrategy[TableCell]:
    """Return a strategy for table cells, including empty ones.

    Empty cells are generated because a renderer that emits nothing for an empty
    cell shifts every later cell left (PR #127, dokuwiki colspan).
    """
    span = st.integers(min_value=1, max_value=2) if allow_span else st.just(1)
    return st.builds(
        TableCell,
        content=st.one_of(st.just([]), inline_content(max_size=2)),
        colspan=span,
        rowspan=span,
    )


def tables(allow_span: bool = True) -> st.SearchStrategy[Table]:
    """Return a strategy for rectangular tables with an optional caption.

    Rectangular means every row declares the same cell count, before spans are
    applied. Ragged tables are a separate concern with a different oracle: the
    scorer compares declared dimensions, so a ragged source is indistinguishable
    from a round trip that lost a cell.

    Captions vary because caption loss is its own class (PRs #157, #129, #132
    all fixed mediawiki ``|+`` handling), and duplicate header labels are
    generated because collapsing them loses a column (PRs #153, #137).
    """

    @st.composite
    def _table(draw: st.DrawFn) -> Table:
        width = draw(st.integers(min_value=1, max_value=3))
        height = draw(st.integers(min_value=1, max_value=3))
        labels = draw(
            st.one_of(
                st.lists(safe_words(max_words=1), min_size=width, max_size=width),
                # Duplicate labels across every column.
                safe_words(max_words=1).map(lambda w: [w] * width),
            )
        )
        header = TableRow(
            cells=[TableCell(content=[Text(content=label)]) for label in labels],
            is_header=True,
        )
        rows = [TableRow(cells=[draw(table_cells(allow_span)) for _ in range(width)]) for _ in range(height)]
        return Table(
            header=header,
            rows=rows,
            caption=draw(st.one_of(st.none(), safe_words(max_words=3))),
        )

    return _table()


def blocks(max_depth: int = 1) -> st.SearchStrategy[object]:
    """Return a strategy for any block-level node."""
    simple = st.one_of(
        headings(),
        paragraphs(),
        code_blocks(),
        st.just(ThematicBreak()),
        lists(max_depth),
        tables(),
    )
    if max_depth <= 0:
        return simple
    return st.one_of(
        simple,
        st.builds(BlockQuote, children=st.lists(blocks(max_depth - 1), min_size=1, max_size=2)),
    )


def documents(min_blocks: int = 1, max_blocks: int = 5) -> st.SearchStrategy[Document]:
    """Return a strategy for whole documents.

    The block count stays small by default. A 40-block document does not find
    defects a 5-block document misses, it just makes the failing example harder
    to read, and a property test is only as useful as the repro it prints.
    """
    return st.builds(Document, children=st.lists(blocks(), min_size=min_blocks, max_size=max_blocks))


def documents_of(*strategies: st.SearchStrategy) -> st.SearchStrategy[Document]:
    """Return a strategy for documents built only from ``strategies``.

    Use this to aim a property at one node class, so a failure names that class
    instead of whatever else happened to be in the document::

        @given(documents_of(tables()))
        def test_table_captions_survive(doc): ...
    """
    return st.builds(Document, children=st.lists(st.one_of(*strategies), min_size=1, max_size=3))


# --------------------------------------------------------------------------- #
# Footnotes
# --------------------------------------------------------------------------- #
#
# Footnotes are the first node class added after the discovery that these
# strategies could only build 19 of the AST's 34 concrete node types. That is a
# ceiling no example budget can lift: a footnote round-trip defect is invisible
# at any ``max_examples`` if nothing ever draws a footnote. They are first
# because the ``benchmarks/roundtrip`` corpus already found real defects here --
# self-escaping HTML in footnote markers, and multi-paragraph definitions
# collapsing to one -- so this is a class known to break, not a speculative one.


def footnote_identifiers() -> st.SearchStrategy[str]:
    """Return a strategy for footnote identifiers.

    Lowercase alphanumerics only. Identifiers appear inside the marker syntax of
    every target format (``[^id]``, ``.. [id]``, ``footnote:id[]``), so a
    metacharacter here tests escaping rather than structure -- the same
    separation of concerns the module docstring draws for text.
    """
    return st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=6)


def footnote_definitions(identifier: str) -> st.SearchStrategy[FootnoteDefinition]:
    """Return a strategy for one footnote's definition, given its identifier.

    The body is one or two paragraphs. Two matters: a multi-paragraph footnote
    is a shape the roundtrip benchmark caught collapsing into a single
    paragraph, and a strategy that only ever builds one-paragraph definitions
    cannot see that class.
    """
    return st.builds(
        FootnoteDefinition,
        identifier=st.just(identifier),
        content=st.lists(paragraphs(), min_size=1, max_size=2),
    )


@st.composite
def documents_with_footnotes(draw: st.DrawFn, min_notes: int = 1, max_notes: int = 3) -> Document:
    """Return a strategy for documents whose footnote references all resolve.

    References and definitions are drawn together rather than independently,
    because an unmatched reference is a *different* property. Every format has
    to invent something for a marker with no definition -- drop it, keep it as
    literal text, synthesise an empty note -- so a document containing one fails
    a structural round trip for reasons that say nothing about footnote support.
    Generate those deliberately, in a test that asserts what should happen to
    them, rather than letting them contaminate this one.

    Each reference is placed inside a paragraph next to ordinary text, which is
    where footnote markers actually occur, and every definition is appended
    after the body, which is where every target format puts them.
    """
    identifiers = draw(
        st.lists(footnote_identifiers(), min_size=min_notes, max_size=max_notes, unique=True),
    )

    body: list[object] = []
    for identifier in identifiers:
        body.append(
            Paragraph(
                content=[
                    Text(content=draw(safe_words())),
                    FootnoteReference(identifier=identifier),
                ]
            )
        )

    definitions = [draw(footnote_definitions(identifier)) for identifier in identifiers]
    return Document(children=[*body, *definitions])


def definition_terms() -> st.SearchStrategy[DefinitionTerm]:
    """Return a strategy for one term of a definition list.

    A term is inline content on a single line in every target spelling, so it is
    built from text rather than from blocks.
    """
    return st.builds(
        DefinitionTerm,
        content=st.lists(st.builds(Text, content=safe_words()), min_size=1, max_size=1),
    )


def definition_descriptions(max_paragraphs: int = 2) -> st.SearchStrategy[DefinitionDescription]:
    """Return a strategy for one description of a definition list.

    A description holds *blocks*, and generating more than one paragraph matters
    for the same reason it does for footnotes: a multi-paragraph body is the
    shape that collapses, and a strategy that only builds single-paragraph
    descriptions cannot see that class of bug.

    The paragraphs hold plain text rather than arbitrary inline content, so that
    a failure here is attributable to definition lists. Drawing full
    :func:`paragraphs` instead finds real bugs, but they are inline bugs: the
    first run of this strategy crashed the AsciiDoc round trip on a nested
    ``Strong`` wrapping a hard break, which reproduces from a bare paragraph
    with no definition list anywhere near it. That belongs to the inline gates,
    not to this one -- an allowlist entry blaming definition lists for it would
    be a false attribution, and the reason string would send the next reader to
    the wrong parser.
    """
    return st.builds(
        DefinitionDescription,
        content=st.lists(
            st.builds(Paragraph, content=st.lists(st.builds(Text, content=safe_words()), min_size=1, max_size=1)),
            min_size=1,
            max_size=max_paragraphs,
        ),
    )


@st.composite
def definition_lists(draw: st.DrawFn, min_items: int = 1, max_items: int = 3) -> DefinitionList:
    """Return a strategy for a definition list.

    ``DefinitionList.items`` is a list of ``(term, [description, ...])`` tuples
    rather than a flat child list, so it is built explicitly -- ``st.builds``
    cannot infer that shape and a flat list of nodes would not type-check
    against it.

    A term is given one or two descriptions. Two matters: several formats spell
    the second description by repeating the marker rather than nesting it, and a
    term that only ever has one description never exercises that path.
    """
    count = draw(st.integers(min_value=min_items, max_value=max_items))
    items = [
        (
            draw(definition_terms()),
            draw(st.lists(definition_descriptions(), min_size=1, max_size=2)),
        )
        for _ in range(count)
    ]
    return DefinitionList(items=items)


@st.composite
def documents_with_definition_lists(draw: st.DrawFn) -> Document:
    """Return a strategy for documents containing a definition list.

    A paragraph precedes the list, because a definition list is the one block
    here whose opening line is ordinary text: several formats mark a term only
    by what follows it, so a list that starts the document cannot show whether
    the preceding block was absorbed into the first term.
    """
    return Document(
        children=[
            Paragraph(content=[Text(content=draw(safe_words()))]),
            draw(definition_lists()),
        ]
    )
