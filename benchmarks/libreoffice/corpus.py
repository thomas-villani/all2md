"""Where the LibreOffice corpus lives, and the committed Word reading of it.

The corpus is LibreOffice's Writer regression data: every ``.docx`` under
``sw/qa/extras/ooxmlexport/data`` and ``sw/qa/extras/ooxmlimport/data`` in a checkout of
https://github.com/LibreOffice/core. It is never committed here -- a sparse, blob-less
clone of those two directories is enough, and the README gives the commands. Files are
keyed ``<set>/<name>``: ``export/tdf119143.docx``.

The Word reading is committed instead, as ``word_reading.json.gz``, because taking it
needs Microsoft Word. It records, per file, what Word shows (main story, notes, text-box
stories) together with the file's SHA-256, so a file that has changed since the reading
is recognized rather than scored against text from another version of it.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterator

LANE = Path(__file__).resolve().parent

#: The corpus sets, by the directory each one lives in under a LibreOffice core checkout.
SETS = {
    "export": "sw/qa/extras/ooxmlexport/data",
    "import": "sw/qa/extras/ooxmlimport/data",
}

#: The committed Word reading.
WORD_READING = LANE / "word_reading.json.gz"

#: Where all2md readings are written, one directory per label. Not committed.
CACHE = LANE / ".cache"

#: The environment variable naming the LibreOffice core checkout, when --core is not given.
CORE_ENV = "ALL2MD_LIBREOFFICE_CORE"


class CorpusError(Exception):
    """The corpus checkout or the Word reading cannot be used."""


def core_root(given: str | None) -> Path:
    """Return the LibreOffice core checkout named by ``--core`` or the environment."""
    value = given or os.environ.get(CORE_ENV)
    if not value:
        raise CorpusError(f"name the LibreOffice core checkout with --core or {CORE_ENV}")
    root = Path(value)
    missing = [directory for directory in SETS.values() if not (root / directory).is_dir()]
    if missing:
        raise CorpusError(f"{root} is not a LibreOffice core checkout with {', '.join(missing)}")
    return root


def core_commit(root: Path) -> str | None:
    """Return the checkout's commit, or None when it is not a git checkout."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def corpus_files(root: Path) -> Iterator[tuple[str, Path]]:
    """Yield ``(key, path)`` for every ``.docx`` in the corpus, sorted by key."""
    for set_name, directory in SETS.items():
        base = root / directory
        for path in sorted(base.iterdir()):
            if path.is_file() and path.suffix.lower() == ".docx":
                yield f"{set_name}/{path.name}", path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_name(key: str) -> str:
    """Return the file name a reading of ``key`` is stored under: ``export__tdf119143.docx.json``."""
    set_name, name = key.split("/", 1)
    return f"{set_name}__{name}.json"


def key_of(file_name: str) -> str:
    """Invert :func:`cache_name`. Only the first ``__`` is the separator; names may hold more."""
    set_name, name = file_name[: -len(".json")].split("__", 1)
    return f"{set_name}/{name}"


def load_word_reading(path: Path = WORD_READING) -> dict[str, Any]:
    """Load the Word reading: ``{"meta": {...}, "files": {key: record}}``."""
    if not path.exists():
        raise CorpusError(f"no Word reading at {path}; record one with `python -m benchmarks.libreoffice word`")
    with gzip.open(path, "rt", encoding="utf8") as handle:
        reading: dict[str, Any] = json.load(handle)
    if "meta" not in reading or "files" not in reading:
        raise CorpusError(f"{path} is not a Word reading")
    return reading


def save_word_reading(reading: dict[str, Any], path: Path = WORD_READING) -> None:
    """Write the Word reading, sorted and without a timestamp, so a re-record diffs by content."""
    data = json.dumps(reading, ensure_ascii=False, sort_keys=True, indent=0).encode("utf8")
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as handle:
        handle.write(data)
