"""Compare one conversion against the Word document its PDF was exported from.

Every number answers a question a person converting a contract would ask: did my clauses stay
separate clauses, is my table still a table, is the page footer still a footer and not a line
in the middle of clause 4? Words are aligned first, then each structure is judged by where its
words landed, so a marker typed into the text or a stray footnote digit cannot hide a result.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from benchmarks.pdfword.reading import Paragraph, Reading, Table

_WORD = re.compile(r"\w+", re.UNICODE)
#: "1.", "1.1", "1.1.2", "(a)", "a)", "(iv)", or a bullet, at the start of a paragraph.
_LEADING_MARKER = re.compile(r"^\s*(?:\(?[A-Za-z]{1,4}\)|\(?\d+\)|\d+(?:\.\d+)*\.?|[•●–-])\s+")
_DIGITS = re.compile(r"\d+")
#: Word reports a different private-use glyph per bullet font; they all print as a bullet.
_BULLETS = {"•", "", "●", "", "o", "-", "–"}

#: A paragraph this short has too few words to say where it went.
MIN_PARAGRAPH_WORDS = 4
#: This share of a paragraph's words must align somewhere, or it counts as missing.
FOUND_SHARE = 0.6
#: This share in one target block means the paragraph stayed in one piece.
WHOLE_SHARE = 0.9
#: Words from another paragraph in the same target before calling it a merge.
MERGE_WORDS = 3
#: Words a line may have beyond a page header or footer and still count as that header or footer.
FURNITURE_EXTRA_WORDS = 2
#: Page geometry within this many points counts as the same.
GEOMETRY_TOLERANCE = 3.0


def words(text: str) -> list[str]:
    """Return the lowercase word tokens of a string."""
    return [token.lower() for token in _WORD.findall(text)]


def strip_marker(text: str) -> str:
    """Remove a leading list marker, which conversions may keep as typed text."""
    return _LEADING_MARKER.sub("", text, count=1)


def _key(text: str) -> str:
    return " ".join(words(strip_marker(text)))


def _pair(truth: int, kept: int, **extra: Any) -> dict[str, Any]:
    return {"truth": truth, "kept": kept, "lost": truth - kept, **extra}


def _stream(reading: Reading) -> tuple[list[str], list[int]]:
    """Return every body word, and the index of the block each one belongs to."""
    tokens: list[str] = []
    owners: list[int] = []
    for index, block in enumerate(reading.blocks):
        pieces = [cell for row in block.rows for cell in row] if isinstance(block, Table) else [block.text]
        for piece in pieces:
            found = words(piece)
            tokens.extend(found)
            owners.extend([index] * len(found))
    return tokens, owners


def _align(truth: Reading, got: Reading) -> dict[str, Any]:
    """Pair up the two word streams in order."""
    truth_tokens, truth_owner = _stream(truth)
    got_tokens, got_owner = _stream(got)
    matcher = difflib.SequenceMatcher(None, truth_tokens, got_tokens, autojunk=False)
    landed: dict[int, Counter[int]] = {}
    sources: dict[int, Counter[int]] = {}
    matched = 0
    for match in matcher.get_matching_blocks():
        for offset in range(match.size):
            source, target = truth_owner[match.a + offset], got_owner[match.b + offset]
            landed.setdefault(source, Counter())[target] += 1
            sources.setdefault(target, Counter())[source] += 1
            matched += 1
    return {
        "landed": landed,
        "sources": sources,
        "matched": matched,
        "truth_words": len(truth_tokens),
        "got_words": len(got_tokens),
    }


def _boundaries(truth: Reading, alignment: dict[str, Any]) -> tuple[dict[str, Any], dict[int, int], dict[int, str]]:
    """Judge whether each paragraph stayed one paragraph. Returns the tally, targets and each outcome."""
    tally: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    targets: dict[int, int] = {}
    outcomes: dict[int, str] = {}
    for index, block in enumerate(truth.blocks):
        if not isinstance(block, Paragraph) or not words(block.text):
            continue
        size = len(words(block.text))
        landed: Counter[int] = alignment["landed"].get(index, Counter())
        total = sum(landed.values())
        # A short paragraph still gets an outcome, because a list item can be one word long.
        # It says too little about where text goes to count in the paragraph tally.
        if size < MIN_PARAGRAPH_WORDS:
            if total == size:
                target = landed.most_common(1)[0][0]
                targets[index] = target
                others = sum(n for source, n in alignment["sources"][target].items() if source != index)
                outcomes[index] = "merged" if others >= MERGE_WORDS else "whole"
            continue
        if total < size * FOUND_SHARE:
            outcome = "missing"
        else:
            target, count = landed.most_common(1)[0]
            targets[index] = target
            if count < total * WHOLE_SHARE:
                outcome = "split"
            else:
                others = sum(n for source, n in alignment["sources"][target].items() if source != index)
                outcome = "merged" if others >= MERGE_WORDS else "whole"
        tally[outcome] += 1
        outcomes[index] = outcome
        if outcome != "whole":
            examples.setdefault(outcome, [])
            if len(examples[outcome]) < 3:
                examples[outcome].append(block.text[:70])
    counted = sum(tally.values())
    return (
        {
            "truth": counted,
            "whole": tally["whole"],
            "merged": tally["merged"],
            "split": tally["split"],
            "missing": tally["missing"],
            "examples": examples,
        },
        targets,
        outcomes,
    )


def _dense(levels: Iterable[int]) -> dict[int, int]:
    return {level: rank for rank, level in enumerate(sorted(set(levels)))}


def _headings(truth: Reading, got: Reading) -> dict[str, Any]:
    wanted = [p for p in truth.paragraphs if p.level is not None and _key(p.text)]
    found = [p for p in got.paragraphs if p.level is not None and _key(p.text)]
    by_text: dict[str, list[Paragraph]] = {}
    for paragraph in found:
        by_text.setdefault(_key(paragraph.text), []).append(paragraph)
    pairs: list[tuple[int, int]] = []
    lost: list[str] = []
    for paragraph in wanted:
        matches = by_text.get(_key(paragraph.text))
        if not matches:
            lost.append(paragraph.text[:60])
            continue
        pairs.append((paragraph.level or 0, matches.pop(0).level or 0))
    # Ranks among the headings both sides have, so one lost title doesn't shift every later level.
    truth_ranks, got_ranks = _dense(a for a, _ in pairs), _dense(b for _, b in pairs)
    kept = len(pairs)
    level_kept = sum(truth_ranks[a] == got_ranks[b] for a, b in pairs)
    spurious = [p.text[:60] for remaining in by_text.values() for p in remaining]
    return _pair(len(wanted), kept, level_kept=level_kept, spurious=len(spurious), lost_examples=lost[:3])


def _marker_key(marker: str) -> str:
    stripped = marker.strip()
    return "bullet" if stripped in _BULLETS else stripped


def _lists(truth: Reading, got: Reading, targets: dict[int, int], outcomes: dict[int, str]) -> dict[str, Any]:
    items = whole = real = printed = level = 0
    for index, block in enumerate(truth.blocks):
        if not isinstance(block, Paragraph) or block.marker is None or not block.marker.strip():
            continue
        items += 1
        target = targets.get(index)
        found = got.blocks[target] if target is not None else None
        if not isinstance(found, Paragraph):
            continue
        whole += outcomes.get(index) == "whole"
        wanted = _marker_key(block.marker)
        if found.marker is not None and found.marker.strip():
            real += 1
            printed += _marker_key(found.marker) == wanted
            level += found.list_level == block.list_level
        elif found.text.strip().startswith(block.marker.strip()) or wanted == "bullet":
            printed += found.text.strip()[:1] in _BULLETS if wanted == "bullet" else 1
    return {"truth": items, "own_paragraph": whole, "real_numbering": real, "marker_printed": printed, "level": level}


def _cells(table: Table) -> dict[tuple[int, int], str]:
    return {
        (r, c): key for r, row in enumerate(table.rows) for c, cell in enumerate(row) if (key := " ".join(words(cell)))
    }


def _tables(truth: Reading, got: Reading) -> dict[str, Any]:
    found = list(got.tables)
    exact_shape = cells_truth = cells_right = paired = 0
    lost_shapes: list[tuple[int, int]] = []
    wrong_shapes: list[dict[str, Any]] = []
    for table in truth.tables:
        cells = _cells(table)
        cells_truth += len(cells)
        wanted = Counter(token for text in cells.values() for token in text.split())
        best, best_overlap = None, 0
        if not cells:
            # A blank comment box has no words to match on, so only its shape can identify it.
            blank = next((c for c in found if c.shape == table.shape and not _cells(c)), None)
            if blank is None:
                lost_shapes.append(table.shape)
                continue
            found.remove(blank)
            paired += 1
            exact_shape += 1
            continue
        for candidate in found:
            have = Counter(token for text in _cells(candidate).values() for token in text.split())
            overlap = sum((wanted & have).values())
            if overlap > best_overlap:
                best, best_overlap = candidate, overlap
        # Half the words must agree: an empty form grid has few, so the labels decide it.
        if best is None or best_overlap < max(1, sum(wanted.values()) // 2):
            lost_shapes.append(table.shape)
            continue
        found.remove(best)
        paired += 1
        if best.shape == table.shape:
            exact_shape += 1
        else:
            wrong_shapes.append({"truth": table.shape, "got": best.shape})
        have_cells = _cells(best)
        cells_right += sum(have_cells.get(position) == text for position, text in cells.items())
    return {
        "truth": len(truth.tables),
        "found": paired,
        "lost": lost_shapes,
        "exact_shape": exact_shape,
        "wrong_shape": wrong_shapes,
        "cells_truth": cells_truth,
        "cells_right": cells_right,
        "spurious": len(found),
    }


def _contains(body: Sequence[str], text: str) -> int:
    return sum(1 for paragraph in body if text and text in paragraph)


def _footnotes(truth: Reading, got: Reading, body: Sequence[str]) -> dict[str, Any]:
    wanted = [" ".join(words(note)) for note in truth.footnotes]
    have = [" ".join(words(note)) for note in got.footnotes]
    kept = sum(1 for note in wanted if any(note and note in other for other in have))
    leaked = sum(1 for note in wanted if _contains(body, note))
    return _pair(len(wanted), kept, leaked_into_body=leaked)


def _strip_digits(text: str) -> str:
    return " ".join(words(_DIGITS.sub(" ", text)))


def _furniture(truth: tuple[str, ...], got: tuple[str, ...], body: Sequence[str]) -> dict[str, Any]:
    """Judge page headers or footers. Digits go first, because a page number changes per page."""
    wanted = [text for text in {_strip_digits(item) for item in truth} if text]
    have = [_strip_digits(item) for item in got]
    bare = [_strip_digits(paragraph) for paragraph in body]
    kept = sum(1 for text in wanted if any(text in other for other in have))
    # A leaked line is the header itself. "CONFIDENTIAL" must not match a clause about
    # "Confidential Information", so the line can't be much longer than what it repeats.
    leaked = sum(
        1
        for text in wanted
        for line in bare
        if text in line and len(line.split()) <= len(text.split()) + FURNITURE_EXTRA_WORDS
    )
    return _pair(len(wanted), kept, leaked_lines_in_body=leaked)


def _page(truth: Reading, got: Reading) -> dict[str, Any]:
    close = GEOMETRY_TOLERANCE
    size = abs(truth.page_width - got.page_width) <= close and abs(truth.page_height - got.page_height) <= close
    margins = all(abs(a - b) <= close for a, b in zip(truth.margins, got.margins, strict=True))
    total = sum(len(words(p.text)) for p in got.paragraphs)
    return {
        "pages": {"truth": truth.pages, "got": got.pages},
        "size_matches": size,
        "margins_match": margins,
        "columns": {"truth": truth.columns, "got": got.columns},
        "body_font": {"truth": truth.body_font, "got": got.body_font},
        "body_font_matches": truth.body_font.lower() == got.body_font.lower(),
        "body_size_matches": abs(truth.body_size - got.body_size) < 0.51,
        "float_word_share": round(got.float_words / total, 3) if total else 0.0,
    }


def score(truth: Reading, got: Reading) -> dict[str, Any]:
    """Score one conversion against its truth.

    Parameters
    ----------
    truth : Reading
        Word's reading of the source document.
    got : Reading
        Word's reading of the conversion.

    Returns
    -------
    dict
        One entry per structure. Nothing here is a pass or a fail: it is a ledger.

    """
    alignment = _align(truth, got)
    boundaries, targets, outcomes = _boundaries(truth, alignment)
    body = [" ".join(words(p.text)) for p in got.paragraphs]
    raw_body = [p.text for p in got.paragraphs]
    return {
        "text": {
            "truth_words": alignment["truth_words"],
            "got_words": alignment["got_words"],
            "in_order": alignment["matched"],
            "recall": round(alignment["matched"] / alignment["truth_words"], 4) if alignment["truth_words"] else 1.0,
        },
        "paragraphs": boundaries,
        "headings": _headings(truth, got),
        "lists": _lists(truth, got, targets, outcomes),
        "tables": _tables(truth, got),
        "footnotes": _footnotes(truth, got, body),
        "headers": _furniture(truth.headers, got.headers, raw_body),
        "footers": _furniture(truth.footers, got.footers, raw_body),
        "pictures": _pair(truth.pictures, min(truth.pictures, got.pictures), got=got.pictures),
        "page": _page(truth, got),
    }


def is_perfect(result: dict[str, Any]) -> list[str]:
    """Return what keeps a result from being a perfect score. A document scored against itself must return nothing."""
    problems = []
    if result["text"]["recall"] < 1.0:
        problems.append("text")
    paragraphs = result["paragraphs"]
    if paragraphs["whole"] != paragraphs["truth"]:
        problems.append("paragraphs")
    headings = result["headings"]
    if headings["lost"] or headings["spurious"] or headings["level_kept"] != headings["kept"]:
        problems.append("headings")
    lists = result["lists"]
    if not lists["truth"] == lists["own_paragraph"] == lists["real_numbering"] == lists["marker_printed"]:
        problems.append("lists")
    tables = result["tables"]
    if tables["lost"] or tables["wrong_shape"] or tables["cells_right"] != tables["cells_truth"]:
        problems.append("tables")
    if result["footnotes"]["lost"]:
        problems.append("footnotes")
    if result["headers"]["lost"] or result["footers"]["lost"]:
        problems.append("furniture")
    if result["pictures"]["lost"]:
        problems.append("pictures")
    return problems


def summarize(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Add up one tool's results across cases."""
    total: dict[str, int] = Counter()
    rows = list(results)
    for result in rows:
        text, paragraphs, headings = result["text"], result["paragraphs"], result["headings"]
        lists, tables, notes = result["lists"], result["tables"], result["footnotes"]
        page = result["page"]
        total.update(
            {
                "words": text["truth_words"],
                "words_in_order": text["in_order"],
                "paragraphs": paragraphs["truth"],
                "paragraphs_whole": paragraphs["whole"],
                "paragraphs_merged": paragraphs["merged"],
                "paragraphs_split": paragraphs["split"],
                "paragraphs_missing": paragraphs["missing"],
                "headings": headings["truth"],
                "headings_kept": headings["kept"],
                "headings_level_kept": headings["level_kept"],
                "headings_spurious": headings["spurious"],
                "list_items": lists["truth"],
                "list_items_own_paragraph": lists["own_paragraph"],
                "list_items_real": lists["real_numbering"],
                "list_markers_printed": lists["marker_printed"],
                "tables": tables["truth"],
                "tables_found": tables["found"],
                "tables_exact_shape": tables["exact_shape"],
                "cells": tables["cells_truth"],
                "cells_right": tables["cells_right"],
                "footnotes": notes["truth"],
                "footnotes_kept": notes["kept"],
                "footnotes_leaked": notes["leaked_into_body"],
                "furniture": result["headers"]["truth"] + result["footers"]["truth"],
                "furniture_kept": result["headers"]["kept"] + result["footers"]["kept"],
                "furniture_leaked_lines": (
                    result["headers"]["leaked_lines_in_body"] + result["footers"]["leaked_lines_in_body"]
                ),
                "pictures": result["pictures"]["truth"],
                "pictures_kept": result["pictures"]["kept"],
                "pages_truth": page["pages"]["truth"],
                "pages_got": page["pages"]["got"],
                "documents": 1,
                "page_size_matches": page["size_matches"],
                "margins_match": page["margins_match"],
                "body_font_matches": page["body_font_matches"],
                "body_size_matches": page["body_size_matches"],
            }
        )
    return dict(total)
