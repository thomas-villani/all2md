"""Built-in lint rule modules.

Importing this package triggers each rule module to register itself with the
global :data:`all2md.linter.registry.rule_registry`.
"""

from __future__ import annotations

from all2md.linter.rules import headings, links, structure, typography  # noqa: F401

__all__: list[str] = []
