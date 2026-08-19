#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Every figure ``benchmarks.rst`` publishes must match the artifact behind it.

The fidelity page is the one place the project makes a public quality claim, and
the claim is only worth anything because each number comes from a committed
artifact -- :file:`benchmarks/pmc/reference.json` and
:file:`benchmarks/omnidocbench/baseline.json`. Nothing enforced that. The page
and the artifacts were written in the same change and agreed on the day; the
first time a pin moved they could silently stop agreeing, and a stale figure on
that page reads exactly like a measured one.

That is not hypothetical. This lane has already published a comparison between
two runs covering different corpora, and issue #332 restored a withdrawn article
precisely because a corpus can change under a page that still quotes the old
reading.

The check is deliberately built the strong way round. Rather than scraping
numbers out of the prose and asking whether each looks plausible -- which cannot
see a figure that should be there and is not, and needs an exemption for every
incidental integer like "981 pages" -- each published claim is declared here as a
*rendered snippet* built from the artifact, and the page must contain it
verbatim. A value that drifts fails, and so does a stale line that was never
updated, because the whole line is matched rather than the number alone.

``test_the_figure_inventory_is_not_empty`` and
``test_a_perturbed_artifact_is_caught`` exist because the obvious ways for this
to break -- an artifact that fails to load, a renderer that returns ``""`` -- all
produce a *passing* test.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_PAGE = _REPO / "docs" / "source" / "benchmarks.rst"
_PMC = _REPO / "benchmarks" / "pmc" / "reference.json"
_OMNI = _REPO / "benchmarks" / "omnidocbench" / "baseline.json"


def _percent(value: float, places: int = 1) -> str:
    return f"{value * 100:.{places}f}%"


def _pmc_figures(pmc: dict[str, Any]) -> list[tuple[str, str]]:
    corpus, recall, precision = pmc["corpus"], pmc["article_recall"], pmc["article_precision"]
    kinds = recall["by_kind"]
    rows: list[tuple[str, str]] = [
        (
            "corpus coverage",
            f"It covers **{corpus['articles_scored']} articles and {corpus['pages_scored']} pages**.",
        ),
        (
            "raw recall row",
            f"   * - Raw recall\n     - {_percent(recall['recall'])}\n"
            f"     - of {recall['scored']:,} ground-truth blocks",
        ),
        ("raw recall prose", f"Raw recall is {_percent(recall['recall'])},"),
        ("attainable ceiling", f"     - {_percent(recall['ceiling'])}\n"),
        ("recall of attainable", f"     - **{_percent(recall['attainable_recall'])}**\n"),
        ("recall control", f"     - {_percent(recall['control_recall'])}\n"),
        ("supported share", f"     - **{_percent(precision['precision'])}**\n"),
        ("novel share", f"     - **{_percent(precision['novel_share'])}**\n"),
        (
            "emitted n-grams",
            f"Over {precision['emitted']:,} emitted n-grams, {precision['novel']:,} are novel.",
        ),
        (
            # Phrased for a surplus rather than a deficit: since the word-gutter and
            # two-column admissions the lane emits tables on more pages than the ground
            # truth expects, and "on 120 of 94 pages that should carry one" stopped
            # parsing as English.
            "tables",
            f"**{corpus['tables_emitted']} emitted against {corpus['tables_expected']}\n"
            f"expected**, with tables emitted on {corpus['pages_with_emitted_table']} pages\n"
            f"against the {corpus['pages_with_expected_table']} that carry one in the ground truth.",
        ),
    ]
    for label, kind in (("text blocks", "text_block"), ("titles", "title"), ("tables", "table")):
        entry = kinds[kind]
        rows.append(
            (
                f"by-kind row: {label}",
                f"     - {entry['attainable']:,} of {entry['scored']:,}\n"
                f"     - {entry['recovered']:,}\n"
                f"     - **{_percent(entry['attainable_recall'])}**",
            )
        )
    return rows


def _omnidocbench_figures(omni: dict[str, Any]) -> list[tuple[str, str]]:
    pages = omni["pages"]["scored"]
    rows = []
    for name in ("text_content_similarity", "reading_order_similarity", "block_structure_similarity"):
        value = omni["dimensions"][name]["value"]
        rows.append((f"omnidocbench {name}", f"   * - ``{name}``\n     - {value:.3f}\n"))
    rows.append(("omnidocbench page count", f"The ``omnidocbench`` lane scores {pages} scanned pages"))
    return rows


