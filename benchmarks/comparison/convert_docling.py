#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Convert every article with Docling at its defaults; dump markdown + timings.

Runs in the baselines venv (see baselines.txt), not the project venv. One
``DocumentConverter`` is reused across articles so model load is paid once. Defaults on
purpose, as with pymupdf4llm.

Windows note: the baselines venv must live at a SHORT path (e.g.
``C:/Users/<you>/AppData/Local/Temp/a2mbl``) -- transformers exceeds MAX_PATH under a
deep venv path and fails with a missing-file error that does not name the real cause.
A transient HF-hub symlink failure (WinError 1314) on the first model download heals on
rerun; the script skips articles it already converted.
"""

from __future__ import annotations

import importlib.metadata
import json
import time
import traceback
from pathlib import Path

from docling.document_converter import DocumentConverter

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "docling"
OUT.mkdir(parents=True, exist_ok=True)

articles = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))["articles"]

converter = DocumentConverter()
timings: dict[str, float] = {}
failures: dict[str, str] = {}
for index, article in enumerate(articles):
    article_id = article["article_id"]
    target = OUT / f"{article_id}.md"
    if target.exists():
        continue
    started = time.perf_counter()
    try:
        result = converter.convert(article["pdf_path"])
        markdown = result.document.export_to_markdown()
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
                "tool": "docling",
                "versions": {"docling": importlib.metadata.version("docling")},
                "settings": "defaults",
                "timings": timings,
                "failures": failures,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
print(f"done: {len(timings)} converted, {len(failures)} failed", flush=True)
