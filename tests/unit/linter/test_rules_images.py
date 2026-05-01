"""Coverage for IMG001-IMG005."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from all2md.ast import Document, Image, Paragraph
from all2md.linter.rule import LintContext
from all2md.linter.rules.images import (
    DecorativeImageAltRule,
    DuplicateImagesRule,
    ImageNotFoundRule,
    ImageSizeExcessiveRule,
    MissingAltTextRule,
)

pytestmark = pytest.mark.unit


def _ctx(doc: Document, options=None, file_path: str | None = None) -> LintContext:
    return LintContext(document=doc, file_path=file_path, config=options or {})


def _doc_with(*images: Image) -> Document:
    return Document(children=[Paragraph(content=list(images))])


class TestMissingAltText:
    def test_flags_empty_alt(self):
        doc = _doc_with(Image(url="x.png", alt_text=""))
        result = MissingAltTextRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "IMG001"

    def test_silent_with_alt(self):
        doc = _doc_with(Image(url="x.png", alt_text="A diagram of the auth flow"))
        assert MissingAltTextRule().check(_ctx(doc)) == []


class TestImageNotFound:
    def test_silent_without_file_path(self):
        doc = _doc_with(Image(url="missing.png", alt_text="x"))
        assert ImageNotFoundRule().check(_ctx(doc)) == []

    def test_silent_for_remote_urls(self, tmp_path: Path):
        host = tmp_path / "host.md"
        host.write_text("placeholder", encoding="utf-8")
        doc = _doc_with(Image(url="https://example.com/x.png", alt_text="x"))
        assert ImageNotFoundRule().check(_ctx(doc, file_path=str(host))) == []

    def test_flags_missing_local_file(self, tmp_path: Path):
        host = tmp_path / "host.md"
        host.write_text("placeholder", encoding="utf-8")
        doc = _doc_with(Image(url="missing.png", alt_text="x"))
        result = ImageNotFoundRule().check(_ctx(doc, file_path=str(host)))
        assert len(result) == 1
        assert result[0].rule_code == "IMG002"

    def test_silent_when_file_exists(self, tmp_path: Path):
        host = tmp_path / "host.md"
        host.write_text("placeholder", encoding="utf-8")
        target = tmp_path / "exists.png"
        target.write_bytes(b"fake")
        doc = _doc_with(Image(url="exists.png", alt_text="x"))
        assert ImageNotFoundRule().check(_ctx(doc, file_path=str(host))) == []


class TestDuplicateImages:
    def test_flags_repeats(self):
        doc = _doc_with(
            Image(url="same.png", alt_text="a"),
            Image(url="same.png", alt_text="b"),
            Image(url="same.png", alt_text="c"),
        )
        result = DuplicateImagesRule().check(_ctx(doc))
        # Two duplicates (after the first occurrence) should be flagged.
        assert len(result) == 2
        assert all(v.rule_code == "IMG003" for v in result)


class TestImageSizeExcessive:
    def test_flags_large_base64(self):
        # ~2 KiB of zeros, base64-encoded
        big_payload = base64.b64encode(b"\x00" * 2048).decode("ascii")
        doc = _doc_with(Image(url=f"data:image/png;base64,{big_payload}", alt_text="x"))
        result = ImageSizeExcessiveRule().check(_ctx(doc, {"max_bytes": 1024}))
        assert len(result) == 1
        assert result[0].rule_code == "IMG004"

    def test_silent_for_remote_urls(self):
        doc = _doc_with(Image(url="https://example.com/big.png", alt_text="x"))
        assert ImageSizeExcessiveRule().check(_ctx(doc, {"max_bytes": 1})) == []


class TestDecorativeImageAlt:
    def test_flags_generic_alt(self):
        doc = _doc_with(Image(url="x.png", alt_text="image"))
        result = DecorativeImageAltRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "IMG005"

    def test_silent_for_descriptive_alt(self):
        doc = _doc_with(Image(url="x.png", alt_text="A diagram of the OAuth handshake"))
        assert DecorativeImageAltRule().check(_ctx(doc)) == []