def _figures() -> list[tuple[str, str]]:
    pmc = json.loads(_PMC.read_bytes())
    omni = json.loads(_OMNI.read_bytes())
    return _pmc_figures(pmc) + _omnidocbench_figures(omni)


def _page_text() -> str:
    # The repo checks these blobs out as CRLF on Windows; normalise so the
    # multi-line snippets above compare the same way on every platform.
    return _PAGE.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _mismatches(render: Callable[[], list[tuple[str, str]]] = _figures) -> list[str]:
    page = _page_text()
    return [f"{label}: {snippet!r}" for label, snippet in render() if snippet not in page]


def test_the_figure_inventory_is_not_empty() -> None:
    """A loader that silently yields nothing would make every other test vacuous."""
    figures = _figures()
    assert len(figures) >= 15, f"expected the full published set, got {len(figures)}"
    assert all(snippet.strip() for _label, snippet in figures), "a figure rendered as empty text"


def test_published_figures_match_their_artifacts() -> None:
    """Every number on the fidelity page comes from a committed artifact."""
    mismatches = _mismatches()
    assert not mismatches, "docs/source/benchmarks.rst disagrees with its artifacts:\n  " + "\n  ".join(mismatches)


def test_the_reference_was_recorded_against_the_committed_manifest() -> None:
    """The strongest form of "the docs and the pin must never disagree".

    The figures above are only meaningful if the run that produced them scored
    the corpus this repository actually names. ``corpus_pin`` is the SHA-256 of
    the manifest, so a manifest edit that lands without a re-record -- exactly
    what #332 had to repair -- is caught here rather than at the next scheduled
    run, or not at all.
    """
    manifest = _REPO / "benchmarks" / "pmc" / "manifest.json"
    recorded = json.loads(_PMC.read_bytes())["provenance"]["corpus_pin"]
    actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert recorded == actual, (
        f"benchmarks/pmc/reference.json was recorded against corpus pin {recorded[:16]}, "
        f"but the committed manifest hashes to {actual[:16]} -- re-record the reference"
    )


def test_the_reference_was_produced_by_the_current_payload_shape() -> None:
    """A payload change without a re-record leaves the artifact describing an older run.

    ``corpus_pin`` catches a *corpus* that moved underneath the reference; this catches the
    *measurement* moving underneath it. Both matter, and neither implies the other -- the
    schema bump that added this check reshaped ``degraded_events`` without touching a single
    figure on the page, so nothing else here would have noticed.
    """
    from benchmarks.pmc.benchmark import SCHEMA_VERSION

    recorded = json.loads(_PMC.read_bytes())["schema_version"]
    assert recorded == SCHEMA_VERSION, (
        f"benchmarks/pmc/reference.json is a schema {recorded} payload but the lane now emits "
        f"{SCHEMA_VERSION} -- re-record the reference"
    )


def test_the_reference_covers_the_whole_corpus() -> None:
    """A partial run must not sit behind figures the page presents as the corpus.

    ``complete_corpus`` going false is the lane's incident signal (#330). It is
    the right behaviour for a run and the wrong state for a *published*
    reference, because the page quotes the artifact as the reading.
    """
    reference = json.loads(_PMC.read_bytes())
    manifest_articles = len(json.loads((_REPO / "benchmarks" / "pmc" / "manifest.json").read_bytes())["articles"])
    assert reference["provenance"]["complete_corpus"] is True, "the published reference is a partial run"
    assert reference["corpus"]["articles_scored"] == manifest_articles


def test_a_perturbed_artifact_is_caught() -> None:
    """Verify the judge can fail: move a figure and the check must go red.

    Without this, every failure mode that produces an empty or unmatched
    inventory reads as a pass -- which is the specific way the gates in this repo
    have gone wrong before.
    """
    pmc = json.loads(_PMC.read_bytes())
    pmc["corpus"]["pages_scored"] += 1
    pmc["article_precision"]["novel_share"] += 0.05

    def perturbed() -> list[tuple[str, str]]:
        return _pmc_figures(pmc)

    mismatches = _mismatches(perturbed)
    assert len(mismatches) >= 2, f"a perturbed artifact still matched the page: {mismatches}"
