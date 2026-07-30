"""The benchmark conftest must hide benchmarks without hijacking ``-m``.

``tests/performance/conftest.py`` hides its benchmarks by rewriting ``markexpr`` in
``pytest_configure``. That hook runs *after* argument parsing, so assigning to
``markexpr`` outright threw away whatever the caller asked for: ``pytest -m unit``
collected the entire suite (7997 tests rather than 3857), quietly turning the
documented fast path into a full run. CI never noticed because it passes no ``-m``,
which makes the overwrite a no-op there.

Two instruments, because neither sees what the other does:

* the parametrized cases below pin the *expression*, and cannot flake;
* :func:`test_a_real_collection_honours_the_marker` runs real pytest, and would catch
  the hook being dropped, renamed, or never registered -- none of which the
  expression tests can see.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_CONFTEST = REPO_ROOT / "tests" / "performance" / "conftest.py"

pytestmark = pytest.mark.unit


def _load_benchmark_conftest() -> ModuleType:
    """Import the benchmark conftest by path.

    ``tests/`` is not a package, so the usual dotted import is not available.
    """
    spec = importlib.util.spec_from_file_location("_benchmark_conftest", BENCHMARK_CONFTEST)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _StubConfig:
    """The two bits of ``pytest.Config`` the hook touches."""

    def __init__(self, markexpr: str, benchmark: bool) -> None:
        self.option = SimpleNamespace(markexpr=markexpr)
        self._benchmark = benchmark

    def getoption(self, name: str, default: object = None) -> object:
        assert name == "--benchmark"
        return self._benchmark


@pytest.mark.parametrize(
    ("markexpr", "benchmark", "expected"),
    [
        # No selection to preserve: the historical behaviour, and what CI hits.
        ("", False, "not benchmark"),
        # A selection *is* present, so it has to survive. This is the regression.
        ("unit", False, "(unit) and not benchmark"),
        ("integration", False, "(integration) and not benchmark"),
        # Parenthesised because `not` binds tighter than `or`; without the parens
        # `unit or integration` would widen to `unit or (integration and not benchmark)`.
        ("unit or integration", False, "(unit or integration) and not benchmark"),
        ("not slow", False, "(not slow) and not benchmark"),
        # --benchmark means the caller wants them; leave the expression alone.
        ("", True, ""),
        ("pdf", True, "pdf"),
    ],
)
def test_the_hook_narrows_rather_than_replaces(markexpr: str, benchmark: bool, expected: str) -> None:
    config = _StubConfig(markexpr=markexpr, benchmark=benchmark)
    _load_benchmark_conftest().pytest_configure(config)  # type: ignore[arg-type]
    assert config.option.markexpr == expected


def test_a_real_collection_honours_the_marker() -> None:
    """Collect a benchmark file and a unit file together, asking for neither.

    ``-m integration`` over this pair must select nothing. Under the overwrite bug the
    expression became a bare ``not benchmark``, which selects the 10 unit tests --
    so this asserts on the exact discrepancy, not merely on "something was filtered".
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/performance",
            "tests/unit/utils/test_fingerprint.py",
            "-m",
            "integration",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert "test_fingerprint" not in result.stdout, (
        "asked for integration tests and got unit tests back; the benchmark conftest "
        f"is overwriting -m again.\n{result.stdout}"
    )
