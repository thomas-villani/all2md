"""CLI input abstractions for handling local, remote, and stdin sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Union

InputPayload = Union[str, Path, bytes]
InputKind = Literal["local_file", "remote_uri", "stdin_bytes"]


@dataclass(frozen=True, slots=True)
class CLIInputItem:
    """Represents a single CLI input entry with context for processing."""

    raw_input: InputPayload
    kind: InputKind
    display_name: str
    path_hint: Path | None = None
    original_argument: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def is_local_file(self) -> bool:
        """Check if this input represents a local file.

        Returns
        -------
        bool
            True if the input is a local file, False otherwise

        """
        return self.kind == "local_file"

    def is_remote(self) -> bool:
        """Check if this input represents a remote URI.

        Returns
        -------
        bool
            True if the input is a remote URI, False otherwise

        """
        return self.kind == "remote_uri"

    def is_stdin(self) -> bool:
        """Check if this input represents stdin bytes.

        Returns
        -------
        bool
            True if the input is from stdin, False otherwise

        """
        return self.kind == "stdin_bytes"

    def best_path(self) -> Path | None:
        """Return the most useful Path representation for this input, when available."""
        if self.is_local_file() and isinstance(self.raw_input, Path):
            return self.raw_input
        return self.path_hint

    @property
    def name(self) -> str:
        """Return a human-friendly display name."""
        hint = self.path_hint
        if hint and hint.name:
            return hint.name
        if self.is_stdin():
            return "stdin"
        return self.display_name

    @property
    def stem(self) -> str:
        """Return the best-effort stem for this input."""
        hint = self.path_hint
        if hint and hint.stem:
            return hint.stem
        if self.is_stdin():
            return "stdin"
        if self.is_remote():
            return self._fallback_remote_stem()
        value = str(self.raw_input)
        return Path(value).stem if value else "input"

    @property
    def suffix(self) -> str:
        """Return the suffix (including leading dot) when available."""
        hint = self.path_hint
        if hint and hint.suffix:
            return hint.suffix
        return ""

    def _fallback_remote_stem(self) -> str:
        if "remote_host" in self.metadata:
            return f"{self.metadata['remote_host']}"
        return "remote"

    def derive_output_stem(self, index: int) -> str:
        """Return a deterministic stem suitable for output naming."""
        if self.path_hint and self.path_hint.stem:
            return self.path_hint.stem

        if self.is_remote():
            host = self.metadata.get("remote_host")
            if host:
                base = host.replace(".", "-")
                if self.path_hint and self.path_hint.name:
                    return Path(self.path_hint.name).stem or base
                return f"{base}-{index:04d}"
            if self.path_hint and self.path_hint.name:
                return Path(self.path_hint.name).stem or f"remote-{index:04d}"
            return f"remote-{index:04d}"

        if self.is_stdin():
            return "stdin"

        # Fallback for unexpected cases
        value = str(self.raw_input)
        stem = Path(value).stem
        return stem or f"input-{index:04d}"


__all__ = ["CLIInputItem", "InputPayload", "InputKind"]
