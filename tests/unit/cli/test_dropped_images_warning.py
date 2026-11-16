"""The CLI says how many images the default attachment mode left out."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from all2md.cli import main
from all2md.cli.processors import warn_if_images_dropped
from all2md.utils.attachments import dropped_image_count, process_attachment, reset_dropped_image_count

pytestmark = pytest.mark.unit


def _pdf_with_images(path: Path, count: int) -> Path:
    import pymupdf

    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 60), False)
    pixmap.clear_with(128)
    png = pixmap.tobytes("png")
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "A page with pictures on it.")
    for index in range(count):
        top = 100 + index * 150
        page.insert_image(pymupdf.Rect(72, top, 192, top + 120), stream=png)
    document.save(path)
    return path


def test_alt_text_mode_counts_images_but_not_files() -> None:
    reset_dropped_image_count()
    process_attachment(None, "a.png", attachment_mode="alt_text", is_image=True)
    process_attachment(None, "b.zip", attachment_mode="alt_text", is_image=False)
    process_attachment(b"\x89PNG", "c.png", attachment_mode="base64", is_image=True)
    process_attachment(None, "d.png", attachment_mode="skip", is_image=True)
    assert dropped_image_count() == 1


@pytest.mark.parametrize(
    ("count", "provided", "expected"),
    [
        (0, set(), None),
        (1, set(), "Warning: 1 image was dropped, use `--attachment-mode base64` to include."),
        (3, set(), "Warning: 3 images were dropped, use `--attachment-mode base64` to include."),
        (3, {"attachment_mode"}, None),
        (3, {"pdf.attachment_mode"}, None),
    ],
)
def test_warning_text(capsys: pytest.CaptureFixture[str], count: int, provided: set[str], expected: str | None) -> None:
    warn_if_images_dropped(argparse.Namespace(_provided_args=provided), count)
    err = capsys.readouterr().err.strip()
    assert err == (expected or "")


@pytest.mark.pdf
def test_pdf_to_docx_by_default_warns(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _pdf_with_images(tmp_path / "pictures.pdf", 2)
    assert main([str(source), "--out", str(tmp_path / "out.docx"), "--no-config"]) == 0
    assert "2 images were dropped, use `--attachment-mode base64` to include." in capsys.readouterr().err


@pytest.mark.pdf
@pytest.mark.parametrize("mode", ["base64", "alt_text"])
def test_a_typed_mode_does_not_warn(tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str) -> None:
    source = _pdf_with_images(tmp_path / "pictures.pdf", 2)
    output = tmp_path / "out.docx"
    assert main([str(source), "--out", str(output), "--no-config", "--attachment-mode", mode]) == 0
    assert "dropped" not in capsys.readouterr().err
