"""Regression tests for the pinned OmniDocBench runtime corpus cache."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlsplit

import pytest

from benchmarks.omnidocbench import corpus

pytestmark = pytest.mark.unit


def _record(position: int, *, image_path: str | None = None) -> dict[str, object]:
    return {
        "layout_dets": [],
        "page_info": {
            "page_attribute": {},
            "page_no": position,
            "height": 1200,
            "width": 900,
            "image_path": image_path or f"page-{position:04d}.jpg",
        },
    }


def _annotation_bytes(
    count: int = corpus.EXPECTED_PAGES,
    *,
    records: list[dict[str, object]] | None = None,
) -> bytes:
    payload = records if records is not None else [_record(i) for i in range(count)]
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def _pdf_bytes(page_id: str) -> bytes:
    return f"%PDF-1.7\nsynthetic {page_id}\n%%EOF\n".encode()


def _install_downloader(
    monkeypatch: pytest.MonkeyPatch,
    annotation: bytes,
) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(corpus, "ANNOTATION_SHA256", hashlib.sha256(annotation).hexdigest())

    def download(url: str, destination: Path, **_: object) -> int:
        calls.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        name = unquote(Path(urlsplit(url).path).name)
        content = annotation if name == corpus.ANNOTATION_FILENAME else _pdf_bytes(Path(name).stem)
        destination.write_bytes(content)
        return len(content)

    monkeypatch.setattr(corpus.corpus_download, "_download", download)
    return calls


def _prime_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    limit: int,
) -> tuple[corpus.CorpusSnapshot, bytes, list[str]]:
    annotation = _annotation_bytes()
    calls = _install_downloader(monkeypatch, annotation)
    snapshot = corpus.load_corpus(tmp_path, limit=limit, workers=1)
    return snapshot, annotation, calls


def _forbid_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_download(*_: object, **__: object) -> int:
        raise AssertionError("warm cache unexpectedly attempted network transport")

    monkeypatch.setattr(corpus.corpus_download, "_download", fail_download)


def _rewrite_index(index_path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    mutate(payload)
    index_path.write_text(json.dumps(payload), encoding="utf-8")


def test_valid_cold_cache_downloads_and_indexes_all_pinned_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cold full run must hash exactly 981 PDFs and write pinned provenance."""
    annotation = _annotation_bytes()
    calls = _install_downloader(monkeypatch, annotation)

    snapshot = corpus.load_corpus(tmp_path, workers=1)

    revision_dir = tmp_path / corpus.REVISION
    index_path = corpus._index_path(revision_dir, None)
    first_pdf = _pdf_bytes("page-0000")
    last_pdf = _pdf_bytes("page-0980")
    assert snapshot.revision == corpus.REVISION
    assert snapshot.annotation_path == revision_dir / corpus.ANNOTATION_FILENAME
    assert snapshot.annotation_path.read_bytes() == annotation
    assert snapshot.expected_pages == 981
    assert snapshot.complete is True
    assert len(snapshot.pages) == 981
    assert snapshot.pages[0] == corpus.CorpusPage(
        page_id="page-0000",
        image_path="page-0000.jpg",
        pdf_path=revision_dir / "pdfs/page-0000.pdf",
        sha256=hashlib.sha256(first_pdf).hexdigest(),
        size_bytes=len(first_pdf),
    )
    assert snapshot.pages[-1] == corpus.CorpusPage(
        page_id="page-0980",
        image_path="page-0980.jpg",
        pdf_path=revision_dir / "pdfs/page-0980.pdf",
        sha256=hashlib.sha256(last_pdf).hexdigest(),
        size_bytes=len(last_pdf),
    )
    assert len(calls) == 982
    assert calls[0] == (
        f"https://huggingface.co/datasets/{corpus.DATASET_ID}/resolve/"
        f"{corpus.REVISION}/{corpus.ANNOTATION_FILENAME}?download=true"
    )
    assert calls[-1].endswith(f"/{corpus.REVISION}/pdfs/page-0980.pdf?download=true")
    assert index_path.is_file() is True
    assert corpus.REVISION in index_path.name
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["revision"] == corpus.REVISION
    assert index["annotation_sha256"] == hashlib.sha256(annotation).hexdigest()
    assert index["expected_pages"] == 981
    assert index["requested_limit"] is None
    assert index["complete"] is True
    assert len(index["pages"]) == 981


