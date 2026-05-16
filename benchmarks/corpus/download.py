"""Download + cache layer for the all2md corpus benchmark.

Each source fetches documents from a public HTTP endpoint and caches them under
``benchmarks/corpus/.cache/<source>/``. A per-source ``_index.json`` records what
was fetched, so re-running ``download`` is a no-op once the cache is populated.

All fetchers use stdlib only (urllib, tarfile, zipfile, xml.etree, json).
"""

from __future__ import annotations

import fnmatch
import json
import random
import re
import socket
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

USER_AGENT = "all2md-corpus-benchmark/1.0 (mailto:thomas.villani@njii.com)"
DEFAULT_TIMEOUT = 60
POLITE_DELAY_SECONDS = 0.4


@dataclass
class CorpusItem:
    """One cached document ready for benchmarking."""

    source: str
    format: str
    source_id: str
    filename: str
    size_bytes: int

    def resolve(self, cache_root: Path) -> Path:
        return cache_root / self.source / self.filename


# ---------------------------------------------------------------------------
# HTTP + cache helpers
# ---------------------------------------------------------------------------


def _open_url(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - vetted public URLs


def _download(url: str, dest: Path, *, chunk: int = 1 << 16, timeout: int = DEFAULT_TIMEOUT) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    total = 0
    with _open_url(url, timeout=timeout) as resp, tmp.open("wb") as f:
        while True:
            buf = resp.read(chunk)
            if not buf:
                break
            f.write(buf)
            total += len(buf)
    tmp.replace(dest)
    return total


def _read_index(source_dir: Path) -> list[CorpusItem] | None:
    idx = source_dir / "_index.json"
    if not idx.exists():
        return None
    rows = json.loads(idx.read_text(encoding="utf-8"))
    return [CorpusItem(**row) for row in rows]


def _write_index(source_dir: Path, items: list[CorpusItem]) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "_index.json").write_text(
        json.dumps([asdict(i) for i in items], indent=2),
        encoding="utf-8",
    )


def _seeded_sample(pool: list[Any], n: int, seed: int) -> list[Any]:
    if n >= len(pool):
        return list(pool)
    rng = random.Random(seed)
    return rng.sample(pool, n)


def _safe_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


def _is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) == b"%PDF"
    except OSError:
        return False


def _try_download(
    url: str,
    dest: Path,
    *,
    label: str,
    timeout: int = DEFAULT_TIMEOUT,
    validator: "Callable[[Path], bool] | None" = None,
) -> int | None:
    try:
        size = _download(url, dest, timeout=timeout)
    except urllib.error.HTTPError as e:
        print(f"    skip {label}: HTTP {e.code}", flush=True)
        return None
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        print(f"    skip {label}: {e}", flush=True)
        return None
    except OSError as e:
        print(f"    skip {label}: {e}", flush=True)
        return None
    if validator is not None and not validator(dest):
        dest.unlink(missing_ok=True)
        print(f"    skip {label}: failed content validation", flush=True)
        return None
    return size


def _invalidate_cache_if_invalid(source_dir: Path, items: list[CorpusItem], validator: Callable[[Path], bool]) -> bool:
    """Drop the cache (files + index) when any cached item fails validation. Returns True if invalidated."""
    if all(validator(source_dir / i.filename) for i in items):
        return False
    for i in items:
        (source_dir / i.filename).unlink(missing_ok=True)
    (source_dir / "_index.json").unlink(missing_ok=True)
    return True


# ---------------------------------------------------------------------------
# arxiv
# ---------------------------------------------------------------------------

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch_arxiv(cfg: dict, source_dir: Path) -> list[CorpusItem]:
    cached = _read_index(source_dir)
    if cached is not None:
        if not _invalidate_cache_if_invalid(source_dir, cached, _is_pdf):
            return cached
        print("  arxiv: invalidated cache (entries failed PDF validation)", flush=True)

    pool_size = int(cfg.get("pool_size", 200))
    sample_size = int(cfg["sample_size"])
    seed = int(cfg["seed"])
    query = cfg.get("query", "cat:cs.CL")

    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "max_results": pool_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    print(f"  arxiv: querying pool of {pool_size} ({query})...", flush=True)
    with _open_url(f"{ARXIV_API}?{params}") as resp:
        feed = resp.read()

    root = ET.fromstring(feed)
    pool: list[str] = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        eid_el = entry.find("atom:id", ARXIV_NS)
        if eid_el is None or not eid_el.text:
            continue
        # entry id is like http://arxiv.org/abs/2401.12345v1
        eid = eid_el.text.rsplit("/", 1)[-1]
        pool.append(eid)

    if not pool:
        print("  arxiv: empty pool, nothing to fetch", flush=True)
        _write_index(source_dir, [])
        return []

    sampled = _seeded_sample(pool, sample_size, seed)
    items: list[CorpusItem] = []
    for i, arxiv_id in enumerate(sampled, 1):
        filename = f"{_safe_filename(arxiv_id)}.pdf"
        dest = source_dir / filename
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        if dest.exists() and _is_pdf(dest):
            size: int = dest.stat().st_size
        else:
            print(f"  arxiv [{i}/{len(sampled)}] {arxiv_id}", flush=True)
            fetched = _try_download(url, dest, label=arxiv_id, validator=_is_pdf)
            if fetched is None:
                continue
            size = fetched
            time.sleep(POLITE_DELAY_SECONDS)
        items.append(CorpusItem(source="arxiv", format="pdf", source_id=arxiv_id, filename=filename, size_bytes=size))
    _write_index(source_dir, items)
    return items


