"""Regression tests for the pinned PMC born-digital corpus adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from benchmarks.pmc import corpus

pytestmark = pytest.mark.unit


def _pdf_bytes(article_id: str) -> bytes:
    return f"%PDF-1.7\nsynthetic {article_id}\n%%EOF\n".encode()


def _xml_bytes(article_id: str) -> bytes:
    return f"<article><body><p>{article_id}</p></body></article>".encode()


def _article_row(article_id: str) -> dict[str, Any]:
    pdf = _pdf_bytes(article_id)
    xml = _xml_bytes(article_id)
    return {
        "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        "pdf_size_bytes": len(pdf),
        "xml_sha256": hashlib.sha256(xml).hexdigest(),
        "xml_size_bytes": len(xml),
        "licence": "https://creativecommons.org/licenses/by/4.0/",
        "paragraphs": 12,
    }


def _manifest_payload(article_ids: list[str] | None = None, **overrides: Any) -> dict[str, Any]:
    ids = article_ids if article_ids is not None else ["PMC2000001.1", "PMC7000002.1", "PMC9000003.2"]
    payload: dict[str, Any] = {
        "schema_version": corpus.MANIFEST_SCHEMA_VERSION,
        "bucket": corpus.BUCKET,
        "selection": {"seeds": ["PMC2000000"], "per_seed": 1, "stride": 11},
        "articles": {article_id: _article_row(article_id) for article_id in ids},
        "rejected": {"PMC5500001.1": "pdf_missing"},
        "rejection_counts": dict.fromkeys(corpus.REJECTION_REASONS, 0) | {"pdf_missing": 1},
    }
    payload.update(overrides)
    return payload


def _write_manifest(tmp_path: Path, payload: dict[str, Any] | None = None) -> Path:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(payload if payload is not None else _manifest_payload(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest_path


def _install_downloader(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve synthetic article bytes and record every URL fetched."""
    calls: list[str] = []

    def download(url: str, destination: Path, *, label: str, retries: int = 0) -> None:
        calls.append(url)
        article_id = Path(url).stem
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = _pdf_bytes(article_id) if url.endswith(".pdf") else _xml_bytes(article_id)
        destination.write_bytes(payload)

    monkeypatch.setattr(corpus, "_download", download)
    return calls


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------


def test_read_manifest_accepts_a_well_formed_manifest(tmp_path: Path) -> None:
    manifest = corpus.read_manifest(_write_manifest(tmp_path))

    assert [entry.article_id for entry in manifest.articles] == [
        "PMC2000001.1",
        "PMC7000002.1",
        "PMC9000003.2",
    ]
    assert manifest.bucket == corpus.BUCKET
    assert manifest.rejected == {"PMC5500001.1": "pdf_missing"}


def test_manifest_digest_is_the_pin(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    expected = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    assert corpus.read_manifest(manifest_path).sha256 == expected


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda p: p.__setitem__("schema_version", 99), "schema version mismatch"),
        (lambda p: p.__setitem__("bucket", "somewhere-else"), "bucket mismatch"),
        (lambda p: p.__setitem__("articles", {}), "names no articles"),
        (lambda p: p.pop("rejection_counts"), "schema does not match"),
        (lambda p: p.__setitem__("extra_key", 1), "schema does not match"),
        (lambda p: p.__setitem__("rejected", {"PMC1.1": "gremlins"}), "unknown rejection reason"),
        (lambda p: p.__setitem__("rejected", {"not-an-id": "pdf_missing"}), "article id is malformed"),
    ],
)
def test_read_manifest_rejects_malformed_manifests(tmp_path: Path, mutate: Any, match: str) -> None:
    payload = _manifest_payload()
    mutate(payload)

    with pytest.raises(corpus.CorpusCacheError, match=match):
        corpus.read_manifest(_write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("pdf_sha256", "nothex", "pdf_sha256 is invalid"),
        ("xml_sha256", "a" * 63, "xml_sha256 is invalid"),
        ("pdf_size_bytes", 0, "pdf_size_bytes is invalid"),
        ("xml_size_bytes", -1, "xml_size_bytes is invalid"),
        ("paragraphs", 0, "paragraphs is invalid"),
        ("licence", "  ", "licence is invalid"),
    ],
)
def test_read_manifest_rejects_invalid_article_rows(tmp_path: Path, field: str, value: Any, match: str) -> None:
    payload = _manifest_payload()
    payload["articles"]["PMC2000001.1"][field] = value

    with pytest.raises(corpus.CorpusCacheError, match=match):
        corpus.read_manifest(_write_manifest(tmp_path, payload))


