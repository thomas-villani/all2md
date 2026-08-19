#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Export the held-out corpus article list (id, pdf, xml) as JSON for the baselines venv.

Runs in the project venv (needs ``benchmarks.pmc``). The baseline converters run in a
separate venv that has pymupdf4llm/docling but not this repository, so they read the
``articles.json`` this writes instead of importing anything from here.

The corpus must already be materialized: ``python -m benchmarks.pmc load --manifest
benchmarks/pmc/manifest-holdout.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from benchmarks.pmc import corpus  # noqa: E402

snapshot = corpus.load_corpus(
    REPO / "benchmarks" / "pmc" / ".cache",
    manifest_path=REPO / "benchmarks" / "pmc" / "manifest-holdout.json",
)
payload = {
    "manifest_sha256": snapshot.manifest_sha256,
    "complete": snapshot.complete,
    "articles": [
        {
            "article_id": article.article_id,
            "pdf_path": str(article.pdf_path),
            "xml_path": str(article.xml_path),
        }
        for article in snapshot.articles
    ],
}
out = HERE / "articles.json"
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"wrote {out} with {len(payload['articles'])} articles; complete={snapshot.complete}")
