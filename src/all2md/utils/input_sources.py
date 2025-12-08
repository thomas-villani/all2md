"""Abstractions for loading document sources from various locations.

This module defines the loader infrastructure that resolves user-supplied
inputs (paths, URLs, streams, etc.) into a consistent representation that
parsers can consume. The goal is to make it easy to add new retrieval
mechanisms (HTTP(S), cloud object stores, etc.) without touching parser
implementations.
"""

from __future__ import annotations

import abc
import os
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Iterable, Optional, Sequence, Union, cast
from urllib.parse import urlparse

from all2md.constants import DEFAULT_ROBOTS_TXT_POLICY, DEFAULT_USER_AGENT, RobotsTxtPolicy
from all2md.exceptions import DependencyError, NetworkSecurityError, ValidationError
from all2md.options import CloneFrozenMixin
from all2md.progress import ProgressCallback, ProgressEvent
from all2md.utils.network_security import fetch_content_securely, is_network_disabled
from all2md.utils.robots_txt import get_global_checker

InputType = Union[str, Path, IO[bytes], IO[str], bytes]


def _looks_like_path(value: str) -> bool:
    """Heuristic to determine if a string appears to reference a filesystem path."""
    if not value:
        return False
    lowered = value.lower()
    if lowered.startswith(("http://", "https://", "http:/", "https:/")):
        return False
    if "\n" in value or "\r" in value:
        return False
    if "<" in value or ">" in value:
        return False
    if value.startswith((os.sep, "./", "../", "~")):
        return True
    if os.altsep and os.altsep in value:
        return True
    if os.sep in value:
        return True
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return True
    suffix = Path(value).suffix
    return bool(suffix)


class NamedBytesIO(BytesIO):
    """BytesIO variant that carries a display name for downstream consumers."""

    def __init__(self, initial_bytes: bytes, name: str | None = None) -> None:
        """Initialize a named bytes IO stream.

        Parameters
        ----------
        initial_bytes : bytes
            Initial byte content
        name : str or None, optional
            Display name for the stream

        """
        super().__init__(initial_bytes)
        self._display_name = name or "inline-bytes"

    @property
    def name(self) -> str:
        """Best-effort filename used for format detection and logging."""
        return self._display_name


@dataclass(frozen=True)
class RemoteInputOptions(CloneFrozenMixin):
    """Global options controlling remote document retrieval."""

    allow_remote_input: bool = field(
        default=False,
        metadata={
            "help": "Allow fetching documents from remote locations.",
            "importance": "core",
            "cli_name": "enabled",
        },
    )
    allowed_hosts: list[str] | None = field(
        default=None,
        metadata={
            "help": "Restrict remote input to these hostnames or CIDR ranges (comma separated).",
            "importance": "security",
        },
    )
    require_https: bool = field(
        default=True,
        metadata={
            "help": "Require HTTPS for remote document retrieval.",
            "importance": "security",
            "cli_negates_default": True,
            "cli_negated_name": "allow-http",
        },
    )
    timeout: float = field(
        default=10.0,
        metadata={
            "help": "Network timeout in seconds for remote document retrieval.",
            "importance": "security",
        },
    )
    max_size_bytes: int = field(
        default=20 * 1024 * 1024,
        metadata={
            "help": "Maximum allowed remote document size in bytes.",
            "importance": "security",
        },
    )
    user_agent: str = field(
        default=DEFAULT_USER_AGENT,
        metadata={"help": "User-Agent included on header for requests", "importance": "security"},
    )
    follow_robots_txt: RobotsTxtPolicy | str = field(
        default=DEFAULT_ROBOTS_TXT_POLICY,
        metadata={
            "help": "Policy for respecting robots.txt: 'strict' blocks disallowed URLs, "
            "'warn' logs warnings, 'ignore' skips checks.",
            "importance": "security",
            "choices": ("strict", "warn", "ignore"),
        },
    )

    def __post_init__(self) -> None:
        """Normalize allowed_hosts to a list and validate follow_robots_txt value after initialization."""
        if self.allowed_hosts is not None:
            object.__setattr__(self, "allowed_hosts", list(self.allowed_hosts))

        # Validate and normalize follow_robots_txt
        if isinstance(self.follow_robots_txt, str):
            policy = self.follow_robots_txt.lower()
            if policy not in ("strict", "warn", "ignore"):
                msg = (
                    f"Invalid follow_robots_txt policy: {self.follow_robots_txt}. Must be 'strict', "
                    "'warn', or 'ignore'."
                )
                raise ValidationError(msg)
            object.__setattr__(self, "follow_robots_txt", policy)


