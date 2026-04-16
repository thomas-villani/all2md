"""Rule registry for the linter.

Mirrors the singleton pattern used by :class:`all2md.transforms.registry.TransformRegistry`:
``__new__``-based singleton, lazy plugin discovery via entry points, and a
small lookup/listing API. Built-in rules register themselves when
``all2md.linter.rules`` (the rule package) is imported.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Iterable, Optional

from all2md.linter.rule import LintRule

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "all2md.lint_rules"


class RuleRegistry:
    """Singleton registry mapping rule codes to ``LintRule`` classes."""

    _instance: Optional["RuleRegistry"] = None
    _rules: dict[str, type[LintRule]]
    _initialized: bool

    def __new__(cls) -> "RuleRegistry":
        """Return the process-wide singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._rules = {}
            cls._instance._initialized = False
        return cls._instance

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._initialized = True
            self._load_builtin_rules()
            self.discover_plugins()

    @staticmethod
    def _load_builtin_rules() -> None:
        """Import the built-in rule package so each rule module registers."""
        import all2md.linter.rules  # noqa: F401

    def register(self, rule_cls: type[LintRule]) -> None:
        """Register a rule class by its ``code`` attribute."""
        code = getattr(rule_cls, "code", None)
        if not code:
            raise ValueError(f"Rule class {rule_cls.__name__} has no 'code' attribute")
        if code in self._rules and self._rules[code] is not rule_cls:
            logger.warning("Rule %s already registered, overwriting", code)
        self._rules[code] = rule_cls

    def unregister(self, code: str) -> bool:
        """Remove a registered rule by code. Returns True if found."""
        return self._rules.pop(code, None) is not None

    def get_rule(self, code: str) -> type[LintRule]:
        """Return the rule class for ``code`` or raise ``KeyError``."""
        self._ensure_initialized()
        if code not in self._rules:
            raise KeyError(f"Rule '{code}' not registered")
        return self._rules[code]

    def has_rule(self, code: str) -> bool:
        """Return True if ``code`` is registered."""
        self._ensure_initialized()
        return code in self._rules

    def list_rules(self, category: Optional[str] = None) -> list[str]:
        """List all registered rule codes, optionally filtered by category."""
        self._ensure_initialized()
        if category is None:
            return sorted(self._rules.keys())
        return sorted(code for code, cls in self._rules.items() if cls.category == category)

    def get_all_rules(self) -> list[type[LintRule]]:
        """Return all registered rule classes, sorted by code."""
        self._ensure_initialized()
        return [self._rules[code] for code in sorted(self._rules.keys())]

    def iter_rules(self) -> Iterable[type[LintRule]]:
        """Iterate over registered rule classes."""
        self._ensure_initialized()
        for code in sorted(self._rules.keys()):
            yield self._rules[code]

    def clear(self) -> None:
        """Remove every registered rule and reset initialisation state.

        Primarily intended for tests that need a clean slate.
        """
        self._rules.clear()
        self._initialized = False

    def discover_plugins(self) -> int:
        """Load rule classes from the ``all2md.lint_rules`` entry point group.

        Each entry point is expected to return a ``LintRule`` subclass.
        Failures are logged but do not abort discovery.
        """
        discovered = 0
        try:
            entry_points = importlib.metadata.entry_points()
            rule_eps = entry_points.select(group=_ENTRY_POINT_GROUP)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Entry point discovery failed: %s", exc)
            return 0

        for ep in rule_eps:
            try:
                rule_cls = ep.load()
            except Exception as exc:
                logger.warning("Failed to load lint rule entry point '%s': %s", ep.name, exc)
                continue
            if not isinstance(rule_cls, type) or not issubclass(rule_cls, LintRule):
                logger.warning("Entry point '%s' did not return a LintRule subclass", ep.name)
                continue
            self.register(rule_cls)
            discovered += 1
        return discovered


rule_registry = RuleRegistry()
