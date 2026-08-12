#!/usr/bin/env python3
"""Runtime for the all2md conversion-quality gate (``action.yml`` at the repo root).

Two jobs, kept in one dependency-free file so the action can run this *before* it
has installed the package it gates:

``resolve-version``
    Decide which ``all2md`` to install.
``run``
    Score the matched documents and decide the build.

Only the standard library is imported here; scoring happens by invoking the
``all2md`` CLI as a subprocess.

Three deliberate refusals to pass
---------------------------------
A gate that goes green by *not measuring* is worse than no gate, because it also
buys false confidence. Every one of the instruments in this repo shipped with a
version of that bug, so this one is built to fail loudly in the three places it
could otherwise slip through:

1. **No matched files** is a failure, not an empty pass. A typo in ``paths``
   otherwise produces a permanently green gate that never reads a document.
2. **No threshold set** is a failure. An action that runs with nothing to compare
   against is theatre, and it is the easiest state to end up in by accident.
3. **A document that cannot be converted at all** scores as a failure, not a skip.
   It is the worst possible fidelity outcome, so it must never be quieter than a
   merely low score.

Each file is scored in its own process. That costs one interpreter start per
document (~180 ms since the lazy-import work in 1.10.0) and buys two things the
batched form cannot give: every failing file is reported rather than just the
first one the CLI aborts on, and the file list never has to fit in a command line.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ``v1.10.1`` -> ``1.10.1``. Anything else (a branch, a SHA, ``main``) is not a
# release and must not be turned into a version pin.
_RELEASE_TAG = re.compile(r"^v(\d+\.\d+\.\d+(?:[-.\w]*)?)$")

TOOLS = ("roundtrip", "report")

# What each tool's score is called in the output, so the summary reads like the
# CLI it wraps rather than like this script.
_METRIC = {"roundtrip": "fidelity", "report": "confidence"}


class GateError(Exception):
    """A configuration problem that must stop the build before any scoring."""


@dataclass
class DocumentScores:
    """One document's scores, keyed by tool.

    Three states, not two, because "could not be measured" and "measured badly" are
    different verdicts and only one of them is the document's fault:

    * an ``int`` in ``scores`` -- a real measurement, comparable to a threshold;
    * ``None`` in ``scores`` -- the document could not be converted at all, a failure;
    * the tool's name in ``unassessed`` -- the tool ran and declined to judge, which is
      neither. See `score_document`.
    """

    path: str
    scores: dict[str, Optional[int]] = field(default_factory=dict)
    unassessed: set[str] = field(default_factory=set)

    def scored(self, tool: str) -> Optional[int]:
        """Return the score for *tool*, or ``None`` if it was not measured."""
        return self.scores.get(tool)


def resolve_version(explicit: str, action_ref: str) -> str:
    """Return the version specifier to install, or ``""`` for the latest release.

    The action lives in the same repository as the library, so ``@v1.10.1`` should
    mean *all2md 1.10.1* rather than "whatever is newest today". That lockstep is
    the whole reason the action ships from here: the gate's verdict **is** the
    library's score, so letting the two versions drift would silently move every
    consumer's threshold underneath them.

    Parameters
    ----------
    explicit
        The ``all2md-version`` input. Empty means "follow the action ref";
        ``latest`` always takes the newest release; anything else is a pin.
    action_ref
        ``github.action_ref`` -- the tag or branch the action was referenced by.

    """
    explicit = (explicit or "").strip()
    if explicit:
        return "" if explicit == "latest" else explicit
    match = _RELEASE_TAG.match((action_ref or "").strip())
    return match.group(1) if match else ""


def pip_spec(version: str, extras: str) -> str:
    """Build the ``pip install`` argument for *version* with *extras*."""
    suffix = f"[{extras}]" if extras else ""
    return f"all2md{suffix}=={version}" if version else f"all2md{suffix}"


def expand_paths(patterns: str, root: Path) -> list[Path]:
    """Resolve newline- or comma-separated glob *patterns* under *root*.

    Globbing happens here rather than in the shell so the file set does not depend
    on the runner's shell or on whether ``nullglob`` is set -- an unmatched pattern
    behaves identically on every platform, which for a gate matters more than
    matching shell conventions.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for raw in re.split(r"[\n,]", patterns or ""):
        pattern = raw.strip()
        if not pattern:
            continue
        for match in sorted(root.glob(pattern)):
            resolved = match.resolve()
            if match.is_file() and resolved not in seen:
                seen.add(resolved)
                found.append(match)
    return found


