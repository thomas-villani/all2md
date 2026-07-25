"""Ratchet on what ``import all2md`` drags in eagerly.

Cold start is O(number of registered formats): importing the package pulls in an
options module for essentially every format, so the cost of ``all2md --version``
grows in proportion to how successful we are at adding formats. That is a scaling
bug, and this is the gate that holds the line on it.

**Why a test and not a benchmark.** The cost shows up as milliseconds, but the
*cause* is a set of module names, and a set can be compared exactly. Measuring it
as time means fighting a 6-7% runner variance floor (see the Startup Runner
Variance workflow), which leaves enough slack for several new eager modules to
land unnoticed - precisely the regression this exists to catch. Counting them
instead is deterministic: zero flake, and it fails on the *first* offending
module rather than the fourth.

A timing gate still has its place for gross regressions; the two are complements,
not alternatives.

**Updating the allowlist.** ``EAGER_OPTIONS_MODULES`` is a ratchet, not a
registry. Removing entries is the win R2 is chasing and needs no justification.
*Adding* one means a new format made cold start slower for everyone who never
uses that format - do it consciously, in the same commit, or make the import lazy
instead. Note the deliberate exception recorded in ``all2md/__init__.py``:
parsers must import eagerly to trigger registration. Options modules must not.
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit


# Every ``all2md.options.*`` module pulled in by a bare ``import all2md``.
# 31 modules to print a version string. Shrinking this list is the point of R2.
EAGER_OPTIONS_MODULES = frozenset(
    {
        "all2md.options",
        "all2md.options.base",
        "all2md.options.common",
        "all2md.options.markdown",
    }
)

# Backstop for the same bug appearing outside ``options`` - e.g. options go lazy
# but a renderer subpackage starts importing eagerly instead. Lower it when the
# number drops; raising it should need a reason in the commit message.
#
# Lowered 64 -> 40 when R2b made the options package lazy (actual: 37). Left with
# a little slack rather than pinned to 37, because unlike the allowlists above
# this is a *ceiling*, and pinning it exactly would turn every legitimate new
# module into a failure of this test instead of a decision someone makes.
MAX_EAGER_ALL2MD_MODULES = 40

# Third-party top-level packages a bare ``import all2md`` costs the user, over
# and above the stdlib. Currently lean, and the cheapest way to keep it that way:
# a single eager ``import pandas`` would cost more than every options module
# combined and is invisible to both gates above, which only count ``all2md.*``.
#
# ``yaml`` and ``tomli_w`` at import time are themselves R2 leads - neither is
# obviously needed to print a version string.
#
# Backports are a property of the interpreter, not of our import graph: on 3.10
# ``options/base.py`` falls back to ``typing_extensions`` for ``Self``, which the
# stdlib provides from 3.11. Gating on it unconditionally would fail 3.10 for
# being 3.10, so it is added per-version. The guard mirrors the dependency marker
# in pyproject.toml (``typing_extensions>=4.0.0;python_version<'3.11'``) - if
# that marker moves, this must move with it.
_BACKPORTS = frozenset({"typing_extensions"}) if sys.version_info < (3, 11) else frozenset()

EAGER_THIRD_PARTY_PACKAGES = frozenset({"all2md", "tomli_w", "yaml"}) | _BACKPORTS

# Enough modules that a broken probe (empty output, import failure swallowed
# somewhere) is obviously distinguishable from a genuinely lean import.
_SANITY_FLOOR = 10


# Runs in a fresh interpreter on purpose: the test process has already imported
# half the package, so probing in-process would report the test suite's imports
# rather than the package's own. Pseudo-modules injected by C extensions (notably
# ``cython_runtime``) have no ``__file__`` and are filtered out - whether they
# appear depends on which wheels the platform installed, not on our code.
_PROBE = """
import json, sys
before = set(sys.modules)
import all2md
new = set(sys.modules) - before

