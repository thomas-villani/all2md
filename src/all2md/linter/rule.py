"""Base classes for linter rules.

Rules are **not** visitors. Each rule receives a ``LintContext`` and is
free to traverse the AST however it likes — ``NodeCollector``, direct loops
over ``document.children``, or regex over text extracted via
``all2md.ast.extract_text``. This keeps rules concise and avoids
forcing every rule into the full visitor interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from all2md.linter.violations import Severity, Violation

if TYPE_CHECKING:
    from all2md.ast import Document


@dataclass(frozen=True, slots=True)
class LintContext:
    """Input passed to every ``LintRule.check()`` call."""

    document: "Document"
    file_path: Optional[str] = None
    config: dict[str, Any] = field(default_factory=dict)


class LintRule(ABC):
    """Abstract base class for lint rules.

    Subclasses must set the class-level metadata attributes (``code``, ``name``,
    ``category``, ``description``, ``default_severity``) and implement
    ``check()``.
    """

    code: str
    name: str
    category: str
    description: str
    default_severity: Severity

    @abstractmethod
    def check(self, ctx: LintContext) -> list[Violation]:
        """Inspect ``ctx.document`` and return any violations found."""

    def build_violation(
        self,
        message: str,
        *,
        severity: Optional[Severity] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
        node_type: Optional[str] = None,
        suggestion: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Violation:
        """Construct a ``Violation`` pre-populated with this rule's metadata."""
        return Violation(
            rule_code=self.code,
            rule_name=self.name,
            message=message,
            severity=severity if severity is not None else self.default_severity,
            line=line,
            column=column,
            node_type=node_type,
            suggestion=suggestion,
            context=context,
        )
