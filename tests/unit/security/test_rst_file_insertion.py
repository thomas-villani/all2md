#  Copyright (c) 2025 Tom Villani, Ph.D.

"""An RST file must not read other files or URLs unless the caller allows it.

``.. include::`` and the ``:file:`` / ``:url:`` options of ``raw`` and ``csv-table``
used to copy any local file, or any URL's response, into the output, even under
``--safe-mode`` (GHSA-q9p2-g3hh-xx9c).
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

import pytest

from all2md import to_markdown
from all2md.options.rst import RstParserOptions

pytest.importorskip("docutils")

SECRET = "TOPSECRET-q9p2"


@pytest.fixture
def secret_files(tmp_path: Path) -> dict[str, str]:
    text = tmp_path / "secret.txt"
    text.write_text(f"{SECRET}\n", encoding="utf-8")
    csv = tmp_path / "secret.csv"
    csv.write_text(f"a,b\n{SECRET},2\n", encoding="utf-8")
    return {"text": text.as_posix(), "csv": csv.as_posix()}


def _directives(paths: dict[str, str]) -> dict[str, str]:
    p, c = paths["text"], paths["csv"]
    return {
        "include": f".. include:: {p}\n",
        "include-literal": f".. include:: {p}\n   :literal:\n",
        "include-code": f".. include:: {p}\n   :code: text\n",
        "include-in-list": f"- item\n\n  .. include:: {p}\n",
        "csv-table-file": f".. csv-table:: T\n   :file: {c}\n",
        "raw-file": f".. raw:: html\n   :file: {p}\n",
    }


def _convert(source: str, **options: object) -> str:
    return to_markdown(source.encode(), source_format="rst", parser_options=RstParserOptions(**options))


@pytest.mark.parametrize(
    "name", ["include", "include-literal", "include-code", "include-in-list", "csv-table-file", "raw-file"]
)
def test_file_reading_directives_refused_by_default(secret_files, name, caplog):
    source = "Before\n\n" + _directives(secret_files)[name] + "\nAfter\n"
    with caplog.at_level(logging.WARNING):
        out = _convert(source)
    assert SECRET not in out
    assert "Before" in out and "After" in out
    assert "--rst-parse-includes" in caplog.text


def test_relative_include_refused(tmp_path, monkeypatch):
    (tmp_path / "secret.txt").write_text(SECRET, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert SECRET not in _convert(".. include:: secret.txt\n")


def test_refused_under_safe_preset_defaults(secret_files):
    # The default parser options are what --safe-mode leaves in place.
    out = to_markdown(_directives(secret_files)["include"].encode(), source_format="rst")
    assert SECRET not in out


@pytest.mark.parametrize(
    "source",
    [
        ".. raw:: html\n   :url: http://127.0.0.1:9/secret\n",
        ".. csv-table:: T\n   :url: http://127.0.0.1:9/secret.csv\n",
    ],
)
def test_url_options_never_fetch_by_default(source, monkeypatch, caplog):
    calls: list[object] = []

    def fake_urlopen(*args: object, **kwargs: object) -> object:
        calls.append(args)
        raise AssertionError("fetched a URL")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with caplog.at_level(logging.WARNING):
        _convert(source)
    assert calls == []
    assert "--rst-parse-includes" in caplog.text


@pytest.mark.parametrize("name", ["include", "csv-table-file", "raw-file"])
def test_parse_includes_opts_in(secret_files, name, caplog):
    with caplog.at_level(logging.WARNING):
        out = _convert(_directives(secret_files)[name], parse_includes=True)
    assert SECRET in out
    assert "--rst-parse-includes" not in caplog.text


def test_ordinary_documents_unaffected(caplog):
    source = (
        "Title\n=====\n\nText with ``code``.\n\n"
        ".. raw:: html\n\n   <b>inline raw</b>\n\n"
        ".. csv-table:: T\n\n   a,b\n   1,2\n\n"
        ".. note:: A note.\n"
    )
    with caplog.at_level(logging.WARNING):
        out = _convert(source)
    assert "inline raw" in out
    assert "| 1 | 2 |" in out.replace("  ", " ")
    assert "A note." in out
    assert "--rst-parse-includes" not in caplog.text


def test_option_defaults_off():
    assert RstParserOptions().parse_includes is False
