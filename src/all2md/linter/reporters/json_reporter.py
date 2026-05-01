"""Machine-readable JSON reporter."""

from __future__ import annotations

import json
from typing import Any, Sequence

from all2md.linter.reporters import ReportableResult, Reporter
from all2md.linter.runner import LintFixResult, LintResult


class JsonReporter(Reporter):
    """Render lint results as JSON suitable for CI consumption.

    Schema (lint-only)::

        {
            "summary": {"files": int, "violations": int, "errors": int,
                        "warnings": int, "info": int},
            "results": [{
                "file_path": str | null,
                "rules_checked": int,
                "error_count": int, "warning_count": int, "info_count": int,
                "violations": [ { ...violation fields... } ]
            }]
        }

    When at least one input is a :class:`LintFixResult`, the summary gains
    ``applied`` and ``skipped`` totals, and each result entry gains
    ``applied_fixes``, ``skipped_fixes``, and ``pre_fix_violations``. The
    ``violations`` field on a fix result is the *post-fix* violations —
    what the user still needs to address.
    """

    def render(self, results: Sequence[ReportableResult]) -> str:
        """Serialize the results to a JSON string matching the schema in the class docstring."""
        any_fix = any(isinstance(r, LintFixResult) for r in results)

        summary_errors = sum(_post(r).error_count for r in results)
        summary_warnings = sum(_post(r).warning_count for r in results)
        summary_infos = sum(_post(r).info_count for r in results)
        summary: dict[str, Any] = {
            "files": len(results),
            "violations": summary_errors + summary_warnings + summary_infos,
            "errors": summary_errors,
            "warnings": summary_warnings,
            "info": summary_infos,
        }
        if any_fix:
            summary["applied"] = sum(len(r.applied) for r in results if isinstance(r, LintFixResult))
            summary["skipped"] = sum(len(r.skipped_conflicts) for r in results if isinstance(r, LintFixResult))

        result_entries: list[dict[str, Any]] = []
        for r in results:
            post = _post(r)
            entry: dict[str, Any] = {
                "file_path": post.file_path,
                "rules_checked": post.rules_checked,
                "error_count": post.error_count,
                "warning_count": post.warning_count,
                "info_count": post.info_count,
                "violations": [v.to_dict() for v in post.violations],
            }
            if isinstance(r, LintFixResult):
                entry["applied_fixes"] = [af.to_dict() for af in r.applied]
                entry["skipped_fixes"] = [af.to_dict() for af in r.skipped_conflicts]
                entry["pre_fix_violations"] = [v.to_dict() for v in r.initial.violations]
                entry["rewritten"] = r.rewritten
            result_entries.append(entry)

        payload = {"summary": summary, "results": result_entries}
        return json.dumps(payload, indent=2, ensure_ascii=False)


def _post(result: ReportableResult) -> LintResult:
    """Return the post-fix :class:`LintResult` for a fix result, or the result itself."""
    if isinstance(result, LintFixResult):
        return result.final
    assert isinstance(result, LintResult)
    return result
