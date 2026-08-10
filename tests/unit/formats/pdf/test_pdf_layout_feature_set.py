#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_layout_feature_set.py
"""Choosing which layout classifier reads the page, and caching one model per choice.

`pymupdf-layout` ships three bundled classifiers. `imf+rf` (the default) and `imf` read a
raster of the page; `rf` reads text geometry alone. Which is better depends on the document,
so the choice is exposed as a searchable option rather than decided globally: on born-digital
journal articles the image-feature models read a dense two-column reference list as a table
and delete it, while `rf` labels all 41 entries correctly -- and the opposite is expected on
scanned pages, where there is no text geometry to read.

The cache is what these tests mostly guard. Models were previously held in a single module
global with no key, which is correct for one fixed choice and silently wrong the moment a
caller switches: every arm of a search over this knob would get whichever model loaded first
and the arms would tie, looking like "the setting does nothing".

The real models are never loaded here. They are several MB of ONNX weights and the extra is
absent from the unit lane's install, so `pymupdf.layout` is stubbed.
"""

from __future__ import annotations

import sys

import pytest

from all2md.constants import DEFAULT_LAYOUT_FEATURE_SET
from all2md.options.pdf import PdfOptions
from all2md.parsers import _pdf_layout

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


class _FakeAnalyzer:
    """Stands in for `pymupdf.layout.DocumentLayoutAnalyzer`, recording what it was asked for."""

    calls: list[str] = []

    @staticmethod
    def get_model(feature_set_name: str = "imf+rf", **kwargs):
        _FakeAnalyzer.calls.append(feature_set_name)
        return f"model:{feature_set_name}"


@pytest.fixture
def stub_layout(monkeypatch):
    import types

    module = types.ModuleType("pymupdf.layout")
    module.DocumentLayoutAnalyzer = _FakeAnalyzer
    monkeypatch.setitem(sys.modules, "pymupdf.layout", module)
    monkeypatch.setattr(_pdf_layout, "_layout_models", {})
    _FakeAnalyzer.calls = []
    return _FakeAnalyzer


class TestModelCacheIsKeyedByFeatureSet:
    def test_different_feature_sets_load_different_models(self, stub_layout):
        first = _pdf_layout.get_layout_model("imf+rf")
        second = _pdf_layout.get_layout_model("rf")

        assert first == "model:imf+rf"
        assert second == "model:rf"
        assert stub_layout.calls == ["imf+rf", "rf"]

    def test_repeating_a_feature_set_reuses_its_model(self, stub_layout):
        _pdf_layout.get_layout_model("rf")
        _pdf_layout.get_layout_model("imf")
        _pdf_layout.get_layout_model("rf")

        # Three requests, two loads: the second 'rf' must come from the cache, or a search
        # revisiting values pays several MB of ONNX load each time it changes its mind.
        assert stub_layout.calls == ["rf", "imf"]

    def test_switching_back_does_not_return_the_other_model(self, stub_layout):
        first = _pdf_layout.get_layout_model("imf+rf")
        _pdf_layout.get_layout_model("rf")
        again = _pdf_layout.get_layout_model("imf+rf")

        # The defect a single unkeyed global would produce: every arm silently identical.
        assert again == first == "model:imf+rf"

    def test_defaults_to_the_documented_feature_set(self, stub_layout):
        _pdf_layout.get_layout_model()

        assert stub_layout.calls == [DEFAULT_LAYOUT_FEATURE_SET]


class TestPredictPassesTheFeatureSetThrough:
    def test_prediction_uses_the_requested_classifier(self, monkeypatch, stub_layout):
        requested: list[str] = []

        class _Model:
            def predict(self, page):
                return []

        def _fake_get_model(feature_set=DEFAULT_LAYOUT_FEATURE_SET):
            requested.append(feature_set)
            return _Model()

        monkeypatch.setattr(_pdf_layout, "get_layout_model", _fake_get_model)
        _pdf_layout.predict_page_layout(object(), "rf")

        assert requested == ["rf"]


class TestOptionAndKnob:
    def test_option_default_matches_upstream(self):
        # Deliberately upstream's default: 'rf' won on one born-digital corpus, which is not
        # grounds for changing what every document gets.
        assert PdfOptions().layout_feature_set == "imf+rf"

    def test_option_is_settable(self):
        assert PdfOptions(layout_feature_set="rf").layout_feature_set == "rf"

    def test_registered_as_a_searchable_knob(self):
        from all2md.optimize import FORBIDDEN_KNOBS, tunable_knobs

        knobs = tunable_knobs("pdf")
        assert knobs["layout_feature_set"] == ["imf+rf", "rf", "imf"]
        assert "layout_feature_set" not in FORBIDDEN_KNOBS

    def test_every_searched_value_is_accepted_by_the_options(self):
        from all2md.optimize import tunable_knobs

        # A knob whose values the options reject would fail only at search time, on a user's
        # document, after the expensive part of the run.
        for value in tunable_knobs("pdf")["layout_feature_set"]:
            assert PdfOptions(layout_feature_set=value).layout_feature_set == value
