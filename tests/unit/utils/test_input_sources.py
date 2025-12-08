from io import BytesIO, StringIO
from pathlib import Path

import pytest

from all2md.exceptions import ValidationError
from all2md.utils.input_sources import (
    BytesRetriever,
    DocumentSource,
    DocumentSourceLoader,
    DocumentSourceRequest,
    FileObjectRetriever,
    LocalPathRetriever,
    NamedBytesIO,
    RemoteInputOptions,
    TextContentRetriever,
    _looks_like_path,
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

    def fake_fetch_content_securely(*, url, allowed_hosts, require_https, max_size_bytes, timeout, user_agent):
        captured["url"] = url
        captured["allowed_hosts"] = allowed_hosts
        captured["require_https"] = require_https
        captured["max_size_bytes"] = max_size_bytes
        captured["timeout"] = timeout
        captured["user_agent"] = user_agent
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


def test_http_retriever_empty_allowlist_denies_all_hosts(monkeypatch, loader):
    """Test that an empty allowed_hosts list denies all remote hosts.

    This is a security test to verify that allowed_hosts=[] is treated
    differently from allowed_hosts=None. An empty list should deny all hosts,
    while None allows all hosts (with a warning).
    """
    captured = {}

    def fake_fetch_content_securely(*, url, allowed_hosts, require_https, max_size_bytes, timeout, user_agent):
        captured["allowed_hosts"] = allowed_hosts
        return b"should not reach here"

    monkeypatch.setattr("all2md.utils.input_sources.fetch_content_securely", fake_fetch_content_securely)

    # Create options with empty allowlist (should deny all)
    remote_options = RemoteInputOptions(
        allow_remote_input=True,
        allowed_hosts=[],  # Empty list should mean "deny all"
    )
    request = DocumentSourceRequest(raw_input="https://example.com/file.txt", remote_options=remote_options)

    # Attempt to load - should call fetch_content_securely with empty list
    loader.load(request)

    # Verify that empty list was passed (not None)
    assert captured["allowed_hosts"] == []
    assert captured["allowed_hosts"] is not None


class TestDocumentSource:
    """Tests for the DocumentSource dataclass."""

    def test_as_path_with_path_payload(self):
        """Test as_path returns Path when payload is a Path."""
        source = DocumentSource(payload=Path("/some/file.txt"), display_name="file.txt")
        assert source.as_path() == Path("/some/file.txt")

    def test_as_path_with_string_payload(self):
        """Test as_path returns Path when payload is a string path."""
        source = DocumentSource(payload="/some/file.txt", display_name="file.txt")
        assert source.as_path() == Path("/some/file.txt")

    def test_as_path_with_bytes_payload(self):
        """Test as_path returns None when payload is bytes."""
        source = DocumentSource(payload=b"content", display_name="data")
        assert source.as_path() is None

    def test_as_path_with_stream_payload(self):
        """Test as_path returns None when payload is a stream."""
        source = DocumentSource(payload=BytesIO(b"content"), display_name="stream")
        assert source.as_path() is None

    def test_origin_uri_default(self):
        """Test origin_uri defaults to None."""
        source = DocumentSource(payload="content", display_name="test")
        assert source.origin_uri is None

    def test_origin_uri_set(self):
        """Test origin_uri can be set."""
        source = DocumentSource(payload="content", display_name="test", origin_uri="https://example.com")
        assert source.origin_uri == "https://example.com"


class TestNamedBytesIO:
    """Tests for the NamedBytesIO class."""

    def test_name_property(self):
        """Test name property returns provided name."""
        stream = NamedBytesIO(b"content", name="test.pdf")
        assert stream.name == "test.pdf"

    def test_default_name(self):
        """Test default name when not provided."""
        stream = NamedBytesIO(b"content")
        assert stream.name == "inline-bytes"

    def test_read_content(self):
        """Test reading content from NamedBytesIO."""
        stream = NamedBytesIO(b"hello world", name="test.txt")
        assert stream.read() == b"hello world"

    def test_seek_and_read(self):
        """Test seeking and reading from NamedBytesIO."""
        stream = NamedBytesIO(b"hello world")
        stream.seek(6)
        assert stream.read() == b"world"


class TestLooksLikePath:
    """Tests for the _looks_like_path function."""

    def test_empty_string(self):
        """Test empty string is not a path."""
        assert _looks_like_path("") is False

    def test_http_url(self):
        """Test HTTP URL is not a path."""
        assert _looks_like_path("http://example.com/file.txt") is False

    def test_https_url(self):
        """Test HTTPS URL is not a path."""
        assert _looks_like_path("https://example.com/file.txt") is False

    def test_absolute_path(self):
        """Test absolute path is recognized."""
        assert _looks_like_path("/home/user/file.txt") is True

    def test_relative_path_dot(self):
        """Test relative path starting with ./ is recognized."""
        assert _looks_like_path("./file.txt") is True

    def test_relative_path_dotdot(self):
        """Test relative path starting with ../ is recognized."""
        assert _looks_like_path("../file.txt") is True

    def test_home_path(self):
        """Test path starting with ~ is recognized."""
        assert _looks_like_path("~/file.txt") is True

    def test_path_with_extension(self):
        """Test filename with extension is recognized."""
        assert _looks_like_path("file.txt") is True

    def test_multiline_string(self):
        """Test multiline string is not a path."""
        assert _looks_like_path("line1\nline2") is False

    def test_string_with_angle_brackets(self):
        """Test string with angle brackets is not a path."""
        assert _looks_like_path("<html>") is False
        assert _looks_like_path("file>output") is False

    def test_windows_absolute_path(self):
        """Test Windows absolute path is recognized."""
        assert _looks_like_path("C:/Users/file.txt") is True
        assert _looks_like_path("D:\\folder\\file.txt") is True


class TestBytesRetriever:
    """Tests for the BytesRetriever class."""

    def test_can_handle_bytes(self):
        """Test can_handle returns True for bytes."""
        retriever = BytesRetriever()
        request = DocumentSourceRequest(raw_input=b"binary content")
        assert retriever.can_handle(request) is True

    def test_can_handle_string(self):
        """Test can_handle returns False for string."""
        retriever = BytesRetriever()
        request = DocumentSourceRequest(raw_input="string content")
        assert retriever.can_handle(request) is False

    def test_load_bytes(self):
        """Test loading bytes content."""
        retriever = BytesRetriever()
        request = DocumentSourceRequest(raw_input=b"hello world")
        source = retriever.load(request)

        assert source.display_name == "inline-bytes"
        assert source.payload.read() == b"hello world"
        assert source.origin_uri is None


class TestFileObjectRetriever:
    """Tests for the FileObjectRetriever class."""

    def test_can_handle_bytesio(self):
        """Test can_handle returns True for BytesIO."""
        retriever = FileObjectRetriever()
        request = DocumentSourceRequest(raw_input=BytesIO(b"content"))
        assert retriever.can_handle(request) is True

    def test_can_handle_stringio(self):
        """Test can_handle returns True for StringIO."""
        retriever = FileObjectRetriever()
        request = DocumentSourceRequest(raw_input=StringIO("content"))
        assert retriever.can_handle(request) is True

    def test_can_handle_string(self):
        """Test can_handle returns False for string."""
        retriever = FileObjectRetriever()
        request = DocumentSourceRequest(raw_input="string content")
        assert retriever.can_handle(request) is False

    def test_can_handle_bytes(self):
        """Test can_handle returns False for bytes."""
        retriever = FileObjectRetriever()
        request = DocumentSourceRequest(raw_input=b"bytes content")
        assert retriever.can_handle(request) is False

    def test_load_stream(self):
        """Test loading stream content."""
        retriever = FileObjectRetriever()
        stream = BytesIO(b"hello world")
        request = DocumentSourceRequest(raw_input=stream)
        source = retriever.load(request)

        assert source.display_name == "stream"
        assert source.payload is stream
        assert source.origin_uri is None

    def test_load_named_stream(self):
        """Test loading named stream."""
        retriever = FileObjectRetriever()
        stream = NamedBytesIO(b"content", name="test.pdf")
        request = DocumentSourceRequest(raw_input=stream)
        source = retriever.load(request)

        assert source.display_name == "test.pdf"


class TestTextContentRetriever:
    """Tests for the TextContentRetriever class."""

    def test_can_handle_inline_text(self):
        """Test can_handle returns True for inline text."""
        retriever = TextContentRetriever()
        request = DocumentSourceRequest(raw_input="# Markdown\n\nContent here")
        assert retriever.can_handle(request) is True

    def test_can_handle_bytes(self):
        """Test can_handle returns False for bytes."""
        retriever = TextContentRetriever()
        request = DocumentSourceRequest(raw_input=b"bytes content")
        assert retriever.can_handle(request) is False

    def test_load_inline_text(self):
        """Test loading inline text content."""
        retriever = TextContentRetriever()
        request = DocumentSourceRequest(raw_input="# Heading\n\nParagraph")
        source = retriever.load(request)

        assert source.display_name == "inline-text"
        assert source.payload == "# Heading\n\nParagraph"
        assert source.origin_uri is None


class TestLocalPathRetriever:
    """Tests for the LocalPathRetriever class."""

    def test_can_handle_existing_file(self, tmp_path):
        """Test can_handle returns True for existing file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        retriever = LocalPathRetriever()
        request = DocumentSourceRequest(raw_input=file_path)
        assert retriever.can_handle(request) is True

    def test_can_handle_nonexistent_file(self, tmp_path):
        """Test can_handle returns False for non-existent file."""
        retriever = LocalPathRetriever()
        request = DocumentSourceRequest(raw_input=tmp_path / "nonexistent.txt")
        assert retriever.can_handle(request) is False

    def test_can_handle_string_path(self, tmp_path):
        """Test can_handle works with string path."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        retriever = LocalPathRetriever()
        request = DocumentSourceRequest(raw_input=str(file_path))
        assert retriever.can_handle(request) is True

    def test_load_file(self, tmp_path):
        """Test loading file from path."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        retriever = LocalPathRetriever()
        request = DocumentSourceRequest(raw_input=file_path)
        source = retriever.load(request)

        assert source.payload == file_path
        assert source.display_name == "test.txt"
        assert str(file_path) in source.origin_uri

    def test_load_nonexistent_raises(self, tmp_path):
        """Test loading non-existent file raises ValidationError."""
        retriever = LocalPathRetriever()
        request = DocumentSourceRequest(raw_input=tmp_path / "nonexistent.txt")

        with pytest.raises(ValidationError):
            retriever.load(request)

    def test_load_directory_raises(self, tmp_path):
        """Test loading directory raises ValidationError."""
        retriever = LocalPathRetriever()
        request = DocumentSourceRequest(raw_input=tmp_path)

        # Directory exists but is not a file
        with pytest.raises(ValidationError):
            retriever.load(request)


class TestDocumentSourceLoader:
    """Tests for the DocumentSourceLoader class."""

    def test_requires_retrievers(self):
        """Test loader requires at least one retriever."""
        with pytest.raises(ValidationError):
            DocumentSourceLoader(retrievers=[])

    def test_dispatches_to_first_matching(self, tmp_path):
        """Test loader dispatches to first capable retriever."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        loader = DocumentSourceLoader(retrievers=[LocalPathRetriever(), TextContentRetriever()])
        request = DocumentSourceRequest(raw_input=file_path)
        source = loader.load(request)

        assert source.payload == file_path

    def test_raises_for_unsupported_input(self):
        """Test loader raises for unsupported input type."""
        loader = DocumentSourceLoader(retrievers=[BytesRetriever()])
        request = DocumentSourceRequest(raw_input=12345)  # Not a supported type

        with pytest.raises(ValidationError) as excinfo:
            loader.load(request)

        assert "Unsupported input type" in str(excinfo.value)


class TestDocumentSourceRequest:
    """Tests for the DocumentSourceRequest class."""

    def test_scheme_http(self):
        """Test scheme detection for HTTP URL."""
        request = DocumentSourceRequest(raw_input="http://example.com/file.txt")
        assert request.scheme() == "http"

    def test_scheme_https(self):
        """Test scheme detection for HTTPS URL."""
        request = DocumentSourceRequest(raw_input="https://example.com/file.txt")
        assert request.scheme() == "https"

    def test_scheme_none_for_path(self):
        """Test scheme is None for file path."""
        request = DocumentSourceRequest(raw_input="/path/to/file.txt")
        assert request.scheme() is None

    def test_scheme_path_object(self):
        """Test scheme is None for Path object."""
        request = DocumentSourceRequest(raw_input=Path("/path/to/file.txt"))
        assert request.scheme() is None

    def test_metadata_default_empty(self):
        """Test metadata defaults to empty dict."""
        request = DocumentSourceRequest(raw_input="content")
        assert request.metadata == {}


class TestRemoteInputOptions:
    """Tests for the RemoteInputOptions class."""

    def test_defaults(self):
        """Test default values."""
        options = RemoteInputOptions()
        assert options.allow_remote_input is False
        assert options.allowed_hosts is None
        assert options.require_https is True
        assert options.timeout == 10.0
        assert options.max_size_bytes == 20 * 1024 * 1024

    def test_allowed_hosts_normalized(self):
        """Test allowed_hosts is normalized to list."""
        options = RemoteInputOptions(allowed_hosts=["example.com", "other.com"])
        assert options.allowed_hosts == ["example.com", "other.com"]

    def test_invalid_robots_policy_raises(self):
        """Test invalid robots.txt policy raises ValidationError."""
        with pytest.raises(ValidationError):
            RemoteInputOptions(follow_robots_txt="invalid")

    def test_valid_robots_policies(self):
        """Test valid robots.txt policies are accepted."""
        for policy in ["strict", "warn", "ignore"]:
            options = RemoteInputOptions(follow_robots_txt=policy)
            assert options.follow_robots_txt == policy
