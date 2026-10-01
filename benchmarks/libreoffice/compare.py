"""Score an all2md sweep against Word's reading, and one sweep against another.

Both sides are reduced to a **word multiset**: runs of Unicode word characters, casefolded, counted.
Layout, order and Markdown syntax do not matter; a word Word shows and all2md lost is
*missing*, a word all2md has and Word does not show is *extra*. Word's side is its main
story, every footnote and endnote, and every top-level text-box story, since all2md reads
notes by default and text boxes as blocks after their anchor.

Neither number is pure loss or pure noise, and the README says what each is made of. In
short: math is written as Unicode by Word and LaTeX by all2md, so math glyphs count as
missing without being lost (they are counted apart as ``missing_math``); list labels and
text inside grouped shapes are invisible to Word's reading, so they count as extra
without being wrong.

The paired comparison is the instrument for a change: sweep the branch and ``main`` from
the same corpus, and every file whose reading differs is listed with how its missing and
extra counts moved. Comparing against an older sweep of a different base mixes in other
changes, so pair a branch with the commit it is based on.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from benchmarks.libreoffice.corpus import SETS

WORD = re.compile(r"\w+", re.UNICODE)

#: Word's placeholders for an embedded object, a note mark, field delimiters and an
#: optional hyphen. They are not text, and a field delimiter can sit inside a word.
WORD_PLACEHOLDERS = dict.fromkeys(map(ord, "\x01\x02\x05\x08\x13\x14\x15\x1f"))


def words(text: str) -> Counter[str]:
    return Counter(WORD.findall(text.translate(WORD_PLACEHOLDERS).casefold()))


def is_math_glyph(token: str) -> bool:
    """Return whether a word holds a math alphanumeric or Greek letter, as Word writes math."""
    return any(0x1D400 <= ord(char) <= 0x1D7FF or 0x0391 <= ord(char) <= 0x03C9 for char in token)


def word_text(record: Mapping[str, Any]) -> str:
    """Return everything Word showed for one file: main story, notes, text-box stories."""
    parts = [record.get("main", ""), *record.get("footnotes", []), *record.get("endnotes", [])]
    return " ".join([*parts, *record.get("shapes", [])])


@dataclass
class FileScore:
    key: str
    words: int
    missing: Counter[str]
    extra: Counter[str]
    has_math: bool

    @property
    def identical(self) -> bool:
        return not self.missing and not self.extra


@dataclass
class SetReport:
    """One corpus set scored: the per-file scores and every file left out, with why."""

    name: str
    scores: list[FileScore] = field(default_factory=list)
    #: all2md failed: (key, error, whether Word opened the file).
    parse_failures: list[tuple[str, str, bool]] = field(default_factory=list)
    render_failures: list[tuple[str, str]] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)

    @property
    def totals(self) -> dict[str, int]:
        missing = sum((score.missing for score in self.scores), Counter[str]())
        return {
            "files": len(self.scores),
            "identical": sum(score.identical for score in self.scores),
            "words": sum(score.words for score in self.scores),
            "missing": sum(missing.values()),
            "missing_math": sum(count for token, count in missing.items() if is_math_glyph(token)),
            "extra": sum(sum(score.extra.values()) for score in self.scores),
            "parse_failures_word_ok": sum(word_ok for _, _, word_ok in self.parse_failures),
            "parse_failures_word_refuses": sum(not word_ok for _, _, word_ok in self.parse_failures),
            "render_failures": len(self.render_failures),
        }


def score_file(key: str, word: Mapping[str, Any], mine: Mapping[str, Any]) -> FileScore:
    theirs, ours = words(word_text(word)), words(mine["text"])
    return FileScore(key, sum(theirs.values()), theirs - ours, ours - theirs, bool(mine.get("math")))


def score(word_reading: Mapping[str, Any], sweep: Mapping[str, Mapping[str, Any]]) -> list[SetReport]:
    """Score a sweep against the Word reading, one report per corpus set."""
    reports = {name: SetReport(name) for name in SETS}
    for key, word in sorted(word_reading["files"].items()):
        report = reports[key.split("/", 1)[0]]
        mine = sweep.get(key)
        if mine is None:
            report.skipped["not swept"] += 1
            continue
        if word.get("sha256") and mine.get("sha256") and word["sha256"] != mine["sha256"]:
            report.skipped["changed since the Word reading"] += 1
            continue
        word_ok = word.get("status") == "ok"
        if mine["status"] != "ok":
            report.parse_failures.append((key, mine.get("error", ""), word_ok))
            continue
        if mine.get("render_error"):
            report.render_failures.append((key, mine["render_error"]))
        if not word_ok:
            report.skipped[f"Word {word.get('status')}"] += 1
            continue
        report.scores.append(score_file(key, word, mine))
    for key in sweep.keys() - word_reading["files"].keys():
        reports[key.split("/", 1)[0]].skipped["not in the Word reading"] += 1
    return list(reports.values())


@dataclass
class Change:
    """A file whose reading differs between two sweeps."""

    key: str
    before: str
    after: str
    missing_delta: int = 0
    extra_delta: int = 0
    gained: Counter[str] = field(default_factory=Counter)
    lost: Counter[str] = field(default_factory=Counter)


def _status(record: Mapping[str, Any] | None) -> str:
    if record is None:
        return "absent"
    return "ok" if record["status"] == "ok" else "fail"


def paired(
    word_reading: Mapping[str, Any],
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
) -> list[Change]:
    """List every file whose status or words differ between two sweeps of the same corpus.

    ``gained`` and ``lost`` are the words the second sweep has more or fewer of than the
    first; the deltas say how that moved the file's missing and extra counts against Word.
    """
    changes = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        old_status, new_status = _status(old), _status(new)
        if old_status != new_status:
            changes.append(Change(key, old_status, new_status))
            continue
        if old is None or new is None or old_status != "ok":
            continue
        old_words, new_words = words(old["text"]), words(new["text"])
        if old_words == new_words:
            continue
        change = Change(key, "ok", "ok", gained=new_words - old_words, lost=old_words - new_words)
        word = word_reading["files"].get(key)
        if word is not None and word.get("status") == "ok":
            old_score, new_score = score_file(key, word, old), score_file(key, word, new)
            change.missing_delta = sum(new_score.missing.values()) - sum(old_score.missing.values())
            change.extra_delta = sum(new_score.extra.values()) - sum(old_score.extra.values())
        changes.append(change)
    return changes


def _sample(counter: Counter[str], show: int) -> str:
    return " ".join(token for token, _ in counter.most_common(show))


def format_report(reports: Iterable[SetReport], show: int = 8, top: int = 20) -> str:
    """Render the scored sweep: the totals table, then failures, then the worst files."""
    reports = list(reports)
    lines = [
        "set      files  identical    words  missing  (math)    extra  fail(Word ok)  fail(Word refuses)",
    ]
    for report in reports:
        t = report.totals
        lines.append(
            f"{report.name:8} {t['files']:5} {t['identical']:10} {t['words']:8} {t['missing']:8} "
            f"{t['missing_math']:7} {t['extra']:8} {t['parse_failures_word_ok']:14} "
            f"{t['parse_failures_word_refuses']:19}"
        )
    for report in reports:
        if report.skipped:
            lines.append(f"{report.name}: skipped {dict(report.skipped)}")
    for report in reports:
        for key, error, word_ok in report.parse_failures:
            lines.append(f"  FAIL   {key:55} Word {'opens it' if word_ok else 'refuses it'}: {error[:110]}")
        for key, error in report.render_failures:
            lines.append(f"  RENDER {key:55} {error[:120]}")
    scores = sorted(
        (score for report in reports for score in report.scores if not score.identical),
        key=lambda score: -sum(score.missing.values()),
    )
    if top and scores:
        lines.append("")
        lines.append(f"most words missing (top {min(top, len(scores))} of {len(scores)} differing files):")
        for item in scores[:top]:
            flag = " MATH" if item.has_math else ""
            lines.append(
                f"{item.key:60} words={item.words:5} missing={sum(item.missing.values()):4} "
                f"extra={sum(item.extra.values()):4}{flag}"
            )
            if item.missing and show:
                lines.append(f"    missing: {_sample(item.missing, show)}")
            if item.extra and show:
                lines.append(f"    extra:   {_sample(item.extra, show)}")
    return "\n".join(lines)


def format_changes(changes: list[Change], show: int = 8) -> str:
    if not changes:
        return "no file reads differently"
    lines = [f"{len(changes)} file(s) read differently:"]
    for change in changes:
        if change.before != change.after:
            lines.append(f"  {change.key:60} {change.before} -> {change.after}")
            continue
        lines.append(f"  {change.key:60} missing {change.missing_delta:+d}, extra {change.extra_delta:+d} against Word")
        if change.gained and show:
            lines.append(f"      now reads: {_sample(change.gained, show)}")
        if change.lost and show:
            lines.append(f"      no longer: {_sample(change.lost, show)}")
    return "\n".join(lines)


def report_json(reports: Iterable[SetReport]) -> dict[str, Any]:
    """Return the scored sweep as data: totals per set, failures, and every differing file."""
    out: dict[str, Any] = {}
    for report in reports:
        out[report.name] = {
            "totals": report.totals,
            "skipped": dict(report.skipped),
            "parse_failures": [
                {"key": key, "error": error, "word_opens": word_ok} for key, error, word_ok in report.parse_failures
            ],
            "render_failures": [{"key": key, "error": error} for key, error in report.render_failures],
            "differing": [
                {"key": s.key, "words": s.words, "missing": dict(s.missing), "extra": dict(s.extra), "math": s.has_math}
                for s in report.scores
                if not s.identical
            ],
        }
    return out
