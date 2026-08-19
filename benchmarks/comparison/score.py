#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Score every tool's markdown output with the PMC lane's own instruments.

Runs in the project venv. Each tool's markdown -- all2md's included -- is re-parsed
through all2md's markdown parser and projected with the shared oracle, so every tool's
text goes through one normalization path. Ground truth and the attainable ceiling are
identical across tools by construction (JATS blocks, the PDF's own text layer).

Usage: ``python benchmarks/comparison/score.py [tool ...]`` (default: every directory
under ``out/``). Writes ``comparison.json``; copy it to a dated ``results-*.json`` when
publishing a reading.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import fitz  # noqa: E402

from all2md import to_ast  # noqa: E402
from benchmarks.omnidocbench.oracles import project_ast  # noqa: E402
from benchmarks.pmc.article import measure_precision, measure_recall  # noqa: E402
from benchmarks.pmc.corpus import _parse_jats  # noqa: E402
from benchmarks.pmc.oracles import project_jats  # noqa: E402

articles = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))["articles"]

print(f"preparing ground truth for {len(articles)} articles...", flush=True)
truth: dict[str, dict] = {}
for article in articles:
    root, _ = _parse_jats(Path(article["xml_path"]).read_bytes())
    blocks, _whole = project_jats(root)
    with fitz.open(article["pdf_path"]) as document:
        pdf_text = " ".join(page.get_text() for page in document)
    truth[article["article_id"]] = {
        "pairs": tuple((block.kind, block.text) for block in blocks if block.text),
        "pdf_text": pdf_text,
        "truth_tables": sum(1 for block in blocks if block.kind == "table"),
    }
print("ground truth ready", flush=True)

out_root = HERE / "out"
tools = sys.argv[1:] or sorted(d.name for d in out_root.iterdir() if d.is_dir())
report: dict[str, dict] = {}

for tool in tools:
    tool_dir = out_root / tool
    run_meta = {}
    run_path = tool_dir / "run.json"
    if run_path.exists():
        run_meta = json.loads(run_path.read_text(encoding="utf-8"))

    scored_rows = []
    per_article: dict[str, dict] = {}
    parse_failures: dict[str, str] = {}
    tables_emitted = 0
    truth_tables = 0
    raw_words = projected_words = 0
    for article in articles:
        article_id = article["article_id"]
        md_path = tool_dir / f"{article_id}.md"
        if not md_path.exists():
            continue
        raw = md_path.read_text(encoding="utf-8")
        try:
            document = to_ast(str(md_path), source_format="markdown")
            projection = project_ast(document)
        except Exception:
            parse_failures[article_id] = traceback.format_exc(limit=3)
            continue
        emitted_text = " ".join(projection.text_blocks)
        raw_words += len(raw.split())
        projected_words += len(emitted_text.split())
        entry = truth[article_id]
        tables_emitted += len(projection.tables)
        truth_tables += entry["truth_tables"]
        scored_rows.append((article_id, entry["pairs"], emitted_text, entry["pdf_text"]))
        single = measure_recall([(article_id, entry["pairs"], emitted_text, entry["pdf_text"])])
        per_article[article_id] = {
            "attainable_recall": single.attainable_recall,
            "tables_emitted": len(projection.tables),
            "tables_expected": entry["truth_tables"],
        }

    if not scored_rows:
        print(f"{tool}: no outputs yet", flush=True)
        continue

    recall = measure_recall(scored_rows)
    precision = measure_precision(scored_rows)
    timings = run_meta.get("timings", {})
    report[tool] = {
        "versions": run_meta.get("versions"),
        "articles_scored": len(scored_rows),
        "articles_missing": len(articles) - len(scored_rows) - len(parse_failures),
        "parse_failures": parse_failures,
        "conversion_failures": sorted(run_meta.get("failures", {})),
        "attainable_recall": recall.attainable_recall,
        "recall_raw": recall.recall,
        "ceiling": recall.ceiling,
        "by_kind": {
            kind: {"attainable_recall": counts.attainable_recall, "attainable": counts.attainable}
            for kind, counts in recall.by_kind.items()
        },
        "control_recall": recall.control_recall,
        "novel_share": precision.novel_share,
        "precision_raw": precision.precision,
        "duplication": precision.duplication,
        "tables_emitted": tables_emitted,
        "tables_expected": truth_tables,
        "seconds_per_article_mean": (sum(timings.values()) / len(timings)) if timings else None,
        # Words surviving the markdown->AST->projection path over raw markdown words.
        # Far below ~0.9 means the re-parse is eating content (e.g. raw HTML blocks) and
        # the tool's recall is understated -- investigate before quoting.
        "reparse_word_ratio": (projected_words / raw_words) if raw_words else None,
        "per_article": per_article,
    }
    title = recall.by_kind["title"].attainable_recall if "title" in recall.by_kind else float("nan")
    table = recall.by_kind["table"].attainable_recall if "table" in recall.by_kind else float("nan")
    print(
        f"{tool}: attainable_recall={recall.attainable_recall:.3f} "
        f"(title={title:.3f} table={table:.3f}) "
        f"novel={precision.novel_share:.4f} dup={precision.duplication:.4f} "
        f"tables {tables_emitted}/{truth_tables} n={len(scored_rows)}",
        flush=True,
    )

out = HERE / "comparison.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"wrote {out}")
