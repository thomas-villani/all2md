import argparse
import logging
from pathlib import Path

import pytest

from all2md.cli.validation import (
    ValidationProblem,
    ValidationSeverity,
    collect_argument_problems,
    report_validation_problems,
    validate_arguments,
)


def make_namespace(**kwargs):
    defaults = {
        "attachment_output_dir": None,
        "attachment_mode": "download",
        "output_dir": None,
        "out": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_collect_argument_problems_includes_attachment_warning():
    parsed = make_namespace(attachment_output_dir="/tmp/out", attachment_mode="skip")

    problems = collect_argument_problems(parsed)

    assert problems == [
        ValidationProblem(
            "--attachment-output-dir specified but attachment mode is 'skip' (expected 'download')",
            ValidationSeverity.WARNING,
        )
    ]


def test_collect_argument_problems_detects_output_dir_file(tmp_path: Path):
    output_file = tmp_path / "not_a_dir"
    output_file.write_text("data", encoding="utf-8")
    parsed = make_namespace(output_dir=str(output_file))

    problems = collect_argument_problems(parsed)

    assert problems and problems[0].severity is ValidationSeverity.ERROR
    assert "must be a directory" in problems[0].message


def test_collect_argument_problems_warns_multi_file_out():
    files = [Path("a"), Path("b")]
    parsed = make_namespace(out="result.md", output_dir=None)

    problems = collect_argument_problems(parsed, files)

    assert problems and problems[0].severity is ValidationSeverity.WARNING
    assert "ignored for multiple files" in problems[0].message


def test_report_validation_problems_logs(caplog: pytest.LogCaptureFixture):
    logger = logging.getLogger("all2md.tests.validation")

    caplog.set_level(logging.INFO, logger="all2md.tests.validation")

    problems = [
        ValidationProblem("warn-msg", ValidationSeverity.WARNING),
        ValidationProblem("error-msg", ValidationSeverity.ERROR),
    ]

    has_errors = report_validation_problems(problems, logger=logger)

    assert has_errors is True
    assert "warn-msg" in caplog.text
    assert "error-msg" in caplog.text


def test_validate_arguments_uses_problem_reporting(monkeypatch):
    warnings = [
        ValidationProblem("warn-msg", ValidationSeverity.WARNING),
    ]

    created = {}

    def fake_collect(namespace, files=None):  # noqa: ANN001
        created["namespace"] = namespace
        created["files"] = files
        return warnings

    reported = {"called": False}

    def fake_report(problems, logger=None):  # noqa: ANN001
        reported["called"] = True
        return False

    monkeypatch.setattr("all2md.cli.validation.collect_argument_problems", fake_collect)
    monkeypatch.setattr("all2md.cli.validation.report_validation_problems", fake_report)

    parsed = make_namespace()
    result = validate_arguments(parsed)

    assert result is True
    assert created["namespace"] is parsed
    assert reported["called"] is True

