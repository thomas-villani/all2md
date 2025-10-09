from __future__ import annotations

from dataclasses import replace, dataclass, field
from typing import Any, Self

from all2md.constants import AttachmentMode, DEFAULT_ATTACHMENT_MODE, AltTextMode, DEFAULT_ALT_TEXT_MODE, \
    DEFAULT_ATTACHMENT_OUTPUT_DIR, DEFAULT_ATTACHMENT_BASE_URL, DEFAULT_EXTRACT_METADATA, DEFAULT_MAX_DOWNLOAD_BYTES

_UNSET = object()


class _CloneMixin:
    def create_updated(self, **kwargs: Any) -> Self:
        return replace(self, **kwargs)  # type: ignore


@dataclass(frozen=True)
class BaseRendererOptions(_CloneMixin):
    """Base class for all renderer options.

    This class serves as the foundation for format-specific renderer options.
    Renderers convert AST documents into various output formats (Markdown, DOCX, PDF, etc.).

    Notes
    -----
    Subclasses should define format-specific rendering options as frozen dataclass fields.

    """

    pass


@dataclass(frozen=True)
class BaseParserOptions(_CloneMixin):
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
        default=DEFAULT_ATTACHMENT_MODE,
        metadata={
            "help": "How to handle attachments/images",
            "choices": ["skip", "alt_text", "download", "base64"]
        }
    )
    alt_text_mode: AltTextMode = field(
        default=DEFAULT_ALT_TEXT_MODE,
        metadata={
            "help": "How to render alt-text content when using alt_text attachment mode",
            "choices": ["default", "plain_filename", "strict_markdown", "footnote"]
        }
    )
    attachment_output_dir: str | None = field(
        default=DEFAULT_ATTACHMENT_OUTPUT_DIR,
        metadata={"help": "Directory to save attachments when using download mode"}
    )
    attachment_base_url: str | None = field(
        default=DEFAULT_ATTACHMENT_BASE_URL,
        metadata={"help": "Base URL for resolving attachment references"}
    )
    extract_metadata: bool = field(
        default=DEFAULT_EXTRACT_METADATA,
        metadata={"help": "Extract document metadata as YAML front matter"}
    )
    max_asset_bytes: int = field(
        default=DEFAULT_MAX_DOWNLOAD_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for any single asset/download (global limit)",
            "type": int
        }
    )

    # Advanced attachment handling options
    attachment_filename_template: str = field(
        default="{stem}_{type}{seq}.{ext}",
        metadata={"help": "Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}"}
    )
    attachment_overwrite: str = field(
        default="unique",
        metadata={
            "help": "File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'",
            "choices": ["unique", "overwrite", "skip"]
        }
    )
    attachment_deduplicate_by_hash: bool = field(
        default=False,
        metadata={"help": "Avoid saving duplicate attachments by content hash"}
    )
    attachments_footnotes_section: str | None = field(
        default="Attachments",
        metadata={"help": "Section title for footnote-style attachment references (None to disable)"}
    )