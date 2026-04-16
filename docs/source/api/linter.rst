Linter
======

The linter inspects an all2md AST ``Document`` and reports structural,
heading, link, and typography issues via a rule-based engine. Because it
operates on the AST, it works against every format all2md can parse.

For CLI usage, rule catalogue, and configuration schema, see :doc:`../cli`
(Lint Command section) and :doc:`../configuration` (``[tool.all2md.lint]``).

Public Entry Points
-------------------

.. autosummary::
   :nosignatures:

   all2md.linter.runner.lint_document
   all2md.linter.runner.lint_file
   all2md.linter.runner.LintRunner
   all2md.linter.runner.LintResult
   all2md.linter.config.LintConfig

Violations
----------

.. autosummary::
   :nosignatures:

   all2md.linter.violations.Severity
   all2md.linter.violations.Violation

Rule Base and Registry
----------------------

Every built-in and third-party rule subclasses ``LintRule`` and is registered
with the process-wide ``rule_registry`` singleton. Plugins can register
additional rules via the ``all2md.lint_rules`` entry point group (see
:doc:`../plugins`).

.. autosummary::
   :nosignatures:

   all2md.linter.rule.LintRule
   all2md.linter.rule.LintContext
   all2md.linter.registry.RuleRegistry

The module-level ``all2md.linter.rule_registry`` instance is the preferred
access point for the singleton — import it directly rather than instantiating
``RuleRegistry`` by hand.

Reporters
---------

.. autosummary::
   :nosignatures:

   all2md.linter.reporters.Reporter
   all2md.linter.reporters.get_reporter
   all2md.linter.reporters.text.TextReporter
   all2md.linter.reporters.json_reporter.JsonReporter

Complete Module Reference
-------------------------

.. toctree::
   :maxdepth: 1

   all2md.linter
   all2md.linter.violations
   all2md.linter.rule
   all2md.linter.config
   all2md.linter.registry
   all2md.linter.runner
   all2md.linter.reporters
   all2md.linter.rules
