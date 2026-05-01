Linter
======

The linter inspects an all2md AST ``Document`` and reports structural,
heading, link, list, table, image, and typography issues via a rule-based
engine. Because it operates on the AST, it works against every format
all2md can parse. A subset of rules carry safe auto-fixes that the framework
applies in place when the user passes ``--fix`` (or calls
``lint_and_fix_document`` from Python).

For CLI usage, rule catalogue, and ``--fix`` documentation, see :doc:`../cli`
(Lint Command section) and :doc:`../configuration` (``[tool.all2md.lint]``).

Public Entry Points
-------------------

.. autosummary::
   :nosignatures:

   all2md.linter.runner.lint_document
   all2md.linter.runner.lint_file
   all2md.linter.runner.lint_and_fix_document
   all2md.linter.runner.lint_and_fix_file
   all2md.linter.runner.LintRunner
   all2md.linter.runner.LintResult
   all2md.linter.runner.LintFixResult
   all2md.linter.config.LintConfig

Violations
----------

.. autosummary::
   :nosignatures:

   all2md.linter.violations.Severity
   all2md.linter.violations.Violation

Auto-Fix Framework
------------------

Fixes are attached to violations via the ``Violation.fix`` field. The
framework applies them through :func:`all2md.linter.fixes.apply_fixes` (or
the ``LintRunner.lint_and_fix_*`` convenience wrappers). Rule authors call
:meth:`LintRule.build_violation` with a ``fix=LintFix(...)`` kwarg to attach
a fix.

.. autosummary::
   :nosignatures:

   all2md.linter.fixes.FixSafety
   all2md.linter.fixes.LintFix
   all2md.linter.fixes.FixContext
   all2md.linter.fixes.AppliedFix
   all2md.linter.fixes.apply_fixes

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
   all2md.linter.fixes
   all2md.linter.registry
   all2md.linter.runner
   all2md.linter.reporters
   all2md.linter.rules
