"""Score PDF to Word conversion against the documents the PDFs came from.

    uv run --with pywin32 python -m benchmarks.pdfword --out reading.json
    uv run --with pywin32 python -m benchmarks.pdfword --family contract --keep ./out --montage ./out

Windows and a Word install only, because Word's reading of the output is the instrument. Word
runs privately and hidden. A ledger, not a gate: the exit status is non-zero only when the lane
itself breaks, meaning a conversion crashed or a source document no longer matches its truth.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from benchmarks.pdfword.corpus import Case, load_corpus
from benchmarks.pdfword.score import is_perfect, score, summarize
from benchmarks.pdfword.word import Word

#: What each of our configurations passes. "default" is what `pip install all2md[pdf]` gets.
POLICIES: dict[str, tuple[str, ...]] = {
    "ours_default": ("--pdf-layout-analysis-mode", "disabled"),
    "ours_full": ("--pdf-layout-analysis-mode", "enabled", "--attachment-mode", "base64"),
}
SUMMARY_ROWS: tuple[tuple[str, str, str], ...] = (
    ("Words kept, in order", "words_in_order", "words"),
    ("Paragraphs left whole", "paragraphs_whole", "paragraphs"),
    ("Headings found", "headings_kept", "headings"),
    ("Headings at the right level", "headings_level_kept", "headings"),
    ("List items in their own paragraph", "list_items_own_paragraph", "list_items"),
    ("List items with real Word numbering", "list_items_real", "list_items"),
    ("List markers printed correctly", "list_markers_printed", "list_items"),
    ("Tables found", "tables_found", "tables"),
    ("Tables with the right shape", "tables_exact_shape", "tables"),
    ("Table cells right", "cells_right", "cells"),
    ("Real footnotes", "footnotes_kept", "footnotes"),
    ("Real page headers and footers", "furniture_kept", "furniture"),
    ("Pictures and charts", "pictures_kept", "pictures"),
    ("Page size right", "page_size_matches", "documents"),
    ("Margins right", "margins_match", "documents"),
    ("Body font right", "body_font_matches", "documents"),
    ("Body size right", "body_size_matches", "documents"),
)
COUNT_ROWS: tuple[tuple[str, str], ...] = (
    ("Paragraphs merged together", "paragraphs_merged"),
    ("Paragraphs split apart", "paragraphs_split"),
    ("Paragraphs missing", "paragraphs_missing"),
    ("Headings invented", "headings_spurious"),
    ("Footnotes leaked into the text", "footnotes_leaked"),
    ("Header or footer lines leaked into the text", "furniture_leaked_lines"),
)


def convert(pdf: Path, output: Path, policy: Sequence[str]) -> str | None:
    """Convert with the real CLI. Returns the error text on a crash."""
    command = [sys.executable, "-m", "all2md", str(pdf), "--out", str(output), "--no-config", *policy]
    done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return None if done.returncode == 0 and output.exists() else done.stderr[-500:]


def montage(paths: Sequence[Path], output_stem: Path) -> None:
    """Write each page's source and renderings side by side, for looking at."""
    import fitz

    documents = [fitz.open(path) for path in paths]
    height = 760
    for page_number in range(len(documents[0])):
        pages = [document[min(page_number, len(document) - 1)] for document in documents]
        zooms = [height / page.rect.height for page in pages]
        width = sum(page.rect.width * zoom for page, zoom in zip(pages, zooms, strict=True)) + 12 * (len(pages) - 1)
        canvas = fitz.open()
        sheet = canvas.new_page(width=width, height=height)
        sheet.draw_rect(sheet.rect, fill=(0.6, 0.6, 0.6))
        left = 0.0
        for page, zoom in zip(pages, zooms, strict=True):
            right = left + page.rect.width * zoom
            image = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            sheet.insert_image(fitz.Rect(left, 0, right, height), pixmap=image)
            left = right + 12
        sheet.get_pixmap().save(f"{output_stem}_{page_number + 1}.png")


