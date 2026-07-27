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
import urllib.error
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


class TestLargeDownloadRetry:
    """A weekly gate that goes red on a network blip gets ignored, and then it is not a gate.

    The bound matters as much as the retry: this pins that the budget is finite and
    that exhausting it still returns ``None``, so the caller still fails loudly.
    """

    @pytest.fixture(autouse=True)
    def _no_real_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(dl.time, "sleep", lambda _: None)

    def _failing_download(self, monkeypatch: pytest.MonkeyPatch, error: Exception, succeed_on: int = 0) -> list[int]:
        calls: list[int] = []

        def fake(url: str, dest: Path, **kwargs: object) -> int:
            calls.append(len(calls) + 1)
            if succeed_on and len(calls) >= succeed_on:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b"payload")
                return 7
            raise error

        monkeypatch.setattr(dl, "_download", fake)
        return calls

    def test_a_transient_failure_is_retried_to_the_bound(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self._failing_download(monkeypatch, urllib.error.URLError("dns went away"))

        size = dl._try_download("http://x/a.tar.gz", tmp_path / "a.tar.gz", label="a", retries=2)

        assert size is None, "an exhausted retry budget must still report failure"
        assert len(calls) == 3, "retries=2 means three attempts"

    def test_a_recovered_download_returns_its_size(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self._failing_download(monkeypatch, urllib.error.URLError("blip"), succeed_on=2)

        size = dl._try_download("http://x/a.tar.gz", tmp_path / "a.tar.gz", label="a", retries=2)

        assert size == 7
        assert len(calls) == 2, "it should stop retrying once it succeeds"

    def test_a_404_is_not_retried(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Retrying a wrong URL is just a slower way to fail."""
        error = urllib.error.HTTPError("http://x/a", 404, "Not Found", {}, None)  # type: ignore[arg-type]
        calls = self._failing_download(monkeypatch, error)

        assert dl._try_download("http://x/a", tmp_path / "a", label="a", retries=2) is None
        assert len(calls) == 1

    def test_a_503_is_retried(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        error = urllib.error.HTTPError("http://x/a", 503, "Unavailable", {}, None)  # type: ignore[arg-type]
        calls = self._failing_download(monkeypatch, error)

        assert dl._try_download("http://x/a", tmp_path / "a", label="a", retries=2) is None
        assert len(calls) == 3

    def test_small_fetches_do_not_retry_by_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Per-document fetches are cheap to lose; retrying each would multiply the run."""
        calls = self._failing_download(monkeypatch, urllib.error.URLError("blip"))

        assert dl._try_download("http://x/a", tmp_path / "a", label="a") is None
        assert len(calls) == 1

    def test_the_two_large_downloads_ask_for_retries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The retry is worthless if the callers that need it do not pass it."""
        seen: list[int] = []

        def fake(*a: object, **kwargs: object) -> None:
            seen.append(int(kwargs.get("retries", 0)))  # type: ignore[arg-type]
            return None

        monkeypatch.setattr(dl, "_try_download", fake)
        dl.fetch_enron({"sample_size": 5, "seed": 42}, tmp_path / "enron")
        dl.fetch_govdocs1({"sample_size": 5, "seed": 42, "shard": 0, "formats": ["pdf"]}, tmp_path / "gov")

        assert seen == [dl.LARGE_DOWNLOAD_RETRIES, dl.LARGE_DOWNLOAD_RETRIES]


class TestUnfulfilledFormatsAreReported:
    """A requested format that matches nothing used to be simply absent.

    ``corpus.toml`` asks govdocs1 for pdf *and* docx and gets zero docx, so the
    benchmark covers a narrower format mix than its own manifest advertises.
    """

    def _items(self, *formats: str) -> list[dl.CorpusItem]:
        return [
            dl.CorpusItem(source="s", format=f, source_id=f"id-{f}", filename=f"f.{f}", size_bytes=1) for f in formats
        ]

    def test_a_format_that_matched_nothing_is_named(self, capsys: pytest.CaptureFixture[str]) -> None:
        missing = dl._report_unfulfilled_formats("govdocs1", {"formats": ["pdf", "docx"]}, self._items("pdf"))

        assert missing == ["docx"]
        assert "docx" in capsys.readouterr().out

    def test_a_fulfilled_manifest_says_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        missing = dl._report_unfulfilled_formats("poi", {"formats": ["docx", "pptx"]}, self._items("docx", "pptx"))

        assert missing == []
        assert capsys.readouterr().out == ""

    def test_a_source_that_returned_nothing_is_left_to_give_up(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``_give_up`` already reported that failure; a second warning is noise."""
        assert dl._report_unfulfilled_formats("enron", {"formats": ["eml"]}, []) == []
        assert capsys.readouterr().out == ""

    def test_case_differences_are_not_a_miss(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert dl._report_unfulfilled_formats("s", {"formats": ["PDF"]}, self._items("pdf")) == []
        assert capsys.readouterr().out == ""


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
