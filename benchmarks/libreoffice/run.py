"""Command line for the LibreOffice corpus lane.

    python -m benchmarks.libreoffice sweep   --core <checkout> --label main [--jobs 2]
    python -m benchmarks.libreoffice compare main [--against base] [--json out.json]
    uv run --with pywin32 python -m benchmarks.libreoffice word --core <checkout>

``sweep`` reads the corpus with all2md; ``compare`` scores a sweep against the committed
Word reading, and with ``--against`` lists every file two sweeps read differently;
``word`` re-records the Word reading (Windows and Word only). A manual instrument: no
step runs it in CI, and nothing it prints is a gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.libreoffice.compare import (  # noqa: E402
    format_changes,
    format_report,
    paired,
    report_json,
    score,
)
from benchmarks.libreoffice.corpus import CorpusError, core_commit, core_root, load_word_reading  # noqa: E402
from benchmarks.libreoffice.sweep import load_sweep, sweep  # noqa: E402


def _sweep(args: argparse.Namespace) -> int:
    root = core_root(args.core)
    recorded = load_word_reading()["meta"].get("libreoffice_commit")
    commit = core_commit(root)
    if recorded and commit and commit != recorded:
        print(
            f"warning: the checkout is at {commit[:12]}, the Word reading at {recorded[:12]}; "
            "files that changed between them are left out of the comparison",
            file=sys.stderr,
        )
    only = set(args.only) if args.only else None
    out = sweep(root, args.label, jobs=args.jobs, only=only)
    print(f"swept into {out}")
    return 0


def _compare(args: argparse.Namespace) -> int:
    word_reading = load_word_reading()
    meta = word_reading["meta"]
    print(
        f"Word reading of {meta.get('date')} (Word {meta.get('word_build')}, "
        f"LibreOffice {str(meta.get('libreoffice_commit'))[:12]})"
    )
    mine = load_sweep(args.sweep)
    reports = score(word_reading, mine)
    print(format_report(reports, show=args.show, top=args.top))
    if args.against:
        print()
        print(f"{args.against} -> {args.sweep}:")
        print(format_changes(paired(word_reading, load_sweep(args.against), mine), show=args.show))
    if args.json:
        Path(args.json).write_text(
            json.dumps({"word_reading": meta, "sets": report_json(reports)}, ensure_ascii=False, indent=1),
            encoding="utf8",
        )
    return 0


def _word(args: argparse.Namespace) -> int:
    from benchmarks.libreoffice.word import record

    reading = record(core_root(args.core), set(args.skip))
    print(f"recorded {len(reading['files'])} files: {reading['meta']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LibreOffice Writer corpus: all2md against Word's reading.")
    commands = parser.add_subparsers(dest="command", required=True)

    sweep_parser = commands.add_parser("sweep", help="read the corpus with all2md")
    sweep_parser.add_argument("--core", help="LibreOffice core checkout (or ALL2MD_LIBREOFFICE_CORE)")
    sweep_parser.add_argument("--label", required=True, help="name of this reading, e.g. main or a branch")
    sweep_parser.add_argument("--jobs", type=int, default=2, help="worker processes (default 2)")
    sweep_parser.add_argument("--only", nargs="*", help="limit to these keys, e.g. export/strict.docx")
    sweep_parser.set_defaults(func=_sweep)

    compare_parser = commands.add_parser("compare", help="score a sweep against Word's reading")
    compare_parser.add_argument("sweep", help="label or directory of the sweep to score")
    compare_parser.add_argument("--against", help="label or directory of a sweep to pair with")
    compare_parser.add_argument("--show", type=int, default=8, help="words shown per file (default 8)")
    compare_parser.add_argument("--top", type=int, default=20, help="differing files listed (default 20)")
    compare_parser.add_argument("--json", help="also write the scored sweep to this file")
    compare_parser.set_defaults(func=_compare)

    word_parser = commands.add_parser("word", help="re-record Word's reading (Windows, Word, pywin32)")
    word_parser.add_argument("--core", help="LibreOffice core checkout (or ALL2MD_LIBREOFFICE_CORE)")
    word_parser.add_argument("--skip", nargs="*", default=[], help="keys Word hangs on, recorded as hangs")
    word_parser.set_defaults(func=_word)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
