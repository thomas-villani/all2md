#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Split each tool's table loss into a content half and an order half, per truth table.

The lane's table figure is n-gram containment, and the scoring audit established what that
actually measures on tables: the median cell is two words and 69-83% of a truth table's
5-grams cross a cell boundary, so the figure is overwhelmingly *cell adjacency and reading
order*, not cell content.  Quoted alone it reads as "share of table content recovered",
which it is not.

So every table is scored twice against the same haystack.  **Multiset token containment**
ignores order entirely and says how many of the table's words reached the output at all;
multiset rather than set, so a table printing ``0.01`` nine times is not credited for
extracting it once.  **N-gram containment** is the published measure.  The difference
between them is the order tax, and reporting the pair is the whole point of this script --
a tool can only be charged for losing order once it is shown to have the words.

Three further readings fall out of the same pass and are printed with it:

* the per-table win/loss split, so a small mean gap is not mistaken for a uniform deficit
  when it is the net of two large opposing populations;
* whether a disagreement is *content* (the winner has words the loser lacks) or purely
  order (both have the words);
* row-count accuracy against the truth table's own row count, which is what separates
  all2md from docling on this corpus.  It is not sufficient on its own and the reading says
  so: pymupdf4llm gets more row counts right than all2md and still scores worst of the
  three, because a row count can be right while the cells inside it are cut wrongly.

Usage: ``python benchmarks/comparison/tablediag.py [tool ...]`` (default: every directory
under ``out/``).  Reads the same ``articles.json`` and ``out/<tool>/`` layout as
``score.py``; run the converters first.  Nothing is cached and nothing is written -- this
reads existing output and prints a reading.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import fitz  # noqa: E402

from all2md import to_ast  # noqa: E402
from benchmarks.omnidocbench.oracles import project_ast  # noqa: E402
from benchmarks.pmc.alignment import MIN_NGRAMS, ngrams, normalize  # noqa: E402
from benchmarks.pmc.corpus import _parse_jats  # noqa: E402
from benchmarks.pmc.oracles import project_jats  # noqa: E402

#: A truth table is only scored when the PDF's own text layer holds this share of its
#: n-grams.  Below it the words never reached the page's text layer and no tool could have
#: recovered them, so charging anyone would measure the corpus rather than the converters.
ATTAINABLE_MIN = 0.80

#: An n-gram containment difference this large is a decided table.  Smaller differences are
#: reported as ties rather than being counted toward either side, because a one-gram
#: difference on a short table is noise.
DECIDED_MARGIN = 0.10

#: A token-containment difference this large means the two tools genuinely hold different
#: words; below it a decided table is a pure ordering disagreement.
CONTENT_MARGIN = 0.05

#: A row count within this factor of the truth's counts as right.  Wide enough that a
#: header band counted differently is not charged, narrow enough to catch a table whose
#: wrapped lines all became rows.
ROW_TOLERANCE = 0.15

#: Permutation resamples for the article-clustering test.
RESAMPLES = 2000


def contained(need: Counter, have: Counter) -> float:
    """Share of a multiset that a haystack multiset covers.

    Parameters
    ----------
    need : Counter
        Token counts the truth table requires.
    have : Counter
        Token counts the tool's output holds.

    Returns
    -------
    float
        Covered share, or 0.0 for an empty requirement.

    """
    total = sum(need.values())
    return sum(min(count, have[token]) for token, count in need.items()) / total if total else 0.0


def pipe_grids(markdown: str) -> list[list[str]]:
    """Return the pipe-table blocks of a markdown document, as lists of lines.

    Row counts are taken from the raw markdown rather than from the parsed AST because a
    grid the AST rejects still tells us how the tool cut the page, and this measure is
    about the cut.
    """
    grids: list[list[str]] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line)
        elif current:
            grids.append(current)
            current = []
    if current:
        grids.append(current)
    return [grid for grid in grids if len(grid) >= 2]


