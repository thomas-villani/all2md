"""Machine-readable JSON reporter."""

from __future__ import annotations

import json

from all2md.linter.reporters import Reporter
from all2md.linter.runner import LintResult


class JsonReporter(Reporter):
    """Render lint results as JSON suitable for CI consumption.

    Schema::

        {
            "summary": {
                "files": int,
                "violations": int,
                "errors": int,
                "warnings": int,
                "info": int
            },
            "results": [
                {
                    "file_path": str | null,
                    "rules_checked": int,
                    "error_count": int,
                    "warning_count": int,
                    "info_count": int,
                    "violations": [ { ...violation fields... } ]
                }
            ]
        }
    """

    def render(self, results: list[LintResult]) -> str:
        """Serialize the results to a JSON string matching the schema in the class docstring."""
        summary_errors = sum(r.error_count for r in results)
        summary_warnings = sum(r.warning_count for r in results)
        summary_infos = sum(r.info_count for r in results)

        payload = {
            "summary": {
                "files": len(results),
                "violations": summary_errors + summary_warnings + summary_infos,
                "errors": summary_errors,
                "warnings": summary_warnings,
                "info": summary_infos,
            },
            "results": [
                {
                    "file_path": r.file_path,
                    "rules_checked": r.rules_checked,
                    "error_count": r.error_count,
                    "warning_count": r.warning_count,
                    "info_count": r.info_count,
                    "violations": [v.to_dict() for v in r.violations],
                }
                for r in results
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)