# ---------------------------------------------------------------------------
# PMC OA
# ---------------------------------------------------------------------------

PMC_OA = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"


def fetch_pmc(cfg: dict, source_dir: Path) -> list[CorpusItem]:
    # Skip empty caches - those are stuck states from a previous fetch that
    # found nothing, and we want a fresh try, not a permanently empty list.
    cached = _read_index(source_dir)
    if cached:
        if not _invalidate_cache_if_invalid(source_dir, cached, _is_pdf):
            return cached
        print("  pmc: invalidated cache (entries failed PDF validation)", flush=True)
    elif cached == []:
        (source_dir / "_index.json").unlink(missing_ok=True)

    sample_size = int(cfg["sample_size"])
    seed = int(cfg["seed"])
    # Use the OA web service's list endpoint (filtered to PDF format), which
    # returns ONLY articles that actually have a PDF available. This is much
    # higher hit-rate than esearch + per-id resolution: esearch returns OA
    # articles broadly, but only a fraction of those actually have a PDF
    # exposed via the OA download service.
    params = urllib.parse.urlencode({"format": "pdf"})
    print("  pmc: listing OA-with-PDF articles...", flush=True)
    with _open_url(f"{PMC_OA}?{params}") as resp:
        body = resp.read()
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        print(f"  pmc: failed to parse OA response: {e}", flush=True)
        return []

    pool: list[tuple[str, str]] = []  # (pmc_id, pdf_url)
    for record in root.findall(".//record"):
        pmc_id = record.get("id", "")
        link = record.find("link[@format='pdf']")
        if link is None:
            continue
        href = link.get("href", "")
        if not href:
            continue
        if href.startswith("ftp://"):
            href = "https://" + href[len("ftp://") :]
        if pmc_id:
            pool.append((pmc_id, href))

    if not pool:
        print("  pmc: empty pool, nothing to fetch", flush=True)
        return []
    print(f"  pmc: pool has {len(pool)} OA-with-PDF articles", flush=True)

    sampled = _seeded_sample(pool, sample_size, seed)
    items: list[CorpusItem] = []
    for i, (pmc_id, pdf_url) in enumerate(sampled, 1):
        filename = f"{_safe_filename(pmc_id)}.pdf"
        dest = source_dir / filename
        if dest.exists() and _is_pdf(dest):
            size: int = dest.stat().st_size
        else:
            print(f"  pmc [{i}/{len(sampled)}] {pmc_id}", flush=True)
            fetched = _try_download(pdf_url, dest, label=pmc_id, validator=_is_pdf)
            if fetched is None:
                continue
            size = fetched
            time.sleep(POLITE_DELAY_SECONDS)
        items.append(CorpusItem(source="pmc", format="pdf", source_id=pmc_id, filename=filename, size_bytes=size))
    _write_index(source_dir, items)
    return items


# ---------------------------------------------------------------------------
# govdocs1
# ---------------------------------------------------------------------------

GOVDOCS1_BASE = "https://digitalcorpora.s3.amazonaws.com/corpora/files/govdocs1/zipfiles"


