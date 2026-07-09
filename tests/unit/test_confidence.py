#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for the conversion-confidence scoring model (``all2md.confidence``)."""

import pytest

from all2md.confidence import (
    BAND_HIGH_THRESHOLD,
    BAND_MEDIUM_THRESHOLD,
    DEGRADED_EVENT_PENALTY_CAP,
    OCR_RELIANCE_MAX_PENALTY,
    TEXT_DENSITY_FLOOR_CPP,
    ConfidenceReport,
    DegradedEvent,
    band_for_score,
    build_report,
    coalesce_events,
    score_conversion,
)

pytestmark = pytest.mark.unit


class TestBands:
    def test_band_thresholds(self):
        assert band_for_score(100) == "high"
        assert band_for_score(BAND_HIGH_THRESHOLD) == "high"
        assert band_for_score(BAND_HIGH_THRESHOLD - 1) == "medium"
        assert band_for_score(BAND_MEDIUM_THRESHOLD) == "medium"
        assert band_for_score(BAND_MEDIUM_THRESHOLD - 1) == "low"
        assert band_for_score(0) == "low"


class TestScoreConversion:
    def test_no_signals_no_events_is_perfect(self):
        assert score_conversion({}, []) == (100, "high")

    def test_healthy_pdf_signals_stay_perfect(self):
        signals = {"chars_per_page": 800.0, "ocr_page_fraction": 0.0, "tables_rejected": 0}
        assert score_conversion(signals, []) == (100, "high")

    def test_text_density_floor_waives_penalty(self):
        at_floor = {"chars_per_page": float(TEXT_DENSITY_FLOOR_CPP)}
        above = {"chars_per_page": float(TEXT_DENSITY_FLOOR_CPP) + 500}
        assert score_conversion(at_floor, [])[0] == 100
        assert score_conversion(above, [])[0] == 100

    def test_empty_page_image_pdf_scores_low(self):
        # Near-zero text density + fully OCR-reliant: the classic scanned PDF.
        score, band = score_conversion({"chars_per_page": 0.0, "ocr_page_fraction": 1.0}, [])
        assert score < 50
        assert band == "low"

    def test_text_density_penalty_is_monotonic(self):
        worse = score_conversion({"chars_per_page": 10.0}, [])[0]
        better = score_conversion({"chars_per_page": 150.0}, [])[0]
        assert worse < better < 100

    def test_recovering_text_raises_score(self):
        # The fitness-function property: extracting more text must improve the
        # score even though OCR reliance rose (e.g. after enabling OCR).
        before = score_conversion({"chars_per_page": 0.0, "ocr_page_fraction": 0.0}, [])[0]
        after = score_conversion({"chars_per_page": 600.0, "ocr_page_fraction": 1.0}, [])[0]
        assert after > before

    def test_ocr_reliance_penalty_scales(self):
        none = score_conversion({"ocr_page_fraction": 0.0}, [])[0]
        half = score_conversion({"ocr_page_fraction": 0.5}, [])[0]
        full = score_conversion({"ocr_page_fraction": 1.0}, [])[0]
        assert none == 100
        assert full == pytest.approx(100 - OCR_RELIANCE_MAX_PENALTY, abs=1)
        assert none > half > full

    def test_warn_events_penalize(self):
        events = [DegradedEvent("pdf", "table_rejected", severity="warn")]
        assert score_conversion({}, events)[0] == 96

    def test_error_events_penalize_more_than_warn(self):
        warn = score_conversion({}, [DegradedEvent("x", "k", severity="warn")])[0]
        error = score_conversion({}, [DegradedEvent("x", "k", severity="error")])[0]
        assert error < warn

    def test_info_events_do_not_penalize(self):
        assert score_conversion({}, [DegradedEvent("x", "k", count=9, severity="info")])[0] == 100

    def test_event_count_multiplies_penalty(self):
        one = score_conversion({}, [DegradedEvent("x", "k", count=1, severity="warn")])[0]
        three = score_conversion({}, [DegradedEvent("x", "k", count=3, severity="warn")])[0]
        assert 100 - three == 3 * (100 - one)

    def test_event_penalty_is_capped(self):
        many = [DegradedEvent("x", "k", count=1, detail=str(i), severity="error") for i in range(100)]
        score = score_conversion({}, many)[0]
        assert score == pytest.approx(100 - DEGRADED_EVENT_PENALTY_CAP, abs=1)

    def test_score_never_negative(self):
        signals = {"chars_per_page": 0.0, "ocr_page_fraction": 1.0}
        events = [DegradedEvent("x", "k", count=50, severity="error")]
        assert score_conversion(signals, events)[0] == 0


class TestCoalesceEvents:
    def test_merges_matching_events_and_sums_counts(self):
        events = [
            DegradedEvent("pdf", "table_rejected", detail="mostly_empty"),
            DegradedEvent("pdf", "table_rejected", detail="mostly_empty"),
            DegradedEvent("pdf", "table_rejected", detail="dot_leader_toc"),
        ]
        merged = coalesce_events(events)
        assert len(merged) == 2
        assert merged[0].detail == "mostly_empty"
        assert merged[0].count == 2
        assert merged[1].detail == "dot_leader_toc"
        assert merged[1].count == 1

    def test_distinct_severity_not_merged(self):
        events = [
            DegradedEvent("x", "k", severity="warn"),
            DegradedEvent("x", "k", severity="error"),
        ]
        assert len(coalesce_events(events)) == 2

    def test_preserves_first_seen_order(self):
        events = [DegradedEvent("x", "b"), DegradedEvent("x", "a"), DegradedEvent("x", "b")]
        merged = coalesce_events(events)
        assert [e.kind for e in merged] == ["b", "a"]


class TestSerialization:
    def test_degraded_event_roundtrip(self):
        event = DegradedEvent("pdf", "table_rejected", count=2, detail="mostly_empty", severity="warn")
        assert DegradedEvent.from_dict(event.to_dict()) == event

    def test_degraded_event_omits_none_detail(self):
        assert "detail" not in DegradedEvent("pdf", "k").to_dict()

    def test_report_roundtrip(self):
        report = build_report(
            "pdf",
            {"chars_per_page": 12.0, "ocr_page_fraction": 1.0},
            [DegradedEvent("pdf", "table_rejected", detail="mostly_empty")],
        )
        restored = ConfidenceReport.from_dict(report.to_dict())
        assert restored == report

    def test_report_dict_is_json_safe(self):
        import json

        report = build_report("pdf", {"chars_per_page": 12.0}, [DegradedEvent("pdf", "k")])
        # Must not raise — the card rides on JSON-serialized AST metadata.
        json.dumps(report.to_dict())


class TestBuildReport:
    def test_coalesces_before_scoring(self):
        events = [DegradedEvent("pdf", "table_rejected", detail="x") for _ in range(3)]
        report = build_report("pdf", {}, events)
        assert len(report.degraded_events) == 1
        assert report.degraded_events[0].count == 3
        assert report.score == 100 - 3 * 4  # three warn events at 4 pts each

    def test_producer_recorded(self):
        assert build_report("docx", {}, []).producer == "docx"