def test_read_manifest_rejects_an_article_that_is_both_accepted_and_rejected(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["rejected"] = {"PMC2000001.1": "pdf_missing"}

    with pytest.raises(corpus.CorpusCacheError, match="both accepts and rejects"):
        corpus.read_manifest(_write_manifest(tmp_path, payload))


def test_read_manifest_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(corpus.CorpusCacheError, match="not a regular file"):
        corpus.read_manifest(tmp_path / "absent.json")


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_limit_selects_a_spread_not_a_prefix() -> None:
    """The regression this adapter exists downstream of.

    Manifest order is lexicographic by PMCID, so taking the first ``limit`` entries would
    draw one era of the archive.  Both sibling lanes shipped that bug; this one must not.
    """
    articles = tuple(
        corpus.ManifestArticle(
            article_id=f"PMC{index:07d}.1",
            pdf_sha256="a" * 64,
            pdf_size_bytes=1,
            xml_sha256="b" * 64,
            xml_size_bytes=1,
            licence="cc",
            paragraphs=1,
        )
        for index in range(100)
    )

    selected = corpus._select(articles, 4)

    assert [entry.article_id for entry in selected] == [
        "PMC0000000.1",
        "PMC0000025.1",
        "PMC0000050.1",
        "PMC0000075.1",
    ]


def test_limit_selection_is_deterministic_and_duplicate_free() -> None:
    articles = tuple(corpus.ManifestArticle(f"PMC{i:07d}.1", "a" * 64, 1, "b" * 64, 1, "cc", 1) for i in range(37))

    for size in range(1, 38):
        selected = corpus._select(articles, size)
        assert len(selected) == size
        assert len({entry.article_id for entry in selected}) == size
        assert selected == corpus._select(articles, size)


def test_limit_none_returns_every_article() -> None:
    articles = tuple(corpus.ManifestArticle(f"PMC{i:07d}.1", "a" * 64, 1, "b" * 64, 1, "cc", 1) for i in range(5))

    assert corpus._select(articles, None) == articles


@pytest.mark.parametrize("limit", [0, -1, 6, True])
def test_limit_out_of_range_is_rejected(limit: Any) -> None:
    articles = tuple(corpus.ManifestArticle(f"PMC{i:07d}.1", "a" * 64, 1, "b" * 64, 1, "cc", 1) for i in range(5))

    with pytest.raises(ValueError, match="limit must be"):
        corpus._select(articles, limit)


# ---------------------------------------------------------------------------
# Cache materialization
# ---------------------------------------------------------------------------


def test_load_corpus_downloads_and_validates_every_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = _write_manifest(tmp_path)
    calls = _install_downloader(monkeypatch)

    snapshot = corpus.load_corpus(tmp_path / "cache", manifest_path=manifest_path, workers=1)

    assert snapshot.complete is True
    assert len(snapshot.articles) == 3
    assert len(calls) == 6
    for article in snapshot.articles:
        assert article.pdf_path.read_bytes() == _pdf_bytes(article.article_id)
        assert article.xml_path.read_bytes() == _xml_bytes(article.article_id)
    assert {a.pmcid for a in snapshot.articles} == {"PMC2000001", "PMC7000002", "PMC9000003"}
    assert {a.version for a in snapshot.articles} == {1, 2}


def test_a_warm_cache_downloads_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = _write_manifest(tmp_path)
    calls = _install_downloader(monkeypatch)
    corpus.load_corpus(tmp_path / "cache", manifest_path=manifest_path, workers=1)
    calls.clear()

    corpus.load_corpus(tmp_path / "cache", manifest_path=manifest_path, workers=1)

    assert calls == []


def test_a_corrupted_warm_file_is_replaced_rather_than_trusted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    calls = _install_downloader(monkeypatch)
    snapshot = corpus.load_corpus(tmp_path / "cache", manifest_path=manifest_path, workers=1)
    victim = snapshot.articles[0].pdf_path
    victim.write_bytes(b"%PDF-1.7 truncated")
    calls.clear()

    reloaded = corpus.load_corpus(tmp_path / "cache", manifest_path=manifest_path, workers=1)

    assert calls == [corpus._object_url(snapshot.articles[0].article_id, "pdf")]
    assert reloaded.articles[0].pdf_path.read_bytes() == _pdf_bytes(snapshot.articles[0].article_id)


def test_a_download_that_disagrees_with_the_manifest_is_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _write_manifest(tmp_path)

    def download(url: str, destination: Path, *, label: str, retries: int = 0) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"%PDF-1.7 impostor\n")

    monkeypatch.setattr(corpus, "_download", download)

    with pytest.raises(corpus.CorpusIntegrityError, match="does not match the manifest"):
        corpus.load_corpus(tmp_path / "cache", manifest_path=manifest_path, workers=1)


