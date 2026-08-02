"""Behavioral tests for the direct OmniDocBench AST benchmark."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from all2md.ast.nodes import Document, Paragraph, Text
from benchmarks.omnidocbench import benchmark
from benchmarks.omnidocbench.corpus import CorpusPage, CorpusSnapshot
from benchmarks.omnidocbench.oracles import GroundTruthPage, PageProjection

pytestmark = pytest.mark.unit


def _page(tmp_path: Path, page_id: str) -> CorpusPage:
    return CorpusPage(
        page_id=page_id,
        image_path=f"images/{page_id}.jpg",
        pdf_path=tmp_path / f"{page_id}.pdf",
        sha256="a" * 64,
        size_bytes=100,
    )


def _snapshot(tmp_path: Path, page_ids: tuple[str, ...] = ("page-a", "page-b")) -> CorpusSnapshot:
    return CorpusSnapshot(
        revision="dataset-revision",
        annotation_path=tmp_path / "OmniDocBench.json",
        pages=tuple(_page(tmp_path, page_id) for page_id in page_ids),
        expected_pages=len(page_ids),
        complete=True,
    )


def _annotation(page_id: str, text: str = "Body") -> dict[str, object]:
    return {
        "page_info": {"image_path": f"images/{page_id}.jpg"},
        "layout_dets": [
            {
                "category_type": "text_block",
                "order": 1,
                "text": text,
                "ignore": False,
            }
        ],
    }


def _truth(page_id: str) -> GroundTruthPage:
    return GroundTruthPage(
        page_id=page_id,
        projection=PageProjection(("Body",), ("text_block",), (), ()),
        unscored_categories={"figure": 1},
        explicitly_ignored=1,
    )


def test_ground_truth_loader_selects_exact_pdf_page_ids(tmp_path: Path) -> None:
    """A limited run must load its exact annotation rows without scoring absent pages."""
    snapshot = _snapshot(tmp_path, ("page-b",))
    snapshot.annotation_path.write_text(
        json.dumps([_annotation("page-a", "A"), _annotation("page-b", "B")]),
        encoding="utf-8",
    )

    truth = benchmark.load_ground_truth(snapshot)

    assert list(truth) == ["page-b"]
    assert truth["page-b"].projection.text_blocks == ("B",)


def test_ground_truth_loader_rejects_missing_selected_page(tmp_path: Path) -> None:
    """A PDF without external truth must fail instead of shrinking the denominator."""
    snapshot = _snapshot(tmp_path, ("page-b",))
    snapshot.annotation_path.write_text(json.dumps([_annotation("page-a")]), encoding="utf-8")

    with pytest.raises(ValueError, match=r"selected PDFs have no annotations: \['page-b'\]"):
        benchmark.load_ground_truth(snapshot)


def test_evaluation_calls_to_ast_once_and_scores_the_returned_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One page must have exactly one parser observation and no renderer or reparsing step."""
    snapshot = _snapshot(tmp_path, ("page-a",))
    calls: list[tuple[Path, str, object]] = []

    def fake_to_ast(source: Path, *, source_format: str, parser_options: object):
        calls.append((source, source_format, parser_options))
        return Document(children=[Paragraph(content=[Text(content="Body")])])

    monkeypatch.setattr("all2md.to_ast", fake_to_ast)
    results = benchmark.evaluate_corpus(
        snapshot,
        {"page-a": _truth("page-a")},
        ocr_languages="eng",
    )

    assert len(calls) == 1
    assert calls[0][0] == snapshot.pages[0].pdf_path
    assert calls[0][1] == "pdf"
    assert calls[0][2].ocr.languages == "eng"
    assert results == [
        benchmark.PageEvaluation(
            page_id="page-a",
            scores={
                "text_content_similarity": 1.0,
                "reading_order_similarity": 1.0,
                "block_structure_similarity": 1.0,
            },
            predicted_tables=0,
            predicted_formulas=0,
            duration_seconds=results[0].duration_seconds,
        )
    ]


