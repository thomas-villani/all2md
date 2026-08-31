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
def test_notes_flags_a_dropped_footnote_body():
    case = make("notes", {"notes": [{"type": "footnote", "text": "The body."}]})
    assert "footnote body" in failures(case, "just the host paragraph\n")


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
    assert len(cases) == 16
    assert sum(1 for c in cases if c.is_control) == 6


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
