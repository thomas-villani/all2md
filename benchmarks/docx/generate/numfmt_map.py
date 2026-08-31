"""Measure ``WdListNumberStyle`` -> OOXML ``w:numFmt``, because the names mislead.

Generation side: **Windows + Word only**, hand-run. Regenerates
``numfmt-map.json``; the committed JSON is the artifact, so nothing downstream
needs Word.

Why measure rather than read the documentation: the COM constant names do not
match what Word writes. ``wdListNumberStyleGBNum1`` (26) writes
``decimalEnclosedFullstop``; ``chineseCounting`` comes from 37. Picking a
constant by its name and asserting the ``w:numFmt`` you expected is a truth
record that quietly lies.

Method: one paragraph style per constant in a fresh document, each linked to a
``ListTemplate`` using that ``NumberStyle``, saved, then ``numbering.xml`` read
back out of the saved file. The file is the evidence, not the COM object.

    uv run --with pywin32 python numfmt_map.py OUT.docx
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path

import win32com.client as win32

WD_STYLE_TYPE_PARAGRAPH = 1
WD_FORMAT_DOCUMENT_DEFAULT = 16
WD_DO_NOT_SAVE = 0
#: Word rejects constants outside this span with a COM error; the run records which.
CONSTANTS = range(0, 48)

HERE = Path(__file__).resolve().parent


def main() -> int:
    out = str(Path(sys.argv[1]).resolve())
    word = win32.GetActiveObject("Word.Application")
    document = word.Documents.Add()

    failed: dict[int, str] = {}
    for constant in CONSTANTS:
        try:
            style = document.Styles.Add(f"NS{constant:02d}", WD_STYLE_TYPE_PARAGRAPH)
            template = document.ListTemplates.Add(OutlineNumbered=True)
            template.ListLevels(1).NumberStyle = constant
            style.LinkToListTemplate(ListTemplate=template, ListLevelNumber=1)
        except Exception as exc:  # noqa: BLE001 - the failure itself is the datum
            failed[constant] = str(exc)[:90]

    document.SaveAs2(out, FileFormat=WD_FORMAT_DOCUMENT_DEFAULT)
    document.Close(WD_DO_NOT_SAVE)

    xml = zipfile.ZipFile(out).read("word/numbering.xml").decode("utf-8")
    found: dict[int, str] = {}
    for match in re.finditer(r'<w:numFmt w:val="([^"]+)"/><w:pStyle w:val="NS(\d+)"/>', xml):
        found[int(match.group(2))] = match.group(1)

    record = {
        "note": (
            "Measured, not documented: WdListNumberStyle constant -> the OOXML w:numFmt "
            f"Word actually writes. Produced by numfmt_map.py against Word {word.Build}. "
            "The COM constant NAMES mislead -- 26 is named GBNum1 but writes "
            "decimalEnclosedFullstop, and chineseCounting comes from 37."
        ),
        "word_build": str(word.Build),
        "measured_utc": dt.datetime.now(dt.timezone.utc).date().isoformat(),
        "map": {str(key): found[key] for key in sorted(found)},
    }
    target = HERE / "numfmt-map.json"
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    unlinked = [c for c in CONSTANTS if c not in found and c not in failed]
    print(f"{len(found)} mapped -> {len(set(found.values()))} distinct w:numFmt values; wrote {target}")
    if failed:
        print(f"rejected by Word: {sorted(failed)}")
    if unlinked:
        print(f"accepted but produced no level-1 pStyle link: {unlinked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
