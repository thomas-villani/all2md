#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for the pluggable OCR engine strategy (tesseract / easyocr).

The ``easyocr`` package is not a test dependency, so these tests inject a fake
``easyocr`` module and patch the dependency version check. numpy and Pillow are
real, so the per-box -> reading-order reconstruction runs against real arrays.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import Mock

import pytest

from all2md.options.common import OCROptions
from all2md.options.pdf import PdfOptions
from all2md.parsers._ocr import easyocr as easyocr_engine
from all2md.parsers._ocr import ocr_pixmap

pytestmark = pytest.mark.unit


def _box(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    """Build an EasyOCR-style 4-point bounding box."""
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class TestOCREngineOption:
    """The engine/gpu fields and their defaults."""

    def test_defaults(self) -> None:
        opts = OCROptions()
        assert opts.engine == "tesseract"
        assert opts.gpu is False

    def test_engine_selectable(self) -> None:
        opts = OCROptions(engine="easyocr", gpu=True)
        assert opts.engine == "easyocr"
        assert opts.gpu is True


class TestDispatch:
    """``ocr_pixmap`` routes to the adapter named by ``options.ocr.engine``."""

    def test_default_routes_to_tesseract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sentinel = Mock(return_value="tess-out")
        monkeypatch.setattr("all2md.parsers._ocr.tesseract.ocr_pixmap", sentinel)
        options = PdfOptions(ocr=OCROptions(engine="tesseract"))

        result = ocr_pixmap(Mock(), Mock(), options)

        assert result == "tess-out"
        sentinel.assert_called_once()

    def test_easyocr_routes_to_easyocr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sentinel = Mock(return_value="easy-out")
        monkeypatch.setattr("all2md.parsers._ocr.easyocr.ocr_pixmap", sentinel)
        options = PdfOptions(ocr=OCROptions(engine="easyocr"))

        result = ocr_pixmap(Mock(), Mock(), options)

        assert result == "easy-out"
        sentinel.assert_called_once()


class TestResolveLanguages:
    """Mapping configured languages to EasyOCR codes."""

    def test_plus_joined_tesseract_codes(self) -> None:
        options = PdfOptions(ocr=OCROptions(engine="easyocr", languages="eng+fra"))
        assert easyocr_engine._resolve_languages(Mock(), options) == ["en", "fr"]

    def test_list_of_codes(self) -> None:
        options = PdfOptions(ocr=OCROptions(engine="easyocr", languages=["chi_sim", "eng"]))
        assert easyocr_engine._resolve_languages(Mock(), options) == ["ch_sim", "en"]

    def test_duplicates_collapsed(self) -> None:
        # "eng" and "en" both map to "en" -> a single entry.
        options = PdfOptions(ocr=OCROptions(engine="easyocr", languages=["eng", "en"]))
        assert easyocr_engine._resolve_languages(Mock(), options) == ["en"]

    def test_unknown_falls_back_to_english(self) -> None:
        options = PdfOptions(ocr=OCROptions(engine="easyocr", languages="xx"))
        assert easyocr_engine._resolve_languages(Mock(), options) == ["en"]

    def test_auto_detect_uses_detected_language(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("all2md.parsers._ocr.easyocr.detect_page_language", lambda page, opts: "deu")
        options = PdfOptions(ocr=OCROptions(engine="easyocr", auto_detect_language=True))
        assert easyocr_engine._resolve_languages(Mock(), options) == ["de"]


class TestResultsToText:
    """Reconstructing reading-order text from EasyOCR's per-box output."""

    def test_orders_boxes_into_lines(self) -> None:
        # Boxes supplied out of reading order; two visual lines ~70px apart.
        results = [
            (_box(200, 10, 300, 40), "world", 0.9),
            (_box(10, 10, 100, 40), "hello", 0.9),
            (_box(140, 80, 200, 110), "line", 0.9),
            (_box(10, 80, 120, 110), "second", 0.9),
        ]
        assert easyocr_engine._results_to_text(results) == "hello world\nsecond line"

    def test_empty_results(self) -> None:
        assert easyocr_engine._results_to_text([]) == ""

    def test_skips_empty_text(self) -> None:
        results = [
            (_box(10, 10, 100, 40), "kept", 0.9),
            (_box(120, 10, 200, 40), "", 0.1),
        ]
        assert easyocr_engine._results_to_text(results) == "kept"

    def test_tolerates_malformed_bbox(self) -> None:
        # A bad bbox should not crash; the text is still emitted.
        results = [(None, "text", 0.9)]
        assert easyocr_engine._results_to_text(results) == "text"


class TestReaderCache:
    """EasyOCR Reader instances are reused per (languages, gpu) key."""

    def test_reader_cached_per_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        constructed: list[tuple[Any, bool]] = []

        class FakeReader:
            def __init__(self, langs: list[str], gpu: bool = False) -> None:
                constructed.append((tuple(langs), gpu))

        fake = types.ModuleType("easyocr")
        fake.Reader = FakeReader  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "easyocr", fake)
        monkeypatch.setattr(easyocr_engine, "_READER_CACHE", {})

        easyocr_engine._get_reader(["en"], False)
        easyocr_engine._get_reader(["en"], False)  # cache hit
        easyocr_engine._get_reader(["en"], True)  # different device -> new
        easyocr_engine._get_reader(["fr"], False)  # different langs -> new

        assert constructed == [(("en",), False), (("en",), True), (("fr",), False)]


class TestEasyOcrPixmapEndToEnd:
    """Full adapter path with a fake easyocr module; numpy/Pillow are real."""

    def test_ocr_pixmap_reconstructs_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        canned = [
            (_box(10, 10, 100, 40), "hello", 0.9),
            (_box(120, 10, 220, 40), "world", 0.9),
        ]

        class FakeReader:
            def __init__(self, langs: list[str], gpu: bool = False) -> None:
                pass

            def readtext(self, array: Any, detail: int = 1, paragraph: bool = False) -> list[Any]:
                return canned

        fake = types.ModuleType("easyocr")
        fake.Reader = FakeReader  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "easyocr", fake)
        monkeypatch.setattr(easyocr_engine, "_READER_CACHE", {})
        # Bypass the optional-dependency version gate (no real easyocr installed).
        monkeypatch.setattr("all2md.utils.decorators.check_version_requirement", lambda name, spec: (True, "1.7.0"))

        # A real 2x3 RGB pixmap stand-in (Pillow reads .samples via frombytes).
        pix = Mock()
        pix.width, pix.height = 3, 2
        pix.samples = bytes([255]) * (3 * 2 * 3)

        options = PdfOptions(ocr=OCROptions(engine="easyocr", languages="eng"))
        result = easyocr_engine.ocr_pixmap(pix, Mock(), options)

        assert result == "hello world"