def test_the_cache_directory_is_keyed_by_the_manifest_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An edited manifest must not re-bless files selected under the old rules."""
    _install_downloader(monkeypatch)
    cache = tmp_path / "cache"
    first = corpus.load_corpus(cache, manifest_path=_write_manifest(tmp_path), workers=1)

    other = tmp_path / "other"
    other.mkdir()
    second_payload = _manifest_payload(["PMC2000001.1", "PMC7000002.1"])
    second = corpus.load_corpus(cache, manifest_path=_write_manifest(other, second_payload), workers=1)

    assert first.manifest_sha256 != second.manifest_sha256
    assert first.articles[0].pdf_path != second.articles[0].pdf_path
    assert {path.name for path in cache.iterdir()} == {
        first.manifest_sha256[:16],
        second.manifest_sha256[:16],
    }


def test_an_incomplete_load_is_marked_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = _write_manifest(tmp_path)
    _install_downloader(monkeypatch)

    snapshot = corpus.load_corpus(tmp_path / "cache", manifest_path=manifest_path, limit=3, workers=1)

    assert snapshot.complete is False
    assert snapshot.expected_articles == 3
    assert len(snapshot.articles) == 3


@pytest.mark.parametrize("workers", [0, -1, True, "eight"])
def test_invalid_worker_counts_are_rejected(tmp_path: Path, workers: Any) -> None:
    with pytest.raises(ValueError, match="workers must be a positive integer"):
        corpus.load_corpus(tmp_path / "cache", manifest_path=_write_manifest(tmp_path), workers=workers)


def test_a_build_warms_the_load_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Otherwise a fresh build leaves bytes on disk that the next load re-downloads."""
    manifest_path = _write_manifest(tmp_path)
    manifest = corpus.read_manifest(manifest_path)
    workspace = tmp_path / "cache"
    for entry in manifest.articles:
        article_dir = workspace / "articles" / entry.article_id
        article_dir.mkdir(parents=True)
        (article_dir / f"{entry.article_id}.pdf").write_bytes(_pdf_bytes(entry.article_id))
        (article_dir / f"{entry.article_id}.xml").write_bytes(_xml_bytes(entry.article_id))

    corpus._promote_workspace(workspace, manifest_path, {e.article_id: e for e in manifest.articles})

    calls = _install_downloader(monkeypatch)
    snapshot = corpus.load_corpus(workspace, manifest_path=manifest_path, workers=1)
    assert calls == []
    assert len(snapshot.articles) == 3


