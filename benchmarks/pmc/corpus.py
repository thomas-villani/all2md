"""Pinned PMC Open Access born-digital corpus: manifest build and cache load.

The PMC ``pmc-oa-opendata`` bucket has **no corpus-wide revision** the way a Hugging
Face dataset does -- article versions bump independently and decade-old articles carry
recent reprocessing timestamps.  A committed manifest of per-object SHA-256 digests
plays the role ``dataset_revision`` plays for the OmniDocBench lane, and it is the whole
reason this corpus cannot drift the way ``benchmarks/corpus`` does.

Two entry points, deliberately separated:

``build_manifest``
    Walks the bucket, applies the born-digital selection filter, and writes the manifest.
    Network-heavy, non-deterministic (the bucket gains articles), and run by hand.

``load_corpus``
    Reads the committed manifest and materializes exactly the articles it names.  Never
    lists the bucket, so what it produces is fixed by the manifest bytes alone.

Unlike the OmniDocBench adapter this needs no separate cache index: the committed
manifest *is* the trusted digest record, so every load revalidates every selected file
against it directly.

This module is deliberately agnostic about whether the eventual lane scores per-page or
per-article -- it exposes whole articles and no page structure.  It also records no PDF
page traits: the born-digital characterization is a separate step that must measure the
built corpus independently, not read back the filter's own premise.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence
from urllib.parse import quote
from uuid import uuid4

# The JATS and S3 listing payloads both come from third-party endpoints, so
# parsing goes through defusedxml: stdlib's parser expands external entities and
# nested entity definitions, which turns a hostile payload into local file
# disclosure or memory exhaustion. `Element` is imported from the stdlib because
# defusedxml does not re-export it -- it is the node type, not a parser, and
# nothing here constructs one, it is only used in annotations.
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from defusedxml.common import EntitiesForbidden

BUCKET = "pmc-oa-opendata"
BUCKET_BASE = f"https://{BUCKET}.s3.amazonaws.com"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_FILENAME = "manifest.json"
DEFAULT_MANIFEST = Path(__file__).with_name(MANIFEST_FILENAME)
USER_AGENT = "all2md-benchmark-corpus"
DEFAULT_TIMEOUT = 120

_S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_ALI_LICENSE_REF = "{http://www.niso.org/schemas/ali/1.0/}license_ref"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_ARTICLE_ID_RE = re.compile(r"PMC(?P<pmcid>[0-9]+)\.(?P<version>[0-9]+)\Z")

#: The anchor spacing behind the default seeds; see `seed_anchors`.
_SEED_ANCHOR_RANGE = range(1_500_000, 12_500_000, 500_000)


def seed_anchors(offset: int = 0) -> tuple[str, ...]:
    """Return ``start-after`` seeds spread across the PMCID range.

    ``offset`` shifts every anchor by the same amount, which is how a
    **held-out** corpus is drawn: a walk from offset anchors lists bucket
    regions the committed manifest's walk never reached (each build consumes
    only a few hundred prefixes past its anchor), so the two corpora cannot
    share articles or even neighbourhoods.  Verify the non-overlap against the
    committed manifest after a build anyway; the offset makes it expected, the
    check makes it evidence.
    """
    return tuple(f"PMC{value + offset}" for value in _SEED_ANCHOR_RANGE)


#: Numeric anchors spread across the PMCID range.  Selection **never** starts at the front
#: of the bucket: the numerically-first PMCIDs are one 19th-century journal's scanned back
#: catalogue, and a sample drawn there is 100% scans while still showing a text layer on
#: every page.  Listing order is lexicographic, so these are seeds for ``start-after`` and
#: not an ordering.  Many seeds taking few articles each beats few seeds taking many: the
#: spread across publishers and eras is the point, and a large ``per_seed`` just walks
#: further into one region.
DEFAULT_SEEDS: tuple[str, ...] = seed_anchors()

#: Candidates are taken every ``DEFAULT_STRIDE``-th prefix rather than consecutively.
#: Adjacent PMCIDs are typically the same journal issue, so a consecutive run would draw
#: one publisher's template repeatedly and call it a corpus.
DEFAULT_STRIDE = 11

#: Transient failures get a patient, exponentially backed-off retry rather than a fast
#: one: a walk of several hundred candidates will meet a DNS blip, and a blip must not be
#: allowed to look like a corpus property.
_RETRIES = 5
_RETRY_CEILING_SECONDS = 8.0

#: A build that loses this share of its candidates to network failure is not measuring the
#: bucket, it is measuring the link.  Past experience on the sibling lane: a DNS blip once
#: shrank a 100-document gate to 50 and every other signal stayed green.
_MAX_UNAVAILABLE_SHARE = 0.1

#: Reasons a candidate can be dropped.  Every rejection is recorded in the manifest by
#: article id -- a silent filter here is the same defect as a silent truncation.
#:
#: Network failures are deliberately **not** in this list.  A rejection is a statement
#: about the article; an unreachable host is a statement about the run, and conflating the
#: two would bake a transient outage into a committed manifest as though it were evidence.
REJECTION_REASONS = (
    "xml_missing",
    "xml_unparsable",
    "no_paragraphs",
    "pdf_missing",
    "pdf_unreadable",
    "no_vector_drawings",
)


class CorpusError(RuntimeError):
    """Base error for an unusable PMC corpus."""


class CorpusDownloadError(CorpusError):
    """A required artifact could not be downloaded."""


class ArtifactMissingError(CorpusDownloadError):
    """The remote object does not exist (HTTP 404)."""


class CorpusIntegrityError(CorpusError):
    """A downloaded artifact did not match its manifest contract."""


class CorpusCacheError(CorpusError):
    """A warm cache or the manifest itself failed validation."""


class CorpusSelectionError(CorpusError):
    """The bucket walk could not produce the requested corpus."""


@dataclass(frozen=True, slots=True)
class CorpusArticle:
    """One pinned PMC Open Access article.

    Attributes
    ----------
    article_id : str
        Versioned bucket prefix, for example ``"PMC11000001.1"``.
    pmcid : str
        Unversioned PMC identifier, for example ``"PMC11000001"``.
    version : int
        Article version carried by the bucket prefix.
    pdf_path : pathlib.Path
        Local path to the validated publisher PDF.
    xml_path : pathlib.Path
        Local path to the validated JATS XML.
    pdf_sha256, xml_sha256 : str
        Lowercase SHA-256 digests, equal to the manifest by construction.
    pdf_size_bytes, xml_size_bytes : int
        Exact cached sizes in bytes.
    licence : str
        Licence recorded by the JATS ``ali:license_ref``/``license`` element.
    paragraphs : int
        Number of JATS ``<p>`` elements, the born-digital body test.

    """

    article_id: str
    pmcid: str
    version: int
    pdf_path: Path
    xml_path: Path
    pdf_sha256: str
    pdf_size_bytes: int
    xml_sha256: str
    xml_size_bytes: int
    licence: str
    paragraphs: int


@dataclass(frozen=True, slots=True)
class CorpusSnapshot:
    """Validated view of a pinned PMC cache.

    Attributes
    ----------
    manifest_path : pathlib.Path
        Manifest the snapshot was materialized from.
    manifest_sha256 : str
        Digest of the manifest bytes; this is the corpus pin.
    bucket : str
        Source bucket recorded in the manifest.
    articles : tuple[CorpusArticle, ...]
        Validated articles selected for this invocation.
    expected_articles : int
        Article count of the complete pinned corpus.
    unavailable : dict[str, str]
        Article id to error text, for pinned articles the bucket no longer serves.
        Empty on a healthy run.  A first-class field rather than a log line because a
        score computed over 65 of 66 articles is a different measurement from one
        computed over 66, and nothing downstream can tell unless it is told.
    complete : bool
        ``True`` only when the caller requested the whole manifest *and* every pinned
        article was materialized.  Supplying a ``limit`` always produces ``False``,
        even when it equals the manifest size.

    """

    manifest_path: Path
    manifest_sha256: str
    bucket: str
    articles: tuple[CorpusArticle, ...]
    expected_articles: int
    unavailable: dict[str, str]
    complete: bool


@dataclass(frozen=True, slots=True)
class ManifestArticle:
    """One article's pinned identity, exactly as committed."""

    article_id: str
    pdf_sha256: str
    pdf_size_bytes: int
    xml_sha256: str
    xml_size_bytes: int
    licence: str
    paragraphs: int


