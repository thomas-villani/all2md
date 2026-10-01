"""Read every corpus file with all2md and keep the text it found.

    python -m benchmarks.libreoffice sweep --core <checkout> --label main --jobs 2

Each file is parsed to the AST with the profile below, and every text-bearing node's
content is collected in document order, with a space at every node boundary so words in
neighboring blocks never run together. Math is collected separately as well, so the
comparison can mark a file whose differences may be notation rather than loss. The file
is then rendered to Markdown, so a renderer crash is caught too.

Records go to ``.cache/<label>/``, one per file, written as each file finishes, so an
interrupted sweep resumes where it stopped. A label is one reading of one all2md tree:
sweep a branch under one label and ``main`` under another, then compare the two.
"""

from __future__ import annotations

import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from benchmarks.libreoffice.corpus import CACHE, cache_name, corpus_files, digest, key_of

#: The parser profile. Word's text holds no comments, and ``Range.Text`` keeps a tracked
#: deletion's runs while revision marks are shown, so revisions are marked rather than
#: resolved: both sides then hold the deleted words.
PROFILE: dict[str, Any] = {"include_comments": False, "revisions": "mark"}


def _collect(node: Any, text: list[str], math: list[str]) -> None:
    from all2md.ast.nodes import Code, CodeBlock, MathBlock, MathInline, Text, get_node_children

    if isinstance(node, (Text, Code, CodeBlock)):
        text.append(node.content)
    elif isinstance(node, (MathInline, MathBlock)):
        math.append(str(node.content))
    text.append(" ")
    caption = getattr(node, "caption", None)
    if isinstance(caption, str):
        text.append(caption)
        text.append(" ")
    for child in get_node_children(node):
        _collect(child, text, math)


def read_one(path: Path) -> dict[str, Any]:
    """Return all2md's reading of one file: status, text, math, timing and any render error."""
    from all2md import to_markdown
    from all2md.options import DocxOptions
    from all2md.parsers.docx import DocxToAstConverter

    options = DocxOptions(**PROFILE)
    start = time.time()
    record: dict[str, Any]
    try:
        document = DocxToAstConverter(options=options).parse(path)
        text: list[str] = []
        math: list[str] = []
        _collect(document, text, math)
        record = {"status": "ok", "text": "".join(text), "math": math}
    except Exception as exc:
        record = {"status": "fail", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        record["traceback"] = traceback.format_exc()[-1500:]
    record["seconds"] = round(time.time() - start, 3)
    if record["status"] == "ok":
        try:
            to_markdown(path, parser_options=options)
        except Exception as exc:
            record["render_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    record["sha256"] = digest(path)
    return record


def sweep(root: Path, label: str, jobs: int = 2, only: set[str] | None = None) -> Path:
    """Read the corpus into ``.cache/<label>/``, resuming, and return that directory.

    ``only`` limits the sweep to those keys; a record already present is never redone, so
    re-reading a file means deleting its record first.
    """
    out = CACHE / label
    out.mkdir(parents=True, exist_ok=True)
    todo = [
        (key, path)
        for key, path in corpus_files(root)
        if (only is None or key in only) and not (out / cache_name(key)).exists()
    ]
    print(f"{label}: {len(todo)} files to read with {jobs} worker(s)", flush=True)
    if jobs <= 1:
        # In-process, so a debugger or a traceback reaches the parser directly.
        for key, path in todo:
            (out / cache_name(key)).write_text(json.dumps(read_one(path), ensure_ascii=False), encoding="utf8")
        return out
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        pending = {pool.submit(read_one, path): key for key, path in todo}
        for count, future in enumerate(as_completed(pending), 1):
            key = pending[future]
            (out / cache_name(key)).write_text(json.dumps(future.result(), ensure_ascii=False), encoding="utf8")
            if count % 100 == 0:
                print(f"{label}: {count}/{len(todo)}", flush=True)
    return out


def load_sweep(label_or_path: str) -> dict[str, dict[str, Any]]:
    """Load a sweep by label (under ``.cache``) or directory path, keyed like the corpus."""
    directory = Path(label_or_path)
    if not directory.is_dir():
        directory = CACHE / label_or_path
    if not directory.is_dir():
        raise FileNotFoundError(f"no sweep at {label_or_path} or {directory}")
    records = {}
    for path in sorted(directory.glob("*.json")):
        records[key_of(path.name)] = json.loads(path.read_text(encoding="utf8"))
    return records
