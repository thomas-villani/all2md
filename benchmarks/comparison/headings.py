#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Score section headings across every tool, by structure rather than by text.

The lane's block instruments cannot see headings.  ``MIN_NGRAMS`` drops any block under
about eight words, which removes 87% of section headings, and lowering the floor does not
help: ``Introduction`` appears in any article's prose, so a containment test would read
near 100% for every tool and measure nothing.  What is left is *structure* -- a truth
heading counts as recovered only when the tool emitted a heading whose text is the same.

That rule needs no threshold, no floor, and no page attribution, so unlike reading order
and table structure it scores third-party output as readily as our own.

Two figures are reported because the whole-corpus one has a weak control by construction:
section headings come from a small shared vocabulary (``Introduction``, ``Discussion``,
``Funding``), so scoring an article against the wrong output still matches some.  The
subset restricted to headings appearing in fewer than ``COMMON_HEADING_ARTICLES`` articles
has a near-zero control and is the sharper number.

Usage: ``python benchmarks/comparison/headings.py [tool ...]`` (default: every directory
under ``out/``).  Reads the same ``articles.json`` and ``out/<tool>/`` layout as
``score.py``; run the converters first.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import fitz  # noqa: E402

from benchmarks.pmc import oracles  # noqa: E402
from benchmarks.pmc.alignment import normalize  # noqa: E402
from benchmarks.pmc.corpus import _parse_jats  # noqa: E402

#: An ATX heading line in a tool's markdown.  Every converter here emits ATX; a setext
#: heading would need adding, and its absence is why this reports emitted counts too --
#: a tool emitting none at all is visible rather than silently scoring zero.
ATX = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)

#: Ancestors that make a ``<title>`` something other than a section heading.  A reference's
#: ``<article-title>`` and a section's ``<title>`` are both kind ``title`` to the oracle,
#: and they are not the same claim about a converter.
NOT_A_HEADING = frozenset({"ref", "ref-list", "fig", "table-wrap", "front", "article-meta"})

#: A heading string appearing in at least this many articles is corpus vocabulary rather
#: than a property of one document, and is what keeps the whole-corpus control off zero.
COMMON_HEADING_ARTICLES = 5


def _headings(node: object, ancestors: frozenset[str] = frozenset()) -> list[str]:
    """Return the normalized text of every section heading under a JATS node."""
    tag = oracles._tag(node)
    if tag in oracles.SKIPPED:
        return []
    if oracles.BLOCKS.get(tag) == "title":
        if NOT_A_HEADING & ancestors:
            return []
        text = " ".join(normalize(oracles._own_text(node)))
        return [text] if text else []
    found: list[str] = []
    for child in node:  # type: ignore[attr-defined]
        found.extend(_headings(child, ancestors | {tag}))
    return found


def _emitted(markdown: str) -> set[str]:
    """Return the normalized text of every ATX heading in a tool's markdown."""
    return {" ".join(normalize(match.group(2))) for match in ATX.finditer(markdown)} - {""}


def main(argv: list[str] | None = None) -> int:
    """Score every requested tool's headings against the JATS section titles."""
    argv = sys.argv[1:] if argv is None else argv
    out_root = HERE / "out"
    tools = argv or sorted(directory.name for directory in out_root.iterdir() if directory.is_dir())
    articles = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))["articles"]

    truth: dict[str, set[str]] = {}
    printed: dict[str, set[str]] = {}
    for article in articles:
        root, _ = _parse_jats(Path(article["xml_path"]).read_bytes())
        wanted = set(_headings(root))
        if not wanted:
            continue
        truth[article["article_id"]] = wanted
        with fitz.open(article["pdf_path"]) as document:
            page = " ".join(normalize(" ".join(p.get_text() for p in document)))
        printed[article["article_id"]] = {heading for heading in wanted if heading in page}

    frequency: Counter[str] = Counter()
    for wanted in truth.values():
        frequency.update(wanted)
    rare = {heading for heading, seen in frequency.items() if seen < COMMON_HEADING_ARTICLES}

    total = sum(len(wanted) for wanted in truth.values())
    rare_total = sum(len(wanted & rare) for wanted in truth.values())
    print(
        f"{total:,} section headings across {len(truth)} articles; {rare_total:,} of them "
        f"appear in fewer than {COMMON_HEADING_ARTICLES} articles"
    )

    order = list(truth)
    for tool in tools:
        heads: dict[str, set[str]] = {}
        for article_id in order:
            markdown = out_root / tool / f"{article_id}.md"
            if markdown.exists():
                heads[article_id] = _emitted(markdown.read_text(encoding="utf-8"))
        if not heads:
            print(f"\n{tool}: no outputs yet")
            continue

        verdicts: Counter[str] = Counter()
        emitted = matched = control = rare_matched = rare_control = rare_seen = 0
        for index, article_id in enumerate(order):
            if article_id not in heads:
                continue
            wanted = truth[article_id]
            mine = heads[article_id]
            neighbour = heads.get(order[(index + 1) % len(order)], set())
            body = " ".join(normalize((out_root / tool / f"{article_id}.md").read_text(encoding="utf-8")))
            emitted += len(mine)
            matched += len(wanted & mine)
            control += len(wanted & neighbour)
            rare_seen += len(wanted & rare)
            rare_matched += len(wanted & rare & mine)
            rare_control += len(wanted & rare & neighbour)
            for heading in wanted:
                if heading in mine:
                    verdicts["recovered as a heading"] += 1
                elif heading not in printed[article_id]:
                    verdicts["the page never printed it"] += 1
                elif heading in body:
                    verdicts["emitted, but not as a heading"] += 1
                else:
                    verdicts["absent from the output"] += 1

        scored = sum(verdicts.values())
        on_page = scored - verdicts["the page never printed it"]
        print(f"\n{tool}  ({scored:,} truth headings, {emitted:,} headings emitted)")
        for kind, count in verdicts.most_common():
            print(f"   {kind:32s} {count:6,d} {count / scored:7.1%}")
        print(f"   {'-> share of PRINTED headings':32s} {verdicts['recovered as a heading'] / on_page:14.1%}")
        print(f"   {'-> precision of emitted headings':32s} {matched / emitted:14.1%}")
        print(f"   {'control: the WRONG article':32s} {control / scored:14.1%}")
        print(
            f"   {'rare headings only':32s} {rare_matched / rare_seen:14.1%}   control {rare_control / rare_seen:.1%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
