"""The lint gate must be able to fail.

``fix = true`` in ``[tool.ruff]`` applies to plain ``ruff check``, not just
``ruff check --fix``. With it set, CI's ``ruff check src/ tests/`` rewrote every
auto-fixable violation inside the runner and exited 0: the job went green, the
repair was discarded with the runner, and the violation stayed on ``main``. Only
rules with no auto-fix -- a small minority -- could ever turn the gate red.

That is the same shape as every other vacuous pass this project has found: a
green produced by not measuring rather than by measuring well. It is worth a
test because the setting is a one-line, entirely reasonable-looking convenience
that would be easy to reintroduce, and because nothing else in the suite would
notice if it came back.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on 3.10
    import tomli as tomllib

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _ruff_config() -> dict:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle).get("tool", {}).get("ruff", {})


def test_ruff_does_not_autofix_by_default() -> None:
    """``ruff check`` must report, not repair."""
    assert _ruff_config().get("fix") is not True, (
        "`fix = true` makes plain `ruff check` rewrite violations and exit 0, "
        "so the CI lint job cannot fail. Use `ruff check --fix` when you want "
        "the repair."
    )


@pytest.mark.skipif(not CI_WORKFLOW.exists(), reason="CI workflow not present in this checkout")
def test_ci_lints_with_no_fix() -> None:
    """The gate should not depend on the config staying correct."""
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    invocations = [line.strip() for line in workflow.splitlines() if line.strip().startswith("ruff check")]

    assert invocations, "no `ruff check` invocation found in ci.yml"
    for invocation in invocations:
        assert "--no-fix" in invocation, f"CI lint invocation can be silenced by config: {invocation!r}"
