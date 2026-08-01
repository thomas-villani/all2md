#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_str_input_disambiguation.py
"""Every text parser must read a ``str`` the same way (#233).

A ``str`` passed to a text parser may be either a file path or the document
content, and nothing in the signature says which. Before #233 the library
guessed two different ways: three parsers read every ``str`` as a path, so raw
content was unusable, and fifteen fell through to "it must be content", so a
mistyped filename silently became a one-line document containing the filename
— a successful conversion of the wrong thing.

These tests pin both halves across the whole set, so the two groups cannot
drift apart again.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from all2md.exceptions import FileNotFoundError as All2MdFileNotFoundError
from all2md.utils.inputs import looks_like_path_attempt, resolve_str_input

#: ``(format, module, class, sample content, extension)`` for every text parser
#: that accepts an ambiguous ``str``.
TEXT_PARSERS = [
    ("asciidoc", "all2md.parsers.asciidoc", "AsciiDocParser", "Hello world", ".adoc"),
    ("bbcode", "all2md.parsers.bbcode", "BBCodeParser", "Hello world", ".bbcode"),
    ("csv", "all2md.parsers.csv", "CsvToAstConverter", "a,b\nc,d", ".csv"),
    ("dokuwiki", "all2md.parsers.dokuwiki", "DokuWikiParser", "Hello world", ".dokuwiki"),
    ("html", "all2md.parsers.html", "HtmlToAstConverter", "<p>Hello</p>", ".html"),
    ("ini", "all2md.parsers.ini", "IniParser", "[s]\nk = v", ".ini"),
    ("json", "all2md.parsers.json", "JsonParser", '{"a": 1}', ".json"),
    ("latex", "all2md.parsers.latex", "LatexParser", "Hello world", ".tex"),
    ("markdown", "all2md.parsers.markdown", "MarkdownToAstConverter", "Hello world", ".md"),
    ("mediawiki", "all2md.parsers.mediawiki", "MediaWikiParser", "Hello world", ".wiki"),
    ("org", "all2md.parsers.org", "OrgParser", "Hello world", ".org"),
    ("plaintext", "all2md.parsers.plaintext", "PlainTextToAstConverter", "Hello world", ".txt"),
    ("rst", "all2md.parsers.rst", "RestructuredTextParser", "Hello world", ".rst"),
    ("rtf", "all2md.parsers.rtf", "RtfToAstConverter", r"{\rtf1\ansi Hello}", ".rtf"),
    ("textile", "all2md.parsers.textile", "TextileParser", "Hello world", ".textile"),
    ("toml", "all2md.parsers.toml", "TomlParser", "a = 1", ".toml"),
    ("yaml", "all2md.parsers.yaml", "YamlParser", "a: 1", ".yaml"),
    # fb2 has no one-line content form, so it appears only in the missing-path test.
    ("fb2", "all2md.parsers.fb2", "Fb2ToAstConverter", None, ".fb2"),
]

IDS = [entry[0] for entry in TEXT_PARSERS]


def _parser(module_name: str, class_name: str):
    """Import and instantiate a parser by name."""
    return getattr(importlib.import_module(module_name), class_name)()


@pytest.mark.unit
@pytest.mark.parametrize(("fmt", "module", "cls", "content", "extension"), TEXT_PARSERS, ids=IDS)
def test_raw_content_str_parses(fmt, module, cls, content, extension) -> None:
    """A ``str`` holding document content parses instead of being read as a path."""
    if content is None:
        pytest.skip(f"{fmt} has no single-line content form")

    document = _parser(module, cls).parse(content)

    assert document.children, f"{fmt} produced an empty document from raw content"


@pytest.mark.unit
@pytest.mark.parametrize(("fmt", "module", "cls", "content", "extension"), TEXT_PARSERS, ids=IDS)
def test_missing_path_str_raises_instead_of_becoming_a_document(fmt, module, cls, content, extension) -> None:
    """A mistyped filename raises rather than parsing into a one-line document."""
    with pytest.raises(All2MdFileNotFoundError):
        _parser(module, cls).parse(f"does_not_exist_{fmt}{extension}")


@pytest.mark.unit
@pytest.mark.parametrize(("fmt", "module", "cls", "content", "extension"), TEXT_PARSERS, ids=IDS)
def test_existing_path_str_is_read(fmt, module, cls, content, extension, tmp_path) -> None:
    """A ``str`` naming a real file is still read from disk."""
    if content is None:
        pytest.skip(f"{fmt} has no single-line content form")

    source = tmp_path / f"sample{extension}"
    source.write_text(content, encoding="utf-8")

    document = _parser(module, cls).parse(str(source))

    assert document.children, f"{fmt} produced an empty document from a real file"


@pytest.mark.unit
class TestLooksLikePathAttempt:
    """The predicate is deliberately narrow: prose must never be read as a path."""

    @pytest.mark.parametrize(
        "value",
        [
            "does_not_exist.md",
            "docs/guide.rst",
            "REPORT.DOCX",  # extension match is case-insensitive
        ],
    )
    def test_path_shaped_strings(self, value: str) -> None:
        assert looks_like_path_attempt(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "read config.json",  # whitespace: prose mentioning a file
            "Visit https://example.com",  # a URL, and prose
            "https://example.com/page.html",  # bare URL ending in a known extension
            "Hello world",  # no extension at all
            "yes/no",  # a separator, but no known extension
            "notes.unknownext",  # extension all2md does not know
            "",
        ],
    )
    def test_content_shaped_strings(self, value: str) -> None:
        assert looks_like_path_attempt(value) is False

    def test_over_long_strings_are_never_probed(self) -> None:
        """A string past the path-length cap is content, whatever it ends with."""
        assert looks_like_path_attempt("x" * 300 + ".md") is False


@pytest.mark.unit
class TestResolveStrInput:
    """The shared classifier used by every text parser."""

    def test_content_resolves_to_none(self) -> None:
        assert resolve_str_input("# A heading") is None

    def test_existing_file_resolves_to_its_path(self, tmp_path) -> None:
        source = tmp_path / "real.md"
        source.write_text("# Hi", encoding="utf-8")

        assert resolve_str_input(str(source)) == Path(str(source))

    def test_missing_path_error_explains_how_to_force_content(self) -> None:
        with pytest.raises(All2MdFileNotFoundError) as excinfo:
            resolve_str_input("does_not_exist.md")

        message = str(excinfo.value)
        assert "does_not_exist.md" in message
        # The escape hatches must be named, or the raise is just a new dead end.
        assert "encode()" in message
        assert "StringIO" in message
        assert "Path(" in message


@pytest.mark.unit
def test_prose_ending_in_a_dotted_word_still_parses() -> None:
    """Regression: ``.com`` is not an all2md extension, so this stays content.

    The asciidoc suite has parsed this exact string since long before #233; it
    is the shape most at risk from a looser "looks like a path" rule.
    """
    from all2md.parsers.asciidoc import AsciiDocParser

    document = AsciiDocParser().parse("Visit https://example.com")

    assert document.children