@dataclass(frozen=True, slots=True)
class Manifest:
    """Parsed and validated manifest contents."""

    path: Path
    sha256: str
    bucket: str
    articles: tuple[ManifestArticle, ...]
    rejected: dict[str, str]
    selection: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BuildReport:
    """Outcome of a bucket walk.

    Attributes
    ----------
    manifest_path : pathlib.Path
        Manifest that was written.
    accepted : tuple[str, ...]
        Article ids kept, in manifest order.
    rejected : dict[str, str]
        Article id to rejection reason, for every candidate that was dropped.
    rejection_counts : dict[str, int]
        Rejection reason to count, covering every reason in `REJECTION_REASONS`.
    unavailable : dict[str, str]
        Article id to error text, for candidates lost to network failure rather than to
        the selection filter.  Kept apart from `rejected` on purpose.
    candidates : int
        Total candidate prefixes examined.

    """

    manifest_path: Path
    accepted: tuple[str, ...]
    rejected: dict[str, str]
    rejection_counts: dict[str, int]
    unavailable: dict[str, str]
    candidates: int


def load_corpus(
    cache_dir: Path,
    *,
    manifest_path: Path | None = None,
    limit: int | None = None,
    workers: int = 8,
) -> CorpusSnapshot:
    """Materialize the pinned PMC corpus named by a committed manifest.

    Every selected PDF and JATS file is revalidated against the manifest digest on each
    call, whether it was just downloaded or found warm in the cache.

    The manifest pins what the bytes *are*, which is not the same as pinning that they
    are still served.  PMC reprocesses articles and withdraws the superseded version, so
    a pinned object can start returning 404 without a single retained byte changing.
    Those articles land in ``CorpusSnapshot.unavailable`` and the snapshot is no longer
    ``complete``; only a large enough share of them aborts the load.

    Parameters
    ----------
    cache_dir : pathlib.Path
        Directory under which downloaded article bytes are kept.
    manifest_path : pathlib.Path or None, optional
        Manifest to pin against.  Defaults to the committed
        ``benchmarks/pmc/manifest.json``.
    limit : int or None, optional
        Positive number of articles for an explicitly incomplete smoke run.  Selection
        is **evenly spaced across the manifest**, never the first ``limit`` entries --
        manifest order is lexicographic by PMCID, so a prefix would draw one era of the
        archive and quietly stop being a spread sample.
    workers : int, optional
        Positive number of concurrent download workers.

    Returns
    -------
    CorpusSnapshot
        Fully validated full or explicitly incomplete corpus view.

    Raises
    ------
    ValueError
        If ``limit`` or ``workers`` is outside its supported range.
    CorpusCacheError
        If the manifest is unreadable or a cached artifact fails validation.
    CorpusDownloadError
        If a manifest artifact cannot be downloaded, or if so many pinned articles have
        been withdrawn that what remains is no longer the pinned corpus.
    CorpusIntegrityError
        If a freshly downloaded artifact does not match the manifest.

    """
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")
    manifest = read_manifest(DEFAULT_MANIFEST if manifest_path is None else Path(manifest_path))
    selected = _select(manifest.articles, limit)

    corpus_dir = _prepare_cache_dir(Path(cache_dir), manifest.sha256)
    with _cache_lock(corpus_dir, manifest.sha256):
        articles, unavailable = _materialize(selected, corpus_dir, workers=workers)
    return CorpusSnapshot(
        manifest_path=manifest.path,
        manifest_sha256=manifest.sha256,
        bucket=manifest.bucket,
        articles=articles,
        expected_articles=len(manifest.articles),
        unavailable=unavailable,
        complete=limit is None and not unavailable,
    )


