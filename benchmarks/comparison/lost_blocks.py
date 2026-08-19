#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Name the truth blocks a baseline recovers that all2md loses, and sketch why.

For each article: a block counts as LOST if it is attainable (contained in the PDF's own
text layer), contained in the baseline's output, and NOT contained in all2md's output --
all at the instruments' own ``RECALL_MIN`` threshold. Writes ``lost_blocks.json`` with
every lost block (article, kind, text) plus the all2md containment score so near-misses
are visible: a block at share 0.6 was shredded, a block at share 0.0 never made it out.

This is the diff that turned the 2026-08-19 reading into issues #405 (side-by-side
regions interleaved line-by-line) and #406 (figure captions absent entirely).

Usage: ``python benchmarks/comparison/lost_blocks.py [baseline]`` (default:
``pymupdf4llm``; any tool directory under ``out/`` works).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import fitz  # noqa: E402

from all2md import to_ast  # noqa: E402
from benchmarks.omnidocbench.oracles import project_ast  # noqa: E402
from benchmarks.pmc.alignment import MIN_NGRAMS, ngrams, normalize  # noqa: E402
from benchmarks.pmc.article import RECALL_MIN  # noqa: E402
from benchmarks.pmc.corpus import _parse_jats  # noqa: E402
from benchmarks.pmc.oracles import project_jats  # noqa: E402

articles = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))["articles"]
baseline = sys.argv[1] if len(sys.argv) > 1 else "pymupdf4llm"


def emitted_ngrams(tool: str, article_id: str) -> set:
    md_path = HERE / "out" / tool / f"{article_id}.md"
    projection = project_ast(to_ast(str(md_path), source_format="markdown"))
    return ngrams(normalize(" ".join(projection.text_blocks)))


lost: list[dict] = []
kind_counts: Counter[str] = Counter()
article_counts: Counter[str] = Counter()
for article in articles:
    article_id = article["article_id"]
    root, _ = _parse_jats(Path(article["xml_path"]).read_bytes())
    blocks, _whole = project_jats(root)
    with fitz.open(article["pdf_path"]) as document:
        ceiling = ngrams(normalize(" ".join(page.get_text() for page in document)))
    ours = emitted_ngrams("all2md", article_id)
    theirs = emitted_ngrams(baseline, article_id)
    for block in blocks:
        if not block.text:
            continue
        grams = ngrams(normalize(block.text))
        if len(grams) < MIN_NGRAMS:
            continue
        if len(grams & ceiling) / len(grams) < RECALL_MIN:
            continue  # not attainable; nobody is charged for it
        ours_share = len(grams & ours) / len(grams)
        theirs_share = len(grams & theirs) / len(grams)
        if theirs_share >= RECALL_MIN and ours_share < RECALL_MIN:
            kind_counts[block.kind] += 1
            article_counts[article_id] += 1
            lost.append(
                {
                    "article_id": article_id,
                    "kind": block.kind,
                    "all2md_share": round(ours_share, 3),
                    f"{baseline}_share": round(theirs_share, 3),
                    "text": block.text[:400],
                }
            )
    print(f"{article_id}: cumulative lost={len(lost)}", flush=True)

(HERE / "lost_blocks.json").write_text(
    json.dumps(
        {
            "definition": f"attainable + recovered by {baseline} + not recovered by all2md, at RECALL_MIN",
            "total": len(lost),
            "by_kind": dict(kind_counts.most_common()),
            "by_article_top": dict(article_counts.most_common(15)),
            "blocks": lost,
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
print(f"total lost blocks: {len(lost)}; by kind: {dict(kind_counts)}")
