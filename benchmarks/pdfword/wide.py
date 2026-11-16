"""The wide tier: hundreds of Word documents other people wrote, made into PDFs by Word and scored.

The lane's 13 documents were all made by one script on one Word template, so a fix tuned on
them can be tuned to that template. This tier takes Word documents from elsewhere (public
fixtures and a government web crawl), has Word export each to a PDF and read it as the
truth, then scores each tool's PDF -> Word conversion against that truth with the lane's
own scorer. The documents are never committed; ``--inventory`` names them.

    uv run --with pywin32 python -m benchmarks.pdfword.wide truth --inventory inv.json --work W
    uv run --with pywin32 python -m benchmarks.pdfword.wide run --tool ours_default --work W
    uv run --with pywin32 python -m benchmarks.pdfword.wide run --tool word_import --work W
    uv run python -m benchmarks.pdfword.wide summary --work W

Each stage resumes where it stopped. Real documents hang Word (a password prompt, a
repair, a conversion dialog), so a worker process does the Word work and the stage
watches it: an item that runs past ``--timeout`` is recorded as a timeout, the worker and
the Word it started (and only that one) are killed, and a new worker takes the next item.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

#: The tools a run can score. Layout analysis is left out: at this scale it is hours of CPU.
TOOLS: dict[str, tuple[str, ...] | None] = {
    "ours_default": ("--pdf-layout-analysis-mode", "disabled"),
    # Images are left out by default (secure by default), so pictures read 0 without this.
    "ours_images": ("--pdf-layout-analysis-mode", "disabled", "--attachment-mode", "base64"),
    "word_import": None,
}
#: msoAutomationSecurityForceDisable: a document's macros never run.
FORCE_DISABLE_MACROS = 3
#: A line counts as in place when its baseline lands within this many points of the source's.
IN_PLACE = 3.0


def key_of(item_id: str) -> str:
    """Return a directory name for an inventory id."""
    return item_id.replace("/", "__").replace("\\", "__")


def load_inventory(path: Path) -> list[dict[str, Any]]:
    """Return the inventory rows chosen for the tier: two or more pages, or 300 or more words."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in rows if (row.get("meta_pages") or 0) >= 2 or (row.get("meta_words") or 0) >= 300]


def done_ids(results: Path) -> set[str]:
    """Return the ids a stage has already recorded, whatever their outcome."""
    if not results.exists():
        return set()
    return {json.loads(line)["id"] for line in results.read_text(encoding="utf-8").splitlines() if line.strip()}


def append(results: Path, record: dict[str, Any]) -> None:
    with results.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


# --------------------------------------------------------------------------- Word, in the worker


def word_pids() -> set[int]:
    """Return the process ids of every running Word."""
    done = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq WINWORD.EXE", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = set()
    for line in done.stdout.splitlines():
        parts = [part.strip('"') for part in line.split('","')]
        if len(parts) > 1 and parts[1].isdigit():
            pids.add(int(parts[1]))
    return pids


def open_quietly(app: Any, path: Path, *, pdf: bool = False) -> Any:
    """Open a document read-only, with every prompt Word could raise answered or refused."""
    if pdf:
        return app.Documents.Open(
            str(path.resolve()), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False, Format=0
        )
    # A wrong password fails at once where no password would prompt and hang.
    return app.Documents.Open(
        str(path.resolve()),
        ConfirmConversions=False,
        ReadOnly=True,
        AddToRecentFiles=False,
        PasswordDocument="all2md-no-password",
        Revert=False,
        Visible=False,
        OpenAndRepair=False,
        NoEncodingDialog=True,
    )


def truth_item(app: Any, row: dict[str, Any], work: Path) -> dict[str, Any]:
    """Read one source document through Word and export its PDF and a DOCX copy."""
    from benchmarks.pdfword.generate.generate import export_pdf
    from benchmarks.pdfword.word import WD_FORMAT_DOCX, read_document

    folder = work / key_of(row["id"])
    folder.mkdir(parents=True, exist_ok=True)
    document = open_quietly(app, Path(row["path"]))
    try:
        reading = read_document(document)
        export_pdf(document, (folder / "source.pdf").resolve(), tagged=False)
        document.SaveAs2(str((folder / "source.docx").resolve()), FileFormat=WD_FORMAT_DOCX)
    finally:
        document.Close(0)
    (folder / "truth.json").write_text(json.dumps(reading.to_json()), encoding="utf-8")
    return {"pages": reading.pages, "words": sum(len(p.text.split()) for p in reading.paragraphs)}


