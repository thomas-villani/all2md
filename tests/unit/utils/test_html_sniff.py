#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Nameless content: HTML fragments are HTML, and comments alone are not TOML.

``echo "<p>V1</p>" | all2md -`` used to print ``<p>V1</p>`` as plain text, since
only a whole page (``<!DOCTYPE html>``, ``<html>``) was recognized. And
``echo "# Test" | all2md -`` came back in a TOML code block: a comment is a
valid, empty TOML document.
"""

from __future__ import annotations

import io

import pytest

from all2md import to_markdown
from all2md.converter_registry import registry
from all2md.parsers.toml import _detect_toml_content
from all2md.utils.html_sniff import looks_like_html_fragment

FRAGMENTS = {
    "paragraph": b"<p>V1</p>\n",
    "nested": b"<div class='x'><span>a</span> <em>b</em></div>",
    "upper-case": b"<P>Shouting</P>",
    "comment-first": b"<!-- generated -->\n<ul><li>one</li></ul>",
    "bom-and-space": b"\xef\xbb\xbf  \n<h2>Title</h2>",
    "void": b"<br>line",
    "table": b"<table><tr><td>1</td></tr></table>",
}

NOT_FRAGMENTS = {
    "prose": b"Dear team, see <p> below.",
    "unclosed": b"<p>never closed",
    "not-an-element": b"<pre-release notes> are here",
    "xml": b'<book xmlns="http://docbook.org/ns/docbook"><title>T</title></book>',
    "svg": b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
    "binary": b"<p>\x00</p>",
    "empty": b"",
}


def detect(data: bytes) -> str:
    return registry.detect_format(io.BytesIO(data))


@pytest.mark.unit
class TestLooksLikeHtmlFragment:
    @pytest.mark.parametrize("name", sorted(FRAGMENTS))
    def test_fragment(self, name):
        assert looks_like_html_fragment(FRAGMENTS[name])

    @pytest.mark.parametrize("name", sorted(NOT_FRAGMENTS))
    def test_not_fragment(self, name):
        assert not looks_like_html_fragment(NOT_FRAGMENTS[name])


@pytest.mark.unit
class TestDetection:
    @pytest.mark.parametrize("name", sorted(FRAGMENTS))
    def test_nameless_fragment_routes_to_html(self, name):
        assert detect(FRAGMENTS[name]) == "html"

    def test_whole_pages_still_html(self):
        assert detect(b"<!DOCTYPE html><html><body><p>x</p></body></html>") == "html"

    def test_markdown_opening_with_html_stays_markdown(self):
        readme = (
            b'<p align="center"><img src="logo.png"></p>\n\n# Project\n\nSome **bold** and a [link](https://x.y).\n'
        )
        assert detect(readme) == "markdown"

    def test_fragment_converts(self):
        assert to_markdown(b"<p>V1 with <b>bold</b></p>").strip() == "V1 with **bold**"

    def test_a_named_file_is_unaffected(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_bytes(b"<p>literal</p>")
        assert registry.detect_format(path) == "plaintext"


@pytest.mark.unit
class TestTomlNeedsAKey:
    @pytest.mark.parametrize(
        "data", [b"# Test\n", b"# Hello World", b"# one\n# two\n", b"\n# indented comment\n"], ids=repr
    )
    def test_comments_alone_are_not_toml(self, data):
        assert not _detect_toml_content(data)
        assert detect(data) != "toml"

    @pytest.mark.parametrize("data", [b"key = 1\n", b"# comment\nkey = 'v'\n", b"[table]\nx = true\n"], ids=repr)
    def test_toml_with_keys(self, data):
        assert _detect_toml_content(data)

    def test_heading_is_not_wrapped_in_a_toml_block(self):
        assert "toml" not in to_markdown(b"# Test\n")