def fetch_govdocs1(cfg: dict, source_dir: Path) -> list[CorpusItem]:
    cached = _read_index(source_dir)
    if cached is not None:
        return cached

    sample_size = int(cfg["sample_size"])
    seed = int(cfg["seed"])
    shard = int(cfg.get("shard", 0))
    formats = [f.lower() for f in cfg.get("formats", ["pdf"])]

    shard_name = f"{shard:03d}.zip"
    shard_path = source_dir / shard_name
    if not shard_path.exists():
        url = f"{GOVDOCS1_BASE}/{shard_name}"
        print(f"  govdocs1: downloading shard {shard_name} (~250 MB)...", flush=True)
        size = _try_download(url, shard_path, label=shard_name, timeout=600)
        if size is None:
            _write_index(source_dir, [])
            return []

    print(f"  govdocs1: scanning {shard_name} for formats {formats}...", flush=True)
    with zipfile.ZipFile(shard_path) as zf:
        candidates = [
            info
            for info in zf.infolist()
            if not info.is_dir() and Path(info.filename).suffix.lower().lstrip(".") in formats
        ]
        if not candidates:
            print(f"  govdocs1: no matching files in shard {shard_name}", flush=True)
            _write_index(source_dir, [])
            return []
        sampled = _seeded_sample(candidates, sample_size, seed)
        items: list[CorpusItem] = []
        for info in sampled:
            ext = Path(info.filename).suffix.lower().lstrip(".")
            base = Path(info.filename).name
            filename = _safe_filename(base) or f"file_{info.CRC:08x}.{ext}"
            dest = source_dir / filename
            if not (dest.exists() and dest.stat().st_size == info.file_size):
                with zf.open(info) as src, dest.open("wb") as out:
                    while True:
                        buf = src.read(1 << 16)
                        if not buf:
                            break
                        out.write(buf)
            items.append(
                CorpusItem(
                    source="govdocs1",
                    format=ext,
                    source_id=info.filename,
                    filename=filename,
                    size_bytes=dest.stat().st_size,
                )
            )
    _write_index(source_dir, items)
    return items


# ---------------------------------------------------------------------------
# Apache POI test corpus (via GitHub contents API)
# ---------------------------------------------------------------------------

GH_CONTENTS = "https://api.github.com/repos/{repo}/contents/{path}"
GH_RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def fetch_poi(cfg: dict, source_dir: Path) -> list[CorpusItem]:
    sample_size = int(cfg["sample_size"])
    seed = int(cfg["seed"])
    repo = cfg["repo"]
    ref = cfg.get("ref", "trunk")
    paths: list[str] = list(cfg.get("paths", []))
    formats = {f.lower() for f in cfg.get("formats", ["docx", "pptx"])}
    exclude_patterns: list[str] = list(cfg.get("exclude_patterns", []))

    cached = _read_index(source_dir)
    if cached is not None:
        cached_excluded = [
            item for item in cached if any(fnmatch.fnmatch(item.source_id, pat) for pat in exclude_patterns)
        ]
        if cached_excluded:
            print(
                f"  poi: invalidating cache ({len(cached_excluded)} item(s) match exclude_patterns)",
                flush=True,
            )
            for item in cached:
                (source_dir / item.filename).unlink(missing_ok=True)
            (source_dir / "_index.json").unlink(missing_ok=True)
        else:
            return cached

    pool: list[tuple[str, str]] = []  # (full_path, ext)
    for sub in paths:
        url = GH_CONTENTS.format(repo=repo, path=urllib.parse.quote(sub)) + f"?ref={ref}"
        print(f"  poi: listing {sub}...", flush=True)
        try:
            with _open_url(url) as resp:
                listing = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            print(f"    skip {sub}: HTTP {e.code}", flush=True)
            continue
        if not isinstance(listing, list):
            print(f"    skip {sub}: unexpected response", flush=True)
            continue
        for entry in listing:
            if entry.get("type") != "file":
                continue
            ep = entry.get("path", "")
            ext = Path(ep).suffix.lower().lstrip(".")
            if ext not in formats:
                continue
            if any(fnmatch.fnmatch(ep, pat) for pat in exclude_patterns):
                continue
            pool.append((ep, ext))

    if not pool:
        print("  poi: empty pool, nothing to fetch", flush=True)
        _write_index(source_dir, [])
        return []

    sampled = _seeded_sample(pool, sample_size, seed)
    items: list[CorpusItem] = []
    for i, (path, ext) in enumerate(sampled, 1):
        filename = _safe_filename(Path(path).name)
        dest = source_dir / filename
        url = GH_RAW.format(repo=repo, ref=ref, path=urllib.parse.quote(path))
        if dest.exists() and dest.stat().st_size > 0:
            size: int = dest.stat().st_size
        else:
            print(f"  poi [{i}/{len(sampled)}] {path}", flush=True)
            fetched = _try_download(url, dest, label=path)
            if fetched is None:
                continue
            size = fetched
        items.append(CorpusItem(source="poi", format=ext, source_id=path, filename=filename, size_bytes=size))
    _write_index(source_dir, items)
    return items


# ---------------------------------------------------------------------------
# Enron emails
# ---------------------------------------------------------------------------

ENRON_URL = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
ENRON_TARBALL = "enron_mail_20150507.tar.gz"
ENRON_NAMES_CACHE = "_member_names.json"