def run_item(app: Any, row: dict[str, Any], work: Path, tool: str) -> dict[str, Any]:
    """Convert one source PDF with ``tool``, have Word read and render the result, and score it."""
    from benchmarks.pdfword.reading import Reading
    from benchmarks.pdfword.run import convert
    from benchmarks.pdfword.score import score
    from benchmarks.pdfword.word import WD_FORMAT_DOCX, WD_FORMAT_PDF, read_document

    folder = work / key_of(row["id"])
    pdf = folder / "source.pdf"
    output = folder / f"{tool}.docx"
    started = time.monotonic()
    policy = TOOLS[tool]
    if policy is None:
        document = open_quietly(app, pdf, pdf=True)
        try:
            document.SaveAs2(str(output.resolve()), FileFormat=WD_FORMAT_DOCX)
        finally:
            document.Close(0)
    else:
        error = convert(pdf, output, policy)
        if error is not None:
            return {"status": "crash", "error": error}
    seconds = round(time.monotonic() - started, 2)
    document = open_quietly(app, output)
    try:
        document.ExportAsFixedFormat(str((folder / f"{tool}.render.pdf").resolve()), WD_FORMAT_PDF)
        got = read_document(document)
    finally:
        document.Close(0)
    truth = Reading.from_json(json.loads((folder / "truth.json").read_text(encoding="utf-8")))
    return {"status": "ok", "seconds": seconds, "score": score(truth, got)}


def worker(stage: str, tool: str | None, work: Path, pending: Path) -> int:
    """Do the Word work for each pending row in turn, reporting progress through files in ``work``."""
    import pythoncom
    import win32com.client

    rows = json.loads(pending.read_text(encoding="utf-8"))
    results = work / (f"run-{tool}.jsonl" if stage == "run" else "truth.jsonl")
    heartbeat = work / "current.json"
    pythoncom.CoInitialize()
    before = word_pids()
    app = win32com.client.DispatchEx("Word.Application")
    mine = sorted(word_pids() - before)
    app.Visible = False
    app.DisplayAlerts = 0
    app.AutomationSecurity = FORCE_DISABLE_MACROS
    try:
        for row in rows:
            heartbeat.write_text(json.dumps({"id": row["id"], "started": time.time(), "word": mine}), "utf-8")
            try:
                if stage == "truth":
                    record = {"status": "ok", **truth_item(app, row, work)}
                else:
                    assert tool is not None
                    record = run_item(app, row, work, tool)
            except Exception as exc:  # noqa: BLE001 - a document Word cannot handle is a finding
                record = {"status": "error", "error": repr(exc)[:500]}
            append(results, {"id": row["id"], **record})
    finally:
        heartbeat.unlink(missing_ok=True)
        try:
            app.Quit(0)
        except Exception:  # noqa: BLE001
            pass
    return 0


# --------------------------------------------------------------------------- the supervising stage


