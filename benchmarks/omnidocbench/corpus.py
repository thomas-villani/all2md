"""Pinned OmniDocBench v1.0 corpus download and cache validation.

The benchmark data is fetched only at runtime into a caller-supplied cache.  The
annotation and every page PDF are tied to the immutable Hugging Face revision;
no OmniDocBench corpus content belongs in the source tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from urllib.parse import quote
from uuid import uuid4

from benchmarks.corpus import download as corpus_download

DATASET_ID = "opendatalab/OmniDocBench"
REVISION = "f5f559bddf50e36f7f9899d842d0006f13ce8afc"
ANNOTATION_SHA256 = "2fafe9329dc92fc426b30036aee51c716b3fcdcc1d20cb964dc7670579533817"
EXPECTED_PAGES = 981
ANNOTATION_FILENAME = "OmniDocBench.json"
INDEX_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_FILENAME = f"_artifacts-{REVISION}.json"
_RESOLVE_BASE = f"https://huggingface.co/datasets/{DATASET_ID}/resolve/{REVISION}"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class CorpusError(RuntimeError):
    """Base error for an unusable OmniDocBench corpus cache."""


class CorpusDownloadError(CorpusError):
    """A pinned corpus artifact could not be downloaded atomically."""


class CorpusIntegrityError(CorpusError):
    """A corpus artifact did not match its required content contract."""


class CorpusCacheError(CorpusError):
    """A warm corpus cache failed revision or artifact validation."""


@dataclass(frozen=True, slots=True)
class CorpusPage:
    """One immutable page PDF in the pinned OmniDocBench snapshot.

    Attributes
    ----------
    page_id : str
        Stable page identifier derived from the annotation image basename.
    image_path : str
        Image path recorded verbatim in ``page_info.image_path``.
    pdf_path : pathlib.Path
        Local path to the downloaded single-page PDF.
    sha256 : str
        Lowercase SHA-256 digest of the cached PDF bytes.
    size_bytes : int
        Exact size of the cached PDF in bytes.

    """

    page_id: str
    image_path: str
    pdf_path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class CorpusSnapshot:
    """Validated view of a pinned OmniDocBench cache.

    Attributes
    ----------
    revision : str
        Immutable Hugging Face dataset revision used by this snapshot.
    annotation_path : pathlib.Path
        Local path to the hash-validated v1.0 annotation JSON.
    pages : tuple[CorpusPage, ...]
        Validated page PDFs selected for this invocation.
    expected_pages : int
        Required size of the complete pinned snapshot, always ``981``.
    complete : bool
        ``True`` only when the caller requested full-corpus mode.  Supplying a
        ``limit`` always produces ``False``, even when the limit is 981.

    """

    revision: str
    annotation_path: Path
    pages: tuple[CorpusPage, ...]
    expected_pages: int = EXPECTED_PAGES
    complete: bool = True


@dataclass(frozen=True, slots=True)
class _AnnotatedPage:
    page_id: str
    image_path: str
    pdf_relative_path: str


@dataclass(frozen=True, slots=True)
class _ManifestPage:
    page_id: str
    image_path: str
    pdf_relative_path: str
    sha256: str
    size_bytes: int


def load_corpus(
    cache_dir: Path,
    *,
    limit: int | None = None,
    workers: int = 8,
) -> CorpusSnapshot:
    """Load or download the pinned OmniDocBench v1.0 page corpus.

    A warm cache is accepted only after the annotation, selected page set, file
    sizes, and every PDF digest have been revalidated.  A revision-wide artifact
    manifest prevents a page cached by one mode from being re-blessed by another.
    A non-``None`` ``limit`` selects the first annotated pages deterministically
    and is always represented as an incomplete snapshot.

    Parameters
    ----------
    cache_dir : pathlib.Path
        Directory under which all downloaded annotation and PDF bytes are kept.
    limit : int or None, optional
        Positive number of pages to select for an explicitly incomplete smoke
        run.  ``None`` requires and selects all 981 pages.
    workers : int, optional
        Positive number of concurrent PDF download workers.

    Returns
    -------
    CorpusSnapshot
        Fully validated full or explicitly incomplete corpus view.

    Raises
    ------
    ValueError
        If ``limit`` or ``workers`` is outside its supported range.
    CorpusDownloadError
        If a required artifact cannot be downloaded.
    CorpusIntegrityError
        If the pinned annotation or newly downloaded PDF is invalid.
    CorpusCacheError
        If an existing revision-qualified index or cached artifact is invalid.

    """
    _validate_options(limit=limit, workers=workers)
    revision_dir = _prepare_revision_dir(Path(cache_dir))
    annotation_path = revision_dir / ANNOTATION_FILENAME
    index_path = _index_path(revision_dir, limit)
    manifest_path = _manifest_path(revision_dir)

    with _cache_lock(revision_dir):
        _ensure_annotation(annotation_path)
        annotated_pages = _read_annotation(annotation_path)
        selected = annotated_pages if limit is None else annotated_pages[:limit]
        manifest = _read_manifest(manifest_path)
        _validate_manifest_page_set(manifest, annotated_pages)

        if index_path.exists():
            rows = _validated_index_rows(index_path, selected=selected, limit=limit)
            _validate_index_manifest_agreement(rows, manifest)
            if all(page.page_id in manifest for page in selected):
                return _load_warm_cache(
                    revision_dir=revision_dir,
                    annotation_path=annotation_path,
                    rows=rows,
                    selected=selected,
                    manifest=manifest,
                    limit=limit,
                )

        pages, discovered = _materialize_pages(
            selected,
            revision_dir,
            manifest=manifest,
            workers=workers,
        )
        for page_id, entry in discovered.items():
            existing = manifest.get(page_id)
            if existing is not None and existing != entry:
                raise CorpusCacheError(f"artifact manifest digest changed for {page_id!r}")
            manifest[page_id] = entry
        if discovered or not manifest_path.exists():
            _write_manifest(manifest_path, manifest)

        snapshot = CorpusSnapshot(
            revision=REVISION,
            annotation_path=annotation_path,
            pages=pages,
            expected_pages=EXPECTED_PAGES,
            complete=limit is None,
        )
        _write_index(index_path, snapshot, revision_dir=revision_dir, limit=limit)
        return snapshot


def _validate_options(*, limit: int | None, workers: int) -> None:
    if isinstance(limit, bool) or (limit is not None and not isinstance(limit, int)):
        raise ValueError("limit must be an integer or None")
    if limit is not None and not 1 <= limit <= EXPECTED_PAGES:
        raise ValueError(f"limit must be between 1 and {EXPECTED_PAGES}")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")


def _prepare_revision_dir(cache_dir: Path) -> Path:
    if cache_dir.exists() and (cache_dir.is_symlink() or not cache_dir.is_dir()):
        raise CorpusCacheError(f"cache directory is not a real directory: {cache_dir}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    revision_dir = cache_dir / REVISION
    if revision_dir.exists() and revision_dir.is_symlink():
        raise CorpusCacheError(f"revision cache must not be a symlink: {revision_dir}")
    revision_dir.mkdir(parents=True, exist_ok=True)
    _require_contained(revision_dir, cache_dir)
    pdf_dir = revision_dir / "pdfs"
    if pdf_dir.exists() and pdf_dir.is_symlink():
        raise CorpusCacheError(f"PDF cache must not be a symlink: {pdf_dir}")
    pdf_dir.mkdir(parents=True, exist_ok=True)
    _require_contained(pdf_dir, cache_dir)
    return revision_dir


@contextmanager
def _cache_lock(revision_dir: Path) -> Iterator[None]:
    # Imported here rather than at module scope so the adapter and its tests stay importable on
    # platforms without `fcntl`. The lock guards cache integrity, so an unlockable platform is
    # refused rather than silently run without exclusion.
    if os.name != "posix":
        raise CorpusCacheError(f"corpus cache locking requires a POSIX platform, got {os.name}")
    import fcntl

    lock_path = revision_dir / f".lock-{REVISION}"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise CorpusCacheError(f"cannot open corpus cache lock: {exc}") from exc
    with os.fdopen(descriptor, "a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _require_contained(path: Path, cache_dir: Path) -> None:
    try:
        path.resolve().relative_to(cache_dir.resolve())
    except ValueError as exc:
        raise CorpusCacheError(f"cache artifact escapes supplied directory: {path}") from exc


def _index_path(revision_dir: Path, limit: int | None) -> Path:
    mode = "full" if limit is None else f"limit-{limit}"
    return revision_dir / f"_index-{REVISION}-{mode}.json"


def _manifest_path(revision_dir: Path) -> Path:
    return revision_dir / MANIFEST_FILENAME


def _ensure_annotation(annotation_path: Path) -> None:
    if annotation_path.exists():
        _require_regular_file(annotation_path, label="annotation")
        actual = _sha256(annotation_path)
        if actual != ANNOTATION_SHA256:
            raise CorpusIntegrityError(f"annotation SHA-256 mismatch: expected {ANNOTATION_SHA256}, got {actual}")
        return

    _download_artifact(_artifact_url(ANNOTATION_FILENAME), annotation_path, label="annotation")
    actual = _sha256(annotation_path)
    if actual != ANNOTATION_SHA256:
        annotation_path.unlink(missing_ok=True)
        raise CorpusIntegrityError(f"annotation SHA-256 mismatch: expected {ANNOTATION_SHA256}, got {actual}")


def _read_annotation(annotation_path: Path) -> tuple[_AnnotatedPage, ...]:
    try:
        raw = json.loads(annotation_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusIntegrityError(f"annotation is not valid JSON: {exc}") from exc

    if not isinstance(raw, list):
        raise CorpusIntegrityError("annotation root must be a JSON array")
    if len(raw) != EXPECTED_PAGES:
        raise CorpusIntegrityError(f"annotation page count mismatch: expected {EXPECTED_PAGES}, got {len(raw)}")

    pages: list[_AnnotatedPage] = []
    seen: set[str] = set()
    for position, record in enumerate(raw):
        page = _parse_annotation_record(record, position=position)
        if page.page_id in seen:
            raise CorpusIntegrityError(f"duplicate page_id {page.page_id!r} at annotation record {position}")
        seen.add(page.page_id)
        pages.append(page)
    return tuple(pages)


def _parse_annotation_record(record: Any, *, position: int) -> _AnnotatedPage:
    if not isinstance(record, dict):
        raise CorpusIntegrityError(f"annotation record {position} must be an object")
    missing_record_fields = {"layout_dets", "page_info"} - record.keys()
    if missing_record_fields:
        fields = ", ".join(sorted(missing_record_fields))
        raise CorpusIntegrityError(f"annotation record {position} is missing fields: {fields}")
    if not isinstance(record["layout_dets"], list):
        raise CorpusIntegrityError(f"annotation record {position} layout_dets must be an array")
    if "extra" in record and not isinstance(record["extra"], dict):
        raise CorpusIntegrityError(f"annotation record {position} extra must be an object")

    page_info = record["page_info"]
    if not isinstance(page_info, dict):
        raise CorpusIntegrityError(f"annotation record {position} page_info must be an object")
    required_page_fields = {"page_attribute", "page_no", "height", "width", "image_path"}
    missing_page_fields = required_page_fields - page_info.keys()
    if missing_page_fields:
        fields = ", ".join(sorted(missing_page_fields))
        raise CorpusIntegrityError(f"annotation record {position} page_info is missing fields: {fields}")
    if not isinstance(page_info["page_attribute"], dict):
        raise CorpusIntegrityError(f"annotation record {position} page_info.page_attribute must be an object")
    if isinstance(page_info["page_no"], bool) or not isinstance(page_info["page_no"], int):
        raise CorpusIntegrityError(f"annotation record {position} page_info.page_no must be an integer")
    for dimension in ("height", "width"):
        value = page_info[dimension]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise CorpusIntegrityError(f"annotation record {position} page_info.{dimension} must be positive")

    image_path = page_info["image_path"]
    if not isinstance(image_path, str) or not image_path.strip():
        raise CorpusIntegrityError(f"annotation record {position} page_info.image_path must be a non-empty string")
    normalized_image = PurePosixPath(image_path.replace("\\", "/"))
    if normalized_image.is_absolute() or ".." in normalized_image.parts:
        raise CorpusIntegrityError(f"annotation record {position} page_info.image_path must be relative")
    image_name = normalized_image.name
    page_id = PurePosixPath(image_name).stem
    if not page_id or page_id in {".", ".."}:
        raise CorpusIntegrityError(f"annotation record {position} page_info.image_path has no page identifier")
    pdf_relative_path = str(PurePosixPath("pdfs") / f"{page_id}.pdf")
    return _AnnotatedPage(
        page_id=page_id,
        image_path=image_path,
        pdf_relative_path=pdf_relative_path,
    )


def _materialize_pages(
    selected: tuple[_AnnotatedPage, ...],
    revision_dir: Path,
    *,
    manifest: dict[str, _ManifestPage],
    workers: int,
) -> tuple[tuple[CorpusPage, ...], dict[str, _ManifestPage]]:
    def materialize(
        page: _AnnotatedPage,
    ) -> tuple[CorpusPage, _ManifestPage | None]:
        pdf_path = revision_dir / page.pdf_relative_path
        _require_contained(pdf_path, revision_dir)
        trusted = manifest.get(page.page_id)
        if pdf_path.exists() and trusted is not None:
            return _cached_page_from_manifest(page, trusted, revision_dir), None
        if pdf_path.exists():
            _require_regular_file(pdf_path, label=f"PDF {page.page_id}")
            pdf_path.unlink()

        remote_path = quote(page.pdf_relative_path, safe="/")
        _download_artifact(
            _artifact_url(remote_path),
            pdf_path,
            label=f"PDF {page.page_id}",
        )
        size_bytes = pdf_path.stat().st_size
        if size_bytes <= 0 or not corpus_download._is_pdf(pdf_path):
            pdf_path.unlink(missing_ok=True)
            raise CorpusIntegrityError(f"downloaded PDF {page.page_id!r} is not a non-empty PDF")
        digest = _sha256(pdf_path)
        downloaded = _ManifestPage(
            page_id=page.page_id,
            image_path=page.image_path,
            pdf_relative_path=page.pdf_relative_path,
            sha256=digest,
            size_bytes=size_bytes,
        )
        if trusted is not None and downloaded != trusted:
            pdf_path.unlink(missing_ok=True)
            raise CorpusCacheError(f"downloaded PDF digest disagrees with artifact manifest for {page.page_id!r}")
        return (
            CorpusPage(
                page_id=page.page_id,
                image_path=page.image_path,
                pdf_path=pdf_path,
                sha256=digest,
                size_bytes=size_bytes,
            ),
            downloaded if trusted is None else None,
        )

    results: tuple[tuple[CorpusPage, _ManifestPage | None], ...]
    if len(selected) == 1:
        results = (materialize(selected[0]),)
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(selected))) as executor:
            results = tuple(executor.map(materialize, selected))
    pages = tuple(result[0] for result in results)
    discovered = {entry.page_id: entry for _, entry in results if entry is not None}
    return pages, discovered


def _cached_page_from_manifest(
    page: _AnnotatedPage,
    trusted: _ManifestPage,
    revision_dir: Path,
) -> CorpusPage:
    pdf_path = revision_dir / page.pdf_relative_path
    _require_contained(pdf_path, revision_dir)
    if not pdf_path.exists():
        raise CorpusCacheError(f"cached PDF is missing for {page.page_id!r}")
    _require_regular_file(pdf_path, label=f"PDF {page.page_id}")
    actual_size = pdf_path.stat().st_size
    if actual_size != trusted.size_bytes:
        raise CorpusCacheError(
            f"cached PDF size mismatch for {page.page_id!r}: " f"expected {trusted.size_bytes}, got {actual_size}"
        )
    if not corpus_download._is_pdf(pdf_path):
        raise CorpusCacheError(f"cached PDF is invalid for {page.page_id!r}")
    actual_digest = _sha256(pdf_path)
    if actual_digest != trusted.sha256:
        raise CorpusCacheError(
            f"cached PDF SHA-256 mismatch for {page.page_id!r}: " f"expected {trusted.sha256}, got {actual_digest}"
        )
    return CorpusPage(
        page_id=page.page_id,
        image_path=page.image_path,
        pdf_path=pdf_path,
        sha256=trusted.sha256,
        size_bytes=trusted.size_bytes,
    )


def _artifact_url(relative_path: str) -> str:
    return f"{_RESOLVE_BASE}/{relative_path}?download=true"


def _download_artifact(url: str, destination: Path, *, label: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    unique = f".{destination.name}.{os.getpid()}.{uuid4().hex}.download"
    staging_path = destination.parent / unique
    transport_part = staging_path.with_suffix(staging_path.suffix + ".part")
    try:
        # A 981-page cold run is fatal on the first throttle without a bounded retry.
        if corpus_download._try_download(url, staging_path, label=label, retries=2) is None:
            raise CorpusDownloadError(f"failed to download {label}")
        if not staging_path.is_file() or staging_path.is_symlink():
            raise CorpusDownloadError(f"failed to download {label}: no regular file was produced")
        staging_path.replace(destination)
    except CorpusDownloadError:
        raise
    except Exception as exc:
        raise CorpusDownloadError(f"failed to download {label}: {exc}") from exc
    finally:
        staging_path.unlink(missing_ok=True)
        transport_part.unlink(missing_ok=True)


def _validated_index_rows(
    index_path: Path,
    *,
    selected: tuple[_AnnotatedPage, ...],
    limit: int | None,
) -> list[dict[str, Any]]:
    _require_regular_file(index_path, label="index")
    index = _read_index(index_path)
    _validate_index_header(index, limit=limit)
    rows = index["pages"]
    if not isinstance(rows, list):
        raise CorpusCacheError("cache index pages must be an array")
    expected_identity = [(page.page_id, page.image_path, page.pdf_relative_path) for page in selected]
    indexed_identity: list[tuple[Any, Any, Any]] = []
    required_fields = {"page_id", "image_path", "pdf_path", "sha256", "size_bytes"}
    for row in rows:
        if not isinstance(row, dict):
            raise CorpusCacheError("cache index page rows must be objects")
        indexed_identity.append((row.get("page_id"), row.get("image_path"), row.get("pdf_path")))
        if set(row) != required_fields:
            raise CorpusCacheError(f"cache index row schema mismatch for {row.get('page_id')!r}")
        page_id = row["page_id"]
        digest = row["sha256"]
        size_bytes = row["size_bytes"]
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            raise CorpusCacheError(f"cache index SHA-256 is invalid for {page_id!r}")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0:
            raise CorpusCacheError(f"cache index size is invalid for {page_id!r}")
    if indexed_identity != expected_identity:
        raise CorpusCacheError("cache index page set does not match pinned annotation")
    return rows


def _validate_index_manifest_agreement(
    rows: list[dict[str, Any]],
    manifest: dict[str, _ManifestPage],
) -> None:
    for row in rows:
        page_id = row["page_id"]
        trusted = manifest.get(page_id)
        if trusted is None:
            continue
        if row["sha256"] != trusted.sha256:
            raise CorpusCacheError(f"cache index digest disagrees with artifact manifest for {page_id!r}")
        if row["size_bytes"] != trusted.size_bytes:
            raise CorpusCacheError(f"cache index size disagrees with artifact manifest for {page_id!r}")


def _load_warm_cache(
    *,
    revision_dir: Path,
    annotation_path: Path,
    rows: list[dict[str, Any]],
    selected: tuple[_AnnotatedPage, ...],
    manifest: dict[str, _ManifestPage],
    limit: int | None,
) -> CorpusSnapshot:
    pages: list[CorpusPage] = []
    for _row, page in zip(rows, selected, strict=True):
        trusted = manifest.get(page.page_id)
        if trusted is None:
            raise CorpusCacheError(f"artifact manifest has no digest for {page.page_id!r}")
        pages.append(_cached_page_from_manifest(page, trusted, revision_dir))

    return CorpusSnapshot(
        revision=REVISION,
        annotation_path=annotation_path,
        pages=tuple(pages),
        expected_pages=EXPECTED_PAGES,
        complete=limit is None,
    )


def _read_manifest(manifest_path: Path) -> dict[str, _ManifestPage]:
    if not manifest_path.exists():
        return {}
    _require_regular_file(manifest_path, label="artifact manifest")
    try:
        payload = json.loads(manifest_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusCacheError(f"artifact manifest is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CorpusCacheError("artifact manifest root must be an object")
    required_fields = {
        "schema_version",
        "dataset",
        "revision",
        "annotation_sha256",
        "expected_pages",
        "pages",
    }
    if set(payload) != required_fields:
        raise CorpusCacheError("artifact manifest schema does not match this adapter")
    if payload["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise CorpusCacheError(
            "artifact manifest schema version mismatch: "
            f"expected {MANIFEST_SCHEMA_VERSION}, got {payload['schema_version']!r}"
        )
    if payload["dataset"] != DATASET_ID:
        raise CorpusCacheError("artifact manifest dataset mismatch")
    if payload["revision"] != REVISION:
        raise CorpusCacheError(
            f"artifact manifest revision mismatch: expected {REVISION}, " f"got {payload['revision']!r}"
        )
    if payload["annotation_sha256"] != ANNOTATION_SHA256:
        raise CorpusCacheError("artifact manifest annotation SHA-256 mismatch")
    if payload["expected_pages"] != EXPECTED_PAGES:
        raise CorpusCacheError("artifact manifest expected page count mismatch")
    raw_pages = payload["pages"]
    if not isinstance(raw_pages, dict):
        raise CorpusCacheError("artifact manifest pages must be an object")

    manifest: dict[str, _ManifestPage] = {}
    required_page_fields = {"image_path", "pdf_path", "sha256", "size_bytes"}
    for page_id, row in raw_pages.items():
        if not isinstance(page_id, str) or not isinstance(row, dict):
            raise CorpusCacheError("artifact manifest page entries must be objects")
        if set(row) != required_page_fields:
            raise CorpusCacheError(f"artifact manifest row schema mismatch for {page_id!r}")
        digest = row["sha256"]
        size_bytes = row["size_bytes"]
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            raise CorpusCacheError(f"artifact manifest SHA-256 is invalid for {page_id!r}")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0:
            raise CorpusCacheError(f"artifact manifest size is invalid for {page_id!r}")
        if not isinstance(row["image_path"], str) or not isinstance(row["pdf_path"], str):
            raise CorpusCacheError(f"artifact manifest paths are invalid for {page_id!r}")
        manifest[page_id] = _ManifestPage(
            page_id=page_id,
            image_path=row["image_path"],
            pdf_relative_path=row["pdf_path"],
            sha256=digest,
            size_bytes=size_bytes,
        )
    return manifest


def _validate_manifest_page_set(
    manifest: dict[str, _ManifestPage],
    annotated_pages: tuple[_AnnotatedPage, ...],
) -> None:
    annotation_by_id = {page.page_id: page for page in annotated_pages}
    for page_id, entry in manifest.items():
        annotated = annotation_by_id.get(page_id)
        if annotated is None:
            raise CorpusCacheError(f"artifact manifest contains unknown page {page_id!r}")
        if entry.image_path != annotated.image_path or entry.pdf_relative_path != annotated.pdf_relative_path:
            raise CorpusCacheError(f"artifact manifest identity disagrees with annotation for {page_id!r}")


def _write_manifest(
    manifest_path: Path,
    manifest: dict[str, _ManifestPage],
) -> None:
    pages = {
        page_id: {
            "image_path": entry.image_path,
            "pdf_path": entry.pdf_relative_path,
            "sha256": entry.sha256,
            "size_bytes": entry.size_bytes,
        }
        for page_id, entry in manifest.items()
    }
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "revision": REVISION,
        "annotation_sha256": ANNOTATION_SHA256,
        "expected_pages": EXPECTED_PAGES,
        "pages": pages,
    }
    _atomic_write_json(manifest_path, payload)


def _read_index(index_path: Path) -> dict[str, Any]:
    try:
        index = json.loads(index_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusCacheError(f"cache index is not valid JSON: {exc}") from exc
    if not isinstance(index, dict):
        raise CorpusCacheError("cache index root must be an object")
    return index


def _validate_index_header(index: dict[str, Any], *, limit: int | None) -> None:
    required_fields = {
        "schema_version",
        "dataset",
        "revision",
        "annotation_path",
        "annotation_sha256",
        "expected_pages",
        "requested_limit",
        "complete",
        "pages",
    }
    if set(index) != required_fields:
        raise CorpusCacheError("cache index schema does not match this adapter")
    if index["schema_version"] != INDEX_SCHEMA_VERSION:
        raise CorpusCacheError(
            f"cache index schema version mismatch: expected {INDEX_SCHEMA_VERSION}, " f"got {index['schema_version']!r}"
        )
    if index["dataset"] != DATASET_ID:
        raise CorpusCacheError(f"cache index dataset mismatch: expected {DATASET_ID!r}, got {index['dataset']!r}")
    if index["revision"] != REVISION:
        raise CorpusCacheError(f"cache index revision mismatch: expected {REVISION}, got {index['revision']!r}")
    if index["annotation_path"] != ANNOTATION_FILENAME:
        raise CorpusCacheError("cache index annotation path mismatch")
    if index["annotation_sha256"] != ANNOTATION_SHA256:
        raise CorpusCacheError("cache index annotation SHA-256 mismatch")
    if index["expected_pages"] != EXPECTED_PAGES:
        raise CorpusCacheError("cache index expected page count mismatch")
    if index["requested_limit"] != limit:
        raise CorpusCacheError("cache index requested limit mismatch")
    if index["complete"] is not (limit is None):
        raise CorpusCacheError("cache index completeness marker mismatch")


def _write_index(
    index_path: Path,
    snapshot: CorpusSnapshot,
    *,
    revision_dir: Path,
    limit: int | None,
) -> None:
    rows = []
    for page in snapshot.pages:
        row = asdict(page)
        row["pdf_path"] = page.pdf_path.relative_to(revision_dir).as_posix()
        rows.append(row)
    payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "revision": REVISION,
        "annotation_path": ANNOTATION_FILENAME,
        "annotation_sha256": ANNOTATION_SHA256,
        "expected_pages": EXPECTED_PAGES,
        "requested_limit": limit,
        "complete": snapshot.complete,
        "pages": rows,
    }
    _atomic_write_json(index_path, payload)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    unique = f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp"
    staging_path = path.parent / unique
    try:
        with staging_path.open("w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        staging_path.replace(path)
    finally:
        staging_path.unlink(missing_ok=True)


def _require_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise CorpusCacheError(f"cached {label} is not a regular file: {path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
