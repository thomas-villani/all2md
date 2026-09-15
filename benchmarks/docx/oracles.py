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
_ORDERED = re.compile(r"^\s*(\d+)[.)]\s+", re.MULTILINE)
#: A Markdown backslash escape, which a printed label may carry (`03\)`).
_UNESCAPE = re.compile(r"\\(?=[^\w\s])")


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


def check_tracked_resolutions(case: Case, alternates: dict[str, str]) -> list[Finding]:
    """Check the other two revision resolutions, each against its recorded truth.

    ``accept`` is what the pinned profile converts, so it is checked above. The
    generating script recorded ``rejected_text`` as well, and a resolution that is
    never scored is a resolution nobody would notice breaking -- so ``reject`` is
    converted separately and held to that record.

    ``mark`` keeps both halves, which run together in the output ("crimsonbrown"), so
    neither text record applies to it. What is checkable is the property that makes
    ``mark`` worth having: every revision's text survives, and the deleted half is
    struck through rather than silently mixed into the prose.
    """
    facts = case.facts
    findings = []

    rejected = alternates.get("reject")
    if rejected is not None:
        wanted = facts.get("rejected_text", [])
        missing = [t for t in wanted if not _present(t, rejected)]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "reject: original text",
                not missing,
                "all present" if not missing else f"{len(missing)} of {len(wanted)} absent: {missing!r}",
            )
        )
        inserted = [r["text"] for r in facts.get("revisions", []) if r["type"] == "insert"]
        leaked = [t for t in inserted if _present(t, rejected)]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "reject: insertions withheld",
                not leaked,
                "none leaked" if not leaked else f"inserted text still emitted: {leaked!r}",
            )
        )

    marked = alternates.get("mark")
    if marked is not None:
        revisions = facts.get("revisions", [])
        absent = [r["text"] for r in revisions if not _present(r["text"], marked)]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "mark: both halves kept",
                not absent,
                "all present" if not absent else f"{len(absent)} of {len(revisions)} absent: {absent!r}",
            )
        )
        deletions = [r["text"] for r in revisions if r["type"] == "delete"]
        unstruck = [t for t in deletions if f"~~{t}~~" not in marked]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "mark: deletions struck",
                not unstruck,
                "all struck" if not unstruck else f"emitted as ordinary prose: {unstruck!r}",
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
    if spec.get("rendered_markers"):
        # Word printed a label Markdown list syntax cannot carry (`03)`), so the item
        # is written as the page prints it -- label, then text -- and that is what gets
        # checked. A Markdown list would pass the ordered check below while printing
        # `3.`, which is not what the page says.
        printed = _UNESCAPE.sub("", out)
        unprinted = [
            f"{marker} {item}"
            for marker, item in zip(spec["rendered_markers"], spec.get("items", []), strict=False)
            if not _present(f"{marker} {item}", printed)
        ]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "Word's labels printed",
                not unprinted,
                "all printed" if not unprinted else f"absent: {unprinted!r}",
            )
        )
    elif spec.get("ordered"):
        markers = len(_ORDERED.findall(out))
        wanted = len(spec.get("items", []))
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "rendered as ordered list",
                markers >= wanted,
                f"{markers} ordered marker(s) for {wanted} item(s)"
                + (
                    ""
                    if markers >= wanted
                    # Report the facts, not a cause: the same failing check covers
                    # numbering the parser cannot reach, numbering it reaches but
                    # cannot name, and a definition that defers to somewhere else.
                    else f"; numFmt={spec.get('numfmt')}, numPr on the {spec.get('numpr_on')}"
                    + (f", defined via {spec['defined_via']}" if spec.get("defined_via") else "")
                ),
            )
        )
        if "start" in spec:
            # Markdown cannot print `03)`, but it can print the number the list starts
            # at. A list that restarts at 1 has every item present and every marker
            # ordered, so neither check above sees a lost start value.
            first = _ORDERED.search(out)
            got = int(first.group(1)) if first else None
            findings.append(
                Finding(
                    case.case_id,
                    case.family,
                    "starts at its first number",
                    got == spec["start"],
                    f"first marker {got}, Word starts at {spec['start']}",
                )
            )
    if "sequence" in spec:
        # Every number the list prints, in order. A continuation after an interrupting
        # paragraph that restarts at 1, or a restart that keeps counting, still has
        # every item present and every marker ordered -- only the sequence shows it.
        numbers = [int(number) for number in _ORDERED.findall(out)]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "prints Word's numbers",
                numbers == spec["sequence"],
                f"printed {numbers}, Word prints {spec['sequence']}",
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
        span = f"colspan {merge['colspan']}" if "colspan" in merge else f"rowspan {merge['rowspan']}"
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "merged cell not duplicated",
                count == 1,
                f"{merge['text']!r} appears {count}x ({span}, expected 1x)",
            )
        )
    rows = [_UNESCAPE.sub("", line) for line in out.splitlines() if line.lstrip().startswith("|")]
    for cell in table.get("cell_lists", []):
        # A Markdown table cell cannot hold a list, so the number has to be printed
        # with the step, in the table row that holds it. Steps present without their
        # numbers have lost the order the document gives them.
        unnumbered = [
            f"{marker} {item}"
            for marker, item in zip(cell["markers"], cell["items"], strict=False)
            if not any(f"{marker} {item}" in row for row in rows)
        ]
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "cell list numbered",
                not unnumbered,
                "all numbered in their row" if not unnumbered else f"absent from every table row: {unnumbered!r}",
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
    # The body check is about the words; emphasis inside them is checked on its own.
    plain = out.replace("**", "")
    for note in case.facts.get("notes", []):
        present = _present(note["text"], plain)
        findings.append(Finding(case.case_id, case.family, f"{note['type']} body", present, repr(note["text"])))
        if note.get("bold"):
            bold = f"**{note['bold']}**" in out
            detail = repr(note["bold"]) + ("" if bold else " not bold")
            findings.append(Finding(case.case_id, case.family, "note bold kept", bold, detail))
        if note.get("list"):
            # Word counts a list continuously from one note into the next, so the
            # second note's items print 3. and 4.; restarting per note would print 1.
            # again with every item still present.
            unprinted = [f"{marker} {item}" for marker, item in note["list"] if not _present(f"{marker} {item}", out)]
            findings.append(
                Finding(
                    case.case_id,
                    case.family,
                    "note list numbers",
                    not unprinted,
                    "all printed" if not unprinted else f"absent: {unprinted!r}",
                )
            )
    return findings


