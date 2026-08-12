#  Copyright (c) 2025 Tom Villani, Ph.D.
"""``python -m all2md`` and ``python -m all2md.cli`` must both reach argparse.

``all2md`` had a ``__main__.py``; ``all2md.cli`` did not. The failure mode is
worse than an unknown command, because Python refuses to run the package *before*
argparse sees the arguments:

    No module named all2md.cli.__main__; 'all2md.cli' is a package and
    cannot be directly executed

Every invocation then fails identically regardless of what follows it. A probe
asking "does the CLI accept this flag?" gets the same answer for a real flag and
an invented one, which is exactly how a docs audit came to report a fabricated
flag as accepted.

So it is not enough to assert the entry point works. The tests below also assert
it can *reject*, which is the property that was silently missing.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit

_ENTRY_POINTS = ["all2md", "all2md.cli"]
_NOT_A_FLAG = "--definitely-not-a-real-flag-xyz"


def _run(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("module", _ENTRY_POINTS)
def test_module_entry_point_runs(module: str) -> None:
    """The package is executable with -m and reports a version."""
    result = _run(module, "--version")

    assert "cannot be directly executed" not in result.stderr, f"{module} has no __main__.py: {result.stderr}"
    assert result.returncode == 0, f"{module} --version failed: {result.stderr}"
    assert "all2md" in result.stdout


@pytest.mark.parametrize("module", _ENTRY_POINTS)
def test_module_entry_point_rejects_an_unknown_flag(module: str) -> None:
    """Guard the guard: the entry point must be able to fail for the right reason.

    Without this, an entry point that cannot start at all looks identical to one
    that accepts everything.
    """
    result = _run(module, "-", _NOT_A_FLAG)

    assert result.returncode != 0, f"{module} accepted {_NOT_A_FLAG}"
    assert "cannot be directly executed" not in result.stderr
    combined = (result.stderr + result.stdout).lower()
    assert "unrecognized argument" in combined, f"{module} failed for the wrong reason: {result.stderr[:400]}"


def test_the_two_entry_points_agree() -> None:
    """``python -m all2md`` and ``python -m all2md.cli`` are the same program."""
    assert _run("all2md", "--version").stdout == _run("all2md.cli", "--version").stdout