def test_valid_warm_cache_revalidates_without_downloading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A warm hit must reproduce exact page metadata without invoking transport."""
    cold, _, cold_calls = _prime_cache(tmp_path, monkeypatch, limit=2)
    assert len(cold_calls) == 3
    _forbid_download(monkeypatch)

    warm = corpus.load_corpus(tmp_path, limit=2, workers=1)

    assert warm == cold
    assert warm.complete is False
    assert warm.expected_pages == 981
    assert tuple(page.page_id for page in warm.pages) == ("page-0000", "page-0001")


def test_annotation_sha256_mismatch_is_rejected_before_page_downloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unpinned annotation bytes must leave no annotation, PDFs, or cache index."""
    annotation = _annotation_bytes()
    calls = _install_downloader(monkeypatch, annotation)
    monkeypatch.setattr(corpus, "ANNOTATION_SHA256", "0" * 64)
    actual = hashlib.sha256(annotation).hexdigest()

    with pytest.raises(corpus.CorpusIntegrityError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    revision_dir = tmp_path / corpus.REVISION
    assert str(raised.value) == f"annotation SHA-256 mismatch: expected {'0' * 64}, got {actual}"
    assert len(calls) == 1
    assert (revision_dir / corpus.ANNOTATION_FILENAME).exists() is False
    assert (revision_dir / f"{corpus.ANNOTATION_FILENAME}.part").exists() is False
    assert corpus._index_path(revision_dir, 1).exists() is False
    assert list((revision_dir / "pdfs").iterdir()) == []


@pytest.mark.parametrize(
    ("count", "expected_message"),
    [
        (0, "annotation page count mismatch: expected 981, got 0"),
        (980, "annotation page count mismatch: expected 981, got 980"),
    ],
    ids=["zero-records", "truncated-record-set"],
)
def test_annotation_requires_the_exact_record_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    expected_message: str,
) -> None:
    """Zero and truncated annotation arrays must never become benchmark corpora."""
    annotation = _annotation_bytes(count)
    calls = _install_downloader(monkeypatch, annotation)

    with pytest.raises(corpus.CorpusIntegrityError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == expected_message
    assert len(calls) == 1
    assert corpus._index_path(tmp_path / corpus.REVISION, 1).exists() is False


def test_annotation_rejects_duplicate_derived_page_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two image paths deriving the same page ID must fail before any PDF fetch."""
    records = [_record(i) for i in range(corpus.EXPECTED_PAGES)]
    records[-1] = _record(corpus.EXPECTED_PAGES - 1, image_path="nested/page-0000.png")
    annotation = _annotation_bytes(records=records)
    calls = _install_downloader(monkeypatch, annotation)

    with pytest.raises(corpus.CorpusIntegrityError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == "duplicate page_id 'page-0000' at annotation record 980"
    assert len(calls) == 1
    assert list((tmp_path / corpus.REVISION / "pdfs").iterdir()) == []


def test_annotation_rejects_a_truncated_page_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A record missing one required page_info field must fail exact schema validation."""
    records = [_record(i) for i in range(corpus.EXPECTED_PAGES)]
    page_info = records[17]["page_info"]
    assert isinstance(page_info, dict)
    del page_info["height"]
    annotation = _annotation_bytes(records=records)
    calls = _install_downloader(monkeypatch, annotation)

    with pytest.raises(corpus.CorpusIntegrityError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == "annotation record 17 page_info is missing fields: height"
    assert len(calls) == 1
    assert corpus._index_path(tmp_path / corpus.REVISION, 1).exists() is False


def test_warm_cache_rejects_an_index_for_the_wrong_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A warm index with any other dataset revision must not authorize cached bytes."""
    _, _, _ = _prime_cache(tmp_path, monkeypatch, limit=1)
    index_path = corpus._index_path(tmp_path / corpus.REVISION, 1)
    _rewrite_index(index_path, lambda index: index.__setitem__("revision", "wrong-revision"))
    _forbid_download(monkeypatch)

    with pytest.raises(corpus.CorpusCacheError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == (f"cache index revision mismatch: expected {corpus.REVISION}, got 'wrong-revision'")
    assert index_path.exists() is True


def test_warm_cache_rejects_a_nonexact_index_page_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dropping one selected page from an index must invalidate the entire warm hit."""
    _, _, _ = _prime_cache(tmp_path, monkeypatch, limit=2)
    index_path = corpus._index_path(tmp_path / corpus.REVISION, 2)

    def drop_last(index: dict[str, object]) -> None:
        pages = index["pages"]
        assert isinstance(pages, list)
        pages.pop()

    _rewrite_index(index_path, drop_last)
    _forbid_download(monkeypatch)

    with pytest.raises(corpus.CorpusCacheError) as raised:
        corpus.load_corpus(tmp_path, limit=2, workers=1)

    assert str(raised.value) == "cache index page set does not match pinned annotation"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(index["pages"]) == 1


def test_warm_cache_rejects_a_missing_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deleted indexed PDF must be reported rather than treated as a cache hit."""
    snapshot, _, _ = _prime_cache(tmp_path, monkeypatch, limit=1)
    pdf_path = snapshot.pages[0].pdf_path
    pdf_path.unlink()
    _forbid_download(monkeypatch)

    with pytest.raises(corpus.CorpusCacheError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == "cached PDF is missing for 'page-0000'"
    assert pdf_path.exists() is False


def test_warm_cache_rejects_a_truncated_pdf_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated PDF must fail the indexed exact-size contract before hashing."""
    snapshot, _, _ = _prime_cache(tmp_path, monkeypatch, limit=1)
    page = snapshot.pages[0]
    original = page.pdf_path.read_bytes()
    page.pdf_path.write_bytes(original[:-1])
    _forbid_download(monkeypatch)

    with pytest.raises(corpus.CorpusCacheError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == (
        f"cached PDF size mismatch for 'page-0000': expected {len(original)}, got {len(original) - 1}"
    )
    assert page.pdf_path.stat().st_size == len(original) - 1


def test_warm_cache_rejects_same_size_pdf_corruption_by_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same-size PDF corruption must be detected by full SHA-256 revalidation."""
    snapshot, _, _ = _prime_cache(tmp_path, monkeypatch, limit=1)
    page = snapshot.pages[0]
    original = page.pdf_path.read_bytes()
    corrupted = original[:-2] + b"X\n"
    assert len(corrupted) == len(original)
    page.pdf_path.write_bytes(corrupted)
    actual = hashlib.sha256(corrupted).hexdigest()
    _forbid_download(monkeypatch)

    with pytest.raises(corpus.CorpusCacheError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == (f"cached PDF SHA-256 mismatch for 'page-0000': expected {page.sha256}, got {actual}")
    assert page.pdf_path.stat().st_size == page.size_bytes


@pytest.mark.parametrize(
    ("invalid_pdf", "expected_size"),
    [(b"", 0), (b"%PD", 3)],
    ids=["zero-byte-pdf", "truncated-pdf"],
)
def test_cold_cache_rejects_zero_or_truncated_pdf_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_pdf: bytes,
    expected_size: int,
) -> None:
    """Zero and truncated PDF downloads must be removed and never indexed."""
    annotation = _annotation_bytes()
    monkeypatch.setattr(corpus, "ANNOTATION_SHA256", hashlib.sha256(annotation).hexdigest())
    calls: list[str] = []

    def invalid_download(url: str, destination: Path, **_: object) -> int:
        calls.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        name = unquote(Path(urlsplit(url).path).name)
        content = annotation if name == corpus.ANNOTATION_FILENAME else invalid_pdf
        destination.write_bytes(content)
        return len(content)

    monkeypatch.setattr(corpus.corpus_download, "_download", invalid_download)

    with pytest.raises(corpus.CorpusIntegrityError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    revision_dir = tmp_path / corpus.REVISION
    pdf_path = revision_dir / "pdfs/page-0000.pdf"
    assert str(raised.value) == "downloaded PDF 'page-0000' is not a non-empty PDF"
    assert len(calls) == 2
    assert len(invalid_pdf) == expected_size
    assert pdf_path.exists() is False
    assert corpus._index_path(revision_dir, 1).exists() is False


def test_failed_download_is_atomic_and_never_writes_an_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transport failure must remove both partial and prematurely final PDF bytes."""
    annotation = _annotation_bytes()
    monkeypatch.setattr(corpus, "ANNOTATION_SHA256", hashlib.sha256(annotation).hexdigest())
    calls: list[str] = []
    monkeypatch.setattr(corpus.corpus_download, "RETRY_BACKOFF_SECONDS", 0)

    def failing_download(url: str, destination: Path, **_: object) -> int:
        calls.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        name = unquote(Path(urlsplit(url).path).name)
        if name == corpus.ANNOTATION_FILENAME:
            destination.write_bytes(annotation)
            return len(annotation)
        destination.with_suffix(destination.suffix + ".part").write_bytes(b"partial")
        destination.write_bytes(b"premature-final")
        raise OSError("synthetic connection reset")

    monkeypatch.setattr(corpus.corpus_download, "_download", failing_download)

    with pytest.raises(corpus.CorpusDownloadError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    revision_dir = tmp_path / corpus.REVISION
    pdf_path = revision_dir / "pdfs/page-0000.pdf"
    assert str(raised.value) == "failed to download PDF page-0000"
    assert len(calls) == 4
    assert (revision_dir / corpus.ANNOTATION_FILENAME).read_bytes() == annotation
    assert pdf_path.exists() is False
    assert pdf_path.with_suffix(".pdf.part").exists() is False
    assert corpus._index_path(revision_dir, 1).exists() is False


def test_limited_mode_is_explicitly_incomplete_even_at_the_full_page_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Supplying any limit must preserve expected_pages=981 while marking incomplete."""
    annotation = _annotation_bytes()
    calls = _install_downloader(monkeypatch, annotation)

    smoke = corpus.load_corpus(tmp_path, limit=2, workers=1)
    all_but_limited = corpus.load_corpus(tmp_path, limit=981, workers=1)

    revision_dir = tmp_path / corpus.REVISION
    smoke_index = json.loads(corpus._index_path(revision_dir, 2).read_text(encoding="utf-8"))
    all_limited_index = json.loads(corpus._index_path(revision_dir, 981).read_text(encoding="utf-8"))
    assert smoke.complete is False
    assert smoke.expected_pages == 981
    assert len(smoke.pages) == 2
    assert smoke_index["complete"] is False
    assert smoke_index["requested_limit"] == 2
    assert len(smoke_index["pages"]) == 2
    assert all_but_limited.complete is False
    assert all_but_limited.expected_pages == 981
    assert len(all_but_limited.pages) == 981
    assert all_limited_index["complete"] is False
    assert all_limited_index["requested_limit"] == 981
    assert len(all_limited_index["pages"]) == 981
    assert corpus._index_path(revision_dir, None).exists() is False
    assert len(calls) == 982


def test_cross_mode_load_rejects_corruption_using_the_shared_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new mode must reject a %PDF-prefixed page corrupted after another mode."""
    snapshot, _, _ = _prime_cache(tmp_path, monkeypatch, limit=2)
    page = snapshot.pages[0]
    original = page.pdf_path.read_bytes()
    corrupted = original[:-2] + b"X\n"
    assert len(corrupted) == len(original)
    assert corrupted.startswith(b"%PDF") is True
    page.pdf_path.write_bytes(corrupted)
    actual = hashlib.sha256(corrupted).hexdigest()
    _forbid_download(monkeypatch)

    with pytest.raises(corpus.CorpusCacheError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    revision_dir = tmp_path / corpus.REVISION
    manifest = json.loads(corpus._manifest_path(revision_dir).read_text(encoding="utf-8"))
    assert str(raised.value) == (
        f"cached PDF SHA-256 mismatch for 'page-0000': " f"expected {page.sha256}, got {actual}"
    )
    assert manifest["pages"]["page-0000"]["sha256"] == page.sha256
    assert corpus._index_path(revision_dir, 1).exists() is False


def test_mode_index_digest_disagreement_with_manifest_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mode index cannot replace a revision-wide immutable page digest."""
    snapshot, _, _ = _prime_cache(tmp_path, monkeypatch, limit=1)
    index_path = corpus._index_path(tmp_path / corpus.REVISION, 1)

    def replace_digest(index: dict[str, object]) -> None:
        pages = index["pages"]
        assert isinstance(pages, list)
        row = pages[0]
        assert isinstance(row, dict)
        row["sha256"] = "0" * 64

    _rewrite_index(index_path, replace_digest)
    _forbid_download(monkeypatch)

    with pytest.raises(corpus.CorpusCacheError) as raised:
        corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert str(raised.value) == ("cache index digest disagrees with artifact manifest for 'page-0000'")
    assert snapshot.pages[0].pdf_path.read_bytes() == _pdf_bytes("page-0000")
    assert snapshot.pages[0].sha256 != "0" * 64


def test_untrusted_existing_pdf_is_redownloaded_before_manifest_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An orphan PDF with no manifest digest must be replaced, not rehashed and blessed."""
    annotation = _annotation_bytes()
    calls = _install_downloader(monkeypatch, annotation)
    revision_dir = tmp_path / corpus.REVISION
    pdf_path = revision_dir / "pdfs/page-0000.pdf"
    pdf_path.parent.mkdir(parents=True)
    (revision_dir / corpus.ANNOTATION_FILENAME).write_bytes(annotation)
    orphan = b"%PDF-1.7\nuntrusted but plausible\n%%EOF\n"
    pdf_path.write_bytes(orphan)

    snapshot = corpus.load_corpus(tmp_path, limit=1, workers=1)

    trusted = _pdf_bytes("page-0000")
    manifest = json.loads(corpus._manifest_path(revision_dir).read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert calls[0].endswith(f"/{corpus.REVISION}/pdfs/page-0000.pdf?download=true")
    assert pdf_path.read_bytes() == trusted
    assert pdf_path.read_bytes() != orphan
    assert snapshot.pages[0].sha256 == hashlib.sha256(trusted).hexdigest()
    assert manifest["pages"]["page-0000"]["sha256"] == snapshot.pages[0].sha256


def test_concurrent_processes_publish_one_complete_materialization(
    tmp_path: Path,
) -> None:
    """Two processes must serialize publication and leave no shared or partial temp."""
    annotation = _annotation_bytes()
    source_path = tmp_path / "_synthetic_annotation.json"
    source_path.write_bytes(annotation)
    log_path = tmp_path / "_download_log.txt"
    start_path = tmp_path / "_start"
    script = """
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit


cache_dir = Path(sys.argv[1])
source_path = Path(sys.argv[2])
log_path = Path(sys.argv[3])
start_path = Path(sys.argv[4])
corpus_path = Path(sys.argv[5])
spec = importlib.util.spec_from_file_location("omnidocbench_corpus_child", corpus_path)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load corpus adapter")
corpus = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = corpus
spec.loader.exec_module(corpus)
annotation = source_path.read_bytes()
corpus.ANNOTATION_SHA256 = hashlib.sha256(annotation).hexdigest()

def record(message):
    with log_path.open("a", encoding="utf-8") as output:
        output.write(message + "\\n")
        output.flush()
        os.fsync(output.fileno())

def download(url, destination, **_):
    name = unquote(Path(urlsplit(url).path).name)
    record("start " + name)
    time.sleep(0.05)
    content = (
        annotation
        if name == corpus.ANNOTATION_FILENAME
        else f"%PDF-1.7\\nsynthetic {Path(name).stem}\\n%%EOF\\n".encode()
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    record("end " + name)
    return len(content)

corpus.corpus_download._download = download
deadline = time.monotonic() + 5
while not start_path.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("start barrier was not released")
    time.sleep(0.01)
snapshot = corpus.load_corpus(cache_dir, limit=1, workers=1)
print(json.dumps({
    "complete": snapshot.complete,
    "page_id": snapshot.pages[0].page_id,
    "sha256": snapshot.pages[0].sha256,
}))
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                script,
                str(tmp_path),
                str(source_path),
                str(log_path),
                str(start_path),
                str(Path(corpus.__file__).resolve()),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    start_path.write_text("start", encoding="utf-8")
    completed = [process.communicate(timeout=15) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], [stderr for _, stderr in completed]
    assert [stderr for _, stderr in completed] == ["", ""]

    expected_digest = hashlib.sha256(_pdf_bytes("page-0000")).hexdigest()
    observed = [json.loads(stdout) for stdout, _ in completed]
    revision_dir = tmp_path / corpus.REVISION
    leftovers = sorted(
        path.name
        for path in revision_dir.rglob("*")
        if ".download" in path.name or path.name.endswith(".part") or path.name.endswith(".tmp")
    )
    assert observed == [
        {
            "complete": False,
            "page_id": "page-0000",
            "sha256": expected_digest,
        },
        {
            "complete": False,
            "page_id": "page-0000",
            "sha256": expected_digest,
        },
    ]
    assert log_path.read_text(encoding="utf-8").splitlines() == [
        f"start {corpus.ANNOTATION_FILENAME}",
        f"end {corpus.ANNOTATION_FILENAME}",
        "start page-0000.pdf",
        "end page-0000.pdf",
    ]
    assert leftovers == []
    assert corpus._manifest_path(revision_dir).is_file() is True
    assert corpus._index_path(revision_dir, 1).is_file() is True


def test_transient_transport_failure_is_retried_before_the_run_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One throttled response out of 981 downloads must not abort a monthly cold run.

    ``_download_artifact`` used to call ``corpus_download._download`` directly, so the very
    first transient network error raised ``CorpusDownloadError`` and discarded every page
    already fetched. It now goes through ``_try_download`` with a bounded retry budget: the
    bound matters in both directions, because retrying forever would stop the gate from ever
    reporting that the network is broken.
    """
    annotation = _annotation_bytes()
    monkeypatch.setattr(corpus, "ANNOTATION_SHA256", hashlib.sha256(annotation).hexdigest())
    monkeypatch.setattr(corpus.corpus_download, "RETRY_BACKOFF_SECONDS", 0)
    attempts: list[str] = []

    def flaky(url: str, destination: Path, **_: object) -> int:
        attempts.append(url)
        name = unquote(Path(urlsplit(url).path).name)
        if name != corpus.ANNOTATION_FILENAME and len([u for u in attempts if u == url]) == 1:
            raise TimeoutError("connection timed out")
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = annotation if name == corpus.ANNOTATION_FILENAME else _pdf_bytes(Path(name).stem)
        destination.write_bytes(content)
        return len(content)

    monkeypatch.setattr(corpus.corpus_download, "_download", flaky)

    snapshot = corpus.load_corpus(tmp_path, limit=1, workers=1)

    assert len(snapshot.pages) == 1
    pdf_urls = [url for url in attempts if url.endswith(".pdf?download=true")]
    assert len(pdf_urls) == 2 and pdf_urls[0] == pdf_urls[1]
    assert snapshot.pages[0].pdf_path.read_bytes().startswith(b"%PDF")
