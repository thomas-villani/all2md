"""Read the DOCX renderer's output back through Word itself: PDF -> AST -> DOCX -> Word.

The re-parse instrument (`benchmarks.pmc.docx_reparse`) reads our DOCX output back with our
own DOCX parser, so it cannot tell a renderer defect from a parser defect, and worse, the two
can **agree** on a reading Word rejects: a parser lenient where Word is strict scores a
broken document as a perfect round trip. This instrument asks Word. Each article's AST is
rendered once, opened in a hidden Word over COM, and read through Word's own object model:
which paragraphs reach the navigation pane and at what level, which paragraphs Word numbers
and how, how many tables Word sees and their shape, which hyperlinks it resolves, which
paragraphs carry the Caption style.

**Three readings of one AST.** The direct AST is what we meant; our parser's reading of the
DOCX is what the re-parse instrument saw; Word's reading is what a user gets. A loss split
three ways says whose it is:

* **Word only** -- lost in Word, kept by our parser. The renderer wrote something our parser
  forgives and Word does not (or reads differently). The defects nothing else can see.
* **Parser only** -- kept by Word, lost by our parser. A parser defect the re-parse
  instrument blamed on the renderer.
* **Both** -- most likely the renderer: two independent readers lost the same thing.

Word's reading is mapped onto the inventory `docx_reparse` already pairs, with Word's own
notion of each structure:

* **Headings** are paragraphs with an outline level -- what the navigation pane shows. The
  renderer writes a lone leading H1 in Word's Title style and shifts later headings up a
  level; that shift is undone here exactly as the DOCX parser undoes it, and counted.
* **Lists** are Word's ``List`` objects, keyed by the list identity Word assigns, and their
  items are the paragraphs Word numbers in them. Word's identity is the numbering instance,
  not adjacency, so two lists that share an instance are one list to Word even with prose
  between them. **List items** are paired separately, by the number Word displays, which
  is what a reader sees whatever the grouping.
* **Tables** are ``Document.Tables``, rows by columns. Two tables with nothing between them
  are one table to Word, whatever the XML says.
* **Links** are ``Document.Hyperlinks`` spans, with Word's normalization of a bare host
  (``https://example.org`` reads back as ``https://example.org/``) applied to both sides.
* **Captions** are paragraphs in the Caption style. Whether Word *numbers* them -- a
  ``SEQ`` field, which is what a table of figures and a cross-reference need -- is counted
  beside them.

Facts with no inventory counterpart are recorded per article: pictures, equations, the
document's compatibility mode, and a census of the paragraph styles Word reports.

**Windows and a Word install only, hand-run, never in CI.** ``win32com`` is imported inside
`WordReader` alone, so everything else here -- the inventory, the pairing, the payload --
runs and is tested anywhere. Word is started as a separate, hidden instance
(``DispatchEx``): a reading never touches a Word the user has open, and never takes over
the desktop. Like the re-parse instrument it is a **ledger, not a gate**; readings are dated
in the README.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import unquote, urlsplit, urlunsplit

from benchmarks.pmc.docx_reparse import (
    EXAMPLE_CHARS,
    EXAMPLES,
    Inventory,
    _collect,
    _pairing,
    compare_inventories,
    inventory,
    reparse_options,
)

#: 1 = first shape: per-structure pairings of Word's reading against the direct AST and
#: against our parser's reading, the three-way loss split, and the per-article Word facts.
SCHEMA_VERSION = 1

#: The inventory structures this instrument pairs. ``heading_text`` pairs headings by text
#: alone, so a heading at the wrong level is told apart from one that stopped being one.
STRUCTURES = ("headings", "heading_text", "tables", "lists", "list_items", "links", "captions")

#: ``Paragraph.OutlineLevel`` for body text: not in the navigation pane.
BODY_TEXT = 10

#: ``WdBuiltinStyle`` ids, resolved per document so a localized Word still matches.
WD_STYLE_TITLE = -63
WD_STYLE_CAPTION = -35

#: ``WdFieldType.wdFieldSequence`` -- the ``SEQ`` field a numbered caption carries.
WD_FIELD_SEQUENCE = 12

#: ``WdInlineShapeType.wdInlineShapePicture``.
WD_INLINE_PICTURE = 3

#: What may lie between two hyperlinks that are one span: spaces, tabs and manual line
#: breaks (Word's vertical tab), never a paragraph or cell mark.
_SPAN_GAP = re.compile(r"[ \t\x0b]*")

#: A number Word displays for an ordered list item: ``3.``, ``iv)``, ``(b)``.
_ORDERED_MARKER = re.compile(r"^\(?([0-9]+|[A-Za-z]{1,6})[.)]$")


@dataclass(frozen=True, slots=True)
class WordParagraph:
    """One paragraph as Word reports it.

    Attributes
    ----------
    style : str
        Paragraph style name, localized.
    outline : int
        Outline level, 1-9, or `BODY_TEXT`.
    text : str
        The paragraph's visible text, field results included and field codes not.

    """

    style: str
    outline: int
    text: str


@dataclass(frozen=True, slots=True)
class WordListItem:
    """One paragraph Word numbers or bullets.

    Attributes
    ----------
    list_id : int
        Word's identity for the list the paragraph belongs to (its ``List`` range start).
    marker : str
        The number or bullet Word displays, exactly.

    """

    list_id: int
    marker: str


@dataclass(frozen=True, slots=True)
class WordHyperlink:
    """One hyperlink Word resolves.

    Attributes
    ----------
    url : str
        Address, with ``#subaddress`` appended for a target inside the document.
    joins_previous : bool
        The previous hyperlink has the same target and only spaces, tabs or manual line
        breaks lie between the two -- one span to a reader, as `docx_reparse.link_spans`
        counts it. A paragraph or cell boundary between them makes two spans there too.

    """

    url: str
    joins_previous: bool = False


@dataclass(frozen=True, slots=True)
class WordReading:
    """Everything this instrument reads out of one document in Word.

    Attributes
    ----------
    paragraphs : tuple[WordParagraph, ...]
        Every paragraph, in order.
    list_items : tuple[WordListItem, ...]
        Every numbered or bulleted paragraph, in order.
    tables : tuple[tuple[int, int], ...]
        ``(rows, columns)`` of every table; columns are the widest row's cell count.
    hyperlinks : tuple[WordHyperlink, ...]
        Every hyperlink, in order.
    title_style, caption_style : str
        The localized names of Word's built-in Title and Caption styles.
    pictures : int
        Inline pictures plus floating shapes.
    equations : int
        ``OMath`` zones.
    sequence_fields : int
        ``SEQ`` fields -- numbered captions.
    compatibility_mode : int
        ``Document.CompatibilityMode``: 15 is current Word, 14 is Word 2010, and a document
        below 15 opens with "Compatibility Mode" in the title bar.

    """

    paragraphs: tuple[WordParagraph, ...]
    list_items: tuple[WordListItem, ...] = ()
    tables: tuple[tuple[int, int], ...] = ()
    hyperlinks: tuple[WordHyperlink, ...] = ()
    title_style: str = "Title"
    caption_style: str = "Caption"
    pictures: int = 0
    equations: int = 0
    sequence_fields: int = 0
    compatibility_mode: int = 15


class WordReader:
    """A hidden Word instance that reads documents, one at a time.

    Use as a context manager; Word is started on entry and quit on exit. ``DispatchEx``
    starts a Word of our own rather than attaching to one the user has open, and the
    instance stays invisible, so a reading never disturbs the desktop. Alerts are off:
    one modal dialog would otherwise hang every later COM call with nothing to time out
    against.
    """

    def __init__(self) -> None:
        self.app: Any = None

    def __enter__(self) -> WordReader:
        import win32com.client

        self.app = win32com.client.DispatchEx("Word.Application")
        self.app.Visible = False
        self.app.DisplayAlerts = 0
        return self

    def __exit__(self, *exc: object) -> None:
        if self.app is not None:
            self.app.Quit(0)
            self.app = None

    def read(self, path: Path) -> WordReading:
        """Open one document read-only and read it through Word's object model.

        Parameters
        ----------
        path : pathlib.Path
            The DOCX file.

        Returns
        -------
        WordReading
            Word's reading of the document.

        """
        # Positional: FileName, ConfirmConversions, ReadOnly, AddToRecentFiles.
        document = self.app.Documents.Open(str(path.resolve()), False, True, False, Visible=False)
        try:
            return _read_document(document)
        finally:
            document.Close(0)


def _read_document(document: Any) -> WordReading:
    paragraphs = tuple(
        WordParagraph(style=str(p.Style.NameLocal), outline=int(p.OutlineLevel), text=str(p.Range.Text))
        for p in document.Paragraphs
    )
    list_items = []
    for paragraph in document.ListParagraphs:
        list_format = paragraph.Range.ListFormat
        list_items.append(WordListItem(list_id=int(list_format.List.Range.Start), marker=str(list_format.ListString)))
    # ListParagraphs runs back to front.
    list_items.reverse()

    tables = []
    for table in document.Tables:
        rows = int(table.Rows.Count)
        tables.append((rows, max((int(table.Rows(index).Cells.Count) for index in range(1, rows + 1)), default=0)))

    hyperlinks: list[WordHyperlink] = []
    previous: tuple[str, int] | None = None
    for hyperlink in document.Hyperlinks:
        address, sub = str(hyperlink.Address or ""), str(hyperlink.SubAddress or "")
        url = f"{address}#{sub}" if sub else address
        start, end = int(hyperlink.Range.Start), int(hyperlink.Range.End)
        joins = (
            previous is not None
            and previous[0] == url
            and _SPAN_GAP.fullmatch(str(document.Range(previous[1], start).Text or "")) is not None
        )
        hyperlinks.append(WordHyperlink(url=url, joins_previous=joins))
        previous = (url, end)

    pictures = sum(1 for shape in document.InlineShapes if int(shape.Type) == WD_INLINE_PICTURE)
    return WordReading(
        paragraphs=paragraphs,
        list_items=tuple(list_items),
        tables=tuple(tables),
        hyperlinks=tuple(hyperlinks),
        title_style=str(document.Styles(WD_STYLE_TITLE).NameLocal),
        caption_style=str(document.Styles(WD_STYLE_CAPTION).NameLocal),
        pictures=pictures + int(document.Shapes.Count),
        equations=int(document.OMaths.Count),
        sequence_fields=sum(1 for item in document.Fields if int(item.Type) == WD_FIELD_SEQUENCE),
        compatibility_mode=int(document.CompatibilityMode),
    )


def clean_text(text: str) -> str:
    """Collapse text to what both readers agree a reader sees.

    Word's paragraph text carries the paragraph mark, cell-end marks, manual line breaks
    and object anchors as control characters; the DOCX renderer drops control characters a
    PDF text layer carries. Both sides lose every control character and collapse runs of
    whitespace, so neither difference scores as a changed heading.
    """
    return " ".join("".join(" " if ch < " " else ch for ch in text).split())


def url_key(url: str) -> str:
    """Normalize a link target the way Word reports it, on both sides of a pairing.

    ``Hyperlink.Address`` is not the relationship target byte for byte: Word lowercases the
    host, gives a bare host its root path, and percent-decodes (``%20`` reads back as a
    space). None of that changes where the link goes, so none of it scores as a loss.
    """
    try:
        parts = urlsplit(unquote(url))
    except ValueError:
        return url
    if parts.scheme in ("http", "https") and parts.netloc:
        parts = parts._replace(netloc=parts.netloc.lower(), path=parts.path or "/")
    return urlunsplit(parts)


@dataclass(frozen=True, slots=True)
class Reading:
    """An inventory with the list items keyed by their displayed number.

    Attributes
    ----------
    inventory : Inventory
        Headings, tables, lists, links and captions, normalized for pairing with Word.
    list_items : Counter[tuple[bool, int | None]]
        ``(ordered, number)`` per list item; ``number`` is None for a bullet, and for an
        ordered item numbered with letters or numerals Word displays non-decimally.

    """

    inventory: Inventory
    list_items: Counter[tuple[bool, int | None]]


def ast_reading(document: Any) -> Reading:
    """Read an AST the way this instrument reads Word: normalized and keyed for pairing.

    Parameters
    ----------
    document : Document
        The direct AST, or our parser's reading of the DOCX.

    Returns
    -------
    Reading
        The AST's structure.

    """
    from all2md.ast.nodes import List

    base = inventory(document)
    items: Counter[tuple[bool, int | None]] = Counter()
    for node in _collect(document, List):
        start = node.start if node.start is not None else 1
        for index in range(len(node.items)):
            items[(True, start + index) if node.ordered else (False, None)] += 1
    return Reading(
        inventory=Inventory(
            nodes=Counter(),
            headings=Counter({(level, clean_text(text)): n for (level, text), n in base.headings.items()}),
            tables=base.tables,
            lists=base.lists,
            links=Counter({url_key(url): n for url, n in base.links.items()}),
            captions=Counter({clean_text(text): n for text, n in base.captions.items()}),
        ),
        list_items=items,
    )


def word_inventory(reading: WordReading) -> tuple[Reading, bool]:
    """Map Word's reading onto the inventory the AST readings use.

    Parameters
    ----------
    reading : WordReading
        Word's reading of one document.

    Returns
    -------
    tuple[Reading, bool]
        The structure, and whether the leading heading was in Word's Title style (and the
        heading levels were shifted back to undo the renderer's promotion).

    """
    first = next((p for p in reading.paragraphs if clean_text(p.text)), None)
    promoted = first is not None and first.style == reading.title_style
    headings: Counter[tuple[int, str]] = Counter()
    captions: Counter[str] = Counter()
    for paragraph in reading.paragraphs:
        text = clean_text(paragraph.text)
        if promoted and paragraph is first:
            headings[(1, text)] += 1
        elif paragraph.outline < BODY_TEXT:
            headings[(paragraph.outline + (1 if promoted else 0), text)] += 1
        if paragraph.style == reading.caption_style and text:
            captions[text] += 1

    by_list: dict[int, list[str]] = {}
    items: Counter[tuple[bool, int | None]] = Counter()
    for item in reading.list_items:
        by_list.setdefault(item.list_id, []).append(item.marker)
        match = _ORDERED_MARKER.match(item.marker.strip())
        if match is None:
            items[(False, None)] += 1
        else:
            items[(True, int(match.group(1)) if match.group(1).isdigit() else None)] += 1
    lists = Counter(
        (any(_ORDERED_MARKER.match(marker.strip()) for marker in markers), len(markers)) for markers in by_list.values()
    )

    links = Counter(url_key(link.url) for link in reading.hyperlinks if not link.joins_previous)
    word = Inventory(
        nodes=Counter(),
        headings=headings,
        tables=Counter(reading.tables),
        lists=lists,
        links=links,
        captions=captions,
    )
    return Reading(inventory=word, list_items=items), promoted


def compare_readings(before: Reading, after: Reading) -> dict[str, Any]:
    """Pair two readings, structure by structure (see `docx_reparse.compare_inventories`)."""
    compared = compare_inventories(before.inventory, after.inventory)
    compared.pop("node_counts_moved")
    compared["list_items"] = _pairing(before.list_items, after.list_items)
    return compared


def _keys(reading: Reading, structure: str) -> Counter[Any]:
    if structure == "list_items":
        return reading.list_items
    if structure == "heading_text":
        return Counter(text for (_level, text), n in reading.inventory.headings.items() for _ in range(n))
    counter: Counter[Any] = getattr(reading.inventory, structure)
    return counter


def blame(direct: Reading, parser: Reading, word: Reading) -> dict[str, Any]:
    """Split each structure's losses by which reader lost them.

    Parameters
    ----------
    direct, parser, word : Reading
        The AST we meant, our parser's reading of the DOCX, and Word's reading of it.

    Returns
    -------
    dict
        Per structure: ``word_only``, ``parser_only`` and ``both`` counts of items lost from
        the direct reading, with examples of the first two.

    """
    split: dict[str, Any] = {}
    for structure in STRUCTURES:
        meant = _keys(direct, structure)
        lost_word = meant - _keys(word, structure)
        lost_parser = meant - _keys(parser, structure)
        word_only = lost_word - lost_parser
        parser_only = lost_parser - lost_word
        split[structure] = {
            "word_only": sum(word_only.values()),
            "parser_only": sum(parser_only.values()),
            "both": sum((lost_word & lost_parser).values()),
            "word_only_examples": [_example(key) for key, _ in word_only.most_common(EXAMPLES)],
            "parser_only_examples": [_example(key) for key, _ in parser_only.most_common(EXAMPLES)],
        }
    return split


def _example(key: Any) -> Any:
    if isinstance(key, str):
        return key[:EXAMPLE_CHARS]
    if isinstance(key, tuple):
        return [_example(part) for part in key]
    return key


@dataclass(frozen=True, slots=True)
class ArticleWordReading:
    """One article read three ways.

    Attributes
    ----------
    article_id : str
        Corpus article id.
    readings : Mapping[str, Reading]
        ``direct``, ``parser`` and ``word``, for every stage that completed.
    word : WordReading or None
        Word's raw reading, when Word opened the document.
    title_promoted : bool
        The leading heading reached Word in its Title style.
    ast_pictures, ast_equations : int
        Images and math nodes in the direct AST, beside Word's counts.
    errors : Mapping[str, str]
        Stage (``parse``, ``render``, ``parser``, ``word``) -> error.
    seconds : Mapping[str, float]
        Wall time per stage.

    """

    article_id: str
    readings: Mapping[str, Reading] = field(default_factory=dict)
    word: WordReading | None = None
    title_promoted: bool = False
    ast_pictures: int = 0
    ast_equations: int = 0
    errors: Mapping[str, str] = field(default_factory=dict)
    seconds: Mapping[str, float] = field(default_factory=dict)


def read_article(
    article: Any,
    reader: WordReader,
    workdir: Path,
    *,
    options: Any = None,
) -> ArticleWordReading:
    """Parse one article's PDF, render it to DOCX, and read the DOCX with our parser and Word.

    Parameters
    ----------
    article : benchmarks.pmc.corpus.CorpusArticle
        Article with a validated PDF path.
    reader : WordReader
        An open Word reader.
    workdir : pathlib.Path
        Directory the rendered DOCX is written to; Word opens files, not bytes.
    options : PdfOptions or None
        PDF parser policy; defaults to `docx_reparse.reparse_options`, so this instrument
        reads exactly the documents the re-parse instrument does.

    Returns
    -------
    ArticleWordReading
        The three readings, or the errors that stopped them.

    """
    from all2md import from_ast, to_ast
    from all2md.ast.nodes import Image, MathBlock, MathInline

    readings: dict[str, Reading] = {}
    errors: dict[str, str] = {}
    seconds: dict[str, float] = {}

    def timed(stage: str, call: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - a failed stage is a ledger entry, not a crash
            errors[stage] = f"{type(exc).__name__}: {exc}"
            return None
        finally:
            seconds[stage] = time.perf_counter() - started

    document = timed(
        "parse", lambda: to_ast(article.pdf_path, source_format="pdf", parser_options=options or reparse_options())
    )
    if document is None:
        return ArticleWordReading(article.article_id, errors=errors, seconds=seconds)
    readings["direct"] = ast_reading(document)
    pictures = len(_collect(document, Image))
    equations = len(_collect(document, MathInline)) + len(_collect(document, MathBlock))

    rendered = timed("render", lambda: from_ast(document, "docx"))
    if not isinstance(rendered, bytes):
        errors.setdefault("render", f"DOCX renderer returned {type(rendered).__name__}, expected bytes")
        return ArticleWordReading(article.article_id, readings, None, False, pictures, equations, errors, seconds)

    parsed = timed("parser", lambda: ast_reading(to_ast(rendered, source_format="docx")))
    if parsed is not None:
        readings["parser"] = parsed

    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / f"{article.article_id}.docx"
    path.write_bytes(rendered)
    word = timed("word", lambda: reader.read(path))
    promoted = False
    if word is not None:
        readings["word"], promoted = word_inventory(word)

    return ArticleWordReading(
        article_id=article.article_id,
        readings=readings,
        word=word,
        title_promoted=promoted,
        ast_pictures=pictures,
        ast_equations=equations,
        errors=errors,
        seconds=seconds,
    )


def _sum(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for row in rows:
        for key in keys:
            totals[key] += row[key]
    return {key: totals[key] for key in keys}


def summarize(readings: Sequence[ArticleWordReading]) -> dict[str, Any]:
    """Reduce article readings to the ledger payload.

    Totals cover the articles all three readings completed, so the pairings share one
    denominator; an article a stage failed on is listed under that stage instead.

    Parameters
    ----------
    readings : Sequence[ArticleWordReading]
        One reading per article.

    Returns
    -------
    dict
        Per-structure pairings (direct against Word, parser against Word), the three-way
        loss split, Word's document facts, and per-article detail.

    """
    pair_keys = ("before", "after", "kept", "lost", "gained")
    blame_keys = ("word_only", "parser_only", "both")
    complete = [r for r in readings if all(name in r.readings for name in ("direct", "parser", "word"))]
    against_direct: dict[str, list[Mapping[str, Any]]] = {name: [] for name in STRUCTURES}
    against_parser: dict[str, list[Mapping[str, Any]]] = {name: [] for name in STRUCTURES}
    blamed: dict[str, list[Mapping[str, Any]]] = {name: [] for name in STRUCTURES}
    styles: Counter[str] = Counter()
    modes: Counter[int] = Counter()
    articles: list[dict[str, Any]] = []
    facts: Counter[str] = Counter()
    complete_ids = {r.article_id for r in complete}

    for reading in readings:
        entry: dict[str, Any] = {
            "article_id": reading.article_id,
            "errors": dict(reading.errors),
            "seconds": {name: round(value, 3) for name, value in reading.seconds.items()},
        }
        if reading.article_id in complete_ids:
            direct, parser, word = (reading.readings[name] for name in ("direct", "parser", "word"))
            versus_direct = compare_readings(direct, word)
            versus_parser = compare_readings(parser, word)
            split = blame(direct, parser, word)
            for name in STRUCTURES:
                against_direct[name].append(versus_direct[name])
                against_parser[name].append(versus_parser[name])
                blamed[name].append(split[name])
            assert reading.word is not None
            raw = reading.word
            styles.update(p.style for p in raw.paragraphs)
            modes[raw.compatibility_mode] += 1
            captions = sum(direct.inventory.captions.values())
            facts.update(
                {
                    "title_promoted": int(reading.title_promoted),
                    "ast_pictures": reading.ast_pictures,
                    "word_pictures": raw.pictures,
                    "ast_equations": reading.ast_equations,
                    "word_equations": raw.equations,
                    "captions": captions,
                    "sequence_fields": raw.sequence_fields,
                }
            )
            entry.update(
                {
                    "compatibility_mode": raw.compatibility_mode,
                    "title_promoted": reading.title_promoted,
                    "pictures": {"ast": reading.ast_pictures, "word": raw.pictures},
                    "equations": {"ast": reading.ast_equations, "word": raw.equations},
                    "sequence_fields": raw.sequence_fields,
                    "direct_vs_word": {
                        name: pairing for name, pairing in versus_direct.items() if pairing["lost"] or pairing["gained"]
                    },
                    "blame": {name: value for name, value in split.items() if any(value[k] for k in blame_keys)},
                }
            )
        articles.append(entry)

    return {
        "schema_version": SCHEMA_VERSION,
        "articles": len(readings),
        "articles_read": len(complete),
        "failures": {
            stage: sorted(r.article_id for r in readings if stage in r.errors)
            for stage in ("parse", "render", "parser", "word")
        },
        "structure": {
            name: {
                "direct_vs_word": _sum(against_direct[name], pair_keys),
                "parser_vs_word": _sum(against_parser[name], pair_keys),
                "lost_by": _sum(blamed[name], blame_keys),
            }
            for name in STRUCTURES
        },
        "word": {
            "compatibility_modes": {str(mode): n for mode, n in sorted(modes.items())},
            "facts": dict(facts),
            "styles": dict(styles.most_common()),
        },
        "per_article": articles,
    }


def run(
    snapshot: Any,
    workdir: Path,
    *,
    all2md_commit: str = "unknown",
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Read a corpus snapshot through Word and build the ledger payload.

    Parameters
    ----------
    snapshot : benchmarks.pmc.corpus.CorpusSnapshot
        Pinned corpus to read.
    workdir : pathlib.Path
        Directory the rendered DOCX files are written to (and left in, for inspection).
    all2md_commit : str
        Commit being measured.
    progress : callable or None
        Receives one line per article.

    Returns
    -------
    dict
        JSON-ready payload.

    """
    import importlib.metadata
    import sys

    readings = []
    with WordReader() as reader:
        word_build = str(reader.app.Build)
        for index, article in enumerate(snapshot.articles):
            reading = read_article(article, reader, workdir)
            readings.append(reading)
            if progress is not None:
                failed = f" errors={sorted(reading.errors)}" if reading.errors else ""
                progress(f"[{index + 1}/{len(snapshot.articles)}] {article.article_id}{failed}")
    readings.sort(key=lambda reading: reading.article_id)

    payload = summarize(readings)
    payload["provenance"] = {
        "corpus_pin": snapshot.manifest_sha256,
        "manifest": str(snapshot.manifest_path),
        "all2md_commit": all2md_commit,
        "all2md_version": importlib.metadata.version("all2md"),
        "word_build": word_build,
        "python": sys.version.split()[0],
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return payload
