"""Reporters that render ``LintResult`` instances to strings.

Two reporters ship with the linter:

- ``TextReporter`` — human-readable CLI output
- ``JsonReporter`` — machine-readable output for CI

Third-party reporters can be added later; the :func:`get_reporter` factory
currently dispatches on short format names only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from all2md.linter.runner import LintResult


class Reporter(ABC):
    """Abstract base for reporters."""

    @abstractmethod
    def render(self, results: list[LintResult]) -> str:
        """Render a list of lint results to a single string."""


def get_reporter(name: str) -> Reporter:
    """Return a reporter by short name.

    Parameters
    ----------
    name : str
        One of ``"text"`` or ``"json"``.

    """
    key = name.strip().lower()
    if key in ("text", "plain", "human"):
        from all2md.linter.reporters.text import TextReporter

        return TextReporter()
    if key == "json":
        from all2md.linter.reporters.json_reporter import JsonReporter

        return JsonReporter()
    raise ValueError(f"Unknown reporter format: {name!r}")


__all__ = ["Reporter", "get_reporter"]