@dataclass(frozen=True)
class DocumentSourceRequest:
    """Encapsulates the input the user provided along with loader options."""

    raw_input: InputType
    remote_options: RemoteInputOptions | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[ProgressCallback] = None

    def scheme(self) -> str | None:
        """Best-effort scheme detection for string inputs."""
        value = self.raw_input
        if isinstance(value, (str, Path)):
            text = str(value)
            lower_text = text.lower()
            if "://" in lower_text:
                return lower_text.split("://", 1)[0]
            if lower_text.startswith(("http:/", "https:/")):
                return lower_text.split(":/", 1)[0]
        return None


@dataclass
class DocumentSource:
    """Resolved document payload returned by retrievers."""

    payload: Union[str, Path, IO[bytes], IO[str], bytes]
    display_name: str
    origin_uri: str | None = None

    def as_path(self) -> Path | None:
        """Return payload as Path when available."""
        if isinstance(self.payload, Path):
            return self.payload
        if isinstance(self.payload, str):
            return Path(self.payload)
        return None


class DocumentSourceRetriever(abc.ABC):
    """Base class for individual source retrievers."""

    priority: int = 0  # higher numbers run earlier

    @abc.abstractmethod
    def can_handle(self, request: DocumentSourceRequest) -> bool:
        """Return True if this retriever can resolve the request."""

    @abc.abstractmethod
    def load(self, request: DocumentSourceRequest) -> DocumentSource:
        """Load the document and return a resolved source.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request containing input source and optional progress callback

        Returns
        -------
        DocumentSource
            Resolved document source with payload

        Notes
        -----
        Retrievers should emit progress events via request.progress_callback
        when performing long-running operations like network downloads.

        """


@dataclass
class DocumentSourceLoader:
    """Coordinator that dispatches requests to registered retrievers."""

    retrievers: Sequence[DocumentSourceRetriever]

    def __post_init__(self) -> None:
        """Validate and sort retrievers by priority after initialization."""
        if not self.retrievers:
            raise ValidationError("DocumentSourceLoader requires at least one retriever")
        # Normalize ordering so higher priority retrievers run first
        object.__setattr__(self, "retrievers", tuple(sorted(self.retrievers, key=lambda r: -r.priority)))

    def load(self, request: DocumentSourceRequest) -> DocumentSource:
        """Resolve a request by delegating to the first capable retriever."""
        for retriever in self.retrievers:
            if retriever.can_handle(request):
                return retriever.load(request)

        type_name = type(request.raw_input).__name__
        raise ValidationError(
            f"Unsupported input type: {type_name}",
            parameter_name="source",
            parameter_value=request.raw_input,
        )


# Note: file:// URLs are not currently supported. Use direct filesystem paths instead.
class LocalPathRetriever(DocumentSourceRetriever):
    """Resolver for local filesystem paths.

    Notes
    -----
    file:// URL scheme is not currently supported. Use direct filesystem paths
    (e.g., "/path/to/file" instead of "file:///path/to/file").

    """

    priority = 100

    def can_handle(self, request: DocumentSourceRequest) -> bool:
        """Check if request can be handled as a local file path.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request to check

        Returns
        -------
        bool
            True if the request is a local file path, False otherwise

        """
        value = request.raw_input
        if isinstance(value, Path):
            return value.exists() and value.is_file()
        if isinstance(value, str) and "://" not in value and _looks_like_path(value):
            return Path(value).exists()
        return False

    def load(self, request: DocumentSourceRequest) -> DocumentSource:
        """Load a document from a local file path.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request containing the file path

        Returns
        -------
        DocumentSource
            The loaded document source

        Raises
        ------
        ValidationError
            If the path doesn't exist or is not a file

        """
        value = request.raw_input
        path = Path(value) if isinstance(value, (str, Path)) else Path(str(value))
        if not path.exists():
            raise ValidationError(
                f"Path does not exist: {path}",
                parameter_name="source",
                parameter_value=value,
            )
        if not path.is_file():
            raise ValidationError(
                f"Path is not a file: {path}",
                parameter_name="source",
                parameter_value=value,
            )
        return DocumentSource(payload=path, display_name=path.name, origin_uri=str(path))