def test_evaluation_serializes_multiple_pymupdf_pages_on_the_caller_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PyMuPDF pages must never be parsed concurrently because its API is not thread-safe."""
    snapshot = _snapshot(tmp_path, ("page-a", "page-b"))
    caller_thread = threading.get_ident()
    calls: list[tuple[Path, int]] = []

    def fake_to_ast(source: Path, **_kwargs):
        calls.append((source, threading.get_ident()))
        return Document(children=[Paragraph(content=[Text(content="Body")])])

    monkeypatch.setattr("all2md.to_ast", fake_to_ast)
    results = benchmark.evaluate_corpus(
        snapshot,
        {"page-a": _truth("page-a"), "page-b": _truth("page-b")},
    )

    assert [result.page_id for result in results] == ["page-a", "page-b"]
    assert calls == [
        (snapshot.pages[0].pdf_path, caller_thread),
        (snapshot.pages[1].pdf_path, caller_thread),
    ]


def test_failed_ast_conversion_contributes_zero_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A parser exception must remain visible and must not earn absence-match credit."""
    snapshot = _snapshot(tmp_path, ("page-a",))

    def fail_to_ast(*_args, **_kwargs):
        raise RuntimeError("broken PDF")

    monkeypatch.setattr("all2md.to_ast", fail_to_ast)
    result = benchmark.evaluate_corpus(
        snapshot,
        {"page-a": _truth("page-a")},
    )[0]

    assert result.scores == {
        "text_content_similarity": 0.0,
        "reading_order_similarity": 0.0,
        "block_structure_similarity": 0.0,
    }
    assert result.error_type == "RuntimeError"
    assert result.error == "broken PDF"


def test_degraded_pdf_fallback_contributes_zero_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An OCR fallback must become ratcheted failure evidence, not a silent success."""
    snapshot = _snapshot(tmp_path, ("page-a",))

    def degraded_to_ast(*_args, **_kwargs):
        return Document(
            children=[Paragraph(content=[Text(content="Body")])],
            metadata={"confidence": {"degraded_events": [{"kind": "ocr_fallback"}]}},
        )

    monkeypatch.setattr("all2md.to_ast", degraded_to_ast)
    result = benchmark.evaluate_corpus(
        snapshot,
        {"page-a": _truth("page-a")},
    )[0]

    assert result.scores == {
        "text_content_similarity": 0.0,
        "reading_order_similarity": 0.0,
        "block_structure_similarity": 0.0,
    }
    assert result.error_type == "DegradedConversionError"
    assert result.error == '[{"kind": "ocr_fallback"}]'


def test_a_deliberate_table_rejection_is_scored_not_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Correctly refusing a non-tabular grid must not zero every dimension on the page.

    ``table_rejected`` is the only degraded event the PDF parser records, and it fires on
    deliberate decisions (dot-leader TOC, degenerate grid, layout region not tabular). Treating
    it as a conversion failure made a byte-perfect page score 0.0 in every dimension while its
    own confidence card read high, and the table and reading-order metrics already score that
    outcome. Any other degradation still fails the page.
    """
    snapshot = _snapshot(tmp_path, ("page-a",))

    def rejected_table_to_ast(*_args, **_kwargs):
        return Document(
            children=[Paragraph(content=[Text(content="Body")])],
            metadata={"confidence": {"degraded_events": [{"kind": "table_rejected", "detail": "dot_leader_toc"}]}},
        )

    monkeypatch.setattr("all2md.to_ast", rejected_table_to_ast)
    result = benchmark.evaluate_corpus(snapshot, {"page-a": _truth("page-a")})[0]

    assert result.error_type is None
    assert result.scores["text_content_similarity"] > 0.0


def test_normalization_records_variance_failures_and_unsupported_dimensions(tmp_path: Path) -> None:
    """The ratchet input must expose exact samples and capabilities, not only averages."""
    snapshot = _snapshot(tmp_path)
    truth = {"page-a": _truth("page-a"), "page-b": _truth("page-b")}
    evaluations = [
        benchmark.PageEvaluation(
            page_id="page-a",
            scores={
                "text_content_similarity": 0.2,
                "reading_order_similarity": 0.5,
                "formula_presence_accuracy": 1.0,
                "table_structure_similarity": 0.3,
                "table_content_similarity": 0.4,
            },
            predicted_tables=1,
            predicted_formulas=0,
            duration_seconds=0.5,
        ),
        benchmark.PageEvaluation(
            page_id="page-b",
            scores={
                "text_content_similarity": 0.6,
                "reading_order_similarity": 0.5,
                "formula_presence_accuracy": 0.0,
                "table_structure_similarity": 0.7,
                "table_content_similarity": 0.8,
                "formula_content_similarity": 0.0,
            },
            predicted_tables=0,
            predicted_formulas=0,
            duration_seconds=0.6,
            error_type="RuntimeError",
            error="broken PDF",
        ),
    ]

    payload = benchmark.normalize_results(
        snapshot=snapshot,
        ground_truth=truth,
        evaluations=evaluations,
        all2md_commit="all2md-commit",
        parser_runtime={"pymupdf": "1.28.0", "tesseract": "tesseract 5.3.0"},
    )

    assert payload["schema_version"] == 2
    assert payload["pages"] == {
        "expected": 2,
        "annotations": 2,
        "pdfs": 2,
        "converted": 1,
        "scored": 2,
        "unique_ids": 2,
    }
    assert payload["dimensions"]["text_content_similarity"] == {
        "value": pytest.approx(0.4),
        "direction": "higher",
        "eligible_items": 2,
        "variance": pytest.approx(0.04),
        "sample_scores": {"page-a": 0.2, "page-b": 0.6},
    }
    assert payload["dimensions"]["table_structure_similarity"]["value"] == pytest.approx(0.5)
    assert "formula_content_similarity" not in payload["dimensions"]
    assert payload["unsupported_dimensions"] == {
        "formula_fidelity": (
            "all2md emitted no MathBlock or MathInline nodes on 1 converted page(s); "
            "0 pages have formula ground truth"
        )
    }
    assert payload["conversion_failures"] == {"page-b": "RuntimeError: broken PDF"}
    assert payload["unscored_annotation_categories"] == {"figure": 2}
    assert payload["explicitly_ignored_annotations"] == 2
    assert payload["provenance"]["oracle_schema_version"] == 5
    assert payload["provenance"]["parser_config"]["layout_analysis_mode"] == "enabled"
    assert payload["provenance"]["parser_runtime"] == {
        "pymupdf": "1.28.0",
        "tesseract": "tesseract 5.3.0",
    }
    assert payload["provenance"]["parser_config"]["ocr"]["languages"] == "eng+chi_sim"


