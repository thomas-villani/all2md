"""Human-readable text reporter."""

from __future__ import annotations

from all2md.linter.reporters import Reporter
from all2md.linter.runner import LintResult


class TextReporter(Reporter):
    """Render lint results in a ruff-style single-line-per-violation format."""

    def render(self, results: list[LintResult]) -> str:
        """Render the results as a newline-separated list plus a summary footer."""
        lines: list[str] = []
        total_errors = 0
        total_warnings = 0
        total_infos = 0

        for result in results:
            path = result.file_path or "<stdin>"
            for v in result.violations:
                line = str(v.line) if v.line is not None else "-"
                column = str(v.column) if v.column is not None else "-"
                location = f"{path}:{line}:{column}"
                lines.append(f"{location}: {v.rule_code} {v.severity.label}: {v.message}")
                if v.suggestion:
                    lines.append(f"    suggestion: {v.suggestion}")
                if v.context:
                    lines.append(f"    context: {v.context}")
            total_errors += result.error_count
            total_warnings += result.warning_count
            total_infos += result.info_count

        total = total_errors + total_warnings + total_infos
        file_count = len(results)
        file_word = "file" if file_count == 1 else "files"

        if total == 0:
            lines.append(f"Found 0 violations in {file_count} {file_word}")
        else:
            lines.append(
                f"Found {total} violations "
                f"({total_errors} errors, {total_warnings} warnings, {total_infos} info) "
                f"in {file_count} {file_word}"
            )
        return "\n".join(lines)