def fetch_enron(cfg: dict, source_dir: Path) -> list[CorpusItem]:
    cached = _read_index(source_dir)
    if cached is not None:
        return cached

    sample_size = int(cfg["sample_size"])
    seed = int(cfg["seed"])

    tarball = source_dir / ENRON_TARBALL
    if not tarball.exists():
        print("  enron: downloading tarball (~423 MB)...", flush=True)
        size = _try_download(ENRON_URL, tarball, label=ENRON_TARBALL, timeout=900)
        if size is None:
            _write_index(source_dir, [])
            return []

    names_cache = source_dir / ENRON_NAMES_CACHE
    if names_cache.exists():
        names = json.loads(names_cache.read_text(encoding="utf-8"))
    else:
        print("  enron: indexing tarball members (one-time, slow)...", flush=True)
        names = []
        with tarfile.open(tarball, "r:gz") as tf:
            for m in tf:
                if m.isfile():
                    names.append(m.name)
        names_cache.write_text(json.dumps(names), encoding="utf-8")
        print(f"  enron: indexed {len(names)} files", flush=True)

    if not names:
        _write_index(source_dir, [])
        return []

    sampled = _seeded_sample(names, sample_size, seed)
    items: list[CorpusItem] = []
    sampled_set = set(sampled)
    name_to_filename: dict[str, str] = {}
    # First pass: figure out where each sampled member lands on disk.
    seen_filenames: set[str] = set()
    for member_name in sampled:
        # Use the maildir-style path as a unique-ish suffix so we don't collide.
        flat = _safe_filename(member_name.replace("/", "__"))
        if not flat.endswith(".eml"):
            flat += ".eml"
        if flat in seen_filenames:
            flat = f"{len(seen_filenames):04d}_{flat}"
        seen_filenames.add(flat)
        name_to_filename[member_name] = flat

    needs_extract = [n for n in sampled if not (source_dir / name_to_filename[n]).exists()]
    if needs_extract:
        print(f"  enron: extracting {len(needs_extract)} sampled emails...", flush=True)
        with tarfile.open(tarball, "r:gz") as tf:
            for m in tf:
                if not m.isfile() or m.name not in sampled_set:
                    continue
                if m.name not in needs_extract:
                    continue
                dest = source_dir / name_to_filename[m.name]
                src = tf.extractfile(m)
                if src is None:
                    continue
                with dest.open("wb") as out:
                    while True:
                        buf = src.read(1 << 16)
                        if not buf:
                            break
                        out.write(buf)

    for member_name in sampled:
        filename = name_to_filename[member_name]
        path = source_dir / filename
        if not path.exists():
            continue
        items.append(
            CorpusItem(
                source="enron",
                format="eml",
                source_id=member_name,
                filename=filename,
                size_bytes=path.stat().st_size,
            )
        )
    _write_index(source_dir, items)
    return items


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

FETCHERS: dict[str, Callable[[dict, Path], list[CorpusItem]]] = {
    "arxiv-api": fetch_arxiv,
    "pmc-oa": fetch_pmc,
    "govdocs1-shard": fetch_govdocs1,
    "github-tree": fetch_poi,
    "enron-tarball": fetch_enron,
}


def load_manifest(toml_path: Path) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    with toml_path.open("rb") as f:
        return tomllib.load(f)


def load_cached(
    manifest: dict,
    cache_root: Path,
    source_filter: Iterable[str] | None = None,
    format_filter: Iterable[str] | None = None,
) -> dict[str, list[CorpusItem]]:
    """Read existing per-source ``_index.json`` files without any HTTP."""
    sources = manifest.get("sources", {})
    name_filter = set(source_filter) if source_filter else None
    fmt_filter = {f.lower() for f in format_filter} if format_filter else None
    selected: dict[str, list[CorpusItem]] = {}
    for name in sources:
        if name_filter and name not in name_filter:
            continue
        items = _read_index(cache_root / name) or []
        if fmt_filter:
            items = [i for i in items if i.format.lower() in fmt_filter]
        selected[name] = items
    return selected


def fetch_all(
    manifest: dict,
    cache_root: Path,
    source_filter: Iterable[str] | None = None,
    format_filter: Iterable[str] | None = None,
) -> dict[str, list[CorpusItem]]:
    sources = manifest.get("sources", {})
    selected: dict[str, list[CorpusItem]] = {}
    name_filter = set(source_filter) if source_filter else None
    fmt_filter = {f.lower() for f in format_filter} if format_filter else None

    for name, cfg in sources.items():
        if name_filter and name not in name_filter:
            continue
        if fmt_filter and not (set(map(str.lower, cfg.get("formats", []))) & fmt_filter):
            continue
        kind = cfg.get("type")
        fetcher = FETCHERS.get(kind)
        if fetcher is None:
            print(f"[{name}] unknown source type {kind!r}, skipping", flush=True)
            continue
        print(f"[{name}] {cfg.get('description', '')}", flush=True)
        source_dir = cache_root / name
        items = fetcher(cfg, source_dir)
        if fmt_filter:
            items = [i for i in items if i.format.lower() in fmt_filter]
        selected[name] = items
        print(f"[{name}] cached {len(items)} item(s)", flush=True)
    return selected
