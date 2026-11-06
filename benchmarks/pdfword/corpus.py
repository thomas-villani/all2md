"""Load the committed corpus and refuse anything that does not match the manifest.

No COM, no Word, no network. A truth record that has drifted away from its document produces
confident numbers about a document nobody described, so every file is checked by digest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmarks.pdfword.reading import Reading

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
MANIFEST_SCHEMA_VERSION = 1


class CorpusError(RuntimeError):
    """The committed corpus does not match its manifest."""


@dataclass(frozen=True)
class Case:
    """One scripted document and its files."""

    case_id: str
    family: str
    name: str
    control: bool
    source: Path
    tagged: Path
    untagged: Path
    truth_path: Path

    def truth(self) -> Reading:
        """Return Word's reading of the source document, recorded when it was generated."""
        return Reading.from_json(json.loads(self.truth_path.read_text(encoding="utf-8"))["reading"])

    def description(self) -> str:
        """Return what the case exercises."""
        return str(json.loads(self.truth_path.read_text(encoding="utf-8"))["description"])


def _verify(path: Path, wanted: str, case_id: str) -> None:
    if not path.is_file():
        raise CorpusError(f"{case_id}: missing {path}")
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != wanted:
        raise CorpusError(f"{case_id}: {path.name} has digest {found}, the manifest pins {wanted}")


def load_corpus(manifest: Path = MANIFEST) -> list[Case]:
    """Load every case, verifying each file against the manifest.

    Parameters
    ----------
    manifest : pathlib.Path
        The manifest file. Files are found relative to it.

    Returns
    -------
    list of Case
        The cases, in manifest order.

    Raises
    ------
    CorpusError
        If the manifest is empty or has the wrong schema, or a file is missing or has changed.

    """
    data: dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise CorpusError(f"manifest schema {data.get('schema_version')}, expected {MANIFEST_SCHEMA_VERSION}")
    if not data.get("cases"):
        raise CorpusError("the manifest lists no cases")
    root = manifest.parent
    cases = []
    for entry in data["cases"]:
        family, name, case_id = entry["family"], entry["name"], entry["case_id"]
        folder = root / "corpus" / family
        case = Case(
            case_id=case_id,
            family=family,
            name=name,
            control=bool(entry["control"]),
            source=folder / f"{name}.docx",
            tagged=folder / f"{name}.tagged.pdf",
            untagged=folder / f"{name}.untagged.pdf",
            truth_path=root / "truth" / family / f"{name}.json",
        )
        _verify(case.source, entry["source_sha256"], case_id)
        _verify(case.tagged, entry["tagged_sha256"], case_id)
        _verify(case.untagged, entry["untagged_sha256"], case_id)
        _verify(case.truth_path, entry["truth_sha256"], case_id)
        cases.append(case)
    return cases