def test_promotion_never_invalidates_an_already_written_manifest(tmp_path: Path) -> None:
    """A promotion failure costs a re-download; it must not raise."""
    manifest_path = _write_manifest(tmp_path)
    manifest = corpus.read_manifest(manifest_path)

    corpus._promote_workspace(tmp_path / "absent", manifest_path, {e.article_id: e for e in manifest.articles})
    corpus._promote_workspace(tmp_path / "cache", tmp_path / "absent.json", {})


# ---------------------------------------------------------------------------
# JATS handling
# ---------------------------------------------------------------------------


def test_undeclared_entities_do_not_reject_an_article() -> None:
    """JATS references DTD-declared entities the bucket does not ship."""
    payload = b"<article><body><p>alpha &mu; beta</p><p>gamma &emsp; delta</p></body></article>"

    root, neutralized = corpus._parse_jats(payload)

    assert neutralized is True
    assert corpus._count_local(root, "p") == 2


def test_a_well_formed_article_is_never_rewritten() -> None:
    payload = b"<article><body><p>alpha &amp; beta &#181;</p></body></article>"

    root, neutralized = corpus._parse_jats(payload)

    assert neutralized is False
    assert "alpha & beta µ" in "".join(root.itertext())


def test_paragraph_counting_ignores_namespaces() -> None:
    payload = b'<article xmlns="http://jats.nlm.nih.gov"><body><p>one</p><p>two</p></body></article>'

    root, _ = corpus._parse_jats(payload)

    assert corpus._count_local(root, "p") == 2
    assert corpus._count_local(root, "sec") == 0


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            b'<article><ali:license_ref xmlns:ali="http://www.niso.org/schemas/ali/1.0/">'
            b"https://creativecommons.org/licenses/by/4.0/</ali:license_ref></article>",
            "https://creativecommons.org/licenses/by/4.0/",
        ),
        (
            b'<article><license xmlns:xlink="http://www.w3.org/1999/xlink" '
            b'xlink:href="http://creativecommons.org/licenses/by-nc-sa/3.0"/></article>',
            "http://creativecommons.org/licenses/by-nc-sa/3.0",
        ),
        (b'<article><license license-type="OpenAccess"/></article>', "OpenAccess"),
        (b"<article><body><p>no licence at all</p></body></article>", "unrecorded"),
    ],
)
def test_licence_extraction_prefers_the_most_precise_source(payload: bytes, expected: str) -> None:
    root, _ = corpus._parse_jats(payload)

    assert corpus._extract_licence(root) == expected


# ---------------------------------------------------------------------------
# Bucket listing
# ---------------------------------------------------------------------------


def _listing(prefixes: list[str], *, truncated: bool = False, token: str = "next") -> bytes:
    body = "".join(f"<CommonPrefixes><Prefix>{prefix}</Prefix></CommonPrefixes>" for prefix in prefixes)
    continuation = f"<NextContinuationToken>{token}</NextContinuationToken>" if truncated else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<IsTruncated>{'true' if truncated else 'false'}</IsTruncated>"
        f"{body}{continuation}</ListBucketResult>"
    ).encode()


def test_listing_keeps_only_versioned_article_prefixes() -> None:
    payload = _listing(["PMC2000001.1/", "oa_comm/", "PMC2000002.3/", "PMC-not-an-id/", "PMC2000003/"])

    prefixes, token = corpus._parse_listing(payload)

    assert prefixes == ("PMC2000001.1", "PMC2000002.3")
    assert token is None


def test_listing_reports_a_continuation_token_only_when_truncated() -> None:
    assert corpus._parse_listing(_listing(["PMC1.1/"], truncated=True))[1] == "next"
    assert corpus._parse_listing(_listing(["PMC1.1/"], truncated=False))[1] is None


def test_a_malformed_listing_is_a_selection_error() -> None:
    with pytest.raises(corpus.CorpusSelectionError, match="not valid XML"):
        corpus._parse_listing(b"<ListBucketResult>truncated...")


# ---------------------------------------------------------------------------
# The committed manifest itself
# ---------------------------------------------------------------------------