#: The id a printed comment carries, and the id a reply names as its parent.
_COMMENT_ID = re.compile(r"^<!-- (?:Comment|Reply) (\S+)")
_REPLY_PARENT = re.compile(r" to (\S+) by ")


def check_comments(case: Case, out: str) -> list[Finding]:
    """Comments are opt-in, so the pinned profile must print the prose and no review notes."""
    facts = case.facts
    missing = [t for t in facts.get("body", []) if not _present(t, out)]
    leaked = [c["text"] for c in facts.get("comments", []) if _present(c["text"], out)]
    return [
        Finding(
            case.case_id,
            case.family,
            "commented text present",
            not missing,
            "all present" if not missing else f"absent: {missing!r}",
        ),
        Finding(
            case.case_id,
            case.family,
            "comments withheld",
            not leaked,
            "none printed by default" if not leaked else f"printed without include_comments: {leaked!r}",
        ),
    ]


def check_comment_threads(case: Case, alternates: dict[str, str]) -> list[Finding]:
    """With comments included: every comment printed, replies threaded, resolved state kept.

    The thread and the resolved flag live in ``commentsExtended.xml``, a different part
    from the comment bodies, so a reader of ``comments.xml`` alone prints every comment
    as an unresolved root and every body check still passes.
    """
    shown = alternates.get("included")
    if shown is None:
        return []
    comments = case.facts.get("comments", [])
    printed = [line for line in shown.splitlines() if line.startswith("<!--")]
    lines = [next((line for line in printed if c["text"] in line), None) for c in comments]
    findings = []
    for comment, line in zip(comments, lines, strict=True):
        label = repr(comment["text"])
        if line is None:
            findings.append(Finding(case.case_id, case.family, "comment printed", False, f"{label} absent"))
            continue
        parent = comment.get("reply_to")
        if parent is None:
            threaded = line.startswith("<!-- Comment ")
            detail = f"{label} " + ("printed as a thread root" if threaded else "printed as a reply, but is a root")
        else:
            parent_line = lines[parent]
            parent_id = _COMMENT_ID.match(parent_line) if parent_line else None
            names = _REPLY_PARENT.search(line)
            threaded = bool(
                line.startswith("<!-- Reply ") and parent_id and names and names.group(1) == parent_id.group(1)
            )
            detail = f"{label} " + ("names its parent" if threaded else "is not threaded under its parent")
        findings.append(Finding(case.case_id, case.family, "reply threaded", threaded, detail))
        resolved = "[resolved]" in line
        wanted = bool(comment.get("resolved"))
        state = f"{label} {'resolved' if resolved else 'open'}"
        if resolved != wanted:
            state += f", Word says {'resolved' if wanted else 'open'}"
        findings.append(Finding(case.case_id, case.family, "resolved state", resolved == wanted, state))
        anchored = comment.get("anchored_text")
        if anchored:
            named = f'on "{anchored}"' in line
            findings.append(
                Finding(
                    case.case_id,
                    case.family,
                    "commented text named",
                    named,
                    f"{label} on {anchored!r}" + ("" if named else " -- not named"),
                )
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
        emitted = bool(re.search(r"\$|\\frac|\\sqrt|\\pm|√", out))
        findings.append(
            Finding(
                case.case_id,
                case.family,
                "equation emitted",
                emitted,
                "math survived" if emitted else "nothing math-like in the output at all",
            )
        )
        # Presence is not correctness. A radical whose radicand silently resolved to
        # nothing still leaves `\frac{...}{...}` behind and still looks like maths --
        # so the expected LaTeX is compared in full, or the check would pass on a
        # formula that had quietly lost half of itself.
        expected = math.get("expected_latex")
        if expected:
            findings.append(
                Finding(
                    case.case_id,
                    case.family,
                    "equation latex correct",
                    _present(expected, out),
                    f"wanted {expected!r}",
                )
            )
        if math.get("display"):
            findings.append(
                Finding(
                    case.case_id,
                    case.family,
                    "equation is a block",
                    "$$" in out,
                    (
                        "emitted as a display block"
                        if "$$" in out
                        else "not a block; a standalone oMath is displayed maths"
                    ),
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
    "comments": check_comments,
    "baseline": check_baseline,
}


#: Extra conversions a family needs beyond the one pinned profile, as option
#: overrides. Revision handling has more than one right answer -- the corpus records
#: all three resolutions and scoring one of them would leave the other two free to
#: rot. Comments are opt-in, so the pinned profile cannot see them at all.
EXTRA_PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "tracked": {"reject": {"revisions": "reject"}, "mark": {"revisions": "mark"}},
    "comments": {"included": {"include_comments": True}},
}

#: The checks that read those extra conversions.
RESOLUTION_CHECKS: dict[str, Callable[[Case, dict[str, str]], list[Finding]]] = {
    "tracked": check_tracked_resolutions,
    "comments": check_comment_threads,
}


def score_case(case: Case, out: str, alternates: dict[str, str] | None = None) -> list[Finding]:
    """Every check a family defines, against one case's output.

    ``alternates`` carries the extra conversions :data:`EXTRA_PROFILES` asked for,
    keyed by name; a family with none is scored exactly as before.
    """
    check: Any = CHECKS.get(case.family)
    if check is None:
        return [Finding(case.case_id, case.family, "family known", False, f"no checks defined for {case.family!r}")]
    findings = list(check(case, out))
    resolutions = RESOLUTION_CHECKS.get(case.family)
    if resolutions is not None:
        findings.extend(resolutions(case, alternates or {}))
    return findings
