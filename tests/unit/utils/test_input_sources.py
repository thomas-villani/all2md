from pathlib import Path

import pytest

from all2md.exceptions import ValidationError
from all2md.utils.input_sources import (
    DocumentSourceRequest,
    RemoteInputOptions,
    default_loader,
)


@pytest.fixture
def loader(monkeypatch):
    monkeypatch.setattr("all2md.utils.input_sources.is_network_disabled", lambda: False)
    return default_loader()


def test_http_retriever_requires_remote_input_enabled(loader):
    request = DocumentSourceRequest(raw_input="https://example.com/doc.pdf", remote_options=None)

    with pytest.raises(ValidationError) as excinfo:
        loader.load(request)

    assert "Remote document fetching is disabled" in str(excinfo.value)


def test_http_retriever_fetches_when_enabled(monkeypatch, loader):
    captured = {}

    def fake_fetch_content_securely(*, url, allowed_hosts, require_https, max_size_bytes, timeout):
        captured["url"] = url
        captured["allowed_hosts"] = allowed_hosts
        captured["require_https"] = require_https
        captured["max_size_bytes"] = max_size_bytes
        captured["timeout"] = timeout
        return b"hello world"

    monkeypatch.setattr("all2md.utils.input_sources.fetch_content_securely", fake_fetch_content_securely)

    remote_options = RemoteInputOptions(
        allow_remote_input=True,
        allowed_hosts=["example.com"],
        max_size_bytes=1024,
        timeout=3.5,
    )
    request = DocumentSourceRequest(raw_input="https://example.com/file.txt", remote_options=remote_options)

    source = loader.load(request)

    assert source.display_name == "file.txt"
    assert source.origin_uri == "https://example.com/file.txt"
    assert source.payload.read() == b"hello world"

    assert captured["url"] == "https://example.com/file.txt"
    assert captured["allowed_hosts"] == ["example.com"]
    assert captured["require_https"] is True
    assert captured["max_size_bytes"] == 1024
    assert captured["timeout"] == 3.5


def test_text_content_retriever_handles_inline_strings(loader):
    request = DocumentSourceRequest(raw_input="# Heading\n\nSome text", remote_options=None)
    source = loader.load(request)

    assert source.display_name == "inline-text"
    assert source.payload == "# Heading\n\nSome text"


def test_local_path_retriever_requires_existing_file(tmp_path, loader):
    existing = tmp_path / "doc.txt"
    existing.write_text("content", encoding="utf-8")

    request = DocumentSourceRequest(raw_input=str(existing), remote_options=None)
    source = loader.load(request)

    assert isinstance(source.payload, Path)
    assert source.payload == existing
