#  Copyright (c) 2025 Tom Villani, Ph.D.
"""The held-out corpus must not be nameable from the tree that is tuned against it.

`benchmarks/pmc/README.md` has always carried the rule -- *score against it, do not tune
against it* -- and the rule was broken anyway. The corpus retired to
`manifest-tuned.json` leaked into **five** tracked files before anyone noticed: two
column-guard tests built their fixtures from its pages, the gridded-prose test from four
of its articles, the wrapped-cell-row test transcribed one of its tables verbatim, and a
comment in `_pdf_tables.py` cited another as "the worst table on the corpus". Every one of
those was a threshold or a strategy read off held-out data, which is exactly what a
development set is for and exactly what a held-out set stops being once it happens.

Nothing fired, because the rule lived in prose. This is the rule as a test: no article of
the current holdout may be *named* anywhere in the tree except in its own manifest and in
the dated readings that are the sanctioned output of scoring it.

The scan is deliberately over the text formats a citation actually lands in -- source,
tests, docs, config, committed JSON. It is a leak test, not a proof of independence: it
cannot see an exemplar an author looked at and paraphrased without the id. What it does
catch is the whole of how the last holdout was burned.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

_ROOT = Path(__file__).resolve().parents[2]
_PMC = _ROOT / "benchmarks" / "pmc"
_HOLDOUT = _PMC / "manifest-holdout.json"

#: Suffixes a citation lands in.  Article bytes themselves are never committed, so the
#: binary formats in the tree are test fixtures that cannot carry a PMCID as text.
_TEXT_SUFFIXES = frozenset({".py", ".md", ".rst", ".json", ".yml", ".yaml", ".toml", ".txt", ".cfg", ".ini"})

#: The two places a holdout article id is *supposed* to appear.
#:
#: The manifest is the pin itself.  The dated `results-*.json` are the output of the one
#: sanctioned read -- publishing a comparison means publishing which articles it covered,
#: and refusing that would trade an auditable reading for an unfalsifiable one.  They are
#: the seal's known weak edge: a reading is greppable once it exists.  What keeps that
#: honest is that a reading is committed *after* the work it scores, so an id reaching a
#: source file from one is still a leak this test catches.
_MAY_NAME_THE_HOLDOUT = ("benchmarks/pmc/manifest-holdout.json", "benchmarks/comparison/results-")


def _holdout_pmcids() -> set[str]:
    articles = json.loads(_HOLDOUT.read_text(encoding="utf-8"))["articles"]
    return {article_id.split(".")[0] for article_id in articles}


def _tracked_text_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
        cwd=_ROOT,
    )
    paths = [_ROOT / name for name in listing.stdout.split("\0") if name]
    return [path for path in paths if path.suffix in _TEXT_SUFFIXES and path.is_file()]


def test_the_scan_actually_reads_files() -> None:
    """Guard the guard: an empty file list, or an empty id set, makes the check vacuous."""
    assert len(_holdout_pmcids()) > 50, "the holdout manifest looks empty or unparsed"
    files = _tracked_text_files()
    assert len(files) > 500, f"only found {len(files)} tracked text files"
    assert any(path.name == "pyproject.toml" for path in files)


def test_no_tracked_file_names_a_held_out_article() -> None:
    """The rule the retired holdout was lost to, enforced instead of documented."""
    pattern = re.compile(r"\bPMC[0-9]+\b")
    holdout = _holdout_pmcids()

    offenders: dict[str, list[str]] = {}
    for path in _tracked_text_files():
        relative = path.relative_to(_ROOT).as_posix()
        if relative.startswith(_MAY_NAME_THE_HOLDOUT) or relative == "tests/unit/test_pmc_holdout_seal.py":
            continue
        named = sorted(set(pattern.findall(path.read_bytes().decode("utf-8", "replace"))) & holdout)
        if named:
            offenders[relative] = named

    assert (
        offenders == {}
    ), f"these files name a held-out article: score against the holdout, never tune against it. {offenders}"


@pytest.mark.parametrize("development_corpus", ["manifest.json", "manifest-tuned.json"])
def test_the_holdout_shares_no_article_with_a_development_corpus(development_corpus: str) -> None:
    """Offset seed anchors make disjointness expected; this makes it evidence.

    Checked on the bare PMCID rather than the versioned article id, so the same article at
    a different version cannot enter both corpora and read as two documents.
    """
    development = json.loads((_PMC / development_corpus).read_text(encoding="utf-8"))["articles"]
    shared = _holdout_pmcids() & {article_id.split(".")[0] for article_id in development}

    assert shared == set(), f"{development_corpus} shares {len(shared)} articles with the holdout: {sorted(shared)}"