def supervise(stage: str, tool: str | None, rows: Sequence[dict[str, Any]], work: Path, timeout: float) -> None:
    """Run ``rows`` through workers, replacing any worker that sits on one item past ``timeout``."""
    results = work / (f"run-{tool}.jsonl" if stage == "run" else "truth.jsonl")
    heartbeat = work / "current.json"
    while True:
        finished = done_ids(results)
        remaining = [row for row in rows if row["id"] not in finished]
        if not remaining:
            return
        pending = work / "pending.json"
        pending.write_text(json.dumps(remaining), encoding="utf-8")
        command = [sys.executable, "-m", "benchmarks.pdfword.wide", "_worker", stage, "--work", str(work)]
        if tool:
            command += ["--tool", tool]
        heartbeat.unlink(missing_ok=True)
        child = subprocess.Popen(command)
        print(f"{stage}{'/' + tool if tool else ''}: {len(remaining)} to go", flush=True)
        while child.poll() is None:
            time.sleep(2)
            try:
                beat = json.loads(heartbeat.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if time.time() - beat["started"] > timeout:
                print(f"  timeout: {beat['id']}", flush=True)
                child.kill()
                for pid in beat.get("word") or []:
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
                child.wait()
                if beat["id"] not in done_ids(results):
                    append(results, {"id": beat["id"], "status": "timeout"})
                break
        else:
            if child.returncode != 0:
                # The worker died on its own (Word crashed): record the item it was on, or
                # stop if it died before taking one, rather than start it again forever.
                try:
                    beat = json.loads(heartbeat.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise RuntimeError(f"the {stage} worker failed before its first document") from exc
                if beat["id"] not in done_ids(results):
                    append(results, {"id": beat["id"], "status": "worker-died"})


# --------------------------------------------------------------------------- the summary, no Word


def _lines(path: Path) -> list[tuple[int, float, str]]:
    import fitz

    rows = []
    with fitz.open(path) as document:
        for number, page in enumerate(document):
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if len(text) >= 8:
                        rows.append((number, line["spans"][0]["origin"][1], text))
    return sorted(rows)


def placement(source: Path, render: Path) -> dict[str, Any]:
    """Return how many of the source's lines the render prints on the same page, within ``IN_PLACE`` points.

    Lines are matched by their exact text, in order; a line printed differently (rewrapped,
    reworded) is unmatched, and says nothing about placement either way.
    """
    theirs = _lines(render)
    used: set[int] = set()
    matched = in_place = 0
    total = 0
    for page, baseline, text in _lines(source):
        total += 1
        for index, (other_page, other_baseline, other_text) in enumerate(theirs):
            if index in used or other_text != text:
                continue
            used.add(index)
            matched += 1
            if other_page == page and abs(other_baseline - baseline) <= IN_PLACE:
                in_place += 1
            break
    return {"lines": total, "matched": matched, "in_place": in_place}


def summary(work: Path, rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Add up each tool across the tier, overall and per source."""
    from benchmarks.pdfword.score import summarize

    truth = {r["id"]: r for r in _records(work / "truth.jsonl")}
    report: dict[str, Any] = {"truth": _outcomes(truth.values())}
    ids = {row["id"] for row in rows}
    for tool in TOOLS:
        records = {r["id"]: r for r in _records(work / f"run-{tool}.jsonl") if r["id"] in ids}
        if not records:
            continue
        ok = {item: r for item, r in records.items() if r.get("status") == "ok"}
        entry: dict[str, Any] = {"outcomes": _outcomes(records.values())}
        for source in sorted({item.split("/")[0] for item in ok} | {"all"}):
            chosen = [r for item, r in ok.items() if source == "all" or item.startswith(source + "/")]
            pages_right = sum(
                r["score"]["page"]["pages"]["truth"] == r["score"]["page"]["pages"]["got"] for r in chosen
            )
            placed = {"lines": 0, "matched": 0, "in_place": 0}
            for item, _ in ((i, r) for i, r in ok.items() if source == "all" or i.startswith(source + "/")):
                folder = work / key_of(item)
                render = folder / f"{tool}.render.pdf"
                if render.exists():
                    for name, value in placement(folder / "source.pdf", render).items():
                        placed[name] += value
            entry[source] = {
                "documents": len(chosen),
                "page_count_right": pages_right,
                "placement": placed,
                "scores": summarize(r["score"] for r in chosen),
            }
        report[tool] = entry
    return report


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _outcomes(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.get("status", "?")] = counts.get(record.get("status", "?"), 0) + 1
    return counts


# --------------------------------------------------------------------------- command line


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks.pdfword.wide", description=__doc__.split("\n")[0])
    parser.add_argument("stage", choices=("truth", "run", "summary", "_worker"))
    parser.add_argument("worker_stage", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("--work", type=Path, required=True, help="Where documents, readings and results go.")
    parser.add_argument("--inventory", type=Path, help="Inventory JSON (truth stage; copied into --work).")
    parser.add_argument("--tool", choices=sorted(TOOLS), help="Which conversion to score (run stage).")
    parser.add_argument("--limit", type=int, help="Only the first N chosen documents.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Seconds one document may take.")
    args = parser.parse_args(argv)
    work: Path = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)

    if args.stage == "_worker":
        return worker(args.worker_stage, args.tool, work, work / "pending.json")

    inventory = work / "inventory.json"
    if args.inventory is not None:
        inventory.write_text(args.inventory.read_text(encoding="utf-8"), encoding="utf-8")
    rows = load_inventory(inventory)
    if args.limit:
        rows = rows[: args.limit]

    if args.stage == "truth":
        supervise("truth", None, rows, work, args.timeout)
    elif args.stage == "run":
        if args.tool is None:
            parser.error("run needs --tool")
        ready = {r["id"] for r in _records(work / "truth.jsonl") if r.get("status") == "ok"}
        supervise("run", args.tool, [row for row in rows if row["id"] in ready], work, args.timeout)
    else:
        report = summary(work, rows)
        (work / "summary.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(
            json.dumps({k: v.get("all", v) if isinstance(v, dict) else v for k, v in report.items()}, indent=1)[:4000]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