def collect(tools: list[str]) -> list[dict]:
    """Score every attainable truth table on the corpus against every tool."""
    articles = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))["articles"]
    rows: list[dict] = []
    for number, article in enumerate(articles, start=1):
        article_id = article["article_id"]
        root, _ = _parse_jats(Path(article["xml_path"]).read_bytes())
        blocks, _ = project_jats(root)
        truth = [block for block in blocks if block.kind == "table" and block.text]
        if not truth:
            continue
        with fitz.open(article["pdf_path"]) as document:
            layer = ngrams(normalize(" ".join(page.get_text() for page in document)))

        hay: dict[str, dict[str, Any]] = {}
        for tool in tools:
            markdown_path = HERE / "out" / tool / f"{article_id}.md"
            if not markdown_path.exists():
                break
            markdown = markdown_path.read_text(encoding="utf-8")
            try:
                projection = project_ast(to_ast(str(markdown_path), source_format="markdown"))
            except Exception:  # noqa: BLE001 -- a tool whose markdown will not parse is skipped, not fatal
                break
            paired = list(zip(projection.text_blocks, projection.block_kinds, strict=False))
            in_table = " ".join(text for text, kind in paired if kind == "table")
            outside = " ".join(text for text, kind in paired if kind != "table")
            hay[tool] = {
                "grams": ngrams(normalize(in_table)) | ngrams(normalize(outside)),
                "tokens": Counter(normalize(in_table)) + Counter(normalize(outside)),
                "grids": pipe_grids(markdown),
            }
        if len(hay) != len(tools):
            continue  # every tool must have scored this article or it is not a comparison

        scored = []
        for block in truth:
            tokens = normalize(block.text)
            grams = ngrams(tokens)
            if len(grams) < MIN_NGRAMS or len(grams & layer) / len(grams) < ATTAINABLE_MIN:
                continue
            scored.append((block, tokens, grams))

        # Assign each emitted grid to the truth table it shares most tokens with, then sum
        # that table's rows across every grid assigned to it.  Matching a truth table to
        # its single best grid instead would report every table continued across a page
        # break as an over-split one.
        wanted = {index: set(tokens) for index, (_, tokens, _) in enumerate(scored)}
        assigned: dict[str, dict[int, list[int]]] = {}
        for tool, bag in hay.items():
            counts = {index: [0, 0] for index in wanted}
            for grid in bag["grids"]:
                grid_tokens = set(normalize(" ".join(cell for line in grid for cell in line.split("|"))))
                best, overlap = None, 0.25
                for index, need in wanted.items():
                    share = len(need & grid_tokens) / len(need) if need else 0.0
                    if share > overlap:
                        best, overlap = index, share
                if best is not None:
                    # Every line but the alignment separator is a printed row.
                    counts[best][0] += len(grid) - 1
                    counts[best][1] += 1
            assigned[tool] = counts

        for index, (block, tokens, grams) in enumerate(scored):
            required = Counter(tokens)
            row = {
                "article": article_id,
                "words": len(tokens),
                "rows": block.table.rows if block.table else 0,
                "columns": block.table.columns if block.table else 0,
            }
            for tool, bag in hay.items():
                emitted, grids = assigned[tool][index]
                row[tool] = {
                    "ngram": len(grams & bag["grams"]) / len(grams),
                    "token": contained(required, bag["tokens"]),
                    "emitted_rows": emitted,
                    "grids": grids,
                }
            rows.append(row)
        print(f"  {number}/{len(articles)} {article_id}", end="\r", flush=True)
    print(" " * 60, end="\r")
    return rows


def row_verdict(row: dict, tool: str) -> str:
    """How a tool's row count for one truth table compares with the truth's."""
    truth_rows = row["rows"]
    if not row[tool]["grids"]:
        return "no grid"
    if not truth_rows:
        return "no truth rows"
    ratio = row[tool]["emitted_rows"] / truth_rows
    if ratio > 1 + ROW_TOLERANCE:
        return "over-split"
    if ratio < 1 - ROW_TOLERANCE:
        return "over-merged"
    return "right"