def run_case(word: Word, case: Case, work: Path, *, with_montage: Path | None) -> dict[str, Any]:
    """Score every tool on one case, on the tagged and the untagged PDF."""
    truth = case.truth()
    work.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"case_id": case.case_id, "control": case.control, "scores": {}, "crashes": {}}
    # The self-check: Word's reading of the source today, scored against the recorded truth.
    self_score = score(truth, word.read(case.source))
    row["self_check_problems"] = is_perfect(self_score)
    for variant, pdf in (("tagged", case.tagged), ("untagged", case.untagged)):
        renders = [pdf]
        for tool in (*POLICIES, "word_import"):
            output = work / f"{case.name}.{variant}.{tool}.docx"
            error = None
            if tool == "word_import":
                try:
                    word.import_pdf(pdf, output)
                except Exception as exc:  # noqa: BLE001 - Word's failure is a finding about Word
                    error = repr(exc)[:500]
            else:
                error = convert(pdf, output, POLICIES[tool])
            key = f"{tool}/{variant}"
            if error is not None:
                row["crashes"][key] = error
                continue
            render = output.with_suffix(".render.pdf")
            row["scores"][key] = score(truth, word.read(output, render=render))
            renders.append(render)
        if with_montage is not None and variant == "tagged":
            with_montage.mkdir(parents=True, exist_ok=True)
            montage(renders, with_montage / f"{case.family}-{case.name}")
    return row


def summarize_run(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Add up each tool across the corpus, per family and overall."""
    keys = sorted({key for row in rows for key in row["scores"]})
    summary: dict[str, Any] = {}
    for key in keys:
        summary[key] = {"all": summarize(row["scores"][key] for row in rows if key in row["scores"])}
        for family in sorted({row["case_id"].split("/")[0] for row in rows}):
            chosen = [
                row["scores"][key] for row in rows if key in row["scores"] and row["case_id"].startswith(f"{family}/")
            ]
            summary[key][family] = summarize(chosen)
    return summary


def print_table(summary: dict[str, Any], variant: str = "untagged", group: str = "all") -> None:
    """Print one tool per column."""
    tools = [key for key in summary if key.endswith(f"/{variant}")]
    print(f"\n{group}, {variant} PDFs")
    print(f"{'':46}" + "".join(f"{tool.split('/')[0]:>16}" for tool in tools))
    for label, kept, total in SUMMARY_ROWS:
        cells = "".join(
            f"{summary[tool][group].get(kept, 0):>9}/{summary[tool][group].get(total, 0):<6}" for tool in tools
        )
        print(f"{label:46}{cells}")
    for label, key in COUNT_ROWS:
        print(f"{label:46}" + "".join(f"{summary[tool][group].get(key, 0):>16}" for tool in tools))
    print(
        f"{'Pages (truth ' + str(summary[tools[0]][group].get('pages_truth', 0)) + ')':46}"
        + "".join(f"{summary[tool][group].get('pages_got', 0):>16}" for tool in tools)
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the lane."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", nargs="*", default=None)
    parser.add_argument("--out", type=Path, default=None, help="write the full reading as JSON")
    parser.add_argument("--keep", type=Path, default=None, help="keep the converted documents here")
    parser.add_argument("--montage", type=Path, default=None, help="write side-by-side page images here")
    args = parser.parse_args(argv)

    cases = load_corpus()
    if args.family:
        cases = [case for case in cases if case.family in args.family]
    rows = []
    with tempfile.TemporaryDirectory() as scratch, Word() as word:
        work = args.keep or Path(scratch)
        for case in cases:
            row = run_case(word, case, work / case.family, with_montage=args.montage)
            rows.append(row)
            print(
                f"{case.case_id}: self-check {row['self_check_problems'] or 'clean'}; crashes {list(row['crashes'])}",
                flush=True,
            )
    summary = summarize_run(rows)
    print_table(summary)
    for family in sorted({case.family for case in cases}):
        print_table(summary, group=family)
    if args.out:
        args.out.write_text(
            json.dumps({"summary": summary, "cases": rows}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    broken = [
        row["case_id"]
        for row in rows
        if row["self_check_problems"] or any(k.startswith("ours") for k in row["crashes"])
    ]
    if broken:
        print(f"\nLane problems: {broken}", file=sys.stderr)
    return 1 if broken else 0
