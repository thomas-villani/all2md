"""Generate the corpus by driving a live Word (Windows + Word only, hand-run).

    uv run --with pywin32 python -m benchmarks.docx.generate.generate
    uv run --with pywin32 python -m benchmarks.docx.generate.generate --only tracked

Word must already be running and visible. The run takes over the application, so it
happens in front of you and you can watch it; nothing here is safe to run unattended.

Each case is a JSON file under ``cases/<family>/<case>.json``:

* ``steps`` — what to do, in order. A step is a ``wordlive`` invocation, an ``exec``
  batch, or one of the COM hatches :mod:`session` provides for the things ``wordlive``
  has no verb for.
* ``verify`` — assertions against the **saved file's XML**. Mandatory, and the reason
  to trust the truth record at all: a case that claims to produce ``w:ins`` proves it
  in the bytes rather than in its own description. This is the generation-side
  analogue of demonstrating a gate red.
* ``facts`` — the structural truth the script knows because it put it there.

What a truth record does **not** contain is any claim about how all2md parses the
document. The first reading of this corpus found two recorded predictions about
current behaviour that were both wrong (see issues #480 and #481), in the same
direction: a silent total loss where the design had imagined graceful degradation.
So today's behaviour is *measured* by the scoring side and recorded as a ledger, and
never hand-written here.

The run also exercises the **re-save stability control**: every file is reopened and
saved again through Word, then re-verified. It guards the premise the whole lane rests
on -- that the document Word wrote is the document the script described -- against
Word normalizing something on save.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from benchmarks.docx.generate.session import WordSession  # noqa: E402

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
CASES = HERE / "cases"
CORPUS = LANE / "corpus"
EXPECTED = LANE / "expected"
MANIFEST = LANE / "manifest.json"

MANIFEST_SCHEMA_VERSION = 1
#: Pinned so tracked-change authorship does not depend on whose machine generated the
#: corpus. The real user name is restored when the run finishes.
CORPUS_AUTHOR = "all2md corpus"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def part_text(path: Path, part: str) -> str:
    """One part of a .docx as text, or empty when the part is absent."""
    with zipfile.ZipFile(path) as archive:
        if part not in archive.namelist():
            return ""
        return archive.read(part).decode("utf-8")


def check(path: Path, rules: list[dict[str, Any]]) -> list[str]:
    """Run a case's ``verify`` rules against the saved file. Returns failures."""
    failures = []
    for rule in rules:
        part = rule.get("part", "word/document.xml")
        text = part_text(path, part)
        pattern = rule["pattern"]
        count = len(re.findall(pattern, text))
        least = rule.get("min", 1)
        most = rule.get("max")
        if count < least or (most is not None and count > most):
            bound = f">= {least}" + (f" and <= {most}" if most is not None else "")
            failures.append(f"{part}: /{pattern}/ matched {count}, wanted {bound}")
    return failures


def run_step(session: WordSession, step: dict[str, Any]) -> Any:
    """Apply one case step."""
    kind = step.get("kind", "wl")
    if kind == "wl":
        return session.wl(*step["args"], stdin=step.get("stdin"))
    if kind == "ops":
        return session.exec_ops(step["ops"], step.get("label", "batch"), step.get("tracked", False))
    if kind == "style_add":
        return session.add_paragraph_style(step["name"], step["based_on"], step.get("park_at", "para:1"))
    if kind == "find_style":
        # Find-then-style, in one step, because a case cannot carry an anchor between
        # steps. Doing it through `find` keeps to the offset-space rule: find offsets
        # are visible-text space, so this must run before any field, note or content
        # control puts hidden characters into Word Range space.
        hits = session.wl("find", "--text", step["find"])
        if not hits:
            raise RuntimeError(f"find {step['find']!r} matched nothing")
        occurrence = step.get("occurrence", 0)
        anchor = hits[occurrence]["anchor_id"]
        return session.wl("style", "apply", "--anchor-id", anchor, "--name", step["style"])
    if kind == "link_list_style":
        return session.link_list_style(
            step["style"],
            number_style=step.get("number_style", 0),
            fmt=step.get("format", "%1."),
            start=step.get("start", 1),
            template_name=step.get("template_name"),
        )
    raise ValueError(f"unknown step kind {kind!r}")


def positional_truth(session: WordSession) -> list[dict[str, Any]]:
    """Word's own paragraph offsets, recorded per case.

    Informational until the DOCX parser emits ``source_location`` (Theme 8 Stage 3),
    at which point this corpus scores provenance with no new instrument. Cheap to
    record now and expensive to retrofit, which is the whole reason it is here.

    ``text`` here is what Word's Range reports, which on a tracked document shows the
    insertion and the deletion *both*, run together ("crimsonbrown"). That is markup
    space, not either resolution of the revisions, so it is recorded as provenance and
    must never be mistaken for the expected output text.
    """
    records = []
    for paragraph in session.wl("paragraphs"):
        if not isinstance(paragraph, dict):
            continue
        records.append(
            {
                "index": paragraph.get("index"),
                "anchor_id": paragraph.get("anchor_id"),
                "start": paragraph.get("start"),
                "end": paragraph.get("end"),
                "style": paragraph.get("style"),
                "range_text": paragraph.get("text"),
            }
        )
    return records


