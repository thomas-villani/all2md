"""Severity enum and Violation dataclass for the linter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class Severity(IntEnum):
    """Severity levels for lint violations.

    Higher numeric value means more severe. The ordering enables simple
    threshold filtering: drop any violation whose severity is below the
    configured threshold.
    """

    INFO = 1
    WARNING = 2
    ERROR = 3

    @classmethod
    def from_name(cls, name: str) -> "Severity":
        """Parse a severity from a case-insensitive name (info/warning/error)."""
        key = name.strip().lower()
        for member in cls:
            if member.name.lower() == key:
                return member
        raise ValueError(f"Unknown severity: {name!r} (expected info, warning, or error)")

    @property
    def label(self) -> str:
        """Lowercase label suitable for human output ('error', 'warning', 'info')."""
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class Violation:
    """A single lint violation emitted by a rule."""

    rule_code: str
    rule_name: str
    message: str
    severity: Severity
    line: Optional[int] = None
    column: Optional[int] = None
    node_type: Optional[str] = None
    suggestion: Optional[str] = None
    fixable: bool = False
    context: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize the violation to a plain dict (used by the JSON reporter)."""
        return {
            "rule_code": self.rule_code,
            "rule_name": self.rule_name,
            "message": self.message,
            "severity": self.severity.label,
            "line": self.line,
            "column": self.column,
            "node_type": self.node_type,
            "suggestion": self.suggestion,
            "fixable": self.fixable,
            "context": self.context,
        }
