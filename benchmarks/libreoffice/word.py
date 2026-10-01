"""Record what Microsoft Word reads from each corpus file.

Windows only, with Word installed and ``pywin32`` available::

    uv run --with pywin32 python -m benchmarks.libreoffice word --core <checkout>

Word runs as a hidden, separate instance (``DispatchEx``), never the user's session, and
each file is opened read-only with repair off, so what is recorded is what Word makes of
the file as it is. Per file it keeps the main story (``Document.Content``), every
footnote and endnote, and the text of every top-level shape with a text frame.

Two things the reading cannot see, both of which show up as words all2md has and Word
does not: list labels (``1.``, ``a)``), which ``Range.Text`` leaves out, and text boxes
inside grouped shapes, which ``Document.Shapes`` does not descend into.

The run is resumable: each file's record is written to ``.cache/word/`` as it is read,
and only the files without one are opened. Before a file is opened its key is written to
``.cache/word/_inprogress``; if Word hangs on it, end the hidden ``WINWORD.EXE`` and run
again with ``--skip <key>`` (the file is recorded as a hang). When every file has a
record, they are packed into ``word_reading.json.gz`` with the date, the Word build, the
LibreOffice commit and each file's digest.
"""

from __future__ import annotations

import importlib
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

from benchmarks.libreoffice.corpus import CACHE, cache_name, core_commit, corpus_files, digest, save_word_reading

#: Where per-file Word records collect until they are packed.
PARTIAL = CACHE / "word"


def _story_texts(collection: Any) -> list[str]:
    return [str(collection(index).Range.Text) for index in range(1, collection.Count + 1)]


def _shape_texts(document: Any) -> list[str]:
    texts = []
    for index in range(1, document.Shapes.Count + 1):
        try:
            frame = document.Shapes(index).TextFrame
            if frame.HasText:
                texts.append(str(frame.TextRange.Text))
        except Exception:  # noqa: S112 - pictures, charts and other shapes have no text frame
            continue
    return texts


def _read_one(app: Any, path: Path) -> dict[str, Any]:
    start = time.time()
    try:
        document = app.Documents.Open(
            str(path.resolve()),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
            OpenAndRepair=False,
            NoEncodingDialog=True,
            PasswordDocument="x",  # an encrypted file fails instead of prompting
        )
        record: dict[str, Any] = {
            "status": "ok",
            "main": str(document.Content.Text),
            "footnotes": _story_texts(document.Footnotes),
            "endnotes": _story_texts(document.Endnotes),
            "shapes": _shape_texts(document),
        }
        document.Close(SaveChanges=0)
    except Exception as exc:
        record = {"status": "fail", "error": str(exc)[:300]}
    record["seconds"] = round(time.time() - start, 2)
    return record


def record(root: Path, skip: set[str]) -> dict[str, Any]:
    """Read every corpus file with Word, resuming from ``PARTIAL``, and pack the reading."""
    # Windows-only, and installed only for a recording; imported by name so type checks pass without it.
    win32com_client = importlib.import_module("win32com.client")

    PARTIAL.mkdir(parents=True, exist_ok=True)
    files = list(corpus_files(root))
    todo = [(key, path) for key, path in files if not (PARTIAL / cache_name(key)).exists()]
    print(f"{len(files)} files, {len(todo)} to read", flush=True)
    in_progress = PARTIAL / "_inprogress"

    app = win32com_client.DispatchEx("Word.Application")
    app.Visible = False
    app.DisplayAlerts = 0
    try:
        build = str(app.Build)
        for count, (key, path) in enumerate(todo, 1):
            if key in skip:
                result: dict[str, Any] = {"status": "hang"}
            else:
                in_progress.write_text(key, encoding="utf8")
                result = _read_one(app, path)
            (PARTIAL / cache_name(key)).write_text(json.dumps(result, ensure_ascii=False), encoding="utf8")
            if count % 50 == 0:
                print(f"{count}/{len(todo)}", flush=True)
    finally:
        in_progress.unlink(missing_ok=True)
        app.Quit(SaveChanges=0)

    reading: dict[str, Any] = {
        "meta": {
            "date": date.today().isoformat(),
            "word_build": build,
            "libreoffice_commit": core_commit(root),
        },
        "files": {},
    }
    for key, path in files:
        entry = json.loads((PARTIAL / cache_name(key)).read_text(encoding="utf8"))
        entry.pop("seconds", None)  # timing churns between runs and is not part of the reading
        entry["sha256"] = digest(path)
        reading["files"][key] = entry
    save_word_reading(reading)
    return reading
