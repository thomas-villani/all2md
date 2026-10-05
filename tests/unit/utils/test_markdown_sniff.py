#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Markdown is recognized from content alone, as stdin delivers it.

``cat notes.md | rcat`` used to print ``\\# Heading``: nameless content never
reached the Markdown parser, so it was read as plain text and its syntax escaped.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from all2md import to_markdown
from all2md.converter_registry import registry
from all2md.utils.markdown_sniff import has_markdown_front_matter, looks_like_markdown

FENCE = "`" * 3
REPO = Path(__file__).resolve().parents[3]

MARKDOWN = {
    "heading-and-list": "# Title\n\n- one\n- two\n",
    "todo-with-emphasis": "# TODO\n\n- buy milk\n- call **Bob**\n",
    "link-and-emphasis": "See the **guide** at [the docs](https://example.com/docs).\n",
    "fenced-python": f"# Usage\n\n{FENCE}python\nimport os\n\ndef main():\n    pass\n{FENCE}\n\nThen run it.\n",
    "table": "| a | b |\n|---|---|\n| 1 | 2 |\n\nSee `a`.\n",
    "yaml-front-matter": "---\ntitle: Notes\ntags: [a, b]\n---\n\n# Notes\n\nSome **bold** text.\n",
    "front-matter-then-prose": "---\ntitle: Notes\n---\nJust one paragraph of prose.\n",
    "toml-front-matter": "+++\ntitle = 'x'\n+++\n\n## Heading\n\n- a\n- b\n",
}

NOT_MARKDOWN = {
    "prose": "Dear team,\n\nThe meeting moved to Friday.\n\nThanks\n",
    "python": "# util\n\nimport os\n\ndef f():\n    return 1\n",
    "shell": "#!/bin/sh\n# install\n\n- not a list\n- really\necho **done**\n",
    "comments-then-code": "# Build the thing\nmake all\n# Install it\nmake install\n",
    "gitignore": "# Byte-compiled\n__pycache__/\n**/*.pyc\n\n# Env\n.venv/\n",
    "rst": "Title\n=====\n\n- one\n- two\n\nSee :func:`main` and **this**.\n\n.. note::\n\n   Body\n",
    "org": "#+TITLE: Notes\n\n* Heading\n\n- one\n- two\n\n*bold* and =code=\n",
    "minified-js": "!function(e){var t={};function n(r){return t[r]}};n.p='**x**';var a=`[y](z)`;",
    "single-mark": "- one\n- two\n- three\n",
    "binary": "# Title\n\n- a\n- b\n\x00\x01",
}


@pytest.mark.unit
class TestLooksLikeMarkdown:
    @pytest.mark.parametrize("name", list(MARKDOWN))
    def test_markdown(self, name):
        assert looks_like_markdown(MARKDOWN[name].encode())

    @pytest.mark.parametrize("name", list(NOT_MARKDOWN))
    def test_not_markdown(self, name):
        assert not looks_like_markdown(NOT_MARKDOWN[name].encode())

    def test_repository_readme(self):
        """A README full of shell and Python examples is still Markdown: fenced code is set aside first."""
        assert looks_like_markdown((REPO / "README.md").read_bytes())

    def test_front_matter_followed_by_yaml_is_a_yaml_stream(self):
        assert not has_markdown_front_matter(b"---\na: 1\n---\nc: 3\n")


@pytest.mark.unit
class TestDetection:
    @pytest.mark.parametrize("name", list(MARKDOWN))
    def test_nameless_markdown_routes_to_markdown(self, name):
        assert registry.detect_format(MARKDOWN[name].encode()) == "markdown"

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b"# hosts\n- alpha.example.com\n- beta.example.com\n", "yaml"),
            (b"# config\n\nname: x\nitems:\n  - a\n  - b\n", "yaml"),
            (b'{"a": 1}', "json"),
            (b"name,age\nalice,30\nbob,25\n", "csv"),
            (NOT_MARKDOWN["prose"].encode(), "plaintext"),
            (NOT_MARKDOWN["python"].encode(), "plaintext"),
        ],
        ids=["yaml-list", "yaml-mapping", "json", "csv", "prose", "python"],
    )
    def test_other_formats_keep_their_detectors(self, data, expected):
        assert registry.detect_format(data) == expected

    def test_without_mistune_stays_plaintext(self, monkeypatch):
        import importlib.util

        real = importlib.util.find_spec
        monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "mistune" else real(name, *a))
        assert registry.detect_format(MARKDOWN["heading-and-list"].encode()) == "plaintext"

    def test_a_named_file_is_unaffected(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_text(MARKDOWN["heading-and-list"], encoding="utf-8")
        assert registry.detect_format(str(path)) == "plaintext"

    def test_stdin_markdown_is_not_escaped(self):
        output = to_markdown(io.BytesIO(MARKDOWN["todo-with-emphasis"].encode()))
        assert output.startswith("# TODO")
        assert "\\#" not in output and "**Bob**" in output
