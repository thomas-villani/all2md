"""Unit tests for the corpus-fingerprint cache-invalidation primitive."""

import pytest

from all2md.utils.fingerprint import bytes_signature, corpus_fingerprint, file_signature

pytestmark = pytest.mark.unit


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


class TestFileSignature:
    def test_signature_has_stable_absolute_path(self, tmp_path):
        f = _write(tmp_path / "a.txt", "hello")
        sig = file_signature(f)
        assert sig["path"].endswith("a.txt")
        assert sig["size"] == 5
        assert "mtime_ns" in sig
        assert "sha256" not in sig  # stat-only by default

    def test_content_hash_opt_in(self, tmp_path):
        f = _write(tmp_path / "a.txt", "hello")
        sig = file_signature(f, content_hash=True)
        assert sig["sha256"] == bytes_signature(b"hello")["sha256"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(OSError):
            file_signature(tmp_path / "nope.txt")


class TestCorpusFingerprint:
    def test_identical_inputs_match(self, tmp_path):
        a = _write(tmp_path / "a.txt", "alpha")
        b = _write(tmp_path / "b.txt", "beta")
        assert corpus_fingerprint([a, b]) == corpus_fingerprint([a, b])

    def test_order_independent(self, tmp_path):
        a = _write(tmp_path / "a.txt", "alpha")
        b = _write(tmp_path / "b.txt", "beta")
        assert corpus_fingerprint([a, b]) == corpus_fingerprint([b, a])

    def test_changed_content_changes_digest(self, tmp_path):
        a = _write(tmp_path / "a.txt", "alpha")
        before = corpus_fingerprint([a])
        _write(a, "alpha and more")  # size changes regardless of mtime granularity
        assert corpus_fingerprint([a]) != before

    def test_added_and_removed_file_changes_digest(self, tmp_path):
        a = _write(tmp_path / "a.txt", "alpha")
        b = _write(tmp_path / "b.txt", "beta")
        assert corpus_fingerprint([a]) != corpus_fingerprint([a, b])

    def test_missing_file_contributes_sentinel(self, tmp_path):
        a = _write(tmp_path / "a.txt", "alpha")
        present = corpus_fingerprint([a])
        a.unlink()
        # A vanished file must still change the digest rather than raising.
        assert corpus_fingerprint([tmp_path / "a.txt"]) != present

    def test_extra_params_affect_digest(self, tmp_path):
        a = _write(tmp_path / "a.txt", "alpha")
        assert corpus_fingerprint([a], extra={"k": 1}) != corpus_fingerprint([a], extra={"k": 2})
        assert corpus_fingerprint([a], extra={"k": 1}) == corpus_fingerprint([a], extra={"k": 1})

    def test_bytes_source_is_content_hashed(self):
        # Same bytes → same digest; different bytes → different digest.
        assert corpus_fingerprint([b"payload"]) == corpus_fingerprint([b"payload"])
        assert corpus_fingerprint([b"payload"]) != corpus_fingerprint([b"other"])
