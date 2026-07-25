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
        "all2md.options.asciidoc",
        "all2md.options.ast_json",
        "all2md.options.base",
        "all2md.options.chm",
        "all2md.options.common",
        "all2md.options.csv",
        "all2md.options.docx",
        "all2md.options.dokuwiki",
        "all2md.options.eml",
        "all2md.options.epub",
        "all2md.options.fb2",
        "all2md.options.html",
        "all2md.options.ipynb",
        "all2md.options.jinja",
        "all2md.options.latex",
        "all2md.options.markdown",
        "all2md.options.mediawiki",
        "all2md.options.mhtml",
        "all2md.options.odp",
        "all2md.options.ods",
        "all2md.options.odt",
        "all2md.options.org",
        "all2md.options.pdf",
        "all2md.options.plaintext",
        "all2md.options.pptx",
        "all2md.options.rst",
        "all2md.options.rtf",
        "all2md.options.sourcecode",
        "all2md.options.xlsx",
        "all2md.options.zip",
    }
)

# Backstop for the same bug appearing outside ``options`` - e.g. options go lazy
# but a renderer subpackage starts importing eagerly instead. Lower it when the
# number drops; raising it should need a reason in the commit message.
MAX_EAGER_ALL2MD_MODULES = 64

# Enough modules that a broken probe (empty output, import failure swallowed
# somewhere) is obviously distinguishable from a genuinely lean import.
_SANITY_FLOOR = 10


@functools.lru_cache(maxsize=1)
def _eager_all2md_modules() -> tuple[str, ...]:
    """``all2md.*`` modules present in ``sys.modules`` after a bare import.

    Must run in a fresh interpreter: the test process has already imported half
    the package, so measuring in-process would report the test suite's imports
    rather than the package's own.
    """
    probe = "import all2md, sys, json; print(json.dumps(sorted(m for m in sys.modules if m.startswith('all2md'))))"
    out = subprocess.check_output([sys.executable, "-c", probe], text=True)
    return tuple(json.loads(out))


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


def test_total_eager_all2md_modules_stays_under_ceiling() -> None:
    modules = _eager_all2md_modules()
    assert len(modules) <= MAX_EAGER_ALL2MD_MODULES, (
        f"import all2md now pulls in {len(modules)} all2md modules, ceiling is "
        f"{MAX_EAGER_ALL2MD_MODULES}. Either make the new imports lazy or raise "
        f"the ceiling deliberately.\nModules: {', '.join(modules)}"
    )