def test_the_committed_manifest_is_valid() -> None:
    """The manifest is the corpus pin, so a hand edit that breaks it must fail here."""
    manifest = corpus.read_manifest(corpus.DEFAULT_MANIFEST)

    assert manifest.articles
    assert all(entry.paragraphs > 0 for entry in manifest.articles)
    assert all(entry.licence.strip() for entry in manifest.articles)


def test_the_committed_manifest_spreads_across_the_id_range() -> None:
    """Guards the trap this lane has now hit three times: a corpus drawn from one region.

    The numerically-first PMCIDs are one journal's scanned back catalogue, so a manifest
    clustered anywhere -- but especially at the front -- is not measuring born-digital
    conversion.
    """
    manifest = corpus.read_manifest(corpus.DEFAULT_MANIFEST)
    numbers = sorted(int(entry.article_id[3:].split(".")[0]) for entry in manifest.articles)

    assert numbers[0] < 3_000_000, "corpus has no early-range articles"
    assert numbers[-1] > 9_000_000, "corpus has no recent articles"
    # No single million-wide band may hold more than a third of the corpus.
    bands: dict[int, int] = {}
    for number in numbers:
        bands[number // 1_000_000] = bands.get(number // 1_000_000, 0) + 1
    assert max(bands.values()) <= len(numbers) / 3


# ---------------------------------------------------------------------------
# Corpus characterization (step 2)
# ---------------------------------------------------------------------------


def _make_pdf(path: Path, *, pages: int, drawings: int, text: bool, full_page_image: bool) -> None:
    """Build a real PDF so the characterization is tested against its actual instrument."""
    import fitz

    document = fitz.open()
    for _ in range(pages):
        page = document.new_page()
        if text:
            page.insert_text((72, 72), "born digital")
        for index in range(drawings):
            page.draw_rect(fitz.Rect(10 + index, 10 + index, 40 + index, 40 + index), color=(0, 0, 0))
        if full_page_image:
            pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8))
            page.insert_image(page.rect, pixmap=pixmap)
    document.save(path)
    document.close()


def _snapshot_of(paths: dict[str, Path]) -> Any:
    articles = tuple(
        corpus.CorpusArticle(
            article_id=article_id,
            pmcid=article_id.split(".")[0],
            version=1,
            pdf_path=path,
            xml_path=path,
            pdf_sha256="a" * 64,
            pdf_size_bytes=1,
            xml_sha256="b" * 64,
            xml_size_bytes=1,
            licence="cc",
            paragraphs=10,
        )
        for article_id, path in paths.items()
    )
    return corpus.CorpusSnapshot(
        manifest_path=Path("manifest.json"),
        manifest_sha256="c" * 64,
        bucket=corpus.BUCKET,
        articles=articles,
        expected_articles=len(articles),
        complete=True,
    )


def test_characterization_separates_born_digital_from_a_scan(tmp_path: Path) -> None:
    from benchmarks.pmc.characterize import characterize

    born = tmp_path / "born.pdf"
    scan = tmp_path / "scan.pdf"
    _make_pdf(born, pages=3, drawings=5, text=True, full_page_image=False)
    _make_pdf(scan, pages=2, drawings=0, text=False, full_page_image=True)

    result = characterize(_snapshot_of({"PMC1000001.1": born, "PMC2000002.1": scan}))

    assert result.pages == 5
    assert result.text_layer_pages == 3
    assert result.vector_drawing_pages == 3
    # The vacuity check that matters: the scan-shape test must be able to fire.
    assert result.scan_shape_pages == 2
    assert result.pages_by_drawing_count == {"zero": 2, "one": 0, "two_or_more": 3}


def test_the_scan_shape_test_is_not_vacuous(tmp_path: Path) -> None:
    """A 0% scan-shape result is only evidence if a scan can produce a non-zero one."""
    from benchmarks.pmc.characterize import characterize

    scan = tmp_path / "scan.pdf"
    _make_pdf(scan, pages=4, drawings=0, text=False, full_page_image=True)

    result = characterize(_snapshot_of({"PMC1000001.1": scan}))

    assert result.scan_shape_pages == 4
    assert result.share(result.scan_shape_pages) == 1.0


