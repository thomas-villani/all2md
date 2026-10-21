"""check-deps reports features that belong to no format (read, mcp, ...)."""

from __future__ import annotations

import json

import pytest

from all2md import dependencies
from all2md.dependencies import FEATURES, Feature, check_feature, get_feature

pytestmark = pytest.mark.unit

VIEWER = Feature("viewer", "a viewer", "tui", (("wijjit", "wijjit"),), (99, 0))
FREE = Feature("free", "needs nothing", "none", ())


@pytest.fixture
def importable(monkeypatch):
    found: set[str] = set()
    monkeypatch.setattr(dependencies, "_importable", lambda module: module in found)
    return found


def test_feature_names_are_not_formats():
    assert not [feature.name for feature in FEATURES if dependencies.is_valid_format(feature.name)]


def test_get_feature():
    assert get_feature("read").extra == "tui"
    assert get_feature("pdf") is None


def test_missing_package(importable):
    status = check_feature(get_feature("mcp"))
    assert not status["available"]
    assert status["packages"] == {"fastmcp": False, "rank-bm25": False}
    assert status["install_command"] == 'pip install "all2md[mcp]"'


def test_available(importable):
    importable.update({"fastmcp", "rank_bm25"})
    assert check_feature(get_feature("mcp"))["available"]


def test_python_too_old(importable):
    importable.add("wijjit")
    status = check_feature(VIEWER)
    assert not status["available"] and not status["python_ok"]
    assert dependencies._feature_lines(VIEWER) == ["  [OK] wijjit", "  Needs Python 99.0 or later"]


def test_no_packages():
    assert check_feature(FREE)["available"]


def test_text_report_lists_features(importable):
    report = dependencies.print_dependency_report()
    features = report.split("Features", 1)[1]
    assert "READ: [MISSING] all2md read and rcat -i" in features
    assert 'Install with: pip install "all2md[tui]"' in features


def test_json_report_has_features(importable):
    importable.add("watchdog")
    features = dependencies.format_json_all_formats()["features"]
    assert set(features) == {feature.name for feature in FEATURES}
    assert features["watch"]["status"] == "ok"
    assert features["chunk"] == {
        "status": "missing",
        "feature": "chunk",
        "description": get_feature("chunk").description,
        "extra": "chunk",
        "min_python": None,
        "packages": {"tiktoken": "missing"},
        "install_command": 'pip install "all2md[chunk]"',
    }


def test_rich_report_lists_features(importable, capsys):
    dependencies.print_dependency_report_rich()
    out = capsys.readouterr().out
    assert "Features" in out and "watch" in out


def test_check_one_feature(importable, capsys):
    assert dependencies.main(["check", "--format", "watch"]) == 1
    out = capsys.readouterr().out
    assert "watch (--watch" in out and 'pip install "all2md[cli_extras]"' in out

    importable.add("watchdog")
    assert dependencies.main(["check", "--format", "watch"]) == 0
    assert "All dependencies for watch" in capsys.readouterr().out


def test_check_one_feature_json(importable, capsys):
    assert dependencies.main(["check", "--format", "chunk", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["packages"] == {"tiktoken": "missing"}


def test_unknown_name_lists_features(capsys):
    assert dependencies.main(["check", "--format", "nope"]) == 1
    assert "Features: read, mcp, watch, chunk, search" in capsys.readouterr().err


def test_through_the_cli(importable, capsys):
    from all2md.cli import main

    assert main(["check-deps", "read"]) == 1
    assert "read (all2md read" in capsys.readouterr().out