def clustering(rows: list[dict], first: str, second: str) -> tuple[float, float, float]:
    """Within-article agreement of the win direction, against a permutation null.

    A handful of articles carrying many tables would manufacture apparent clustering on
    their own, so the observed agreement is only meaningful beside a null that reshuffles
    the same verdicts across the same article sizes.

    Returns
    -------
    tuple of (float, float, float)
        Observed agreement, mean agreement under the null, and the share of resamples
        reaching the observed value.

    """
    leaning: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        delta = row[second]["ngram"] - row[first]["ngram"]
        if abs(delta) > DECIDED_MARGIN:
            leaning[row["article"]].append(1 if delta > 0 else -1)
    multi = {key: value for key, value in leaning.items() if len(value) > 1}
    if not multi:
        return 0.0, 0.0, 1.0

    def agreement(groups: dict[str, list[int]]) -> float:
        total = sum(len(value) for value in groups.values())
        return sum(len(value) for value in groups.values() if len(set(value)) == 1) / total

    observed = agreement(multi)
    labels = [value for values in multi.values() for value in values]
    random.seed(0)
    null = []
    for _ in range(RESAMPLES):
        random.shuffle(labels)
        shuffled, cursor = {}, 0
        for key, values in multi.items():
            shuffled[key] = labels[cursor : cursor + len(values)]
            cursor += len(values)
        null.append(agreement(shuffled))
    return observed, statistics.mean(null), sum(1 for value in null if value >= observed) / len(null)


def main() -> int:
    tools = sys.argv[1:] or sorted(path.name for path in (HERE / "out").iterdir() if path.is_dir())
    rows = collect(tools)
    if not rows:
        print("no attainable truth tables scored -- run the converters first")
        return 1

    print(f"{len(rows):,} attainable truth tables\n")
    print("=== content or order? ===\n")
    print(f"{'tool':16s} {'n-gram':>9s} {'token':>9s} {'order tax':>11s}")
    for tool in tools:
        gram = statistics.mean(row[tool]["ngram"] for row in rows)
        token = statistics.mean(row[tool]["token"] for row in rows)
        print(f"{tool:16s} {gram:9.3f} {token:9.3f} {token - gram:+11.3f}")
    print("\n  Token containment is order-free: a tool at ceiling there has every word and")
    print("  loses only arrangement.  The published table figure is the n-gram column.\n")

    print("=== row-count accuracy against the truth's own row count ===\n")
    for tool in tools:
        verdicts = Counter(row_verdict(row, tool) for row in rows)
        total = sum(verdicts.values())
        summary = "  ".join(f"{kind} {count} ({count / total:.0%})" for kind, count in sorted(verdicts.items()))
        print(f"  {tool:16s} {summary}")

    if len(tools) < 2:
        return 0
    first = "all2md" if "all2md" in tools else tools[0]
    for second in tools:
        if second == first:
            continue
        print(f"\n=== {first} against {second}, table by table ===\n")
        wins: dict[int, list[dict]] = {value: [] for value in (1, 0, -1)}
        for row in rows:
            delta = row[second]["ngram"] - row[first]["ngram"]
            wins[1 if delta > DECIDED_MARGIN else -1 if delta < -DECIDED_MARGIN else 0].append(row)
        for value, label in ((1, f"{second} wins"), (-1, f"{first} wins")):
            subset = wins[value]
            if not subset:
                continue
            winner, loser = (second, first) if value == 1 else (first, second)
            order_only = [row for row in subset if abs(row[second]["token"] - row[first]["token"]) <= CONTENT_MARGIN]
            content = [row for row in subset if row[winner]["token"] - row[loser]["token"] > CONTENT_MARGIN]
            print(f"  {label:22s} {len(subset):3d} tables")
            print(f"    same words, different order {len(order_only):3d} ({len(order_only) / len(subset):.0%})")
            print(f"    the winner has words the loser lacks {len(content):3d}")
            verdicts = Counter(row_verdict(row, first) for row in subset)
            print(f"    {first} row count: " + "  ".join(f"{k} {v}" for k, v in sorted(verdicts.items())))
        print(f"  {'ties':22s} {len(wins[0]):3d} tables")

        observed, null, probability = clustering(rows, first, second)
        print(
            f"\n  within-article agreement of the win direction {observed:.1%}"
            f" against a {null:.1%} permutation null (p = {probability:.3f})"
        )
        verdict = "the disagreement is article-level" if probability < 0.05 else "not distinguishable from scatter"
        print(f"  -> {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
