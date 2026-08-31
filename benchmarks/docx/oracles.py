"""Per-family checks: what the document contains, against what all2md emitted.

The lane's output is a **defect ledger**, not a score. A single scalar over sixteen
documents would say nothing useful and would invite tuning against it; a list of named
failing checks says exactly what is broken and can be diffed run to run.

Every check is written against the ``facts`` the generating script recorded, never
against a belief about the parser. Where a family's construct is genuinely absent from
the output, that is what the check reports -- it does not soften a total loss into a
partial score, because the first reading of this corpus found exactly that failure mode
twice (#480, #481) and a forgiving measure would have hidden both.

Checks are deliberately coarse. Matching is text-level because the DOCX parser sets no
``source_location``, so there is nothing finer to align on yet; a check asks "is this
content present, and shaped the way the document shapes it", which is enough to catch a
dropped construct and cheap enough to stay honest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from benchmarks.docx.corpus import Case


@dataclass(frozen=True)
class Finding:
    """One check against one case."""

    case_id: str
    family: str
    check: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        return f"{'ok  ' if self.ok else 'FAIL'} {self.case_id:44s} {self.check:26s} {self.detail}"


#: Markdown ordered-list marker at the start of a line.
_ORDERED = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
#: Any markdown list marker.
_BULLET = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)


def _present(needle: str, haystack: str) -> bool:
    """Whitespace-tolerant containment; markdown re-wraps freely."""
    return " ".join(needle.split()) in " ".join(haystack.split())


def check_tracked(case: Case, out: str) -> list[Finding]:
    facts = case.facts
    findings = []
    missing = [t for t in facts.get("accepted_text", []) if not _present(t, out)]
    findings.append(
        Finding(
            case.case_id,
            case.family,
            "accepted text present",
            not missing,
            (
                "all present"
                if not missing
                else f"{len(missing)} of {len(facts.get('accepted_text', []))} absent: {missing!r}"
            ),
        )
    )
    # A deletion that survives into the output means the revisions were rejected, not
    # accepted -- worth distinguishing from a drop, since it is a different bug.
    deleted = [r["text"] for r in facts.get("revisions", []) if r["type"] == "delete"]
    leaked = [t for t in deleted if _present(t, out)]
    findings.append(
        Finding(
            case.case_id,
            case.family,
            "deleted text withheld",
            not leaked,
            "none leaked" if not leaked else f"deleted text still emitted: {leaked!r}",
        )
    )
    return findings


def check_numbering(case: Case, out: str) -> list[Finding]:
    spec = case.facts.get("list", {})
    findings = []
    missing = [i for i in spec.get("items", []) if not _present(i, out)]
    findings.append(
        Finding(
            case.case_id,
            case.family,
            "item text present",
            not missing,
            "all present" if not missing else f"absent: {missing!r}",
        )
    )
    if spec.get("ordered"):
        markers = len(_ORDERED.findall(out))
        wanted = len(spec.get("items", []))
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "rendered as ordered list",
                markers >= wanted,
                f"{markers} ordered marker(s) for {wanted} item(s)"
                + ("" if markers >= wanted else f"; numPr lives on the {spec.get('numpr_on')}"),
            )
        )
    return findings


def check_fields(case: Case, out: str) -> list[Finding]:
    facts = case.facts
    findings = []
    for field in facts.get("fields", []):
        target = field.get("resolved_target")
        if target:
            # Presence of the URL is NOT the check. A HYPERLINK field's instruction
            # leaks into the output as bare prose, so "is the URL somewhere in the
            # text" passes on precisely the defect it is meant to catch -- which it
            # did, on the first run. The question is whether the target became a
            # link, the way the w:hyperlink control does.
            linked = f"]({target})" in out
            leaked = not linked and _present(target, out)
            detail = f"{target} "
            if linked:
                detail += "emitted as a link"
            elif leaked:
                detail += "leaked as bare text -- the field instruction is printed, not resolved"
            else:
                detail += "absent -- the field code is never read"
            findings.append(Finding(case.case_id, case.family, f"{field['field_type']} linked", linked, detail))
        cached = field.get("cached_result")
        if cached:
            findings.append(
                Finding(case.case_id, case.family, f"{field['field_type']} result", _present(cached, out), repr(cached))
            )
    caption = facts.get("caption")
    if caption:
        want = caption["expected_text"]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "caption text",
                _present(want, out),
                f"wanted {want!r}" + ("" if _present(want, out) else " -- the SEQ number lives in the field result"),
            )
        )
    link = facts.get("link")
    if link:
        findings.append(Finding(case.case_id, case.family, "link target", _present(link["url"], out), link["url"]))
    return findings


def check_formatting(case: Case, out: str) -> list[Finding]:
    findings = []
    for run in case.facts.get("runs", []):
        if not run.get("effective_bold"):
            continue
        emphasised = f"**{run['text']}**" in out
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "effective bold emitted",
                emphasised,
                f"{run['text']!r} "
                + ("bold" if emphasised else f"not bold; weight is carried by style {run.get('character_style')!r}"),
            )
        )
    return findings


def check_tables(case: Case, out: str) -> list[Finding]:
    table = case.facts.get("table", {})
    findings = []
    missing = [h for h in table.get("header_row", []) if not _present(h, out)]
    findings.append(
        Finding(
            case.case_id,
            case.family,
            "header cells present",
            not missing,
            "all present" if not missing else f"absent: {missing!r}",
        )
    )
    for merge in table.get("merged", []):
        # A spanned cell holds its text once. Emitting it once per spanned column is
        # the duplication defect, and is visible as a repeat count.
        count = " ".join(out.split()).count(merge["text"])
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "merged cell not duplicated",
                count == 1,
                f"{merge['text']!r} appears {count}x (colspan {merge['colspan']}, expected 1x)",
            )
        )
    return findings


def check_sdt(case: Case, out: str) -> list[Finding]:
    findings = []
    for control in case.facts.get("sdt", []):
        if control.get("is_placeholder"):
            continue
        text = control["text"]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "content control text",
                _present(text, out),
                f"{text!r} " + ("emitted" if _present(text, out) else "absent -- content sits inside w:sdtContent"),
            )
        )
    return findings


def check_notes(case: Case, out: str) -> list[Finding]:
    findings = []
    for note in case.facts.get("notes", []):
        findings.append(
            Finding(case.case_id, case.family, f"{note['type']} body", _present(note["text"], out), repr(note["text"]))
        )
    return findings


def check_baseline(case: Case, out: str) -> list[Finding]:
    facts = case.facts
    findings = []
    for heading in facts.get("headings", []):
        marker = "#" * heading["level"]
        wanted = f"{marker} {heading['text']}"
        findings.append(
            Finding(
                case.case_id, case.family, f"h{heading['level']} emitted", _present(wanted, out), repr(heading["text"])
            )
        )
    for span in facts.get("inline", []):
        if span.get("bold"):
            findings.append(
                Finding(case.case_id, case.family, "inline bold", f"**{span['text']}**" in out, repr(span["text"]))
            )
        if span.get("italic"):
            italic = re.search(rf"(?<!\*)\*{re.escape(span['text'])}\*(?!\*)", out) is not None
            findings.append(Finding(case.case_id, case.family, "inline italic", italic, repr(span["text"])))
        if span.get("code"):
            findings.append(
                Finding(case.case_id, case.family, "inline code", f"`{span['text']}`" in out, repr(span["text"]))
            )
    math = facts.get("math")
    if math:
        # The equation is present if anything mathematical survived at all. Kept
        # deliberately weak: a weak check that fails is a strong signal.
        emitted = bool(re.search(r"\$|\\frac|\\sqrt|\\pm|√", out))
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "equation emitted",
                emitted,
                "some math survived" if emitted else "nothing math-like in the output at all",
            )
        )
    return findings


CHECKS: dict[str, Callable[[Case, str], list[Finding]]] = {
    "tracked": check_tracked,
    "numbering": check_numbering,
    "fields": check_fields,
    "formatting": check_formatting,
    "tables": check_tables,
    "sdt": check_sdt,
    "notes": check_notes,
    "baseline": check_baseline,
}


def score_case(case: Case, out: str) -> list[Finding]:
    """Every check a family defines, against one case's output."""
    check: Any = CHECKS.get(case.family)
    if check is None:
        return [Finding(case.case_id, case.family, "family known", False, f"no checks defined for {case.family!r}")]
    return list(check(case, out))
