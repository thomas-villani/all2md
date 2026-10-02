# benchmarks/libreoffice — real DOCX files, scored against Word

LibreOffice's Writer regression corpus, read by all2md and compared word for word
with what Microsoft Word shows for the same file.

    python -m benchmarks.libreoffice sweep --core <checkout> --label main
    python -m benchmarks.libreoffice compare main

## Why this lane

`benchmarks/docx` holds 23 documents we made by scripting Word, so it asserts what we
believed the format means, and it is clean by construction. LibreOffice's Writer
regression files (`sw/qa/extras/ooxmlexport/data` and `sw/qa/extras/ooxmlimport/data`,
1,526 `.docx`) are documents other people made, many of them attached to bug reports:
the noisy counterpart the DOCX lane's README said it still needed.

There is no structural truth beside them, so the truth is Word itself. For each file,
Word is asked over COM what it shows: the main story, every footnote and endnote, and
every text-box story. all2md's reading is reduced to the same thing, and both sides are
compared as **word multisets** (runs of Unicode word characters, casefolded, counted).
Layout and order do not count; a word Word shows that all2md lost is *missing*, and a
word all2md has that Word does not show is *extra*.

## Posture

**A manual instrument and a ledger, not a gate.** Nothing runs it in CI. It is run by
hand before and after a DOCX reader change, and the paired comparison (below) is how
such a change is judged. The unit tests in `tests/unit/test_libreoffice_benchmark.py`
hold its arithmetic and its storage, not any reading of the corpus.

**The corpus is never committed.** It is fetched from LibreOffice at the commit the Word
reading was taken against (below).

**The Word reading is committed and dated** (`word_reading.json.gz`, about 350 KB),
because taking it needs Windows and Word. It records the date, the Word build, the
LibreOffice commit, and each file's SHA-256. A file whose digest no longer matches is
left out of the scores rather than compared with text from another version of itself.
It holds text extracted from LibreOffice's test documents, which are published under the
Mozilla Public License 2.0.

## Getting the corpus

A blob-less, sparse clone of the two data directories, at the commit the Word reading
was taken against:

```bash
git clone --filter=blob:none --sparse https://github.com/LibreOffice/core.git libreoffice-core
cd libreoffice-core
git sparse-checkout set sw/qa/extras/ooxmlexport/data sw/qa/extras/ooxmlimport/data
git checkout 6296615b8d5c96530c59b06a9873be3614a1e76c
```

Then pass `--core <path>` or set `ALL2MD_LIBREOFFICE_CORE`. A checkout at another commit
still works; `sweep` warns, and `compare` leaves out the files that changed.

## Running it

`sweep` reads every file into `.cache/<label>/`, one record per file, with `--jobs`
worker processes (default 2; `--jobs 1` runs in-process, for a debugger). It resumes: a
file with a record is not read again, so an interrupted sweep continues, and re-reading
a file means deleting its record. `--only export/strict.docx ...` limits it to some keys.

`compare <label>` prints the totals per set, every parse and render failure (with
whether Word opens the file), and the files missing the most words. `--json out.json`
writes all of it as data.

**Judging a change: pair it with its base.** Sweep the branch and the commit it is based
on, under two labels, and compare them:

```bash
git worktree add ../all2md-main main
PYTHONPATH=../all2md-main/src python -m benchmarks.libreoffice sweep --label main
python -m benchmarks.libreoffice sweep --label my-branch
python -m benchmarks.libreoffice compare my-branch --against main
```

`--against` lists every file whose status or words differ between the two sweeps, with
how its missing and extra counts moved against Word, and the words it now reads or no
longer reads. A change that should touch a dozen files and lists two hundred is
answered before its totals are read. Pairing with an older sweep of a different base
mixes other changes in, so sweep the base again when `src/` has moved.

## Reading the numbers

Neither number is pure loss or pure noise.

- **Missing includes math that is not lost.** Word shows an equation as Unicode math
  letters (`𝐴=𝜋𝑟2`); all2md writes LaTeX (`A=\pi r^{2}`), so its words differ. Math
  glyphs are counted apart as `(math)`; the rest of a math file's missing words, such
  as its digits, are not, and such files are flagged `MATH`.
- **Extra includes words Word's reading cannot see.** `Range.Text` leaves out list
  labels (`1.`, `a)`, `Sect 1.1`), which all2md prints, and `Document.Shapes` does not
  descend into grouped shapes, whose text boxes all2md reads. Extra rose from 1,895
  to 2,793 when the reader learned text boxes (#532), mostly for this reason.
- **Files Word refuses are skipped,** since there is nothing to compare with. When
  all2md also fails on one, it is listed as `Word refuses it`, which is not a defect.

## Readings

| Date | Set | Files | Identical | Word's words | Missing (math) | Extra | Fail, Word opens |
|---|---|---|---|---|---|---|---|
| 2026-09-29 | export | 1,311 | 1,021 | 122,096 | 3,908 | 1,895 | 21 |
| 2026-09-29 | import | 153 | 128 | 6,235 | 82 | 21 | 4 |
| 2026-10-01 | export | 1,332 | 1,122 | 122,198 | 657 (267) | 2,840 | 0 |
| 2026-10-01 | import | 157 | 130 | 6,310 | 17 (5) | 132 | 0 |

The first reading opened the defect stream; the second is after it was worked:

1. An XML comment in `document.xml` crashed the parser (#531).
2. Text boxes were not read (#532).
3. Tables nested in cells, and text boxes in cells, were not read; nesting is now read
   up to 30 levels and flattened below that (#534).
4. Text inside `w:dir`, `w:bdo`, `w:smartTag` and `w:customXml` was not read (#535).
5. A package naming a part it does not contain (#536), and Strict Open XML (#538), were
   refused.

Every file still failing is one Word refuses too: encrypted, malformed XML, or missing
content types. Of the 657 missing export words, 267 are math glyphs, 113 are other words
in files with equations (their digits and operators among them), and 277 are in files
without math: the stream's next leads.

## Re-recording the Word reading

```bash
uv run --with pywin32 python -m benchmarks.libreoffice word --core <checkout>
```

Word runs hidden, as a separate instance, never the user's session, and each file is
opened read-only with repair off. Records collect in `.cache/word/` and the run
resumes. If Word hangs on a file, end the hidden `WINWORD.EXE`, read the key in
`.cache/word/_inprogress`, and run again with `--skip <key>`. When every file has a
record they are packed into `word_reading.json.gz`, written deterministically so a
re-record diffs by content. Move the clone above to the new commit in the same change.
