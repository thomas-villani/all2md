"""Score the DOCX renderer by re-reading its output: PDF -> AST -> DOCX -> AST.

"Make this PDF an editable Word document" is the most-requested conversion in the wild and,
until this module, nothing measured it. Its fidelity is the product of two halves: the PDF
parse, which the rest of this lane scores, and the DOCX renderer, which had no instrument.

**The design isolates the renderer by holding the PDF parse fixed.** Each article is parsed
once; that one AST is scored directly *and* after a trip through ``from_ast(..., "docx")``
and the DOCX parser. Every difference between the two readings happened on the DOCX leg,
so the delta needs no new ground truth -- the JATS oracle and the PDF's own text layer are
the same on both sides by construction.

**What it cannot do is say which half of that leg lost something.** The re-read goes
through our own DOCX parser, so a renderer defect and a parser defect look identical here,
and the two can also *agree* on a reading Word itself rejects. Separating them is the job
of the Word read-back instrument (``wordlive``, run by hand). The DOCX parser has been
through its own defect stream against a Word-generated corpus (``benchmarks/docx``), which
is why this instrument is worth running now rather than before that batch.

Three readings, from coarse to sharp:

* **Truth recall and precision** -- the lane's own article-level instruments, applied to
  both readings. This says whether a loss matters against what the page printed.
* **Text survival without truth** -- the direct reading's own n-grams against the re-read's.
  Truth-free, so it sees loss in blocks too short or too scrambled for the JATS oracle, and
  it sees text the round trip *adds* (a stray marker, a duplicated caption), which recall
  cannot.
* **Structure inventory** -- headings, tables, lists, figures, links and math counted and
  paired on both sides. Text can survive while its structure does not: a table flattened to
  paragraphs keeps every word.

**The Markdown round trip is carried as a reference column.** The same AST through the
Markdown renderer and parser shows which losses are the AST round trip in general and which
belong to DOCX. It is not ground truth -- the Markdown path has defects of its own -- only a
second opinion on the same input.

This instrument is a **ledger, not a gate**, the route the DOCX corpus lane took: its first
reading is a defect list for a renderer that has never had one, and a threshold recorded
before that list is worked would ratchet the defects in as accepted.

Scope, stated before the first reading rather than discovered after it:

* **Article level only.** The lane's per-page instruments need page attribution, which rides
  on page-separator nodes a Word document has no reason to keep. The PDF is parsed with the
  library's default separator policy -- what a user converting to DOCX gets -- not the
  lane's numbered separators, which would reach the document as review comments.
* **Section and column layout is not scored.** A two-column source rendered as one column
  is a legitimate default for an editable document.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from benchmarks.pmc.alignment import MIN_NGRAMS, ngram_counts, ngrams, normalize
from benchmarks.pmc.article import RECALL_MIN, measure_precision, measure_recall

#: 1 = first shape: truth recall/precision per route, truth-free text survival, the
#: structure inventory, and per-article loss examples.
SCHEMA_VERSION = 1

#: The routes each article's AST is scored through. ``direct`` is the baseline the others
#: are compared against; ``markdown`` is the reference column.
ROUTES = ("direct", "docx", "markdown")

#: Examples kept per article and per ledger entry. The ledger is read by a person, and a
#: hundred lost link URLs from one reference list say no more than five.
EXAMPLES = 5

#: Characters of a block kept in an example.
EXAMPLE_CHARS = 120


def reparse_options() -> Any:
    """Build the PDF parser policy for this instrument.

    The lane's policy (layout analysis on, OCR auto, images extracted as base64) with the
    library's **default page-separator policy** substituted for the lane's numbered one.
    Numbered separators exist so the per-page instruments can attribute nodes to pages;
    rendered to DOCX they become one review comment per page, which is the lane's
    instrumentation leaking into the measured document rather than anything a user sees.

    Images stay extracted because a picture is what a Word user expects where the PDF had a
    figure, and a lane that dropped them could never see a figure defect.

    Returns
    -------
    PdfOptions
        Parser options.

    """
    from all2md.options.pdf import PdfOptions
    from benchmarks.pmc.convert import pdf_options

    defaults = PdfOptions()
    return pdf_options(
        include_page_numbers=defaults.include_page_numbers,
        page_separator_template=defaults.page_separator_template,
    )


def via_docx(document: Any) -> Any:
    """Render an AST to DOCX in memory and parse it back.

    Parameters
    ----------
    document : Document
        AST to round-trip.

    Returns
    -------
    Document
        The DOCX parser's reading of the rendered document.

    """
    from all2md import from_ast, to_ast

    rendered = from_ast(document, "docx")
    if not isinstance(rendered, bytes):
        raise TypeError(f"DOCX renderer returned {type(rendered).__name__}, expected bytes")
    return to_ast(rendered, source_format="docx")


def via_markdown(document: Any) -> Any:
    """Render an AST to Markdown and parse it back -- the reference column.

    Parameters
    ----------
    document : Document
        AST to round-trip.

    Returns
    -------
    Document
        The Markdown parser's reading of the rendered text.

    """
    from all2md import from_ast, to_ast

    rendered = from_ast(document, "markdown")
    if not isinstance(rendered, str):
        raise TypeError(f"Markdown renderer returned {type(rendered).__name__}, expected str")
    return to_ast(rendered.encode("utf-8"), source_format="markdown")


#: Route name -> round trip. ``direct`` is the identity by definition.
ROUND_TRIPS: Mapping[str, Callable[[Any], Any]] = {
    "direct": lambda document: document,
    "docx": via_docx,
    "markdown": via_markdown,
}


def _plain(nodes: Any) -> str:
    from all2md.ast.utils import extract_text

    return " ".join(extract_text(nodes).split())


def _collect(document: Any, kind: type) -> list[Any]:
    from all2md.ast.transforms import NodeCollector

    collector = NodeCollector(lambda node: isinstance(node, kind))
    document.accept(collector)
    return collector.collected


@dataclass(frozen=True, slots=True)
class Inventory:
    """What one reading of an article contains, structurally.

    Each field is a multiset so the two readings can be paired rather than merely counted: a
    reading that loses one heading and invents another has the same heading *count* and is
    still two defects.

    Attributes
    ----------
    nodes : Counter[str]
        Every node by type name.
    headings : Counter[tuple[int, str]]
        ``(level, text)`` of every heading.
    tables : Counter[tuple[int, int]]
        ``(rows, columns)`` of every table, header row included in ``rows``; columns are the
        widest row's cell count.
    lists : Counter[tuple[bool, int]]
        ``(ordered, items)`` of every list, nested lists included.
    links : Counter[str]
        Target URL of every link span (see `link_spans`).
    captions : Counter[str]
        Caption text of every figure and table that carries one.

    """

    nodes: Counter[str]
    headings: Counter[tuple[int, str]]
    tables: Counter[tuple[int, int]]
    lists: Counter[tuple[bool, int]]
    links: Counter[str]
    captions: Counter[str]


def inventory(document: Any) -> Inventory:
    """Count and key the structure a reading carries.

    Parameters
    ----------
    document : Document
        A reading of one article.

    Returns
    -------
    Inventory
        The reading's structure, keyed for pairing.

    """
    from all2md.ast.nodes import Figure, Heading, List, Node, Table

    nodes = Counter(type(node).__name__ for node in _collect(document, Node))
    headings = Counter((node.level, _plain(node.content)) for node in _collect(document, Heading))
    tables: Counter[tuple[int, int]] = Counter()
    captions: Counter[str] = Counter()
    for table in _collect(document, Table):
        rows = ([table.header] if table.header is not None else []) + list(table.rows)
        tables[(len(rows), max((len(row.cells) for row in rows), default=0))] += 1
        if table.caption:
            captions[" ".join(table.caption.split())] += 1
    for figure in _collect(document, Figure):
        if figure.caption:
            captions[" ".join(figure.caption.split())] += 1
    lists = Counter((bool(node.ordered), len(node.items)) for node in _collect(document, List))
    links = link_spans(document)
    return Inventory(nodes=nodes, headings=headings, tables=tables, lists=lists, links=links, captions=captions)


def link_spans(document: Any) -> Counter[str]:
    """Count a reading's links as spans of text, keyed by target URL.

    The PDF parser emits one ``Link`` per printed line, so a reference that wraps over three
    lines is three adjacent links to one URL. The DOCX parser reads adjacent hyperlink runs to
    one target back as a single link, which a count of ``Link`` nodes scores as two lost links
    when every URL and every word survived. Adjacent links to the same URL, separated by
    nothing but whitespace or line breaks, are therefore one span here. A link split by other
    text is two spans on both sides and is not merged.

    Parameters
    ----------
    document : Document
        A reading of one article.

    Returns
    -------
    Counter[str]
        Target URL of every link span.

    """
    from all2md.ast.nodes import LineBreak, Link, Node, Text

    spans: Counter[str] = Counter()
    for container in _collect(document, Node):
        content = getattr(container, "content", None)
        if isinstance(container, Link) or not isinstance(content, list):
            continue
        open_url: str | None = None
        for node in content:
            if isinstance(node, Link):
                if node.url != open_url:
                    spans[node.url] += 1
                open_url = node.url
            elif not (isinstance(node, LineBreak) or (isinstance(node, Text) and not node.content.strip())):
                open_url = None
    return spans


def _pairing(before: Counter[Any], after: Counter[Any]) -> dict[str, Any]:
    """Pair two multisets: how many survived, and examples of what was lost or gained."""
    lost = before - after
    gained = after - before
    return {
        "before": sum(before.values()),
        "after": sum(after.values()),
        "kept": sum((before & after).values()),
        "lost": sum(lost.values()),
        "gained": sum(gained.values()),
        "lost_examples": [_example(key) for key, _ in lost.most_common(EXAMPLES)],
        "gained_examples": [_example(key) for key, _ in gained.most_common(EXAMPLES)],
    }


def _example(key: Any) -> Any:
    if isinstance(key, str):
        return key[:EXAMPLE_CHARS]
    if isinstance(key, tuple):
        return [_example(part) for part in key]
    return key


def compare_inventories(before: Inventory, after: Inventory) -> dict[str, Any]:
    """Describe what a round trip did to a reading's structure.

    Headings are paired twice: by ``(level, text)``, which is what a reader navigating by
    outline sees, and by text alone, so a heading that survived at the wrong level is told
    apart from one that stopped being a heading.

    Parameters
    ----------
    before, after : Inventory
        The direct reading and the round-tripped one.

    Returns
    -------
    dict
        One pairing per structure, plus the node-type counts that moved.

    """
    heading_text_before = Counter(text for (_level, text), count in before.headings.items() for _ in range(count))
    heading_text_after = Counter(text for (_level, text), count in after.headings.items() for _ in range(count))
    moved = {
        name: {"before": before.nodes.get(name, 0), "after": after.nodes.get(name, 0)}
        for name in sorted(set(before.nodes) | set(after.nodes))
        if before.nodes.get(name, 0) != after.nodes.get(name, 0)
    }
    return {
        "headings": _pairing(before.headings, after.headings),
        "heading_text": _pairing(heading_text_before, heading_text_after),
        "tables": _pairing(before.tables, after.tables),
        "lists": _pairing(before.lists, after.lists),
        "links": _pairing(before.links, after.links),
        "captions": _pairing(before.captions, after.captions),
        "node_counts_moved": moved,
    }


def text_survival(before: str, after: str) -> dict[str, Any]:
    """Compare two readings' text to each other, with no ground truth involved.

    Counted n-grams rather than sets: a caption emitted twice is a set that has not moved
    and a multiset that has grown, and duplication is a real round-trip defect.

    Parameters
    ----------
    before, after : str
        Projected text of the direct and the round-tripped reading.

    Returns
    -------
    dict
        ``lost`` is the share of the direct reading's n-gram occurrences missing after the
        trip; ``added`` is the share of the round-tripped reading's occurrences the direct
        reading does not account for.

    """
    first = ngram_counts(normalize(before))
    second = ngram_counts(normalize(after))
    first_total = sum(first.values())
    second_total = sum(second.values())
    lost = sum((first - second).values())
    added = sum((second - first).values())
    return {
        "ngrams_before": first_total,
        "ngrams_after": second_total,
        "lost": lost / first_total if first_total else 0.0,
        "added": added / second_total if second_total else 0.0,
    }


def lost_blocks(
    truth: Sequence[tuple[str, str]],
    before: str,
    after: str,
    pdf_text: str,
) -> list[dict[str, str]]:
    """Return the attainable truth blocks the direct reading had and the round trip lost.

    The same containment rule `benchmarks.pmc.article.measure_recall` applies, per block, so
    every entry here is one block that moved the recall delta.

    Parameters
    ----------
    truth : Sequence[tuple[str, str]]
        ``(kind, text)`` ground-truth pairs.
    before, after, pdf_text : str
        Direct reading, round-tripped reading, and the PDF's own text layer.

    Returns
    -------
    list[dict]
        ``{"kind", "text"}`` for each lost block, text truncated for reading.

    """
    haystack_before = ngrams(normalize(before))
    haystack_after = ngrams(normalize(after))
    ceiling = ngrams(normalize(pdf_text))

    def contained(block: set[tuple[str, ...]], haystack: set[tuple[str, ...]]) -> bool:
        return len(block & haystack) / len(block) >= RECALL_MIN

    lost = []
    for kind, text in truth:
        block = ngrams(normalize(text))
        if len(block) < MIN_NGRAMS or not contained(block, ceiling):
            continue
        if contained(block, haystack_before) and not contained(block, haystack_after):
            lost.append({"kind": kind, "text": " ".join(text.split())[:EXAMPLE_CHARS]})
    return lost


@dataclass(frozen=True, slots=True)
class ArticleReading:
    """One article, parsed once and read through every route.

    Attributes
    ----------
    article_id : str
        Corpus article id.
    truth : tuple[tuple[str, str], ...]
        ``(kind, text)`` ground-truth pairs.
    pdf_text : str
        The PDF's own text layer.
    texts : Mapping[str, str]
        Projected text per route that completed.
    inventories : Mapping[str, Inventory]
        Structure per route that completed.
    errors : Mapping[str, str]
        Route -> error, for every route that raised. A PDF-parse failure is recorded under
        ``direct`` and leaves no route to score.
    seconds : Mapping[str, float]
        Wall time per stage: ``parse`` for the PDF, then one entry per round trip.
    docx_bytes : int
        Size of the rendered DOCX, or 0 when rendering failed.

    """

    article_id: str
    truth: tuple[tuple[str, str], ...]
    pdf_text: str
    texts: Mapping[str, str] = field(default_factory=dict)
    inventories: Mapping[str, Inventory] = field(default_factory=dict)
    errors: Mapping[str, str] = field(default_factory=dict)
    seconds: Mapping[str, float] = field(default_factory=dict)
    docx_bytes: int = 0


def read_article(article: Any, *, options: Any = None, keep_docx: Path | None = None) -> ArticleReading:
    """Parse one article's PDF once and read the AST through every route.

    Parameters
    ----------
    article : benchmarks.pmc.corpus.CorpusArticle
        Article with validated PDF and XML paths.
    options : PdfOptions or None
        PDF parser policy; defaults to `reparse_options`.
    keep_docx : pathlib.Path or None
        Directory to write the rendered DOCX into, so a reading can be opened in Word.

    Returns
    -------
    ArticleReading
        Every route's reading, or the errors that stopped them.

    """
    from all2md import from_ast, to_ast
    from benchmarks.omnidocbench.oracles import project_ast
    from benchmarks.pmc.benchmark import _pdf_facts
    from benchmarks.pmc.corpus import _parse_jats
    from benchmarks.pmc.oracles import project_jats

    root, _ = _parse_jats(article.xml_path.read_bytes())
    blocks, _whole = project_jats(root)
    truth = tuple((block.kind, block.text) for block in blocks if block.text)
    _pages, _words, pdf_text = _pdf_facts(article.pdf_path)

    texts: dict[str, str] = {}
    inventories: dict[str, Inventory] = {}
    errors: dict[str, str] = {}
    seconds: dict[str, float] = {}
    docx_bytes = 0

    started = time.perf_counter()
    try:
        document = to_ast(article.pdf_path, source_format="pdf", parser_options=options or reparse_options())
    except Exception as exc:  # noqa: BLE001 - a failed article stays in every denominator
        errors["direct"] = f"{type(exc).__name__}: {exc}"
        return ArticleReading(article.article_id, truth, pdf_text, errors=errors)
    seconds["parse"] = time.perf_counter() - started

    for route in ROUTES:
        started = time.perf_counter()
        try:
            if route == "docx":
                # Rendered here rather than through `via_docx` so the bytes can be sized and
                # kept; the parse half is the same call.
                rendered = from_ast(document, "docx")
                if not isinstance(rendered, bytes):
                    raise TypeError(f"DOCX renderer returned {type(rendered).__name__}, expected bytes")
                docx_bytes = len(rendered)
                if keep_docx is not None:
                    keep_docx.mkdir(parents=True, exist_ok=True)
                    (keep_docx / f"{article.article_id}.docx").write_bytes(rendered)
                reading = to_ast(rendered, source_format="docx")
            else:
                reading = ROUND_TRIPS[route](document)
            projection = project_ast(reading)
        except Exception as exc:  # noqa: BLE001 - a failed route is a ledger entry, not a crash
            errors[route] = f"{type(exc).__name__}: {exc}"
            continue
        texts[route] = " ".join(projection.text_blocks)
        inventories[route] = inventory(reading)
        seconds[route] = time.perf_counter() - started

    return ArticleReading(
        article_id=article.article_id,
        truth=truth,
        pdf_text=pdf_text,
        texts=texts,
        inventories=inventories,
        errors=errors,
        seconds=seconds,
        docx_bytes=docx_bytes,
    )


def _recall_summary(rows: Sequence[tuple[str, Sequence[tuple[str, str]], str, str]]) -> dict[str, Any]:
    recall = measure_recall(rows)
    precision = measure_precision(rows)
    return {
        "articles": len(rows),
        "attainable_recall": recall.attainable_recall,
        "by_kind": {kind: counts.attainable_recall for kind, counts in recall.by_kind.items()},
        "control_recall": recall.control_recall,
        "precision": precision.precision,
        "novel_share": precision.novel_share,
        "duplication": precision.duplication,
    }


def _sum_pairings(pairings: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for pairing in pairings:
        for key in ("before", "after", "kept", "lost", "gained"):
            totals[key] += pairing[key]
    return dict(totals)


def summarize_readings(readings: Sequence[ArticleReading]) -> dict[str, Any]:
    """Reduce article readings to the ledger payload.

    Truth recall and precision are computed over the articles **every** route completed, so
    the routes are compared on one denominator; an article a route failed on is listed
    under that route's failures instead.

    Parameters
    ----------
    readings : Sequence[ArticleReading]
        One reading per article.

    Returns
    -------
    dict
        Per-route truth scores, per-route structure and text deltas against ``direct``, and
        per-article detail.

    """
    complete = [reading for reading in readings if all(route in reading.texts for route in ROUTES)]
    truth = {
        route: _recall_summary(
            [(reading.article_id, reading.truth, reading.texts[route], reading.pdf_text) for reading in complete]
        )
        for route in ROUTES
    }
    for route in ROUTES[1:]:
        for name in ("attainable_recall", "novel_share"):
            truth[route][f"{name}_delta"] = truth[route][name] - truth["direct"][name]

    articles: list[dict[str, Any]] = []
    structure: dict[str, dict[str, list[Mapping[str, Any]]]] = {route: {} for route in ROUTES[1:]}
    survival: dict[str, list[Mapping[str, Any]]] = {route: [] for route in ROUTES[1:]}
    for reading in readings:
        entry: dict[str, Any] = {
            "article_id": reading.article_id,
            "errors": dict(reading.errors),
            "seconds": {name: round(value, 3) for name, value in reading.seconds.items()},
            "docx_bytes": reading.docx_bytes,
        }
        for route in ROUTES[1:]:
            if route not in reading.texts or "direct" not in reading.texts:
                continue
            compared = compare_inventories(reading.inventories["direct"], reading.inventories[route])
            text = text_survival(reading.texts["direct"], reading.texts[route])
            single = measure_recall(
                [(reading.article_id, reading.truth, reading.texts[route], reading.pdf_text)]
            ).attainable_recall
            direct = measure_recall(
                [(reading.article_id, reading.truth, reading.texts["direct"], reading.pdf_text)]
            ).attainable_recall
            lost = lost_blocks(reading.truth, reading.texts["direct"], reading.texts[route], reading.pdf_text)
            entry[route] = {
                "attainable_recall_delta": single - direct,
                "text": text,
                "structure": compared,
                "lost_blocks": lost[:EXAMPLES],
            }
            survival[route].append(text)
            for name, pairing in compared.items():
                if name != "node_counts_moved":
                    structure[route].setdefault(name, []).append(pairing)
        articles.append(entry)

    routes: dict[str, Any] = {}
    for route in ROUTES[1:]:
        texts = survival[route]
        routes[route] = {
            "truth": truth[route],
            "failures": sorted(reading.article_id for reading in readings if route in reading.errors),
            "text": {
                "lost": _weighted(texts, "lost", "ngrams_before"),
                "added": _weighted(texts, "added", "ngrams_after"),
            },
            "structure": {name: _sum_pairings(pairings) for name, pairings in structure[route].items()},
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "articles": len(readings),
        "articles_all_routes": len(complete),
        "parse_failures": sorted(reading.article_id for reading in readings if "direct" in reading.errors),
        "direct": truth["direct"],
        "routes": routes,
        "per_article": articles,
    }


def _weighted(rows: Sequence[Mapping[str, Any]], share: str, weight: str) -> float:
    total = sum(row[weight] for row in rows)
    return sum(row[share] * row[weight] for row in rows) / total if total else 0.0


def run(
    snapshot: Any,
    *,
    all2md_commit: str = "unknown",
    keep_docx: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Read a corpus snapshot through every route and build the ledger payload.

    Parameters
    ----------
    snapshot : benchmarks.pmc.corpus.CorpusSnapshot
        Pinned corpus to read.
    all2md_commit : str
        Commit being measured.
    keep_docx : pathlib.Path or None
        Directory to keep each rendered DOCX in.
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
    for index, article in enumerate(snapshot.articles):
        reading = read_article(article, keep_docx=keep_docx)
        readings.append(reading)
        if progress is not None:
            failed = f" errors={sorted(reading.errors)}" if reading.errors else ""
            progress(f"[{index + 1}/{len(snapshot.articles)}] {article.article_id}{failed}")
    readings.sort(key=lambda reading: reading.article_id)

    payload = summarize_readings(readings)
    payload["provenance"] = {
        "corpus_pin": snapshot.manifest_sha256,
        "manifest": str(snapshot.manifest_path),
        "all2md_commit": all2md_commit,
        "all2md_version": importlib.metadata.version("all2md"),
        "python": sys.version.split()[0],
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return payload
