#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Every ``--flag`` the prose docs name must be a flag the CLI actually has.

Seven documented flags did not exist. The pattern behind most of them is the
boolean-default rule: a bool field generates only the flag that *changes* its
default, so ``require_https=True`` yields ``--html-network-no-require-https`` and
the docs wrote the positive form nobody can type. Two were worse than a wrong
name - ``--html-network-require-https`` was documented as "Default: Disabled"
when HTTPS is required by default, and ``--html-network-max-remote-asset-bytes``
was a renamed option still documented at its old name *and* its old value.

Building the real flag set is the hard half, and getting it wrong is easy in a
direction that reads as success:

* ``create_parser()`` has no subparsers - every subcommand builds its own
  standalone parser inside its module, so the top-level parser alone misses 130+.
* Not every flag exists as a string literal. ``argparse.BooleanOptionalAction``
  synthesises ``--no-x`` from ``--x``, which is where ``--no-regex`` comes from.
* ``benchmarks/`` has its own CLI, and ``optimizations.rst`` documents it.

So this walks the AST for ``add_argument`` calls, synthesises the
BooleanOptionalAction negatives, and unions that with the top-level parser.
``test_the_flag_inventory_is_not_empty`` and ``test_a_fabricated_flag_is_caught``
exist because every one of the failure modes above produces a *passing* test.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

import pytest

from all2md.cli import create_parser

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DOC_DIR = _REPO / "docs" / "source"

# ``options.rst`` is generated from the option dataclasses by
# scripts/generate_options_doc.py, so it cannot drift by hand.
_GENERATED = {"options.rst"}

_FLAG_IN_PROSE = re.compile(r"``(--[a-z0-9][a-z0-9-]*)``")

# Flags named deliberately while not being real flags. Keep this as close to empty
# as possible: every entry is a flag the check can no longer catch. overview.rst
# explains the boolean-default rule *without* naming the non-existent positive
# form in literal markup, precisely so it does not need an exemption here - an
# entry for it would have masked the original bug on that very page.
_NOT_MEANT_TO_EXIST = {
    # lint_guide.rst uses it as a stand-in for "some rule flag".
    "--foo",
}


def _flags_from_source() -> set[str]:
    """Long options registered anywhere, including generated ``--no-`` forms."""
    found: set[str] = set()
    for root in (_REPO / "src" / "all2md", _REPO / "benchmarks"):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr != "add_argument":
                    continue
                names = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                longs = [n for n in names if n.startswith("--")]
                found.update(longs)

                boolean_optional = any(
                    kw.arg == "action" and "BooleanOptionalAction" in ast.dump(kw.value) for kw in node.keywords
                )
                if boolean_optional:
                    found.update(f"--no-{n[2:]}" for n in longs)
    return found


_REAL_FLAGS = {
    s for a in create_parser()._actions for s in a.option_strings if s.startswith("--")
} | _flags_from_source()


def _documented_flags() -> dict[str, set[str]]:
    """Prose page -> the flags it names in ``literal`` markup."""
    documented: dict[str, set[str]] = {}
    for path in sorted(_DOC_DIR.glob("*.rst")):
        if path.name in _GENERATED:
            continue
        flags = set(_FLAG_IN_PROSE.findall(path.read_text(encoding="utf-8", errors="replace")))
        if flags:
            documented[path.name] = flags
    return documented


_DOCUMENTED = _documented_flags()


def test_the_flag_inventory_is_not_empty() -> None:
    """Guard the guard: an empty or tiny inventory makes every doc flag 'undefined'.

    Conversely a *broken* inventory that returned everything would make the real
    test vacuous - so this pins the order of magnitude, not just non-emptiness.
    """
    assert len(_REAL_FLAGS) > 1000, f"expected the full generated flag surface, found {len(_REAL_FLAGS)}"
    assert "--pdf-pages" in _REAL_FLAGS, "top-level format flags missing from the inventory"
    assert "--no-wait" in _REAL_FLAGS, "subcommand flags missing from the inventory"
    assert "--no-regex" in _REAL_FLAGS, "BooleanOptionalAction negatives missing from the inventory"


def test_the_docs_actually_name_flags() -> None:
    """Guard the guard: if the prose scan finds nothing, nothing can fail."""
    total = sum(len(v) for v in _DOCUMENTED.values())
    assert total > 200, f"expected the docs to name many flags, found {total}"


def test_a_fabricated_flag_is_caught() -> None:
    """The check must be able to fail."""
    assert "--definitely-not-a-real-flag-xyz" not in _REAL_FLAGS


@pytest.mark.parametrize("page", sorted(_DOCUMENTED))
def test_documented_flags_exist(page: str) -> None:
    """No prose page may name a flag the CLI does not accept."""
    undefined = sorted(_DOCUMENTED[page] - _REAL_FLAGS - _NOT_MEANT_TO_EXIST)
    assert not undefined, f"{page} documents flags that do not exist: {undefined}"


def test_the_boolean_default_rule_still_holds() -> None:
    """The rule behind most of the bugs, pinned so the docs' explanation stays true.

    A bool defaulting True generates only the negative flag; one defaulting False
    generates only the positive.
    """
    assert "--html-network-no-require-https" in _REAL_FLAGS
    assert "--html-network-require-https" not in _REAL_FLAGS

    assert "--pptx-include-slide-numbers" in _REAL_FLAGS
    assert "--pptx-no-include-slide-numbers" not in _REAL_FLAGS


def test_boolean_optional_action_is_still_how_no_regex_exists() -> None:
    """If grep stops using BooleanOptionalAction, the inventory logic needs revisiting."""
    from all2md.cli.commands import search

    assert hasattr(argparse, "BooleanOptionalAction")
    source = Path(search.__file__).read_text(encoding="utf-8")
    assert "BooleanOptionalAction" in source