def _select(articles: tuple[ManifestArticle, ...], limit: int | None) -> tuple[ManifestArticle, ...]:
    if limit is None:
        return articles
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer or None")
    if not 1 <= limit <= len(articles):
        raise ValueError(f"limit must be between 1 and {len(articles)}")
    step = len(articles) / limit
    return tuple(articles[int(index * step)] for index in range(limit))


def read_manifest(manifest_path: Path) -> Manifest:
    """Parse and fully validate a committed corpus manifest.

    Parameters
    ----------
    manifest_path : pathlib.Path
        Manifest file to read.

    Returns
    -------
    Manifest
        Validated manifest, including the digest of its own bytes.

    Raises
    ------
    CorpusCacheError
        If the manifest is missing, unreadable, or violates its schema.

    """
    manifest_path = Path(manifest_path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise CorpusCacheError(f"corpus manifest is not a regular file: {manifest_path}")
    raw = manifest_path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusCacheError(f"corpus manifest is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CorpusCacheError("corpus manifest root must be an object")

    required = {"schema_version", "bucket", "selection", "articles", "rejected", "rejection_counts"}
    if set(payload) != required:
        raise CorpusCacheError("corpus manifest schema does not match this adapter")
    if payload["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise CorpusCacheError(
            f"corpus manifest schema version mismatch: expected {MANIFEST_SCHEMA_VERSION}, "
            f"got {payload['schema_version']!r}"
        )
    if payload["bucket"] != BUCKET:
        raise CorpusCacheError(f"corpus manifest bucket mismatch: expected {BUCKET!r}, got {payload['bucket']!r}")
    for key in ("selection", "articles", "rejected", "rejection_counts"):
        if not isinstance(payload[key], dict):
            raise CorpusCacheError(f"corpus manifest {key} must be an object")
    if not payload["articles"]:
        raise CorpusCacheError("corpus manifest names no articles")

    articles: list[ManifestArticle] = []
    article_fields = {"pdf_sha256", "pdf_size_bytes", "xml_sha256", "xml_size_bytes", "licence", "paragraphs"}
    for article_id, row in payload["articles"].items():
        _parse_article_id(article_id, source="corpus manifest")
        if not isinstance(row, dict) or set(row) != article_fields:
            raise CorpusCacheError(f"corpus manifest row schema mismatch for {article_id!r}")
        for field in ("pdf_sha256", "xml_sha256"):
            if not isinstance(row[field], str) or _SHA256_RE.fullmatch(row[field]) is None:
                raise CorpusCacheError(f"corpus manifest {field} is invalid for {article_id!r}")
        for field in ("pdf_size_bytes", "xml_size_bytes", "paragraphs"):
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise CorpusCacheError(f"corpus manifest {field} is invalid for {article_id!r}")
        if not isinstance(row["licence"], str) or not row["licence"].strip():
            raise CorpusCacheError(f"corpus manifest licence is invalid for {article_id!r}")
        articles.append(
            ManifestArticle(
                article_id=article_id,
                pdf_sha256=row["pdf_sha256"],
                pdf_size_bytes=row["pdf_size_bytes"],
                xml_sha256=row["xml_sha256"],
                xml_size_bytes=row["xml_size_bytes"],
                licence=row["licence"],
                paragraphs=row["paragraphs"],
            )
        )

    rejected = payload["rejected"]
    for article_id, reason in rejected.items():
        _parse_article_id(article_id, source="corpus manifest rejection")
        if reason not in REJECTION_REASONS:
            raise CorpusCacheError(f"corpus manifest records unknown rejection reason {reason!r}")
        if article_id in payload["articles"]:
            raise CorpusCacheError(f"corpus manifest both accepts and rejects {article_id!r}")

    return Manifest(
        path=manifest_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        bucket=payload["bucket"],
        articles=tuple(sorted(articles, key=lambda entry: entry.article_id)),
        rejected=dict(rejected),
        selection=dict(payload["selection"]),
    )


def _parse_article_id(article_id: Any, *, source: str) -> tuple[str, int]:
    if not isinstance(article_id, str):
        raise CorpusCacheError(f"{source} article id must be a string")
    match = _ARTICLE_ID_RE.fullmatch(article_id)
    if match is None:
        raise CorpusCacheError(f"{source} article id is malformed: {article_id!r}")
    return f"PMC{match['pmcid']}", int(match["version"])


def _prepare_cache_dir(cache_dir: Path, manifest_sha256: str) -> Path:
    if cache_dir.exists() and (cache_dir.is_symlink() or not cache_dir.is_dir()):
        raise CorpusCacheError(f"cache directory is not a real directory: {cache_dir}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Keyed by the manifest digest, which is this corpus's pin: a manifest edit yields a
    # new directory rather than re-blessing files selected under different rules.
    corpus_dir = cache_dir / manifest_sha256[:16]
    if corpus_dir.exists() and corpus_dir.is_symlink():
        raise CorpusCacheError(f"corpus cache must not be a symlink: {corpus_dir}")
    corpus_dir.mkdir(parents=True, exist_ok=True)
    _require_contained(corpus_dir, cache_dir)
    return corpus_dir


def _require_contained(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusCacheError(f"cache artifact escapes supplied directory: {path}") from exc


# An OS-level file lock rather than a lock directory, on both platforms: a cold
# materialization runs inside it, so a crashed holder must not leave the cache
# permanently unopenable.  The branch is on `sys.platform` so a type checker analyses
# only the branch that exists on the host.
if sys.platform == "win32":
    import msvcrt

    _LOCK_CONTENTION_ERRNOS = frozenset({errno.EACCES, errno.EDEADLOCK, errno.EDEADLK})

    def _acquire_lock(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                if exc.errno not in _LOCK_CONTENTION_ERRNOS:
                    raise CorpusCacheError(f"cannot lock corpus cache: {exc}") from exc
                time.sleep(0.05)

    def _release_lock(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _acquire_lock(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_EX)

    def _release_lock(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


@contextmanager
def _cache_lock(corpus_dir: Path, manifest_sha256: str) -> Iterator[None]:
    lock_path = corpus_dir / f".lock-{manifest_sha256[:16]}"
    flags = os.O_RDWR | os.O_CREAT
    for name in ("O_NOFOLLOW", "O_BINARY", "O_NOINHERIT"):
        flags |= getattr(os, name, 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise CorpusCacheError(f"cannot open corpus cache lock: {exc}") from exc
    try:
        _acquire_lock(descriptor)
        try:
            yield
        finally:
            _release_lock(descriptor)
    finally:
        os.close(descriptor)


def _materialize(
    selected: tuple[ManifestArticle, ...],
    corpus_dir: Path,
    *,
    workers: int,
) -> tuple[tuple[CorpusArticle, ...], dict[str, str]]:
    """Materialize every selected article, tolerating ones the bucket has withdrawn.

    A 404 is the one download failure a retry cannot fix, and the only one that says
    nothing about the bytes: everything still served matches the manifest exactly.
    Every other failure -- a transient network error, a digest mismatch, an unreadable
    warm file -- still raises, because those are claims about the artifact rather than
    about its existence.
    """

    def materialize(entry: ManifestArticle) -> CorpusArticle | str:
        pmcid, version = _parse_article_id(entry.article_id, source="corpus manifest")
        article_dir = corpus_dir / "articles" / entry.article_id
        _require_contained(article_dir, corpus_dir)
        article_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = article_dir / f"{entry.article_id}.pdf"
        xml_path = article_dir / f"{entry.article_id}.xml"
        try:
            _ensure_artifact(
                pdf_path,
                url=_object_url(entry.article_id, "pdf"),
                sha256=entry.pdf_sha256,
                size_bytes=entry.pdf_size_bytes,
                label=f"PDF {entry.article_id}",
            )
            _ensure_artifact(
                xml_path,
                url=_object_url(entry.article_id, "xml"),
                sha256=entry.xml_sha256,
                size_bytes=entry.xml_size_bytes,
                label=f"JATS {entry.article_id}",
            )
        except ArtifactMissingError as exc:
            return str(exc)
        return CorpusArticle(
            article_id=entry.article_id,
            pmcid=pmcid,
            version=version,
            pdf_path=pdf_path,
            xml_path=xml_path,
            pdf_sha256=entry.pdf_sha256,
            pdf_size_bytes=entry.pdf_size_bytes,
            xml_sha256=entry.xml_sha256,
            xml_size_bytes=entry.xml_size_bytes,
            licence=entry.licence,
            paragraphs=entry.paragraphs,
        )

    if len(selected) == 1:
        outcomes: list[CorpusArticle | str] = [materialize(selected[0])]
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(selected))) as executor:
            outcomes = list(executor.map(materialize, selected))

    articles = tuple(outcome for outcome in outcomes if isinstance(outcome, CorpusArticle))
    unavailable = {
        entry.article_id: outcome for entry, outcome in zip(selected, outcomes, strict=True) if isinstance(outcome, str)
    }
    # A tolerance, not a licence to erode: past this point the surviving articles are a
    # different corpus than the one the pin names, and reporting them under that pin
    # would be the quiet truncation the manifest exists to prevent.  The empty case is
    # spelled out because the share test alone would wave through losing the only
    # article of a one-article selection.
    if not articles or len(unavailable) > max(1, int(_MAX_UNAVAILABLE_SHARE * len(selected))):
        raise CorpusDownloadError(
            f"corpus pin is no longer served: {len(unavailable)} of {len(selected)} pinned "
            f"articles have been withdrawn ({', '.join(sorted(unavailable))}); rebuild the manifest"
        )
    return articles, unavailable


def _ensure_artifact(
    path: Path,
    *,
    url: str,
    sha256: str,
    size_bytes: int,
    label: str,
) -> None:
    """Guarantee ``path`` holds exactly the manifest's bytes, downloading if needed."""
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise CorpusCacheError(f"cached {label} is not a regular file: {path}")
        if path.stat().st_size == size_bytes and _sha256(path) == sha256:
            return
        # A warm file that disagrees with the manifest is replaced, not trusted and not
        # fatal: partial writes happen, and the digest check below still gates the result.
        path.unlink()

    _download(url, path, label=label)
    actual_size = path.stat().st_size
    actual_digest = _sha256(path)
    if actual_size != size_bytes or actual_digest != sha256:
        path.unlink(missing_ok=True)
        raise CorpusIntegrityError(
            f"{label} does not match the manifest: expected {sha256} ({size_bytes} bytes), "
            f"got {actual_digest} ({actual_size} bytes)"
        )


def _object_url(article_id: str, suffix: str) -> str:
    name = quote(f"{article_id}/{article_id}.{suffix}", safe="/")
    return f"{BUCKET_BASE}/{name}"


def _open_url(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310 - fixed https bucket


def _http_get(url: str, *, label: str, retries: int = _RETRIES, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """Fetch ``url`` into memory, distinguishing a genuine 404 from a transient failure."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with _open_url(url, timeout=timeout) as response:
                return bytes(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ArtifactMissingError(f"{label} does not exist: {url}") from exc
            last = exc
        except OSError as exc:
            last = exc
        time.sleep(min(_RETRY_CEILING_SECONDS, 2.0**attempt))
    raise CorpusDownloadError(f"failed to download {label}: {last}")


def _download(url: str, destination: Path, *, label: str, retries: int = _RETRIES) -> None:
    """Stream ``url`` to ``destination`` atomically."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_path = destination.parent / f".{destination.name}.{os.getpid()}.{uuid4().hex}.download"
    last: Exception | None = None
    try:
        for attempt in range(retries):
            try:
                with _open_url(url) as response, staging_path.open("wb") as output:
                    for chunk in iter(lambda: response.read(1 << 16), b""):
                        output.write(chunk)
                staging_path.replace(destination)
                return
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise ArtifactMissingError(f"{label} does not exist: {url}") from exc
                last = exc
            except OSError as exc:
                last = exc
            time.sleep(0.5 * (attempt + 1))
        raise CorpusDownloadError(f"failed to download {label}: {last}")
    finally:
        staging_path.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = path.parent / f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp"
    try:
        # Explicit LF, not the platform default: the manifest's own digest is this
        # corpus's pin, and .gitattributes checks the file out as LF everywhere. Writing
        # CRLF on Windows would make the builder compute a pin no other machine can
        # reproduce from the same committed bytes.
        with staging_path.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        staging_path.replace(path)
    finally:
        staging_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Manifest construction
# ---------------------------------------------------------------------------


#: The five entities XML defines itself.  Everything else in a JATS file is declared by a
#: DTD the bucket does not ship alongside the article.
_XML_BUILTIN_ENTITIES = frozenset({"amp", "lt", "gt", "apos", "quot"})
_NAMED_ENTITY_RE = re.compile(rb"&([A-Za-z][A-Za-z0-9._-]*);")


def _neutralize_entities(payload: bytes) -> bytes:
    """Replace externally-declared named entities with the Unicode replacement character.

    JATS routinely references entities (``&mu;``, ``&emsp;``) declared in DTDs the bucket
    does not ship.  Dropping those articles would bias the corpus toward whichever
    publishers happen to avoid them.  Numeric references are left alone, and nothing is
    ever resolved *externally* -- there is no fetch and no local file read, only a
    substitution on bytes already in hand.
    """
    return _NAMED_ENTITY_RE.sub(
        lambda match: match.group(0) if match.group(1).decode("ascii") in _XML_BUILTIN_ENTITIES else b"&#xFFFD;",
        payload,
    )


def _parse_jats(payload: bytes) -> tuple[Element, bool]:
    """Parse JATS bytes, reporting whether entity neutralization was needed.

    Strict parsing is tried first so a well-formed article is never rewritten, and the
    fallback is counted rather than applied invisibly.

    The two shapes this fallback exists for -- a reference to an entity declared in a DTD
    the bucket does not ship, and one declared nowhere at all -- raise ``ParseError`` under
    defusedxml exactly as they did under stdlib, so the swap does not change them.

    An article that *declares* entities in an internal subset is deliberately **not**
    neutralized.  Stdlib accepted those; defusedxml raises ``EntitiesForbidden``, and that
    is the whole point of the swap, since a nested declaration is the entity-expansion
    vector.  Neutralization could not rescue one anyway -- it rewrites references and
    leaves the declaration in place, so the parse fails again.  The caller records such an
    article as ``xml_unparsable``, which is a recorded rejection rather than a silent loss.
    No article in the pinned corpus takes either path today.
    """
    try:
        return ElementTree.fromstring(payload), False
    except ElementTree.ParseError:
        return ElementTree.fromstring(_neutralize_entities(payload)), True


def _count_local(root: Element, tag: str) -> int:
    return sum(1 for element in root.iter() if _local_name(element.tag) == tag)


def _local_name(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _extract_licence(root: Element) -> str:
    """Read the article licence out of the JATS itself, in decreasing order of precision."""
    for reference in root.iter(_ALI_LICENSE_REF):
        if reference.text and reference.text.strip():
            return reference.text.strip()
    for element in root.iter():
        if _local_name(element.tag) != "license":
            continue
        for key, value in element.attrib.items():
            if _local_name(key) == "href" and value.strip():
                return value.strip()
        license_type = element.attrib.get("license-type")
        if isinstance(license_type, str) and license_type.strip():
            return license_type.strip()
    return "unrecorded"


def _has_vector_drawings(pdf_path: Path) -> bool | None:
    """Report whether any page carries vector drawings, or ``None`` if unreadable.

    Read with PyMuPDF directly rather than through all2md, for the same reason the
    OmniDocBench characterization is: a parser change must never alter what the corpus
    is reported to contain.

    **This is a backstop, not the born-digital discriminator** -- measured, against the
    plan's expectation.  The bucket holds two kinds of non-born-digital material and this
    test handles neither well: against a raster scan it is redundant with the
    page-area image test, and against an OCR text dump re-typeset into a PDF it is
    actively fooled, because such a file's one "drawing" per page is a page-sized
    background rectangle.  Geometrically those files *are* born-digital; only the JATS
    ``<p>`` test reveals them, and it runs first.  See ``README.md``.
    """
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - build-time dependency
        raise CorpusSelectionError("PyMuPDF is required to build the PMC corpus manifest") from exc
    try:
        with fitz.open(pdf_path) as document:
            return any(bool(page.get_drawings()) for page in document)
    except Exception:  # noqa: BLE001 - an unreadable PDF is a rejection, not a crash
        return None


def list_article_prefixes(start_after: str, *, max_keys: int = 200) -> tuple[tuple[str, ...], str | None]:
    """List one page of versioned article prefixes at or after ``start_after``.

    Parameters
    ----------
    start_after : str
        Key to resume after.  Listing order is lexicographic, so this is a seed rather
        than a numeric position.
    max_keys : int, optional
        Maximum prefixes to request in one page.

    Returns
    -------
    tuple[tuple[str, ...], str | None]
        Article ids in listing order, and the continuation token if more remain.

    """
    url = f"{BUCKET_BASE}/?list-type=2&delimiter=%2F&start-after={quote(start_after, safe='')}&max-keys={int(max_keys)}"
    return _parse_listing(_http_get(url, label=f"listing after {start_after}"))


def _list_continuation(token: str, *, max_keys: int = 200) -> tuple[tuple[str, ...], str | None]:
    url = (
        f"{BUCKET_BASE}/?list-type=2&delimiter=%2F&continuation-token={quote(token, safe='')}&max-keys={int(max_keys)}"
    )
    return _parse_listing(_http_get(url, label="listing continuation"))


def _parse_listing(payload: bytes) -> tuple[tuple[str, ...], str | None]:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise CorpusSelectionError(f"bucket listing is not valid XML: {exc}") from exc
    prefixes: list[str] = []
    for element in root.findall(f"{_S3_NS}CommonPrefixes"):
        prefix = element.findtext(f"{_S3_NS}Prefix") or ""
        article_id = prefix.rstrip("/")
        if _ARTICLE_ID_RE.fullmatch(article_id):
            prefixes.append(article_id)
    truncated = (root.findtext(f"{_S3_NS}IsTruncated") or "").strip().lower() == "true"
    token = root.findtext(f"{_S3_NS}NextContinuationToken") if truncated else None
    return tuple(prefixes), token


def build_manifest(
    destination: Path,
    *,
    workspace: Path,
    seeds: Sequence[str] = DEFAULT_SEEDS,
    per_seed: int = 3,
    stride: int = DEFAULT_STRIDE,
    max_candidates_per_seed: int = 60,
    progress: Callable[[str], None] | None = None,
) -> BuildReport:
    """Walk the bucket, apply the born-digital filter, and write a pinned manifest.

    Selection keeps an article only when its JATS has at least one ``<p>`` **and** its
    PDF carries vector drawings on some page.  The ``<p>`` test is deliberately not a
    ``<sec>`` test: short unsectioned pieces are born-digital too, and requiring sections
    would bias the corpus toward long research papers.

    A text layer is *not* part of the filter, because scans ship an embedded OCR layer.
    The ``<p>`` test carries the discrimination: scanned back-catalogue articles deposit
    their body as one ``<preformat>`` blob of raw OCR text and so have zero paragraphs.
    See `_has_vector_drawings` for why its arm is only a backstop.

    Parameters
    ----------
    destination : pathlib.Path
        Manifest path to write.
    workspace : pathlib.Path
        Directory for candidate downloads.  Accepted articles are left in place so a
        build also warms a cache; rejected ones are removed.
    seeds : Sequence[str], optional
        ``start-after`` seeds spread across the PMCID range.
    per_seed : int, optional
        Articles to accept per seed, so no single era dominates the corpus.
    stride : int, optional
        Take every ``stride``-th listed prefix, to avoid drawing a run of same-issue
        articles from one publisher.
    max_candidates_per_seed : int, optional
        Give up on a seed after this many candidates, so one barren region cannot stall
        the walk indefinitely.
    progress : Callable[[str], None] or None, optional
        Receives one line per candidate outcome.

    Returns
    -------
    BuildReport
        Accepted ids plus the full rejection ledger.

    Raises
    ------
    ValueError
        If a numeric parameter is outside its supported range.
    CorpusSelectionError
        If no article survives selection.

    """
    limits = (("per_seed", per_seed), ("stride", stride), ("max_candidates_per_seed", max_candidates_per_seed))
    for name, value in limits:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not seeds:
        raise ValueError("seeds must not be empty")

    emit = progress if progress is not None else (lambda _message: None)
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    accepted: dict[str, ManifestArticle] = {}
    rejected: dict[str, str] = {}
    unavailable: dict[str, str] = {}
    candidates = 0
    entity_fallbacks = 0

    for seed in seeds:
        emit(f"seed {seed}")
        kept = 0
        examined = 0
        token: str | None = None
        offset = 0
        while kept < per_seed and examined < max_candidates_per_seed:
            try:
                if token is None:
                    prefixes, token = list_article_prefixes(seed)
                else:
                    prefixes, token = _list_continuation(token)
            except CorpusDownloadError as exc:
                # A seed whose listing is unreachable is abandoned, not silently treated
                # as an exhausted region; the unavailable ledger below is what makes the
                # difference visible.
                unavailable[seed] = str(exc)
                emit(f"  unavailable {seed}: listing failed")
                break
            if not prefixes:
                break
            for index, article_id in enumerate(prefixes):
                if (offset + index) % stride:
                    continue
                if article_id in accepted or article_id in rejected or article_id in unavailable:
                    continue
                if kept >= per_seed or examined >= max_candidates_per_seed:
                    break
                examined += 1
                candidates += 1
                try:
                    entry, reason, neutralized = _evaluate_candidate(article_id, workspace)
                except CorpusDownloadError as exc:
                    unavailable[article_id] = str(exc)
                    emit(f"  unavailable {article_id}: {exc}")
                    continue
                entity_fallbacks += int(neutralized)
                if entry is None:
                    rejected[article_id] = reason or "xml_missing"
                    emit(f"  reject {article_id}: {rejected[article_id]}")
                    continue
                accepted[article_id] = entry
                kept += 1
                emit(f"  accept {article_id}: {entry.paragraphs} <p>, {entry.licence}")
            offset += len(prefixes)
            if token is None:
                break

    if not accepted:
        raise CorpusSelectionError("bucket walk accepted no articles")
    # Fail loudly rather than committing a manifest that a bad link quietly thinned out.
    if unavailable and len(unavailable) > max(2, int(_MAX_UNAVAILABLE_SHARE * candidates)):
        raise CorpusSelectionError(
            f"bucket walk lost {len(unavailable)} of {candidates} candidates to network failure; "
            "this measures the link, not the corpus -- rerun when the network is healthy"
        )

    rejection_counts = dict.fromkeys(REJECTION_REASONS, 0)
    for reason in rejected.values():
        rejection_counts[reason] += 1

    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "bucket": BUCKET,
        "selection": {
            "seeds": list(seeds),
            "per_seed": per_seed,
            "stride": stride,
            "max_candidates_per_seed": max_candidates_per_seed,
            "candidates": candidates,
            "xml_entity_fallbacks": entity_fallbacks,
            "unavailable": sorted(unavailable),
            "filter": "JATS <p> > 0 and vector drawings on some PDF page",
        },
        "articles": {
            article_id: {
                "pdf_sha256": entry.pdf_sha256,
                "pdf_size_bytes": entry.pdf_size_bytes,
                "xml_sha256": entry.xml_sha256,
                "xml_size_bytes": entry.xml_size_bytes,
                "licence": entry.licence,
                "paragraphs": entry.paragraphs,
            }
            for article_id, entry in sorted(accepted.items())
        },
        "rejected": dict(sorted(rejected.items())),
        "rejection_counts": rejection_counts,
    }
    destination = Path(destination)
    _atomic_write_json(destination, payload)
    _promote_workspace(workspace, destination, accepted)
    return BuildReport(
        manifest_path=destination,
        accepted=tuple(sorted(accepted)),
        rejected=dict(sorted(rejected.items())),
        rejection_counts=rejection_counts,
        unavailable=dict(sorted(unavailable.items())),
        candidates=candidates,
    )


def _promote_workspace(workspace: Path, manifest_path: Path, accepted: dict[str, ManifestArticle]) -> None:
    """Move the accepted downloads into the digest-keyed layout `load_corpus` reads.

    The build cannot write there directly -- the digest that names the directory does not
    exist until the manifest does.  Without this a fresh build leaves several hundred
    megabytes on disk that the very next load re-downloads, so the promotion is what makes
    "a build also warms the cache" true rather than merely claimed.

    Best-effort by design: a failure here costs a re-download, and must never invalidate a
    manifest that is already written and correct.
    """
    try:
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    except OSError:
        return
    source_root = workspace / "articles"
    target_root = workspace / digest[:16] / "articles"
    if not source_root.is_dir() or source_root.resolve() == target_root.resolve():
        return
    for article_id in accepted:
        source = source_root / article_id
        target = target_root / article_id
        if not source.is_dir() or target.exists():
            continue
        with suppress(OSError):
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
    with suppress(OSError):
        source_root.rmdir()


def _evaluate_candidate(article_id: str, workspace: Path) -> tuple[ManifestArticle | None, str | None, bool]:
    """Apply the born-digital filter to one candidate, cheapest test first.

    Returns the accepted entry or a rejection reason, plus whether the JATS needed
    entity neutralization to parse.
    """
    article_dir = workspace / "articles" / article_id
    article_dir.mkdir(parents=True, exist_ok=True)
    xml_path = article_dir / f"{article_id}.xml"
    pdf_path = article_dir / f"{article_id}.pdf"

    def drop(reason: str, neutralized: bool) -> tuple[None, str, bool]:
        pdf_path.unlink(missing_ok=True)
        # Leave no empty directory behind for an article the corpus does not contain.
        with suppress(OSError):
            article_dir.rmdir()
        return None, reason, neutralized

    try:
        xml_bytes = _http_get(_object_url(article_id, "xml"), label=f"JATS {article_id}")
    except ArtifactMissingError:
        return drop("xml_missing", False)
    try:
        root, neutralized = _parse_jats(xml_bytes)
    except (ElementTree.ParseError, EntitiesForbidden):
        # EntitiesForbidden is defusedxml refusing an internal entity declaration -- the
        # entity-expansion vector. Recorded as a rejection like any other unparsable
        # article rather than allowed to abort the whole walk.
        return drop("xml_unparsable", False)
    paragraphs = _count_local(root, "p")
    if paragraphs <= 0:
        return drop("no_paragraphs", neutralized)

    try:
        _download(_object_url(article_id, "pdf"), pdf_path, label=f"PDF {article_id}")
    except ArtifactMissingError:
        return drop("pdf_missing", neutralized)
    has_drawings = _has_vector_drawings(pdf_path)
    if has_drawings is None:
        return drop("pdf_unreadable", neutralized)
    if not has_drawings:
        return drop("no_vector_drawings", neutralized)

    xml_path.write_bytes(xml_bytes)
    return (
        ManifestArticle(
            article_id=article_id,
            pdf_sha256=_sha256(pdf_path),
            pdf_size_bytes=pdf_path.stat().st_size,
            xml_sha256=hashlib.sha256(xml_bytes).hexdigest(),
            xml_size_bytes=len(xml_bytes),
            licence=_extract_licence(root),
            paragraphs=paragraphs,
        ),
        None,
        neutralized,
    )