def score_document(
    tool: str, path: Path, via: str, executable: Optional[str] = None
) -> tuple[Optional[int], str, bool]:
    """Score one document, returning ``(score, note, assessed)``.

    A ``None`` score means the document could not be scored at all, which the caller
    must treat as a failure rather than as missing data.

    ``assessed=False`` means something different and had been silently read as a pass:
    the confidence report emits ``band: "not_assessed"`` with a **hardcoded score of
    100** when no detector ran for the document's producer. `all2md.confidence` calls
    that "a vacuous 100 that means 'no detector ran', not 'verified clean'", and it is
    the value every Markdown, text, docx, pptx and html input returns. Reading only
    ``score`` therefore turned ``--report-fail-under`` into a constant for those
    formats: an empty file, a valid file and a deliberately broken file all score 100.
    The band is the field that says so, so it is now read.
    """
    command = [executable or sys.executable, "-m", "all2md", tool, str(path), "--json"]
    if tool == "roundtrip":
        command += ["--via", via]
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()
        return None, detail[-1] if detail else f"{tool} exited {proc.returncode}", True
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, "the report was not valid JSON", True
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    score = payload.get("score")
    if not isinstance(score, int):
        return None, "the report carried no score", True
    if payload.get("band") == "not_assessed":
        return None, "no confidence detector ran for this format", False
    return score, "", True


def _thresholds(args: argparse.Namespace) -> dict[str, int]:
    """Collect the thresholds that were actually set, rejecting an empty gate."""
    chosen = {
        tool: getattr(args, f"{tool}_fail_under") for tool in TOOLS if getattr(args, f"{tool}_fail_under") is not None
    }
    if not chosen:
        raise GateError(
            "Set roundtrip-fail-under, report-fail-under, or both. "
            "With neither, this action reads every document and can never fail, "
            "which looks like a passing quality gate but is not one."
        )
    for tool, value in chosen.items():
        if not 0 <= value <= 100:
            raise GateError(f"{tool}-fail-under must be between 0 and 100, got {value}.")
    return chosen


def _summarise(rows: list[DocumentScores], thresholds: dict[str, int], calibration: list[str]) -> str:
    """Render the job summary shown on the workflow run page."""
    header = "| Document | " + " | ".join(_METRIC[t].title() for t in thresholds) + " |"
    divider = "|---" * (len(thresholds) + 1) + "|"
    lines = [header, divider]
    for row in rows:
        cells = []
        for tool in thresholds:
            score = row.scored(tool)
            if tool in row.unassessed:
                # Never a bare number here: the underlying payload says 100, and printing
                # it is how this read as a passing gate for every Markdown document.
                cells.append("_not assessed_")
                continue
            if score is None:
                cells.append("**not convertible**")
            else:
                mark = "" if score >= thresholds[tool] else " :x:"
                cells.append(f"{score}{mark}")
        lines.append(f"| `{row.path}` | " + " | ".join(cells) + " |")
    body = "\n".join(lines)
    thresholds_text = ", ".join(f"{_METRIC[t]} ≥ {v}" for t, v in thresholds.items())
    return f"## all2md quality gate\n\n" f"{len(rows)} document(s), gated on {thresholds_text}.\n\n{body}\n\n" + (
        "\n".join(calibration) + "\n" if calibration else ""
    )


