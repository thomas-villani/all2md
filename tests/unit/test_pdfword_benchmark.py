"""The PDF to Word lane: its scorer, its corpus loader, and a crash gate over the real PDFs.

An oracle that cannot fail is worthless, so each check is shown failing on the defect it exists
to catch. The defects used here are the ones the first probe found in real conversions.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from benchmarks.pdfword.corpus import MANIFEST, CorpusError, load_corpus
from benchmarks.pdfword.reading import Paragraph, Reading, Table
from benchmarks.pdfword.score import is_perfect, score, strip_marker, summarize

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

CLAUSE_A = "The Customer shall pay the Fees within forty-five days of each invoice."
CLAUSE_B = "Overdue amounts bear interest at one and one half percent per month."
TRUTH = Reading(
    blocks=(
        Paragraph("Master Agreement", style="Title", level=0),
        Paragraph("Fees and Payment", style="Heading 1", level=1, marker="1.", list_level=1),
        Paragraph(CLAUSE_A, marker="1.1", list_level=2),
        Paragraph(CLAUSE_B, marker="1.2", list_level=2),
        Table(rows=(("Service", "Fee"), ("Hosting", "$10"), ("Support", ""))),
    ),
    footnotes=("Interest accrues daily from the due date.",),
    headers=("CONFIDENTIAL",),
    footers=("Master Agreement, page 1",),
    pictures=1,
    pages=2,
    page_width=612.0,
    page_height=792.0,
    margins=(72.0, 72.0, 72.0, 72.0),
    body_font="Aptos",
    body_size=12.0,
)


def with_blocks(*blocks: Paragraph | Table) -> Reading:
    return replace(TRUTH, blocks=blocks)


def test_a_document_scored_against_itself_is_perfect() -> None:
    assert is_perfect(score(TRUTH, TRUTH)) == []


def test_a_reading_survives_json() -> None:
    assert Reading.from_json(json.loads(json.dumps(TRUTH.to_json()))) == TRUTH


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1.1 The text", "The text"), ("(a) The text", "The text"), ("2. The text", "The text"), ("The text", "The text")],
)
def test_strip_marker(text: str, expected: str) -> None:
    assert strip_marker(text) == expected


def test_clauses_run_together_read_as_merged() -> None:
    got = with_blocks(*TRUTH.blocks[:2], Paragraph(f"1.1 {CLAUSE_A} 1.2 {CLAUSE_B}"), TRUTH.blocks[4])
    result = score(TRUTH, got)
    assert result["paragraphs"]["merged"] == 2
    assert result["paragraphs"]["whole"] == 0
    assert result["lists"]["own_paragraph"] == 1  # only the heading; the merged clauses don't count
    assert "paragraphs" in is_perfect(result)


def test_a_wrapped_line_read_as_a_new_paragraph_is_split() -> None:
    half = len(CLAUSE_A) // 2
    got = with_blocks(*TRUTH.blocks[:2], Paragraph(CLAUSE_A[:half]), Paragraph(CLAUSE_A[half:]), *TRUTH.blocks[3:])
    assert score(TRUTH, got)["paragraphs"]["split"] == 1


def test_a_dropped_paragraph_is_missing() -> None:
    got = with_blocks(*TRUTH.blocks[:2], TRUTH.blocks[3], TRUTH.blocks[4])
    result = score(TRUTH, got)
    assert result["paragraphs"]["missing"] == 1
    assert "text" in is_perfect(result)


def test_a_typed_marker_keeps_the_paragraph_whole_but_is_not_real_numbering() -> None:
    got = with_blocks(*TRUTH.blocks[:2], Paragraph(f"1.1 {CLAUSE_A}"), Paragraph(f"1.2 {CLAUSE_B}"), TRUTH.blocks[4])
    result = score(TRUTH, got)
    assert result["paragraphs"]["whole"] == 2
    assert result["lists"]["own_paragraph"] == 3
    assert result["lists"]["real_numbering"] == 1  # only the heading kept its real number
    assert result["lists"]["marker_printed"] == 3


def test_a_heading_with_its_number_typed_still_counts_as_found() -> None:
    got = with_blocks(TRUTH.blocks[0], Paragraph("1. Fees and Payment", level=1), *TRUTH.blocks[2:])
    assert score(TRUTH, got)["headings"]["lost"] == 0


def test_a_heading_turned_into_body_text_is_lost() -> None:
    got = with_blocks(TRUTH.blocks[0], Paragraph("Fees and Payment"), *TRUTH.blocks[2:])
    assert score(TRUTH, got)["headings"]["lost"] == 1


def test_a_heading_that_was_not_there_is_spurious() -> None:
    got = with_blocks(*TRUTH.blocks, Paragraph("Invented Heading", level=1))
    assert score(TRUTH, got)["headings"]["spurious"] == 1


def test_a_heading_at_the_wrong_depth_is_counted() -> None:
    truth = with_blocks(Paragraph("Top", level=1), Paragraph("Sub", level=2))
    got = with_blocks(Paragraph("Top", level=1), Paragraph("Sub", level=1))
    result = score(truth, got)["headings"]
    assert (result["kept"], result["level_kept"]) == (2, 1)


def test_a_title_promoted_one_level_up_keeps_its_relative_levels() -> None:
    truth = with_blocks(Paragraph("Doc", level=0), Paragraph("Top", level=1), Paragraph("Sub", level=2))
    got = with_blocks(Paragraph("Doc", level=1), Paragraph("Top", level=2), Paragraph("Sub", level=3))
    assert score(truth, got)["headings"]["level_kept"] == 3


def test_a_grid_flattened_to_a_line_of_labels_is_a_lost_table() -> None:
    truth = with_blocks(Table(rows=(("Legal name", "", "Trading name", ""), ("Tax ID", "", "Phone", ""))))
    got = with_blocks(Paragraph("Legal name Trading name Tax ID Phone"))
    result = score(truth, got)["tables"]
    assert result["lost"] == [(2, 4)]
    assert result["found"] == 0


def test_a_table_with_the_wrong_grid_is_found_but_wrong() -> None:
    wrong = Table(rows=(("Service", "", "Fee"), ("Hosting", "", "$10"), ("Support", "", "")))
    result = score(TRUTH, with_blocks(*TRUTH.blocks[:4], wrong))["tables"]
    assert result["found"] == 1
    assert result["exact_shape"] == 0
    assert result["cells_right"] < result["cells_truth"]


def test_rows_collapsed_into_one_cell_lose_their_cells() -> None:
    wrong = Table(rows=(("Service", "Fee"), ("Hosting $10", ""), ("Support", "")))
    result = score(TRUTH, with_blocks(*TRUTH.blocks[:4], wrong))["tables"]
    assert result["exact_shape"] == 1
    assert result["cells_right"] == result["cells_truth"] - 2


def test_a_blank_table_is_found_by_its_shape() -> None:
    blank = Table(rows=(("",),))
    assert score(with_blocks(blank), with_blocks(blank))["tables"]["found"] == 1
    assert score(with_blocks(blank), with_blocks(Paragraph("Something else entirely")))["tables"]["lost"] == [(1, 1)]


def test_a_footnote_dropped_into_the_text_is_counted_as_a_leak() -> None:
    got = replace(with_blocks(*TRUTH.blocks, Paragraph("1 Interest accrues daily from the due date.")), footnotes=())
    result = score(TRUTH, got)["footnotes"]
    assert result["kept"] == 0
    assert result["leaked_into_body"] == 1


def test_a_page_footer_in_the_text_is_counted_on_every_page() -> None:
    got = replace(
        with_blocks(Paragraph("Master Agreement, page 1"), *TRUTH.blocks, Paragraph("Master Agreement, page 2")),
        footers=(),
    )
    result = score(TRUTH, got)["footers"]
    assert result["lost"] == 1
    assert result["leaked_lines_in_body"] == 2


def test_a_clause_mentioning_the_header_is_not_a_leak() -> None:
    truth = replace(TRUTH, headers=("CONFIDENTIAL",))
    got = replace(
        with_blocks(*TRUTH.blocks, Paragraph("Each party shall keep Confidential Information secret.")), headers=()
    )
    assert score(truth, got)["headers"]["leaked_lines_in_body"] == 0
    leaked = replace(with_blocks(*TRUTH.blocks, Paragraph("CONFIDENTIAL")), headers=())
    assert score(truth, leaked)["headers"]["leaked_lines_in_body"] == 1


def test_a_lost_title_does_not_shift_the_levels_after_it() -> None:
    truth = with_blocks(Paragraph("Doc", level=0), Paragraph("Top", level=1), Paragraph("Sub", level=2))
    got = with_blocks(Paragraph("Doc"), Paragraph("Top", level=1), Paragraph("Sub", level=2))
    assert score(truth, got)["headings"]["level_kept"] == 2


def test_a_lost_picture_is_counted() -> None:
    assert score(TRUTH, replace(TRUTH, pictures=0))["pictures"]["lost"] == 1


def test_page_setup_differences_are_reported() -> None:
    got = replace(TRUTH, page_width=595.0, margins=(72.0, 72.0, 90.0, 90.0), body_font="Calibri", body_size=11.0)
    page = score(TRUTH, got)["page"]
    assert page["size_matches"] is False
    assert page["margins_match"] is False
    assert page["body_font_matches"] is False
    assert page["body_size_matches"] is False


def test_words_in_text_boxes_are_reported_as_a_share() -> None:
    assert score(TRUTH, replace(TRUTH, float_words=10))["page"]["float_word_share"] > 0


def test_summarize_adds_up() -> None:
    total = summarize([score(TRUTH, TRUTH), score(TRUTH, TRUTH)])
    assert total["documents"] == 2
    assert total["paragraphs_whole"] == 2 * total["paragraphs"] / 2
    assert total["cells_right"] == total["cells"]


class TestCorpus:
    """The committed corpus."""

    def test_it_loads_and_covers_every_family(self) -> None:
        families = {case.family for case in load_corpus()}
        assert {"control", "contract", "report", "form"} <= families

    def test_there_is_a_control(self) -> None:
        assert any(case.control for case in load_corpus())

    def test_a_changed_file_is_refused(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        case = load_corpus()[0]
        for path in (case.source, case.tagged, case.untagged):
            target = tmp_path / "corpus" / case.family / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        truth = tmp_path / "truth" / case.family / case.truth_path.name
        truth.parent.mkdir(parents=True, exist_ok=True)
        truth.write_bytes(case.truth_path.read_bytes())
        real = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entry = next(item for item in real["cases"] if item["case_id"] == case.case_id)
        manifest.write_text(json.dumps({"schema_version": 1, "cases": [entry]}), encoding="utf-8")
        assert len(load_corpus(manifest)) == 1
        tampered = tmp_path / "corpus" / case.family / case.tagged.name
        tampered.write_bytes(tampered.read_bytes() + b"\n")
        with pytest.raises(CorpusError, match="digest"):
            load_corpus(manifest)

    def test_an_empty_manifest_is_refused(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"schema_version": 1, "cases": []}), encoding="utf-8")
        with pytest.raises(CorpusError, match="no cases"):
            load_corpus(manifest)

    def test_each_truth_scores_perfectly_against_itself(self) -> None:
        for case in load_corpus():
            truth = case.truth()
            assert is_perfect(score(truth, truth)) == [], case.case_id

    def test_the_truth_has_no_placeholder_left_in_it(self) -> None:
        for case in load_corpus():
            text = " ".join(p.text for p in case.truth().paragraphs)
            for placeholder in ("CHARTHERE", "CHARTEND", "TOCHERE", "PICTUREHERE", "SECTIONBREAK", "COMMENTBOX"):
                assert placeholder not in text, case.case_id


@pytest.mark.integration
@pytest.mark.docx
class TestNothingCrashes:
    """Fidelity here is a hand-run ledger, but a conversion that crashes fails every pull request."""

    @pytest.mark.parametrize("case", load_corpus(), ids=lambda case: case.case_id)
    def test_both_pdfs_convert_to_a_document_with_text(self, case, tmp_path: Path) -> None:
        pytest.importorskip("fitz")
        pytest.importorskip("docx")
        from docx import Document

        from all2md import convert

        for pdf in (case.tagged, case.untagged):
            output = tmp_path / f"{pdf.stem}.docx"
            convert(str(pdf), str(output))
            document = Document(str(output))
            assert any(paragraph.text.strip() for paragraph in document.paragraphs), pdf.name
