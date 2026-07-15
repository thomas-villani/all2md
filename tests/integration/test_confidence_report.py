#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for conversion confidence reports (D1 quality card).

Covers the parser producers (PDF, DOCX), the ``confidence_report`` API + the
``Document.metadata['confidence']`` attachment, and the ``all2md report`` CLI.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from all2md import confidence_report, to_ast
from all2md.ast.nodes import Document
from all2md.confidence import ConfidenceReport

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "documents"
BASIC_PDF = FIXTURES / "basic.pdf"
COMPLEX_PDF = FIXTURES / "complex.pdf"
BASIC_DOCX = FIXTURES / "basic.docx"
COMPLEX_DOCX = FIXTURES / "complex.docx"


@pytest.fixture
def blank_pdf(tmp_path) -> Path:
    """A single blank page — the near-empty / scanned-PDF shape (no text layer)."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.new_page()
    path = tmp_path / "blank.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.mark.integration
@pytest.mark.pdf
class TestPdfProducer:
    def test_clean_pdf_scores_high_with_signals(self):
        report = confidence_report(str(BASIC_PDF))
        assert report.producer == "pdf"
        assert report.score == 100
        assert report.band == "high"
        # The reference-free PDF signal set.
        for key in ("page_count", "meaningful_chars", "chars_per_page", "ocr_page_fraction", "tables_detected"):
            assert key in report.signals
        assert report.signals["meaningful_chars"] > 0

    def test_blank_pdf_scores_low_on_text_density(self, blank_pdf):
        report = confidence_report(str(blank_pdf))
        assert report.signals["chars_per_page"] < 200
        assert report.score < 80  # not "high" — the card flags an empty extraction

    def test_tables_detected_accounts_for_emitted_and_rejected(self):
        report = confidence_report(str(COMPLEX_PDF))
        signals = report.signals
        assert signals["tables_detected"] == signals["tables_emitted"] + signals["tables_rejected"]


@pytest.mark.integration
@pytest.mark.docx
class TestDocxProducer:
    def test_clean_docx_is_not_assessed(self):
        """Docx emits no scored signals, so a clean file is 100/not_assessed.

        The 100 means "no quality detector ran", not "verified clean" -- banding
        it ``"not_assessed"`` keeps a mangled .docx from reading as 100/HIGH.
        """
        report = confidence_report(str(BASIC_DOCX))
        assert report.producer == "docx"
        assert report.score == 100
        assert not report.degraded_events
        assert report.band == "not_assessed"

    def test_dropped_chart_is_surfaced_and_penalized(self):
        # complex.docx embeds a chart, which all2md has no Markdown form for.
        report = confidence_report(str(COMPLEX_DOCX))
        kinds = {event.kind for event in report.degraded_events}
        assert "chart_dropped" in kinds
        assert report.signals.get("chart_dropped", 0) >= 1
        assert report.score < 100


@pytest.mark.integration
class TestConfidenceApi:
    def test_to_ast_attaches_confidence_metadata(self):
        doc = to_ast(str(BASIC_PDF))
        assert "confidence" in doc.metadata
        card = doc.metadata["confidence"]
        assert set(card) >= {"score", "band", "producer", "signals", "degraded_events"}

    def test_confidence_report_reads_prebuilt_document(self):
        doc = to_ast(str(BASIC_PDF))
        report = confidence_report(doc)
        assert isinstance(report, ConfidenceReport)
        assert report.score == doc.metadata["confidence"]["score"]

    def test_confidence_metadata_survives_json_roundtrip(self):
        from all2md.ast.serialization import ast_to_json

        doc = to_ast(str(COMPLEX_DOCX))
        # The card must serialize cleanly with the rest of the AST metadata.
        payload = json.loads(ast_to_json(doc))
        assert "confidence" in payload["metadata"]

    def test_handbuilt_document_is_not_assessed(self):
        # A Document with no attached confidence metadata was never assessed;
        # the card must say so rather than implying a verified-clean 100.
        report = confidence_report(Document(children=[]))
        assert report.score == 100
        assert report.band == "not_assessed"
        assert report.degraded_events == []


def _run_report(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "all2md", "report", *args],
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
@pytest.mark.cli
class TestReportCli:
    def test_pretty_output(self):
        result = _run_report([str(BASIC_PDF)])
        assert result.returncode == 0
        assert "confidence:" in result.stdout
        assert "producer:" in result.stdout

    def test_json_output_is_parseable(self):
        result = _run_report([str(BASIC_PDF), "--json"])
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["producer"] == "pdf"
        assert payload["score"] == 100

    def test_json_array_for_multiple_inputs(self):
        result = _run_report([str(BASIC_PDF), str(BASIC_DOCX), "--json"])
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert {entry["producer"] for entry in payload} == {"pdf", "docx"}

    def test_fail_under_trips_exit_code(self):
        # complex.docx scores below 100 (dropped chart); gate at 100 must fail.
        result = _run_report([str(COMPLEX_DOCX), "--fail-under", "100"])
        assert result.returncode != 0
        assert "below --fail-under" in result.stderr

    def test_fail_under_passes_when_met(self):
        result = _run_report([str(BASIC_PDF), "--fail-under", "50"])
        assert result.returncode == 0

    def test_fail_under_rejects_out_of_range(self):
        result = _run_report([str(BASIC_PDF), "--fail-under", "150"])
        assert result.returncode != 0
        assert "between 0 and 100" in result.stderr
