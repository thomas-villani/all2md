#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Convert every article with all2md into markdown files, like the other tools.

Runs in the project venv. Same parser policy as the PMC benchmark lane (layout analysis
on, OCR auto) except ``attachment_mode`` stays at its default so the markdown is not
bloated with base64 images -- images contribute no text to the instruments either way.

Output feeds ``score.py`` as the tool ``all2md``. This column exists for fairness, not
convenience: it puts all2md's own text through the same markdown re-parse the baselines
go through, so any loss on that path is charged to every tool equally (measured cost:
0.3pp of attainable recall, novel share unchanged).
"""

from __future__ import annotations

import importlib.metadata
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from all2md import to_markdown  # noqa: E402
from all2md.options.common import OCROptions  # noqa: E402
from all2md.options.pdf import PdfOptions  # noqa: E402

OUT = HERE / "out" / "all2md"
OUT.mkdir(parents=True, exist_ok=True)

articles = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))["articles"]

options = PdfOptions(
    layout_analysis_mode="enabled",
    ocr=OCROptions(enabled=True, mode="auto", engine="tesseract", languages="eng", dpi=200),
)

timings: dict[str, float] = {}
failures: dict[str, str] = {}
for index, article in enumerate(articles):
    article_id = article["article_id"]
    target = OUT / f"{article_id}.md"
    if target.exists():
        continue
    started = time.perf_counter()
    try:
        markdown = to_markdown(article["pdf_path"], parser_options=options)
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
                "tool": "all2md",
                "versions": {"all2md": importlib.metadata.version("all2md")},
                "settings": "lane policy (layout enabled, ocr auto); attachment_mode default",
                "timings": timings,
                "failures": failures,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
print(f"done: {len(timings)} converted, {len(failures)} failed", flush=True)
