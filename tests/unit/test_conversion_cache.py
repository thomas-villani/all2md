"""Unit tests for the opt-in conversion cache."""

import pytest

from all2md import to_ast
from all2md.ast.nodes import Document
from all2md.conversion_cache import (
    ConversionCache,
    cache_enabled_by_env,
    get_active_cache,
    make_cache_key,
    use_conversion_cache,
)

pytestmark = pytest.mark.unit

SAMPLE = "# Title\n\nThe alpha protocol governs the handshake.\n"


def _write(path, text=SAMPLE):
    path.write_text(text, encoding="utf-8")
    return path


class TestActivation:
    def test_disabled_by_default(self):
        assert get_active_cache() is None

    def test_context_enables_and_restores(self, tmp_path):
        assert get_active_cache() is None
        with use_conversion_cache(enabled=True, cache_dir=tmp_path) as cache:
            assert cache is not None
            assert get_active_cache() is cache
        assert get_active_cache() is None

    def test_disabled_context_is_inert(self, tmp_path):
        with use_conversion_cache(enabled=False, cache_dir=tmp_path) as cache:
            assert cache is None
            assert get_active_cache() is None

    def test_env_var_toggles_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ALL2MD_CACHE", "1")
        assert cache_enabled_by_env() is True
        with use_conversion_cache(cache_dir=tmp_path) as cache:  # enabled=None -> env
            assert cache is not None
        monkeypatch.setenv("ALL2MD_CACHE", "off")
        assert cache_enabled_by_env() is False
        with use_conversion_cache(cache_dir=tmp_path) as cache:
            assert cache is None


class TestConversionCacheStore:
    def test_put_get_roundtrip(self, tmp_path):
        cache = ConversionCache(tmp_path)
        doc = to_ast(SAMPLE.encode("utf-8"), source_format="markdown")
        assert isinstance(doc, Document)
        assert cache.get("deadbeef") is None  # miss
        cache.put("deadbeef", doc)
        restored = cache.get("deadbeef")
        assert isinstance(restored, Document)
        # Structural equivalence via the node types of the top-level children.
        assert [type(n).__name__ for n in restored.children] == [type(n).__name__ for n in doc.children]

    def test_corrupt_entry_is_a_miss(self, tmp_path):
        cache = ConversionCache(tmp_path)
        entry = cache._entry_path("cafef00d")
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("{not valid ast json", encoding="utf-8")
        assert cache.get("cafef00d") is None  # swallowed, treated as miss


class TestKeying:
    def test_key_changes_with_options_and_format(self, tmp_path):
        src = str(_write(tmp_path / "a.md"))
        base = make_cache_key(src, source_format="markdown", options_repr="None")
        assert make_cache_key(src, source_format="markdown", options_repr="None") == base
        assert make_cache_key(src, source_format="html", options_repr="None") != base
        assert make_cache_key(src, source_format="markdown", options_repr="Options(x=1)") != base


class TestToAstIntegration:
    def test_hit_and_miss_through_to_ast(self, tmp_path):
        cache_dir = tmp_path / "cache"
        src = _write(tmp_path / "doc.md")

        def entry_count():
            return len(list(cache_dir.rglob("*.json")))

        with use_conversion_cache(enabled=True, cache_dir=cache_dir):
            to_ast(src)
            assert entry_count() == 1
            # Second call is a hit: no new entry written.
            to_ast(src)
            assert entry_count() == 1

            # Change content (length differs → fingerprint differs) → new entry.
            _write(src, "# Title\n\nEntirely different and noticeably longer body text.\n")
            to_ast(src)
            assert entry_count() == 2

    def test_no_writes_when_disabled(self, tmp_path):
        cache_dir = tmp_path / "cache"
        src = _write(tmp_path / "doc.md")
        with use_conversion_cache(enabled=False, cache_dir=cache_dir):
            to_ast(src)
        assert not cache_dir.exists()

    def test_bytes_source_not_cached(self, tmp_path):
        # Non-file sources (bytes/stdin) are never cached.
        cache_dir = tmp_path / "cache"
        with use_conversion_cache(enabled=True, cache_dir=cache_dir):
            to_ast(SAMPLE.encode("utf-8"), source_format="markdown")
        assert not cache_dir.exists()
