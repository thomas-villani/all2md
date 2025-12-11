"""Base classes for parser and renderer options.

This module defines the foundation classes for all format-specific options
used throughout the all2md conversion pipeline.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from typing import Any

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from all2md.constants import (
    DEFAULT_CREATOR,
    DEFAULT_EXTRACT_METADATA,
    DEFAULT_MAX_ASSET_SIZE_BYTES,
)
from all2md.utils.metadata import MetadataRenderPolicy

UNSET = object()


@dataclass(frozen=True)
class CloneFrozenMixin:
    """Mixin providing frozen dataclass cloning capabilities.

    This mixin adds the ability to create modified copies of frozen dataclass
    instances, which is useful for immutable configuration objects.
    """

    def create_updated(self, **kwargs: Any) -> Self:
        """Create a new instance with updated field values.

        Parameters
        ----------
        **kwargs : Any
            Field names and their new values

        Returns
        -------
        Self
            New instance with specified fields updated

        """
        return replace(self, **kwargs)


@dataclass(frozen=True)
class BaseRendererOptions(CloneFrozenMixin):
    """Base class for all renderer options.

    This class serves as the foundation for format-specific renderer options.
    Renderers convert AST documents into various output formats (Markdown, DOCX, PDF, etc.).

    Parameters
    ----------
    fail_on_resource_errors : bool, default=False
        Whether to raise RenderingError when resource loading fails (e.g., images).
        If False (default), warnings are logged but rendering continues.
        If True, rendering stops immediately on resource errors.
    max_asset_size_bytes : int
        Maximum allowed size in bytes for any single asset (images, downloads, etc.)

    Notes
    -----
    Subclasses should define format-specific rendering options as frozen dataclass fields.

    """

    fail_on_resource_errors: bool = field(
        default=False,
        metadata={
            "help": "Raise RenderingError on resource failures (images, etc.) instead of logging warnings",
            "importance": "advanced",
        },
    )
    max_asset_size_bytes: int = field(
        default=DEFAULT_MAX_ASSET_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)",
            "type": int,
            "importance": "security",
        },
    )
    metadata_policy: MetadataRenderPolicy = field(
        default_factory=MetadataRenderPolicy,
        metadata={
            "help": "Metadata rendering policy controlling which fields appear in output",
            "importance": "advanced",
        },
    )
    creator: str | None = field(
        default=DEFAULT_CREATOR,
        metadata={
            "help": "Creator application name for document metadata (e.g., 'all2md'). "
            "Set to None to disable creator metadata.",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for base renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Validate positive asset size limit
        if self.max_asset_size_bytes <= 0:
            raise ValueError(f"max_asset_size_bytes must be positive, got {self.max_asset_size_bytes}")


@dataclass(frozen=True)
class BaseParserOptions(CloneFrozenMixin):
    """Base class for all parser options.

    This class serves as the foundation for format-specific parser options.
    Parsers convert source documents into AST representation.

    For parsers that handle attachments (images, downloads, etc.), also inherit
    from AttachmentOptionsMixin to get attachment-related configuration fields.

    Parameters
    ----------
    extract_metadata : bool
        Whether to extract document metadata

    Notes
    -----
    Subclasses should define format-specific parsing options as frozen dataclass fields.

    For parsers handling binary assets (PDF, DOCX, HTML, etc.), also inherit from
    AttachmentOptionsMixin::

        @dataclass(frozen=True)
        class PdfOptions(BaseParserOptions, AttachmentOptionsMixin):
            pass

    """

    extract_metadata: bool = field(
        default=DEFAULT_EXTRACT_METADATA,
        metadata={"help": "Extract document metadata as YAML front matter", "importance": "core"},
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for base renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        pass
