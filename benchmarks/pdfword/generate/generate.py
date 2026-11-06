"""Generate the corpus by driving a live Word (Windows and Word only, hand-run).

    uv run --with pywin32 python -m benchmarks.pdfword.generate.generate
    uv run --with pywin32 python -m benchmarks.pdfword.generate.generate --only form/invoice

Word must already be running and visible, and the run takes it over while it works. Each case
produces three committed files: the source ``.docx``, its PDF with structure tags, and its PDF
without them. Word's reading of the source becomes the truth record, but only after it matches
what the case declared.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmarks.docx.generate.session import WordSession
from benchmarks.pdfword.generate.cases import CASES, Builder, Case
from benchmarks.pdfword.reading import Reading
from benchmarks.pdfword.word import WD_FORMAT_PDF, read_document

LANE = Path(__file__).resolve().parent.parent
CORPUS = LANE / "corpus"
TRUTH = LANE / "truth"
MANIFEST = LANE / "manifest.json"
MANIFEST_SCHEMA_VERSION = 1
CORPUS_AUTHOR = "all2md corpus"
#: Positional arguments of ExportAsFixedFormat after ExportFormat, up to DocStructureTags.
WD_OPTIMIZE_FOR_PRINT = 0
WD_EXPORT_ALL = 0
WD_EXPORT_DOCUMENT_CONTENT = 0
WD_NO_BOOKMARKS = 0


#: The scripts park on these while building. One left behind is a defect in the truth record.
_PLACEHOLDER = re.compile(r"CHARTHERE|CHARTEND|TOCHERE|PICTUREHERE|SECTIONBREAK|COMMENTBOX")


def digest(path: Path) -> str:
    """Return a file's SHA-256."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mismatches(case: Case, reading: Reading) -> list[str]:
    """Compare Word's reading of the finished document with what the case declared."""
    expect = case.expect
    problems = []
    leftovers = [p.text for p in reading.paragraphs if _PLACEHOLDER.search(p.text)]
    if leftovers:
        problems.append(f"placeholders left in the document: {leftovers}")
    headings = tuple(p.text for p in reading.paragraphs if p.level is not None)
    if headings != expect.headings:
        problems.append(f"headings: Word reads {headings}, the case declares {expect.headings}")
    tables = tuple(table.shape for table in reading.tables)
    if tables != expect.tables:
        problems.append(f"tables: Word reads {tables}, the case declares {expect.tables}")
    if len(reading.footnotes) != expect.footnotes:
        problems.append(f"footnotes: Word reads {len(reading.footnotes)}, the case declares {expect.footnotes}")
    if not all(reading.footnotes):
        problems.append(f"footnotes: at least one has no text: {reading.footnotes}")
    if reading.pictures != expect.pictures:
        problems.append(f"pictures: Word reads {reading.pictures}, the case declares {expect.pictures}")
    markers = tuple(
        p.marker.strip() for p in reading.paragraphs if p.marker and p.marker.strip() and len(p.marker.strip()) > 1
    )
    if expect.markers and markers != expect.markers:
        problems.append(f"markers: Word reads {markers}, the case declares {expect.markers}")
    if expect.header and not any(expect.header in text for text in reading.headers):
        problems.append(f"header: Word reads {reading.headers}, the case declares {expect.header!r}")
    if expect.footer and not any(expect.footer in text for text in reading.footers):
        problems.append(f"footer: Word reads {reading.footers}, the case declares {expect.footer!r}")
    if reading.columns != expect.columns:
        problems.append(f"columns: Word reads {reading.columns}, the case declares {expect.columns}")
    return problems


def export_pdf(document: Any, path: Path, *, tagged: bool) -> None:
    """Export a PDF. Word has no other option that differs between the two copies."""
    document.ExportAsFixedFormat(
        str(path),
        WD_FORMAT_PDF,
        False,
        WD_OPTIMIZE_FOR_PRINT,
        WD_EXPORT_ALL,
        1,
        1,
        WD_EXPORT_DOCUMENT_CONTENT,
        True,
        True,
        WD_NO_BOOKMARKS,
        tagged,
    )


def generate_case(session: WordSession, case: Case) -> dict[str, Any]:
    """Build one document, check it against its declaration, then write its files."""
    target = CORPUS / case.family
    target.mkdir(parents=True, exist_ok=True)
    session.new()
    try:
        case.build(Builder(session))
    except Exception:
        session.close()  # or a failed case leaves its half-built document open in Word
        raise
    document = session.doc()
    document.Fields.Update()
    for contents in document.TablesOfContents:
        contents.Update()
    document.Repaginate()
    reading = read_document(document)
    problems = mismatches(case, reading)
    if problems:
        session.close()
        raise RuntimeError("the document does not match its declaration:\n  " + "\n  ".join(problems))

    saved = Path(session.save_as(f"{case.name}.docx"))
    document = session.doc()
    tagged = target / f"{case.name}.tagged.pdf"
    untagged = target / f"{case.name}.untagged.pdf"
    export_pdf(document, tagged, tagged=True)
    export_pdf(document, untagged, tagged=False)
    session.close()
    final = target / f"{case.name}.docx"
    if saved.resolve() != final.resolve():
        final.write_bytes(saved.read_bytes())
        saved.unlink()

    TRUTH.joinpath(case.family).mkdir(parents=True, exist_ok=True)
    truth_path = TRUTH / case.family / f"{case.name}.json"
    record = {
        "schema_version": 1,
        "case_id": f"{case.family}/{case.name}",
        "family": case.family,
        "description": case.description,
        "control": case.control,
        "reading": reading.to_json(),
    }
    with truth_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
    return {
        "case_id": f"{case.family}/{case.name}",
        "family": case.family,
        "name": case.name,
        "control": case.control,
        "source_sha256": digest(final),
        "tagged_sha256": digest(tagged),
        "untagged_sha256": digest(untagged),
        "truth_sha256": digest(truth_path),
    }


def main() -> int:
    """Generate the requested cases and merge them into the manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=None, help="family, or family/case")
    args = parser.parse_args()
    cases = list(CASES)
    if args.only:
        wanted = set(args.only)
        cases = [c for c in cases if c.family in wanted or f"{c.family}/{c.name}" in wanted]
    if not cases:
        print("no cases matched", file=sys.stderr)
        return 1

    CORPUS.mkdir(parents=True, exist_ok=True)
    session = WordSession(str(CORPUS))
    session.pin_author(CORPUS_AUTHOR)
    entries = []
    failed = []
    try:
        for case in cases:
            case_id = f"{case.family}/{case.name}"
            try:
                entries.append(generate_case(session, case))
                print(f"ok   {case_id}", flush=True)
            except Exception as exc:  # noqa: BLE001 - one bad case must not lose the rest
                print(f"FAIL {case_id}: {exc}", file=sys.stderr, flush=True)
                failed.append(case_id)
    finally:
        session.restore_author()

    existing: dict[str, dict[str, Any]] = {}
    if MANIFEST.exists():
        existing = {c["case_id"]: c for c in json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]}
    existing.update({entry["case_id"]: entry for entry in entries})
    version = subprocess.run(["wordlive", "--version"], capture_output=True, text=True, check=False).stdout.strip()
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "provenance": {
            "word_build": str(session.app.Build),
            "word_version": str(session.app.Version),
            "wordlive_version": version,
            "generated_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        },
        "cases": [existing[key] for key in sorted(existing)],
    }
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
    print(f"\n{len(entries)} case(s) written; {len(failed)} failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
