#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for the ``llm-minify`` CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.cli.commands.llm_minify import _squeeze_whitespace, handle_llm_minify_command

pytestmark = pytest.mark.unit


SAMPLE = (
    "# Title\n\n\n\n"
    "Some **bold** and *italic* text with a [link](https://example.com) "
    "and ![img](data:image/png;base64,AAAA).\n\n\n"
    "<!-- a comment -->\n\n<div>raw html</div>\n\n\nDone.\n"
)


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    path = tmp_path / "sample.md"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_squeeze_whitespace_collapses_blank_lines() -> None:
    out = _squeeze_whitespace("a\n\n\n\nb\n   \nc   \n\n\n")
    assert out == "a\n\nb\n\nc\n"


def test_squeeze_whitespace_collapses_interior_spaces_outside_code() -> None:
    text = "Some  text   with    gaps.\n\n```py\nx  =  1   #  keep\n```\n"
    out = _squeeze_whitespace(text)
    assert "Some text with gaps." in out
    # Code fence contents are preserved verbatim.
    assert "x  =  1   #  keep" in out


def test_squeeze_whitespace_preserves_leading_indentation() -> None:
    out = _squeeze_whitespace("- item\n    nested  continuation\n")
    # Leading indentation kept; interior double space collapsed.
    assert "    nested continuation" in out


def test_default_preset_keeps_markdown_drops_filler(sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = handle_llm_minify_command([str(sample_md), "--no-config"])
    assert rc == 0
    out = capsys.readouterr().out
    # Structure kept.
    assert "# Title" in out
    assert "**bold**" in out
    # Filler dropped: comment, raw HTML, and excess blank lines.
    assert "a comment" not in out
    assert "<div>" not in out
    assert "\n\n\n" not in out


def test_default_preset_placeholders_data_uri_images(sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = handle_llm_minify_command([str(sample_md), "--no-config"])
    assert rc == 0
    out = capsys.readouterr().out
    # Base64 blob dropped, but the image reference and alt text survive.
    assert "data:image" not in out
    assert "AAAA" not in out
    assert "![img]" in out


def test_aggressive_preset_strips_formatting(sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = handle_llm_minify_command([str(sample_md), "--aggressive", "--no-config"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Title" not in out
    assert "Title" in out
    assert "**" not in out
    assert "bold" in out


def test_strip_flags(sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = handle_llm_minify_command(
        [str(sample_md), "--strip-links", "--strip-images", "--strip-formatting", "--no-config"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "**" not in out  # formatting stripped
    assert "https://example.com" not in out  # link url dropped
    assert "link" in out  # link text kept
    assert "data:image" not in out  # image dropped


def test_out_file(sample_md: Path, tmp_path: Path) -> None:
    dest = tmp_path / "out.md"
    rc = handle_llm_minify_command([str(sample_md), "--out", str(dest), "--no-config"])
    assert rc == 0
    assert dest.exists()
    assert "# Title" in dest.read_text(encoding="utf-8")


def test_missing_input_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = handle_llm_minify_command([str(tmp_path / "nope.md"), "--no-config"])
    assert rc != 0
    assert "not found" in capsys.readouterr().err.lower()
