"""Human-readable text reporter."""

from __future__ import annotations

from typing import Sequence

from all2md.linter.reporters import ReportableResult, Reporter
from all2md.linter.runner import LintFixResult, LintResult


class TextReporter(Reporter):
    """Render lint results in a ruff-style single-line-per-violation format.

    When given :class:`LintFixResult` instances, the report prepends an
    "Applied N fixes" line per file (with the rule code + description for
    each applied fix) and adds a "deferred conflicts" footer if any fixes
    were skipped because another fix touched the same node first.
    """

    def render(self, results: Sequence[ReportableResult]) -> str:
        """Render the results as a newline-separated list plus a summary footer."""
        lines: list[str] = []
        total_errors = 0
        total_warnings = 0
        total_infos = 0
        total_applied = 0
        total_skipped = 0
        any_fix_results = False

        for result in results:
            path = result.file_path or "<stdin>"
            base = result.final if isinstance(result, LintFixResult) else result
            assert isinstance(base, LintResult)

            if isinstance(result, LintFixResult):
                any_fix_results = True
                if result.applied:
                    lines.append(f"{path}: applied {len(result.applied)} fix(es)")
                    for af in result.applied:
                        lines.append(f"    {af.rule_code} ({af.safety.label}): {af.description}")
                total_applied += len(result.applied)
                total_skipped += len(result.skipped_conflicts)

            for v in base.violations:
                line = str(v.line) if v.line is not None else "-"
                column = str(v.column) if v.column is not None else "-"
                location = f"{path}:{line}:{column}"
                lines.append(f"{location}: {v.rule_code} {v.severity.label}: {v.message}")
                if v.suggestion:
                    lines.append(f"    suggestion: {v.suggestion}")
                if v.context:
                    lines.append(f"    context: {v.context}")
            total_errors += base.error_count
            total_warnings += base.warning_count
            total_infos += base.info_count

        total = total_errors + total_warnings + total_infos
        file_count = len(results)
        file_word = "file" if file_count == 1 else "files"

        if any_fix_results:
            applied_word = "fix" if total_applied == 1 else "fixes"
            if total == 0:
                lines.append(
                    f"Applied {total_applied} {applied_word}; 0 violations remaining in {file_count} {file_word}"
                )
            else:
                lines.append(
                    f"Applied {total_applied} {applied_word}; "
                    f"{total} violations remaining "
                    f"({total_errors} errors, {total_warnings} warnings, {total_infos} info) "
                    f"in {file_count} {file_word}"
                )
            if total_skipped:
                conflict_word = "conflict" if total_skipped == 1 else "conflicts"
                lines.append(f"{total_skipped} fix(es) deferred due to {conflict_word} — re-run lint --fix to apply")
        else:
            if total == 0:
                lines.append(f"Found 0 violations in {file_count} {file_word}")
            else:
                lines.append(
                    f"Found {total} violations "
                    f"({total_errors} errors, {total_warnings} warnings, {total_infos} info) "
                    f"in {file_count} {file_word}"
                )
        return "\n".join(lines)