def test_strict_result_json_rejects_non_finite_scores(tmp_path: Path) -> None:
    """NaN cannot enter a baseline because JSON readers disagree on its meaning."""
    with pytest.raises(ValueError, match="Out of range float values"):
        benchmark.write_result({"score": float("nan")}, tmp_path / "result.json")


def _write_vector_pdf(path: Path) -> None:
    """A born-digital page: real text and a ruled box."""
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 100), "Quarterly results", fontsize=12)
    page.draw_rect(fitz.Rect(72, 120, 300, 200))
    document.save(path)
    document.close()


def _write_scanned_pdf(path: Path, tmp_path: Path) -> None:
    """A scanned page: one full-page raster, no text layer, no vector drawings."""
    fitz = pytest.importorskip("fitz")
    source = tmp_path / "_source.pdf"
    _write_vector_pdf(source)
    with fitz.open(source) as origin:
        pixmap = origin[0].get_pixmap(dpi=72)
        rect = origin[0].rect
    document = fitz.open()
    page = document.new_page(width=rect.width, height=rect.height)
    page.insert_image(page.rect, pixmap=pixmap)
    document.save(path)
    document.close()


def test_input_traits_tell_a_born_digital_page_from_a_scan(tmp_path: Path) -> None:
    """The lane must record what its corpus contains, not assume PDFs carry text.

    This is the check whose absence let an all-raster corpus be scored, gated and
    baselined as though it exercised the PDF text and table paths.
    """
    vector = tmp_path / "vector.pdf"
    scanned = tmp_path / "scanned.pdf"
    _write_vector_pdf(vector)
    _write_scanned_pdf(scanned, tmp_path)

    assert benchmark._input_traits(vector) == frozenset({"text_layer", "vector_drawings"})
    assert benchmark._input_traits(scanned) == frozenset({"one_full_page_image"})


def test_an_unreadable_pdf_is_uncharacterized_rather_than_trait_free(tmp_path: Path) -> None:
    """``None`` and "no traits" must stay distinct, or unreadable files read as scans."""
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf at all")

    assert benchmark._input_traits(broken) is None
    assert benchmark._input_traits(tmp_path / "absent.pdf") is None


def test_characterization_counts_only_pages_it_could_measure(tmp_path: Path) -> None:
    """An uncharacterized page must not be counted as lacking every trait."""
    snapshot = _snapshot(tmp_path)
    truth = {"page-a": _truth("page-a"), "page-b": _truth("page-b")}
    evaluations = [
        benchmark.PageEvaluation(
            page_id="page-a",
            scores={"text_content_similarity": 0.5},
            predicted_tables=0,
            predicted_formulas=0,
            duration_seconds=0.1,
            traits=frozenset({"one_full_page_image", "ocr_applied"}),
        ),
        benchmark.PageEvaluation(
            page_id="page-b",
            scores={"text_content_similarity": 0.5},
            predicted_tables=0,
            predicted_formulas=0,
            duration_seconds=0.1,
            traits=None,
        ),
    ]

    payload = benchmark.normalize_results(
        snapshot=snapshot,
        ground_truth=truth,
        evaluations=evaluations,
        all2md_commit="all2md-commit",
        parser_runtime={"pymupdf": "1.28.0"},
    )

    assert payload["provenance"]["corpus_characterization"] == {
        "pages_characterized": 1,
        "pages_with_text_layer": 0,
        "pages_with_vector_drawings": 0,
        "pages_with_one_full_page_image": 1,
        "pages_ocr_applied": 1,
    }
