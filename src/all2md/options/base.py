"""Base classes for parser and renderer options.

This module defines the foundation classes for all format-specific options
used throughout the all2md conversion pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Self

from all2md.constants import (
    DEFAULT_ALT_TEXT_MODE,
    DEFAULT_ATTACHMENT_BASE_URL,
    DEFAULT_ATTACHMENT_MODE,
    DEFAULT_ATTACHMENT_OUTPUT_DIR,
    DEFAULT_EXTRACT_METADATA,
    DEFAULT_MAX_ASSET_SIZE_BYTES,
    AltTextMode,
    AttachmentMode,
)

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
        return replace(self, **kwargs)  # type: ignore


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
            "importance": "advanced"
        }
    )
    max_asset_size_bytes: int = field(
        default=DEFAULT_MAX_ASSET_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)",
            "type": int,
            "importance": "security"
        }
    )


@dataclass(frozen=True)
class BaseParserOptions(CloneFrozenMixin):
    """Base class for all parser options.

    This class serves as the foundation for format-specific parser options.
    Parsers convert source documents into AST representation.

    Parameters
    ----------
    attachment_mode : AttachmentMode
        How to handle attachments/images during parsing
    alt_text_mode : AltTextMode
        How to render alt-text content
    extract_metadata : bool
        Whether to extract document metadata

    Notes
    -----
    Subclasses should define format-specific parsing options as frozen dataclass fields.

    """

    attachment_mode: AttachmentMode = field(
        default=DEFAULT_ATTACHMENT_MODE,  # alt_text
        metadata={
            "help": "How to handle attachments/images",
            "choices": ["skip", "alt_text", "download", "base64"],
            "importance": "core"
        }
    )
    alt_text_mode: AltTextMode = field(
        default=DEFAULT_ALT_TEXT_MODE,
        metadata={
            "help": "How to render alt-text content when using alt_text attachment mode",
            "choices": ["default", "plain_filename", "strict_markdown", "footnote"],
            "importance": "core"
        }
    )
    attachment_output_dir: str | None = field(
        default=DEFAULT_ATTACHMENT_OUTPUT_DIR,
        metadata={
            "help": "Directory to save attachments when using download mode",
            "importance": "advanced"
        }
    )
    attachment_base_url: str | None = field(
        default=DEFAULT_ATTACHMENT_BASE_URL,
        metadata={
            "help": "Base URL for resolving attachment references",
            "importance": "advanced"
        }
    )
    extract_metadata: bool = field(
        default=DEFAULT_EXTRACT_METADATA,
        metadata={
            "help": "Extract document metadata as YAML front matter",
            "importance": "core"
        }
    )
    max_asset_size_bytes: int = field(
        default=DEFAULT_MAX_ASSET_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)",
            "type": int,
            "importance": "security"
        }
    )

    # Advanced attachment handling options
    attachment_filename_template: str = field(
        default="{stem}_{type}{seq}.{ext}",
        metadata={
            "help": "Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}",
            "importance": "advanced"

        }
    )
    attachment_overwrite: Literal["unique", "overwrite", "skip"] = field(
        default="unique",
        metadata={
            "help": "File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'",
            "choices": ["unique", "overwrite", "skip"],
            "importance": "advanced"
        }
    )
    attachment_deduplicate_by_hash: bool = field(
        default=False,
        metadata={
            "help": "Avoid saving duplicate attachments by content hash",
            "importance": "advanced"
        }
    )
    attachments_footnotes_section: str | None = field(
        default="Attachments",
        metadata={
            "help": "Section title for footnote-style attachment references (None to disable)",
            "importance": "advanced"

        }
    )