def test_characterization_reports_unreadable_articles_rather_than_crashing(tmp_path: Path) -> None:
    from benchmarks.pmc.characterize import characterize

    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf at all")

    result = characterize(_snapshot_of({"PMC1000001.1": broken}))

    assert result.unreadable == ("PMC1000001.1",)
    assert result.pages == 0
    assert result.share(0) == 0.0


def test_a_single_embedded_font_is_visible_as_the_retypeset_signature(tmp_path: Path) -> None:
    """Geometrically born-digital, but an OCR dump: the font count is the only tell."""
    from benchmarks.pmc.characterize import characterize

    dump = tmp_path / "dump.pdf"
    _make_pdf(dump, pages=2, drawings=1, text=True, full_page_image=False)

    result = characterize(_snapshot_of({"PMC1000001.1": dump}))

    assert result.min_font_count == 1
    assert result.scan_shape_pages == 0
    assert result.vector_drawing_pages == 2


# ---------------------------------------------------------------------------
# JATS-to-page alignment probe
# ---------------------------------------------------------------------------


def test_normalize_repairs_typesetter_hyphenation() -> None:
    from benchmarks.pmc.alignment import normalize

    assert normalize("hyphen-\nated word") == ["hyphenated", "word"]
    assert normalize("soft­hyphen") == ["softhyphen"]
    assert normalize("MiXeD Case!") == ["mixed", "case"]


def test_jats_blocks_join_with_a_separator() -> None:
    """The regression that made tables look unlocatable.

    Concatenating element text fuses ``<label>Table 2</label>`` onto its caption into the
    bogus token ``2obtained``, corrupting an n-gram at every element boundary. Tables have
    the most boundaries, so they suffered most: 32.1% apparently missing against a real
    1.4%.
    """
    from xml.etree import ElementTree

    from benchmarks.pmc.alignment import jats_blocks, normalize

    root = ElementTree.fromstring(
        "<article><table-wrap><label>Table 2</label>" "<caption><p>Obtained values</p></caption></table-wrap></article>"
    )
    table = next(text for kind, text in jats_blocks(root) if kind == "table-wrap")

    assert "2obtained" not in normalize(table)
    assert "obtained" in normalize(table)


def _grams(text: str) -> Any:
    from benchmarks.pmc.alignment import ngrams, normalize

    return ngrams(normalize(text))


def test_a_block_wholly_on_one_page_reads_clean() -> None:
    from benchmarks.pmc.alignment import place_block

    block = _grams("the mitochondrial membrane potential was measured with a fluorescent probe")
    pages = [_grams("unrelated introductory matter about something else entirely here"), block]

    placement = place_block(block, pages)

    assert placement.verdict == "clean"
    assert placement.page == 1


def test_a_block_broken_by_a_page_break_reads_spans() -> None:
    from benchmarks.pmc.alignment import place_block

    head = "the mitochondrial membrane potential was measured with a fluorescent probe and"
    tail = "and the resulting signal was normalized against the untreated control samples"
    block = _grams(f"{head} {tail}")
    pages = [_grams(head), _grams(tail)]

    placement = place_block(block, pages)

    assert placement.verdict == "spans"
    assert (placement.page, placement.runner_up_page) == (0, 1)


def test_a_block_matching_two_distant_pages_reads_split() -> None:
    from benchmarks.pmc.alignment import place_block

    head = "the mitochondrial membrane potential was measured with a fluorescent probe and"
    tail = "and the resulting signal was normalized against the untreated control samples"
    block = _grams(f"{head} {tail}")
    pages = [_grams(head), _grams("wholly unrelated filler text occupying the middle page"), _grams(tail)]

    placement = place_block(block, pages)

    assert placement.verdict == "split"
    assert {placement.page, placement.runner_up_page} == {0, 2}


def test_a_block_that_is_nowhere_reads_missing() -> None:
    from benchmarks.pmc.alignment import place_block

    block = _grams("the mitochondrial membrane potential was measured with a fluorescent probe")
    pages = [_grams("entirely different words concerning agricultural policy in the region")]

    placement = place_block(block, pages)

    assert placement.verdict == "missing"


