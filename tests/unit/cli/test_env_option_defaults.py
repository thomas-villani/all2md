"""``ALL2MD_<OPTION>`` environment variables reach the converter options.

The tracking actions read each variable into the argparse default, but the
options mapper only took arguments typed on the command line, so every
per-option variable parsed and was then dropped. The documented order is:
built-in defaults < environment < config file < explicit flags.
"""

from __future__ import annotations

import logging

import pytest

from all2md.cli import main
from all2md.cli.builder import DynamicCLIBuilder, create_parser


def options_for(argv: list[str], config: dict | None = None) -> dict:
    parsed = create_parser().parse_args(argv)
    return DynamicCLIBuilder().map_args_to_options(parsed, json_options=config)


@pytest.fixture
def doc(tmp_path):
    path = tmp_path / "a.md"
    path.write_text("*hi*" + chr(10), encoding="utf-8")
    return path


def convert(path, *extra: str) -> str:
    out = path.with_suffix(".out.md")
    assert main([str(path), "--no-config", "--out", str(out), *extra]) == 0
    return out.read_text(encoding="utf-8").strip()


@pytest.mark.unit
@pytest.mark.cli
class TestMapping:
    def test_environment_default_is_mapped(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", "_")
        assert options_for(["x.md"])["markdown.emphasis_symbol"] == "_"

    def test_unset_argument_is_not_mapped(self, monkeypatch):
        monkeypatch.delenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", raising=False)
        assert "markdown.emphasis_symbol" not in options_for(["x.md"])

    def test_flag_beats_environment(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", "_")
        options = options_for(["x.md", "--markdown-emphasis-symbol", "*"])
        assert options["markdown.emphasis_symbol"] == "*"

    def test_config_beats_environment(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", "_")
        options = options_for(["x.md"], config={"markdown": {"emphasis_symbol": "*"}})
        assert options["markdown.emphasis_symbol"] == "*"

    def test_environment_fills_what_config_leaves(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", "_")
        options = options_for(["x.md"], config={"markdown": {"bullet_symbols": "-"}})
        assert options["markdown.emphasis_symbol"] == "_"
        assert options["markdown.bullet_symbols"] == "-"

    def test_boolean(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_HTML_EXTRACT_TITLE", "yes")
        assert options_for(["x.html"])["html.extract_title"] is True

    def test_store_false_flag_names_the_value(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_PDF_DETECT_COLUMNS", "false")
        assert options_for(["x.pdf"])["pdf.detect_columns"] is False

    def test_global_attachment_mode_reaches_formats(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_ATTACHMENT_MODE", "skip")
        assert options_for(["x.html"])["html.attachment_mode"] == "skip"

    def test_global_attachment_flag_beats_environment(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_ATTACHMENT_MODE", "skip")
        options = options_for(["x.html", "--attachment-mode", "base64"])
        assert options["html.attachment_mode"] == "base64"


@pytest.mark.unit
@pytest.mark.cli
class TestInvalidValues:
    def test_bad_choice_is_ignored_with_a_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", "x")
        with caplog.at_level(logging.WARNING):
            options = options_for(["x.md"])
        assert "markdown.emphasis_symbol" not in options
        assert "ALL2MD_MARKDOWN_EMPHASIS_SYMBOL" in caplog.text

    @pytest.mark.parametrize("value", ["maybe", "", "2"])
    def test_bad_boolean_is_ignored_with_a_warning(self, monkeypatch, caplog, value):
        monkeypatch.setenv("ALL2MD_HTML_EXTRACT_TITLE", value)
        with caplog.at_level(logging.WARNING):
            options = options_for(["x.html"])
        assert "html.extract_title" not in options
        assert "ALL2MD_HTML_EXTRACT_TITLE" in caplog.text

    @pytest.mark.parametrize("value", ["0", "off", "FALSE", " no "])
    def test_false_spellings(self, monkeypatch, value):
        monkeypatch.setenv("ALL2MD_HTML_EXTRACT_TITLE", value)
        assert options_for(["x.html"])["html.extract_title"] is False


@pytest.mark.unit
@pytest.mark.cli
class TestCliOnlyVariables:
    def test_format(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_FORMAT", "csv")
        assert create_parser().parse_args(["x"]).format == "csv"

    def test_unknown_format_is_ignored(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_FORMAT", "nonsense")
        assert create_parser().parse_args(["x"]).format == "auto"

    def test_strict_args(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_STRICT_ARGS", "true")
        assert create_parser().parse_args(["x"]).strict_args is True

    def test_cli_only_variables_are_not_options(self, monkeypatch):
        monkeypatch.setenv("ALL2MD_FORMAT", "csv")
        monkeypatch.setenv("ALL2MD_STRICT_ARGS", "true")
        options = options_for(["x"])
        assert "format" not in options and "strict_args" not in options


@pytest.mark.unit
@pytest.mark.cli
class TestEndToEnd:
    def test_environment_changes_the_output(self, monkeypatch, doc):
        monkeypatch.delenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", raising=False)
        assert convert(doc) == "*hi*"
        monkeypatch.setenv("ALL2MD_MARKDOWN_EMPHASIS_SYMBOL", "_")
        assert convert(doc) == "_hi_"
        assert convert(doc, "--markdown-emphasis-symbol", "*") == "*hi*"
