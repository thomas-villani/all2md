"""Red-path tests for the DOCX lane's oracle and corpus loader.

Every check gets shown failing on deliberately broken output. An oracle that cannot
fail is worthless, and this lane found the point the hard way: its `fields` check
originally asked "does the URL appear anywhere in the text", which passes on the very
defect it exists to catch, because a HYPERLINK field's instruction leaks into the
output as bare prose. It reported a pass on a broken document until it was made to
prove it could fail.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.docx.corpus import Case, CorpusError, load_corpus
from benchmarks.docx.oracles import score_case

pytestmark = [pytest.mark.unit, pytest.mark.docx]


def make(family: str, facts: dict, *, control: bool = False) -> Case:
    return Case(
        case_id=f"{family}/synthetic",
        family=family,
        path=Path("unused.docx"),
        expected={"facts": facts, "control": control},
    )


def failures(case: Case, out: str) -> list[str]:
    return [f.check for f in score_case(case, out) if not f.ok]


# --------------------------------------------------------------------------- tracked
TRACKED = {
    "accepted_text": ["Kept sentence.", "Inserted sentence."],
    "revisions": [{"type": "delete", "text": "Removed sentence."}],
}


def test_tracked_passes_on_accepted_output():
    assert not failures(make("tracked", TRACKED), "Kept sentence.\n\nInserted sentence.\n")


def test_tracked_flags_a_dropped_insertion():
    assert "accepted text present" in failures(make("tracked", TRACKED), "Kept sentence.\n")


def test_tracked_flags_a_leaked_deletion():
    out = "Kept sentence.\n\nInserted sentence.\n\nRemoved sentence.\n"
    assert "deleted text withheld" in failures(make("tracked", TRACKED), out)


# ------------------------------------------------------------------------- numbering
NUMBERING = {"list": {"ordered": True, "items": ["One", "Two"], "numpr_on": "style"}}


def test_numbering_passes_on_a_real_ordered_list():
    assert not failures(make("numbering", NUMBERING), "1. One\n2. Two\n")


def test_numbering_flags_items_emitted_as_plain_paragraphs():
    checks = failures(make("numbering", NUMBERING), "One\n\nTwo\n")
    assert "rendered as ordered list" in checks
    assert "item text present" not in checks  # the text is there; the numbering is not


def test_numbering_flags_missing_items():
    assert "item text present" in failures(make("numbering", NUMBERING), "1. One\n")


STARTS_AT_3 = {"list": {**NUMBERING["list"], "start": 3}}


def test_numbering_passes_when_the_start_value_survives():
    assert not failures(make("numbering", STARTS_AT_3), "3. One\n4. Two\n")


def test_numbering_flags_a_list_restarted_at_one():
    assert failures(make("numbering", STARTS_AT_3), "1. One\n2. Two\n") == ["starts at its first number"]


PRINTED_LABELS = {"list": {**STARTS_AT_3["list"], "rendered_markers": ["03)", "04)"]}}


def test_numbering_passes_when_word_labels_are_printed_even_escaped():
    assert not failures(make("numbering", PRINTED_LABELS), "03\\) One\n\n04\\) Two\n")


def test_numbering_flags_a_markdown_list_that_drops_word_labels():
    assert failures(make("numbering", PRINTED_LABELS), "3. One\n4. Two\n") == ["Word's labels printed"]


# ---------------------------------------------------------------------------- fields
FIELDS = {"fields": [{"field_type": "HYPERLINK", "resolved_target": "https://example.com/x"}]}


def test_fields_passes_when_the_target_becomes_a_link():
    assert not failures(make("fields", FIELDS), "see [x](https://example.com/x) here\n")


def test_fields_flags_a_field_instruction_leaking_as_bare_text():
    """The regression this whole module exists for: a pass on a broken document."""
    assert "HYPERLINK linked" in failures(make("fields", FIELDS), "https://example.com/x glued to prose\n")


def test_fields_flags_a_missing_caption_number():
    case = make("fields", {"caption": {"expected_text": "Figure 1: A probe figure"}})
    assert "caption text" in failures(case, "Figure : A probe figure\n")


# ------------------------------------------------------------------------ formatting
FORMATTING = {"runs": [{"text": "LABEL", "effective_bold": True, "character_style": "S"}]}


def test_formatting_passes_on_emitted_bold():
    assert not failures(make("formatting", FORMATTING), "a **LABEL** word\n")


def test_formatting_flags_style_carried_weight_that_was_lost():
    assert "effective bold emitted" in failures(make("formatting", FORMATTING), "a LABEL word\n")


# ---------------------------------------------------------------------------- tables
TABLES = {"table": {"header_row": ["H1"], "merged": [{"text": "spanned", "colspan": 2}]}}


def test_tables_passes_when_a_merged_cell_appears_once():
    assert not failures(make("tables", TABLES), "| H1 |\n| spanned |\n")


def test_tables_flags_a_merged_cell_duplicated_across_its_span():
    assert "merged cell not duplicated" in failures(make("tables", TABLES), "| H1 |\n| spanned | spanned |\n")


def test_tables_flags_missing_headers():
    assert "header cells present" in failures(make("tables", TABLES), "| spanned |\n")


# ------------------------------------------------------------------------------- sdt
SDT = {"sdt": [{"text": "Author Name", "is_placeholder": False}]}


def test_sdt_flags_dropped_control_content():
    assert "content control text" in failures(make("sdt", SDT), "nothing here\n")


def test_sdt_ignores_placeholder_content():
    case = make("sdt", {"sdt": [{"text": "Click to enter", "is_placeholder": True}]})
    assert not failures(case, "nothing here\n")


# ----------------------------------------------------------------------------- notes
SEQUENCE = {"list": {"ordered": True, "items": ["A", "B", "C"], "sequence": [1, 2, 1]}}


def test_numbering_passes_when_word_numbers_are_printed_in_order():
    assert not failures(make("numbering", SEQUENCE), "1. A\n2. B\n\nBreak.\n\n1) C\n")


def test_numbering_flags_a_restart_that_kept_counting():
    assert failures(make("numbering", SEQUENCE), "1. A\n2. B\n\nBreak.\n\n3. C\n") == ["prints Word's numbers"]


CELL_LIST = {
    "table": {
        "header_row": ["Task", "Steps"],
        "cell_lists": [{"row": 2, "col": 2, "items": ["Build", "Ship"], "markers": ["1.", "2."]}],
    }
}


def test_tables_pass_when_cell_steps_keep_their_numbers():
    out = "| Task | Steps |\n|---|---|\n| Deploy | 1\\. Build<br>2\\. Ship |\n"
    assert not failures(make("tables", CELL_LIST), out)


def test_tables_flag_cell_steps_that_lost_their_numbers():
    out = "| Task | Steps |\n|---|---|\n| Deploy | Build<br>Ship |\n"
    assert failures(make("tables", CELL_LIST), out) == ["cell list numbered"]


def test_tables_flag_numbers_printed_outside_the_table():
    out = "| Task | Steps |\n|---|---|\n| Deploy | |\n\n1. Build\n2. Ship\n"
    assert failures(make("tables", CELL_LIST), out) == ["cell list numbered"]


# ----------------------------------------------------------------------------- notes
def test_notes_flags_a_dropped_footnote_body():
    case = make("notes", {"notes": [{"type": "footnote", "text": "The body."}]})
    assert "footnote body" in failures(case, "just the host paragraph\n")


NOTE_LIST = {
    "notes": [
        {"type": "footnote", "text": "Steps with a bold word:", "bold": "bold", "list": [["1.", "One"]]},
        {"type": "footnote", "text": "More:", "list": [["2.", "Two"]]},
    ]
}


def test_notes_pass_when_a_list_keeps_counting_into_the_next_note():
    out = "[^1]: Steps with a **bold** word:\n\n    1. One\n\n[^2]: More:\n\n    2. Two\n"
    assert not failures(make("notes", NOTE_LIST), out)


def test_notes_flag_a_list_restarted_in_each_note():
    out = "[^1]: Steps with a **bold** word:\n\n    1. One\n\n[^2]: More:\n\n    1. Two\n"
    assert failures(make("notes", NOTE_LIST), out) == ["note list numbers"]


def test_notes_flag_lost_bold():
    out = "[^1]: Steps with a bold word:\n\n    1. One\n\n[^2]: More:\n\n    2. Two\n"
    assert failures(make("notes", NOTE_LIST), out) == ["note bold kept"]


# -------------------------------------------------------------------------- comments
COMMENTS = {
    "body": ["The commented sentence."],
    "comments": [
        {"text": "Root note.", "anchored_text": "commented sentence", "reply_to": None, "resolved": False},
        {"text": "A reply.", "reply_to": 0, "resolved": False},
        {"text": "Done note.", "anchored_text": "commented sentence", "reply_to": None, "resolved": True},
    ],
}
THREADS = (
    "The commented sentence.\n\n"
    '<!-- Comment c1 by A (d) on "commented sentence": Root note. -->\n\n'
    '<!-- Reply c2 to c1 by A (d) on "commented sentence": A reply. -->\n\n'
    '<!-- Comment c3 by A (d) [resolved] on "commented sentence": Done note. -->\n'
)


def comment_failures(included: str, default: str = "The commented sentence.\n") -> list[str]:
    return [f.check for f in score_case(make("comments", COMMENTS), default, {"included": included}) if not f.ok]


def test_comments_pass_on_threaded_output():
    assert not comment_failures(THREADS)


def test_comments_flag_review_notes_printed_by_default():
    assert "comments withheld" in comment_failures(THREADS, default=THREADS)


def test_comments_flag_a_reply_printed_as_a_root():
    flat = THREADS.replace("<!-- Reply c2 to c1 by", "<!-- Comment c2 by")
    assert comment_failures(flat) == ["reply threaded"]


def test_comments_flag_a_reply_naming_the_wrong_parent():
    assert comment_failures(THREADS.replace("to c1 by", "to c3 by")) == ["reply threaded"]


def test_comments_flag_a_lost_resolved_state():
    assert comment_failures(THREADS.replace(" [resolved]", "")) == ["resolved state"]


# -------------------------------------------------------------------------- baseline
BASELINE = {
    "headings": [{"level": 2, "text": "Section"}],
    "inline": [{"text": "b", "bold": True}, {"text": "i", "italic": True}],
    "math": {"unicodemath": "x"},
}


def test_baseline_passes_on_complete_output():
    assert not failures(make("baseline", BASELINE), "## Section\n\n**b** and *i* and $x$\n")


def test_baseline_flags_a_heading_emitted_at_the_wrong_level():
    assert "h2 emitted" in failures(make("baseline", BASELINE), "# Section\n\n**b** and *i* and $x$\n")


def test_baseline_flags_a_dropped_equation():
    assert "equation emitted" in failures(make("baseline", BASELINE), "## Section\n\n**b** and *i*\n")


def test_baseline_italic_check_is_not_fooled_by_bold():
    """`**i**` is bold, not italic; a naive `*i*` substring test would pass on it."""
    assert "inline italic" in failures(make("baseline", BASELINE), "## Section\n\n**b** and **i** and $x$\n")


# ---------------------------------------------------------------------- unknown family
def test_an_unknown_family_fails_rather_than_scoring_zero_checks():
    assert "family known" in failures(make("nonsense", {}), "anything")


# ---------------------------------------------------------------------------- corpus
def test_the_committed_corpus_verifies():
    cases = load_corpus()
    assert len(cases) == 23
    assert sum(1 for c in cases if c.is_control) == 6


def score_the_committed_corpus():
    """Every committed case converted and scored. Returns (findings, crashes)."""
    from benchmarks.docx.run import alternates, convert

    findings, crashes = [], []
    for case in sorted(load_corpus(), key=lambda c: c.case_id):
        try:
            out = convert(case)
            extra = alternates(case)
        except Exception as exc:  # noqa: BLE001 - a crash is the thing being tested for
            crashes.append(f"{case.case_id}: {type(exc).__name__}: {exc}")
            continue
        findings.extend(score_case(case, out, extra))
    return findings, crashes


def test_no_committed_case_crashes_the_parser():
    """The lane's first gate, run per-PR rather than only by hand.

    ``python -m benchmarks.docx`` is crash- and control-gated and never gated on the
    defect count, and that gate lived only on a developer's machine while six fixes
    landed against it. It is cheap enough to be a test -- the corpus is committed
    bytes, so there is no download and nothing external to be hostage to -- and a
    regression on real Word output is exactly what the hand-built fixtures elsewhere
    in ``tests/unit/formats/docx/`` cannot catch.
    """
    _, crashes = score_the_committed_corpus()
    assert not crashes, "conversion crashed:\n  " + "\n  ".join(crashes)


def test_no_control_case_reports_a_defect():
    """A control failing means the lane is wrong, not that the parser is.

    Kept separate from the crash gate because the two say different things: a crash
    is a parser bug, a failing control is a bad oracle or an over-claiming case. Both
    earned their keep on the lane's first run.
    """
    findings, _ = score_the_committed_corpus()
    controls = {c.case_id for c in load_corpus() if c.is_control}
    failed = [str(f) for f in findings if not f.ok and f.case_id in controls]
    assert not failed, "control case(s) reporting a defect:\n  " + "\n  ".join(failed)


def test_the_defect_ledger_is_not_gated_on_its_count():
    """The count is recorded, deliberately without an assertion on its value.

    A gate on the defect count would punish finding things -- adding a corpus case
    that exposes a real defect would break the build. What this pins instead is that
    scoring produces findings at all, so a loader or oracle that silently scores
    nothing cannot read as a clean run.
    """
    findings, _ = score_the_committed_corpus()
    assert len(findings) > 30
    assert {f.family for f in findings} >= {"tracked", "numbering", "fields", "tables"}


def build_corpus(tmp_path: Path, *, document: bytes = b"docx bytes") -> Path:
    """A minimal, valid corpus on disk. Returns the manifest path."""
    import hashlib

    (tmp_path / "corpus" / "tracked").mkdir(parents=True)
    (tmp_path / "expected" / "tracked").mkdir(parents=True)
    doc = tmp_path / "corpus" / "tracked" / "synthetic.docx"
    doc.write_bytes(document)
    truth = tmp_path / "expected" / "tracked" / "synthetic.json"
    truth.write_text(json.dumps({"case_id": "tracked/synthetic", "facts": {}}), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "provenance": {},
        "cases": [
            {
                "case_id": "tracked/synthetic",
                "family": "tracked",
                "path": "corpus/tracked/synthetic.docx",
                "sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
                "size_bytes": doc.stat().st_size,
                "generator": "cases/tracked/synthetic.json",
                "expected_sha256": hashlib.sha256(truth.read_bytes()).hexdigest(),
                "resave_stable": True,
                "resave_failures": [],
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_the_synthetic_corpus_loads(tmp_path: Path):
    """The green path, so the red ones below mean something."""
    assert len(load_corpus(build_corpus(tmp_path))) == 1


def test_a_tampered_document_is_rejected(tmp_path: Path):
    """The digest pin is the whole reason to trust a committed corpus."""
    path = build_corpus(tmp_path)
    (tmp_path / "corpus" / "tracked" / "synthetic.docx").write_bytes(b"tampered!!")
    with pytest.raises(CorpusError, match="digest"):
        load_corpus(path)


def test_a_truth_record_edited_without_a_re_record_is_rejected(tmp_path: Path):
    """Document and truth must move together, or the corpus lies confidently."""
    path = build_corpus(tmp_path)
    truth = tmp_path / "expected" / "tracked" / "synthetic.json"
    truth.write_text(json.dumps({"case_id": "tracked/synthetic", "facts": {"edited": True}}), encoding="utf-8")
    with pytest.raises(CorpusError, match="truth record has changed"):
        load_corpus(path)


def test_a_manifest_key_typo_is_rejected(tmp_path: Path):
    path = build_corpus(tmp_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["cases"][0]["sha_256"] = manifest["cases"][0].pop("sha256")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusError, match="key mismatch"):
        load_corpus(path)


def test_a_boolean_size_is_rejected(tmp_path: Path):
    """`bool` is an `int` in Python, so a bare isinstance check would pass this."""
    path = build_corpus(tmp_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["cases"][0]["size_bytes"] = True
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusError, match="positive int"):
        load_corpus(path)


def test_a_schema_bump_is_rejected(tmp_path: Path):
    forged = tmp_path / "manifest.json"
    forged.write_text(json.dumps({"schema_version": 99, "cases": []}), encoding="utf-8")
    with pytest.raises(CorpusError, match="schema"):
        load_corpus(forged)
