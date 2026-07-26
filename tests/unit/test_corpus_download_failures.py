"""A failed corpus fetch must not be cached as an empty result.

``_read_index`` returns ``[]`` -- not ``None`` -- for an empty ``_index.json``, and
every fetcher opens with ``if cached is not None: return cached``. So writing an empty
index after a failed download made that source permanently empty on any machine that
keeps the cache: the next run read the emptiness back as a valid hit and never
retried.

This is not hypothetical. A DNS failure fetching the Enron tarball produced
``[enron] cached 0 item(s)``, the download step exited 0, and the benchmark ran over
half a corpus. Only the gate's ``MISSING_DOCS`` check kept that from reading as a
pass, and the poisoned index would have reproduced it on every subsequent run.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from benchmarks.corpus import download as dl
from benchmarks.corpus import run as corpus_run

pytestmark = pytest.mark.unit


def test_an_empty_index_reads_back_as_a_cache_hit(tmp_path: Path) -> None:
    """The trap the rest of this module exists to avoid.

    If this ever returns ``None``, caching an empty result stops being dangerous and
    the ``_give_up`` calls could be simplified away.
    """
    (tmp_path / "_index.json").write_text("[]", encoding="utf-8")
    assert dl._read_index(tmp_path) == []
    assert dl._read_index(tmp_path) is not None


class TestFailuresAreNotCached:
    def test_a_failed_enron_download_leaves_no_index(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(dl, "_try_download", lambda *a, **k: None)

        items = dl.fetch_enron({"sample_size": 5, "seed": 42}, tmp_path)

        assert items == []
        assert not (tmp_path / "_index.json").exists(), "a failed download poisoned the cache"
        assert dl._read_index(tmp_path) is None, "the next run would short-circuit instead of retrying"

    def test_a_failed_govdocs1_download_leaves_no_index(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(dl, "_try_download", lambda *a, **k: None)

        items = dl.fetch_govdocs1({"sample_size": 5, "seed": 42, "shard": 0, "formats": ["pdf"]}, tmp_path)

        assert items == []
        assert dl._read_index(tmp_path) is None

    def test_the_retry_actually_happens_after_a_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Not caching is only useful if the next call re-enters the fetch."""
        attempts: list[str] = []

        def failing(*a: object, **k: object) -> None:
            attempts.append("tried")
            return None

        monkeypatch.setattr(dl, "_try_download", failing)
        dl.fetch_enron({"sample_size": 5, "seed": 42}, tmp_path)
        dl.fetch_enron({"sample_size": 5, "seed": 42}, tmp_path)

        assert len(attempts) == 2, "the second run short-circuited on a cached failure"


def test_a_genuinely_empty_shard_is_cached(tmp_path: Path) -> None:
    """The one empty result that *should* stick.

    The shard downloaded fine and holds none of the requested formats. That answer is
    deterministic, so re-deriving it every run buys nothing -- and if this stopped
    being cached, nothing would break except speed, which is why it is worth pinning
    that the distinction is deliberate rather than accidental.
    """
    shard = tmp_path / "000.zip"
    with zipfile.ZipFile(shard, "w") as zf:
        zf.writestr("notes.txt", "no pdfs here")

    items = dl.fetch_govdocs1({"sample_size": 5, "seed": 42, "shard": 0, "formats": ["pdf"]}, tmp_path)

    assert items == []
    assert (tmp_path / "_index.json").exists()
    assert json.loads((tmp_path / "_index.json").read_text(encoding="utf-8")) == []


class TestDownloadReportsFailure:
    """``download`` exiting 0 with nothing cached is the earliest vacuous pass."""

    def _invoke(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: dict) -> int:
        monkeypatch.setattr(corpus_run, "fetch_all", lambda *a, **k: fetched)
        return corpus_run.main(
            [
                "download",
                "--cache-dir",
                str(tmp_path / "cache"),
                "--results-dir",
                str(tmp_path / "results"),
            ]
        )

    def test_a_source_that_returned_nothing_is_a_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._invoke(tmp_path, monkeypatch, {"govdocs1": ["a"], "enron": []}) == 1

    def test_all_sources_empty_is_a_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._invoke(tmp_path, monkeypatch, {"govdocs1": [], "enron": []}) == 1

    def test_a_full_download_still_succeeds(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._invoke(tmp_path, monkeypatch, {"govdocs1": ["a"], "enron": ["b"]}) == 0