third_party = sorted(
    top
    for top in {m.split(".")[0] for m in new}
    if top not in sys.stdlib_module_names
    and not top.startswith("_")
    and getattr(sys.modules.get(top), "__file__", None) is not None
)
print(json.dumps({
    "all2md": sorted(m for m in sys.modules if m.startswith("all2md")),
    "third_party": third_party,
}))
"""


@functools.lru_cache(maxsize=1)
def _probe() -> dict[str, list[str]]:
    """What a bare ``import all2md`` leaves in ``sys.modules``."""
    out = subprocess.check_output([sys.executable, "-c", _PROBE], text=True)
    return json.loads(out)


def _eager_all2md_modules() -> tuple[str, ...]:
    return tuple(_probe()["all2md"])


def _eager_third_party_packages() -> frozenset[str]:
    return frozenset(_probe()["third_party"])


def _paste_ready(modules: set[str]) -> str:
    body = "\n".join(f'        "{m}",' for m in sorted(modules))
    return f"EAGER_OPTIONS_MODULES = frozenset(\n    {{\n{body}\n    }}\n)"


def test_probe_reports_a_plausible_import_set() -> None:
    """Guard the guard: a dead probe must not read as a lean import.

    Verified by stubbing the probe to return nothing: the exact-set gate below
    catches that on its own (an empty set has 31 entries *missing*), but the
    ceiling gate passes vacuously, since zero modules is comfortably under any
    ceiling. This test is what covers that hole.
    """
    modules = _eager_all2md_modules()
    assert "all2md" in modules, "the probe did not import all2md at all"
    assert len(modules) >= _SANITY_FLOOR, f"probe returned only {len(modules)} modules; it is probably broken, not fast"


def test_eager_options_imports_match_the_allowlist() -> None:
    actual = {m for m in _eager_all2md_modules() if m.startswith("all2md.options")}
    added = actual - EAGER_OPTIONS_MODULES
    removed = EAGER_OPTIONS_MODULES - actual

    if added or removed:
        lines = ["Eagerly-imported all2md.options.* modules changed.", ""]
        if added:
            lines += [
                "NEW eager imports (each one makes cold start slower for every user,",
                "including those who never touch that format - prefer a lazy import):",
                *(f"  + {m}" for m in sorted(added)),
                "",
            ]
        if removed:
            lines += [
                "No longer imported eagerly (this is the win - record it):",
                *(f"  - {m}" for m in sorted(removed)),
                "",
            ]
        lines += ["Updated allowlist:", "", _paste_ready(actual)]
        pytest.fail("\n".join(lines))


def test_eager_third_party_packages_match_the_allowlist() -> None:
    actual = _eager_third_party_packages()
    added = actual - EAGER_THIRD_PARTY_PACKAGES
    removed = EAGER_THIRD_PARTY_PACKAGES - actual

    if added or removed:
        lines = ["Third-party packages imported eagerly by `import all2md` changed.", ""]
        if added:
            lines += [
                "NEW eager third-party imports. Every all2md user now pays this",
                "package's import cost, whether or not they use the feature that",
                "needs it - move it inside the function that uses it if you can:",
                *(f"  + {m}" for m in sorted(added)),
                "",
            ]
        if removed:
            lines += ["No longer imported eagerly (record the win):", *(f"  - {m}" for m in sorted(removed)), ""]
        # Backports are added per-version, so pasting them into the base set
        # would break every other interpreter in the matrix.
        base = sorted(actual - _BACKPORTS)
        lines += ["Updated allowlist (version-specific backports excluded):", "", f"    frozenset({base!r})"]
        pytest.fail("\n".join(lines))


def test_total_eager_all2md_modules_stays_under_ceiling() -> None:
    modules = _eager_all2md_modules()
    assert len(modules) <= MAX_EAGER_ALL2MD_MODULES, (
        f"import all2md now pulls in {len(modules)} all2md modules, ceiling is "
        f"{MAX_EAGER_ALL2MD_MODULES}. Either make the new imports lazy or raise "
        f"the ceiling deliberately.\nModules: {', '.join(modules)}"
    )