def generate_case(session: WordSession, spec_path: Path) -> dict[str, Any]:
    """Generate one document, verify it, re-save it, verify it again."""
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    family = spec["family"]
    name = spec_path.stem
    case_id = f"{family}/{name}"

    target_dir = CORPUS / family
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{name}.docx"

    session.new()
    for step in spec["steps"]:
        run_step(session, step)
    paragraphs = positional_truth(session)
    saved = Path(session.save_as(filename))
    session.close()

    failures = check(saved, spec.get("verify", []))
    if failures:
        raise RuntimeError(f"{case_id}: the saved file does not match its own claims:\n  " + "\n  ".join(failures))

    # Re-save stability control: what Word writes on a second save must still satisfy
    # the same claims, or the "exact truth" premise is false for this case.
    session.doc_name = filename
    session.app.Documents.Open(str(saved))
    session.wl("save")
    session.close()
    resave_failures = check(saved, spec.get("verify", []))

    # Word saves into the whitelisted staging directory; the corpus is organised by
    # family, so the document is filed and the staged copy removed. Leaving it behind
    # puts a duplicate of every case at the corpus root.
    final = target_dir / filename
    if saved.resolve() != final.resolve():
        final.write_bytes(saved.read_bytes())
        saved.unlink()

    expected_dir = EXPECTED / family
    expected_dir.mkdir(parents=True, exist_ok=True)
    expected_path = expected_dir / f"{name}.json"
    record = {
        "schema_version": 1,
        "case_id": case_id,
        "family": family,
        "description": spec["description"],
        "control": bool(spec.get("control", False)),
        "facts": spec.get("facts", {}),
        "positional": paragraphs,
    }
    with expected_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    return {
        "case_id": case_id,
        "family": family,
        "path": f"corpus/{family}/{filename}",
        "sha256": digest(final),
        "size_bytes": final.stat().st_size,
        "generator": f"cases/{family}/{name}.json",
        "expected_sha256": digest(expected_path),
        "resave_stable": not resave_failures,
        "resave_failures": resave_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=None, help="family, or family/case")
    parser.add_argument("--outdir", default=None, help="where Word saves before filing (default: corpus/)")
    args = parser.parse_args()

    specs = sorted(CASES.glob("*/*.json"))
    if args.only:
        wanted = set(args.only)
        specs = [s for s in specs if s.parent.name in wanted or f"{s.parent.name}/{s.stem}" in wanted]
    if not specs:
        print("no cases matched", file=sys.stderr)
        return 1

    outdir = args.outdir or str(CORPUS)
    session = WordSession(outdir)
    session.pin_author(CORPUS_AUTHOR)

    entries: list[dict[str, Any]] = []
    failed: list[str] = []
    try:
        for spec_path in specs:
            case_id = f"{spec_path.parent.name}/{spec_path.stem}"
            try:
                entry = generate_case(session, spec_path)
            except Exception as exc:  # noqa: BLE001 - one bad case must not lose the rest
                print(f"FAIL {case_id}: {exc}", file=sys.stderr)
                failed.append(case_id)
                continue
            flag = "" if entry["resave_stable"] else "  (UNSTABLE ON RE-SAVE)"
            print(f"ok   {case_id}{flag}")
            entries.append(entry)
    finally:
        session.restore_author()

    wordlive_version = subprocess.run(
        ["wordlive", "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()
    # A partial run (`--only`) must MERGE into the manifest, not replace it. Writing
    # only what this run produced would silently drop every case it did not touch, and
    # the corpus would still load cleanly -- just smaller, with no sign anything went
    # missing. Regenerating one case is the normal way to fix one case's truth record.
    existing: dict[str, dict[str, Any]] = {}
    if MANIFEST.exists():
        previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
        existing = {case["case_id"]: case for case in previous.get("cases", [])}
    for entry in entries:
        existing[entry["case_id"]] = entry

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "provenance": {
            "word_build": str(session.app.Build),
            "word_version": str(session.app.Version),
            "wordlive_version": wordlive_version,
            "word_user_name": CORPUS_AUTHOR,
            "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        },
        "cases": [existing[key] for key in sorted(existing)],
    }
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"\n{len(entries)} case(s) written; manifest at {MANIFEST}")
    if failed:
        print(f"{len(failed)} failed: {', '.join(failed)}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
