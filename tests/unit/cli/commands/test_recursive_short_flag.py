#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Every command with ``--recursive`` takes ``-r`` too, as ``all2md`` and ``serve`` already did."""

from __future__ import annotations

import pytest

from all2md.cli.commands.generate_site import _create_generate_site_parser
from all2md.cli.commands.lint import _build_parser as _build_lint_parser
from all2md.cli.commands.search import _build_search_argument_parser, handle_grep_command


@pytest.mark.unit
@pytest.mark.parametrize(
    ("build", "argv"),
    [
        (_build_search_argument_parser, ["query", "docs", "-r"]),
        (_build_lint_parser, ["docs", "-r"]),
        (_create_generate_site_parser, ["docs", "--output-dir", "site", "--generator", "hugo", "-r"]),
    ],
    ids=["search", "lint", "generate-site"],
)
def test_short_flag_sets_recursive(build, argv):
    assert build().parse_args(argv).recursive is True


@pytest.mark.unit
def test_grep_short_flag_finds_nested_files(tmp_path, capsys):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "notes.md").write_text("The deadline is Friday.\n", encoding="utf-8")

    assert handle_grep_command(["deadline", str(tmp_path), "-r"]) == 0
    assert "notes.md" in capsys.readouterr().out
