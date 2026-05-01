"""Built-in lint rule modules.

Importing this package triggers each rule module to register itself with the
global :data:`all2md.linter.registry.rule_registry`.
"""

from __future__ import annotations

from all2md.linter.rules import (  # noqa: F401
    headings,
    images,
    links,
    lists,
    structure,
    tables,
    typography,
)

__all__: list[str] = []