def _calibration_notes(rows: list[DocumentScores], thresholds: dict[str, int]) -> list[str]:
    """Warn when a threshold sits so far below reality that it cannot fire.

    Real documents in this repo's own fixtures score 99-100, so a threshold picked
    by intuition -- 80, say -- has twenty points of dead headroom and will pass
    through any regression short of total breakage. That is the same defect the
    absolute timing ceilings in ``tests/performance`` had, and it is invisible
    precisely because it looks like a passing gate. Say so, rather than let a
    number that never fires read as evidence of quality.
    """
    notes = []
    for tool, threshold in thresholds.items():
        scores = [s for s in (r.scored(tool) for r in rows) if s is not None]
        if not scores:
            continue
        worst = min(scores)
        if worst - threshold >= 10:
            notes.append(
                f"> [!NOTE]\n"
                f"> Lowest {_METRIC[tool]} is {worst}, against a threshold of {threshold} "
                f"-- {worst - threshold} points of headroom. A threshold this far below "
                f"your documents' actual scores will not catch a regression. Consider "
                f"raising `{tool}-fail-under` to {worst}."
            )
    return notes


def _emit(name: str, value: str) -> None:
    """Write a step output, when running inside GitHub Actions."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def run(args: argparse.Namespace) -> int:
    """Score the matched documents and return the exit code for the build."""
    thresholds = _thresholds(args)

    root = Path(args.working_directory).resolve()
    files = expand_paths(args.paths, root)
    if not files:
        raise GateError(
            f"No files matched {args.paths!r} under {root}. "
            "Refusing to report success without reading a document -- an empty match "
            "is almost always a wrong pattern, and it would pass forever."
        )

    rows: list[DocumentScores] = []
    for path in files:
        row = DocumentScores(path=path.relative_to(root).as_posix())
        for tool in thresholds:
            score, note, assessed = score_document(tool, path, args.via, args.executable)
            row.scores[tool] = score
            if not assessed:
                row.unassessed.add(tool)
                print(f"{row.path}: {_METRIC[tool]} not assessed -- {note}", file=sys.stderr)
            elif score is None:
                print(f"{row.path}: {tool} could not score this document -- {note}", file=sys.stderr)
        rows.append(row)

    # A threshold that judged nothing is the defect this gate exists to refuse, and it is
    # the one the gate had itself: every root Markdown file returns an unassessed 100, so
    # `--report-fail-under 100` could not fail. Refusing here rather than passing keeps a
    # mixed corpus working -- only a threshold with no assessable document at all is an
    # error, not one whose Markdown files happen to be unassessable.
    for tool in thresholds:
        if all(tool in row.unassessed for row in rows):
            raise GateError(
                f"{tool}-fail-under was set, but not one of the {len(rows)} matched "
                f"document(s) could be assessed for {_METRIC[tool]}: all2md reports "
                f"band 'not_assessed' for every one, which carries a placeholder score "
                f"of 100 rather than a measurement. This threshold could only ever pass. "
                f"Drop {tool}-fail-under, or point it at formats with "
                f"{_METRIC[tool]} detectors."
            )

    failures = []
    for row in rows:
        for tool, threshold in thresholds.items():
            if tool in row.unassessed:
                continue
            score = row.scored(tool)
            if score is None:
                failures.append(f"{row.path}: could not be converted at all")
            elif score < threshold:
                failures.append(f"{row.path}: {_METRIC[tool]} {score} is below {threshold}")

    calibration = _calibration_notes(rows, thresholds)
    summary = _summarise(rows, thresholds, calibration)
    print(summary)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")

    for tool in thresholds:
        scores = [s for s in (r.scored(tool) for r in rows) if s is not None]
        _emit(f"worst-{_METRIC[tool]}", str(min(scores)) if scores else "")
    _emit("files-checked", str(len(files)))

    if failures:
        print("\nQuality gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the action."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    version = sub.add_parser("resolve-version", help="print the pip specifier to install")
    version.add_argument("--explicit", default="")
    version.add_argument("--action-ref", default="")
    version.add_argument("--extras", default="all")

    gate = sub.add_parser("run", help="score documents and gate the build")
    gate.add_argument("--paths", required=True)
    gate.add_argument("--roundtrip-fail-under", type=int, default=None)
    gate.add_argument("--report-fail-under", type=int, default=None)
    gate.add_argument("--via", default="markdown")
    gate.add_argument("--working-directory", default=".")
    gate.add_argument("--executable", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "resolve-version":
            print(pip_spec(resolve_version(args.explicit, args.action_ref), args.extras))
            return 0
        return run(args)
    except GateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