class HttpRetriever(DocumentSourceRetriever):
    """Resolver that downloads documents from HTTP(S) URLs."""

    priority = 80

    def can_handle(self, request: DocumentSourceRequest) -> bool:
        """Check if request can be handled as an HTTP(S) URL.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request to check

        Returns
        -------
        bool
            True if the request is an HTTP(S) URL, False otherwise

        """
        return request.scheme() in {"http", "https"}

    def load(self, request: DocumentSourceRequest) -> DocumentSource:
        """Load a document from an HTTP(S) URL.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request containing the URL

        Returns
        -------
        DocumentSource
            The loaded document source

        Raises
        ------
        ValidationError
            If network access is disabled or remote input is not allowed
        NetworkSecurityError
            If the request fails security checks
        DependencyError
            If httpx is not installed

        """
        if is_network_disabled():
            raise ValidationError(
                "Network access is disabled via ALL2MD_DISABLE_NETWORK.",
                parameter_name="source",
                parameter_value=request.raw_input,
            )

        remote_options = request.remote_options or RemoteInputOptions()
        if not remote_options.allow_remote_input:
            raise ValidationError(
                "Remote document fetching is disabled. Enable allow_remote_input (`--remote-input-enabled`) "
                "to proceed.",
                parameter_name="remote_input.allow_remote_input",
                parameter_value=remote_options.allow_remote_input,
            )

        url = str(request.raw_input)
        parsed = urlparse(url)
        if remote_options.require_https and parsed.scheme != "https":
            raise ValidationError(
                "Remote input requires HTTPS. Set require_https=False to allow HTTP sources.",
                parameter_name="remote_input.require_https",
                parameter_value=remote_options.require_https,
            )

        # Check robots.txt if policy is not "ignore"
        policy = cast(RobotsTxtPolicy, remote_options.follow_robots_txt)
        if policy != "ignore":
            checker = get_global_checker()
            allowed, crawl_delay = checker.can_fetch(
                url=url,
                remote_options=remote_options,
                policy=policy,
            )

            # Apply crawl delay if specified
            if crawl_delay is not None and crawl_delay > 0:
                time.sleep(crawl_delay)

        # Emit download started event
        if request.progress_callback:
            try:
                request.progress_callback(
                    ProgressEvent(
                        event_type="started",
                        message=f"Downloading {url}",
                        current=0,
                        total=0,
                        metadata={"item_type": "download", "url": url},
                    )
                )
            except Exception:  # pragma: no cover - don't let callback errors break fetch
                pass

        try:
            content = fetch_content_securely(
                url=url,
                allowed_hosts=list(remote_options.allowed_hosts) if remote_options.allowed_hosts is not None else None,
                require_https=remote_options.require_https,
                max_size_bytes=remote_options.max_size_bytes,
                timeout=remote_options.timeout,
                user_agent=remote_options.user_agent,
            )

            # Emit download completed event
            if request.progress_callback:

                try:
                    request.progress_callback(
                        ProgressEvent(
                            event_type="item_done",
                            message=f"Downloaded {url}",
                            current=1,
                            total=1,
                            metadata={"item_type": "download", "bytes": len(content), "url": url},
                        )
                    )
                except Exception:  # pragma: no cover - don't let callback errors break processing
                    pass

        except NetworkSecurityError:
            # Emit error event
            if request.progress_callback:

                try:
                    request.progress_callback(
                        ProgressEvent(
                            event_type="error",
                            message=f"Download failed: {url}",
                            current=0,
                            total=1,
                            metadata={"error": "Security error", "stage": "download", "url": url},
                        )
                    )
                except Exception:  # pragma: no cover
                    pass
            raise
        except ImportError as exc:
            raise DependencyError(
                "remote_input",
                missing_packages=[("httpx", ">=0.28.1")],
                install_command="pip install all2md[http]",
                original_import_error=exc,
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive fallback
            # Emit error event
            if request.progress_callback:

                try:
                    request.progress_callback(
                        ProgressEvent(
                            event_type="error",
                            message=f"Download failed: {url}",
                            current=0,
                            total=1,
                            metadata={"error": str(exc), "stage": "download", "url": url},
                        )
                    )
                except Exception:  # pragma: no cover
                    pass
            raise NetworkSecurityError(f"Failed to fetch remote document: {exc}") from exc

        name_hint = Path(parsed.path).name or "remote-document"
        payload = NamedBytesIO(content, name=name_hint)
        return DocumentSource(payload=payload, display_name=payload.name, origin_uri=url)


class BytesRetriever(DocumentSourceRetriever):
    """Resolver for raw byte strings."""

    priority = 50

    def can_handle(self, request: DocumentSourceRequest) -> bool:
        """Check if request can be handled as raw bytes.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request to check

        Returns
        -------
        bool
            True if the request is raw bytes, False otherwise

        """
        return isinstance(request.raw_input, bytes)

    def load(self, request: DocumentSourceRequest) -> DocumentSource:
        """Load a document from raw bytes.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request containing raw bytes

        Returns
        -------
        DocumentSource
            The loaded document source

        """
        # We know raw_input is bytes because can_handle() checks isinstance(request.raw_input, bytes)
        assert isinstance(request.raw_input, bytes)
        payload = NamedBytesIO(request.raw_input)
        return DocumentSource(payload=payload, display_name=payload.name, origin_uri=None)


class FileObjectRetriever(DocumentSourceRetriever):
    """Resolver for existing file-like objects."""

    priority = 40

    def can_handle(self, request: DocumentSourceRequest) -> bool:
        """Check if request can be handled as a file-like object.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request to check

        Returns
        -------
        bool
            True if the request is a file-like object, False otherwise

        """
        value = request.raw_input
        return hasattr(value, "read") and not isinstance(value, (str, bytes, Path))

    def load(self, request: DocumentSourceRequest) -> DocumentSource:
        """Load a document from a file-like object.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request containing the file-like object

        Returns
        -------
        DocumentSource
            The loaded document source

        """
        stream = request.raw_input
        display_name = getattr(stream, "name", "stream")
        return DocumentSource(payload=stream, display_name=str(display_name), origin_uri=None)


class TextContentRetriever(DocumentSourceRetriever):
    """Resolver for inline string content."""

    priority = 30

    def can_handle(self, request: DocumentSourceRequest) -> bool:
        """Check if request can be handled as inline text content.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request to check

        Returns
        -------
        bool
            True if the request is inline text, False otherwise

        """
        value = request.raw_input
        if not isinstance(value, str):
            return False

        if os.path.exists(value):
            return False
        return True

    def load(self, request: DocumentSourceRequest) -> DocumentSource:
        """Load a document from inline text content.

        Parameters
        ----------
        request : DocumentSourceRequest
            The request containing inline text

        Returns
        -------
        DocumentSource
            The loaded document source

        """
        text = request.raw_input
        return DocumentSource(payload=text, display_name="inline-text", origin_uri=None)


DEFAULT_RETRIEVERS: tuple[DocumentSourceRetriever, ...] = (
    LocalPathRetriever(),
    HttpRetriever(),
    BytesRetriever(),
    FileObjectRetriever(),
    TextContentRetriever(),
)


def default_loader(additional_retrievers: Optional[Iterable[DocumentSourceRetriever]] = None) -> DocumentSourceLoader:
    """Create a loader with built-in retrievers and optional extensions."""
    retriever_list: list[DocumentSourceRetriever] = list(DEFAULT_RETRIEVERS)
    if additional_retrievers:
        retriever_list.extend(additional_retrievers)
    return DocumentSourceLoader(retrievers=retriever_list)