def test_a_block_with_too_little_text_is_not_counted_as_a_failure() -> None:
    from benchmarks.pmc.alignment import place_block

    placement = place_block(_grams("three short words"), [_grams("three short words")])

    assert placement.verdict == "too_short"


def test_placement_never_uses_page_order() -> None:
    """Order-free by construction: shuffling the pages must only move the index."""
    from benchmarks.pmc.alignment import place_block

    block = _grams("the mitochondrial membrane potential was measured with a fluorescent probe")
    filler = _grams("entirely different words concerning agricultural policy in the region")

    first = place_block(block, [block, filler])
    second = place_block(block, [filler, block])

    assert first.verdict == second.verdict == "clean"
    assert (first.page, second.page) == (0, 1)


def test_the_control_collapses_when_blocks_meet_the_wrong_article(tmp_path: Path) -> None:
    """A placement rate is meaningless unless the same method fails on the wrong article."""
    import fitz

    from benchmarks.pmc.alignment import measure

    sentences = {
        "PMC1000001.1": "the mitochondrial membrane potential was measured with a fluorescent probe",
        "PMC2000002.1": "agricultural policy in the region shifted after the subsidy was withdrawn",
    }
    articles = []
    for article_id, sentence in sentences.items():
        pdf_path = tmp_path / f"{article_id}.pdf"
        xml_path = tmp_path / f"{article_id}.xml"
        document = fitz.open()
        page = document.new_page()
        page.insert_text((40, 60), sentence)
        document.save(pdf_path)
        document.close()
        xml_path.write_bytes(f"<article><body><p>{sentence}</p></body></article>".encode())
        articles.append(
            corpus.CorpusArticle(
                article_id=article_id,
                pmcid=article_id.split(".")[0],
                version=1,
                pdf_path=pdf_path,
                xml_path=xml_path,
                pdf_sha256="a" * 64,
                pdf_size_bytes=1,
                xml_sha256="b" * 64,
                xml_size_bytes=1,
                licence="cc",
                paragraphs=1,
            )
        )

    report = measure(articles)

    assert report.placeable == report.scored
    assert report.control_false_placement == 0.0
    assert report.share(report.placeable) == 1.0


def test_a_page_holding_the_whole_block_wins_over_an_echo_elsewhere() -> None:
    """Completeness beats ambiguity, and the ordering is the point.

    Checking the runner-up first was a real defect: body text restating a figure caption
    made 71% of 'split' blocks -- and 88% of split figures -- read as ambiguous when their
    top page already held 100% of them.
    """
    from benchmarks.pmc.alignment import place_block

    caption = "figure eight tensile toughness of the hybrid biocomposite films under strain"
    block = _grams(caption)
    pages = [
        _grams("introductory material with no bearing on the matter at hand whatsoever"),
        _grams(caption),
        _grams("unrelated filler"),
        _grams("as discussed above the tensile toughness result demonstrates this clearly"),
    ]

    placement = place_block(block, pages)

    assert placement.verdict == "clean"
    assert placement.page == 1


def test_a_genuine_page_break_still_reads_spans_under_the_completeness_rule() -> None:
    """The completeness short-circuit must not swallow real page-break splits."""
    from benchmarks.pmc.alignment import place_block

    head = "the mitochondrial membrane potential was measured with a fluorescent probe and"
    tail = "and the resulting signal was normalized against the untreated control samples"
    block = _grams(f"{head} {tail}")

    placement = place_block(block, [_grams(head), _grams(tail)])

    assert placement.verdict == "spans"
    assert placement.top_share < 0.95


def test_equal_scoring_pages_break_toward_the_earliest() -> None:
    """Without an explicit tie-break the sort silently preferred the *last* page."""
    from benchmarks.pmc.alignment import place_block

    text = "the mitochondrial membrane potential was measured with a fluorescent probe"
    block = _grams(text)

    placement = place_block(block, [_grams(text), _grams("filler"), _grams(text)])

    assert placement.page == 0
