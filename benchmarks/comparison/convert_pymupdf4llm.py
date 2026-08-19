#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Convert every article with pymupdf4llm at its defaults; dump markdown + timings.

Runs in the baselines venv (see baselines.txt), not the project venv. Output:
``out/pymupdf4llm/<article_id>.md`` plus a ``run.json`` with versions, per-article
timing, and failures. Defaults on purpose: the comparison is against what a user of
each tool gets without tuning.
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import pymupdf
import pymupdf4llm

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "pymupdf4llm"
OUT.mkdir(parents=True, exist_ok=True)

articles = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))["articles"]

timings: dict[str, float] = {}
failures: dict[str, str] = {}
for index, article in enumerate(articles):
    article_id = article["article_id"]
    target = OUT / f"{article_id}.md"
    if target.exists():
        continue
    started = time.perf_counter()
    try:
        markdown = pymupdf4llm.to_markdown(article["pdf_path"])
    except Exception:
        failures[article_id] = traceback.format_exc(limit=3)
        print(f"[{index + 1}/{len(articles)}] {article_id} FAILED", flush=True)
        continue
    timings[article_id] = time.perf_counter() - started
    target.write_text(markdown, encoding="utf-8")
    print(f"[{index + 1}/{len(articles)}] {article_id} {timings[article_id]:.1f}s", flush=True)

    (OUT / "run.json").write_text(
        json.dumps(
            {
                "tool": "pymupdf4llm",
                "versions": {
                    "pymupdf4llm": pymupdf4llm.__version__,
                    "pymupdf": pymupdf.__doc__,
                },
                "settings": "defaults",
                "timings": timings,
                "failures": failures,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
print(f"done: {len(timings)} converted, {len(failures)} failed", flush=True)
