"""Tests for the GitHub Action's quality gate (``scripts/action_gate.py``).

The gate's whole job is to go red, so most of these tests check that it does, in
each of the ways it can be wrong: a pattern that matches nothing, a threshold that
was never set, a document that cannot be converted, and a score below the line.
The last test runs the real script over real fixtures, because everything above it
stubs the scorer and would pass just as happily if the CLI plumbing were broken.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "action_gate.py"


def _load():
    """Import the script by path -- ``scripts/`` is not a package.

    The module has to go into ``sys.modules`` *before* it executes: ``@dataclass``
    resolves the string annotations that ``from __future__ import annotations``
    produces by looking its own module up there, and finds ``None`` otherwise.
    """
    spec = importlib.util.spec_from_file_location("action_gate", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load()


def _args(**overrides) -> argparse.Namespace:
    defaults = {
        "paths": "*.md",
        "roundtrip_fail_under": 90,
        "report_fail_under": None,
        "via": "markdown",
        "working_directory": ".",
        "executable": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestVersionResolution:
    """``@v1.10.1`` must mean all2md 1.10.1, not "newest today"."""

    @pytest.mark.parametrize(
        ("explicit", "action_ref", "expected"),
        [
            ("", "v1.10.1", "1.10.1"),
            ("", "v2.0.0-rc1", "2.0.0-rc1"),
            ("", "main", ""),
            ("", "feature/quality-gate", ""),
            ("", "a1b2c3d4e5f6", ""),
            ("", "", ""),
            ("latest", "v1.10.1", ""),
            ("1.9.0", "v1.10.1", "1.9.0"),
            ("  1.9.0  ", "", "1.9.0"),
        ],
    )
    def test_resolution(self, explicit, action_ref, expected):
        assert gate.resolve_version(explicit, action_ref) == expected

    def test_a_branch_ref_is_never_turned_into_a_pin(self):
        """A non-release ref must fall back to latest rather than invent a version."""
        assert gate.resolve_version("", "release/1.10") == ""

    @pytest.mark.parametrize(
        ("version", "extras", "expected"),
        [
            ("1.10.1", "all", "all2md[all]==1.10.1"),
            ("", "all", "all2md[all]"),
            ("1.10.1", "", "all2md==1.10.1"),
        ],
    )
    def test_pip_spec(self, version, extras, expected):
        assert gate.pip_spec(version, extras) == expected


class TestPathExpansion:
    def test_globs_are_expanded_and_sorted(self, tmp_path):
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "a.md").write_text("a")
        found = gate.expand_paths("*.md", tmp_path)
        assert [p.name for p in found] == ["a.md", "b.md"]

    def test_multiple_patterns_are_deduplicated(self, tmp_path):
        (tmp_path / "a.md").write_text("a")
        found = gate.expand_paths("*.md\n a.md, **/*.md", tmp_path)
        assert [p.name for p in found] == ["a.md"]

    def test_directories_are_not_documents(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.md").write_text("a")
        assert [p.name for p in gate.expand_paths("*", tmp_path)] == []

    def test_recursive_globs_work(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.md").write_text("a")
        assert len(gate.expand_paths("**/*.md", tmp_path)) == 1

    def test_a_pattern_matching_nothing_returns_nothing(self, tmp_path):
        assert gate.expand_paths("*.md", tmp_path) == []


class TestRefusalsToPass:
    """The three ways a green could be produced without measuring anything."""

    def test_no_matched_files_is_a_failure(self, tmp_path):
        with pytest.raises(gate.GateError, match="No files matched"):
            gate.run(_args(paths="*.md", working_directory=str(tmp_path)))

    def test_no_threshold_is_a_failure(self, tmp_path):
        (tmp_path / "a.md").write_text("hi")
        with pytest.raises(gate.GateError, match="can never fail"):
            gate.run(
                _args(
                    working_directory=str(tmp_path),
                    roundtrip_fail_under=None,
                    report_fail_under=None,
                )
            )

    def test_an_unconvertible_document_fails_rather_than_being_skipped(self, tmp_path, monkeypatch):
        (tmp_path / "a.md").write_text("hi")
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: (None, "boom", True))
        assert gate.run(_args(working_directory=str(tmp_path))) == 1

    @pytest.mark.parametrize("threshold", [-1, 101])
    def test_an_out_of_range_threshold_is_a_failure(self, tmp_path, threshold):
        (tmp_path / "a.md").write_text("hi")
        with pytest.raises(gate.GateError, match="between 0 and 100"):
            gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=threshold))


class TestScoring:
    def test_a_score_above_the_threshold_passes(self, tmp_path, monkeypatch):
        (tmp_path / "a.md").write_text("hi")
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: (95, "", True))
        assert gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=90)) == 0

    def test_a_score_below_the_threshold_fails(self, tmp_path, monkeypatch):
        (tmp_path / "a.md").write_text("hi")
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: (89, "", True))
        assert gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=90)) == 1

    def test_a_score_exactly_on_the_threshold_passes(self, tmp_path, monkeypatch):
        """``--fail-under`` means *under*, matching the CLI it wraps."""
        (tmp_path / "a.md").write_text("hi")
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: (90, "", True))
        assert gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=90)) == 0

    def test_one_bad_document_in_a_good_batch_fails_the_build(self, tmp_path, monkeypatch):
        for name in ("a.md", "b.md", "c.md"):
            (tmp_path / name).write_text("hi")
        scores = iter([(100, "", True), (50, "", True), (100, "", True)])
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: next(scores))
        assert gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=90)) == 1

    def test_every_failing_document_is_reported_not_just_the_first(self, tmp_path, monkeypatch, capsys):
        """The batched CLI aborts on the first bad file; this must not."""
        for name in ("a.md", "b.md"):
            (tmp_path / name).write_text("hi")
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: (10, "", True))
        gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=90))
        err = capsys.readouterr().err
        assert "a.md" in err and "b.md" in err

    def test_both_tools_gate_independently(self, tmp_path, monkeypatch):
        """Confidence can fail a build that fidelity would have passed."""
        (tmp_path / "a.md").write_text("hi")
        monkeypatch.setattr(
            gate,
            "score_document",
            lambda tool, *a, **k: (100, "", True) if tool == "roundtrip" else (40, "", True),
        )
        args = _args(working_directory=str(tmp_path), roundtrip_fail_under=90, report_fail_under=90)
        assert gate.run(args) == 1


class TestScoreDocument:
    """The one function that talks to the CLI, so the one that must not guess.

    Every failure here has to come back as ``None`` rather than as a number. A
    substituted score would be indistinguishable from a real one downstream, which
    is how "it reported something" quietly becomes "it measured something".
    """

    @staticmethod
    def _fake_run(monkeypatch, *, returncode=0, stdout="", stderr=""):
        import subprocess

        result = subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)
        monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: result)

    def test_a_valid_report_yields_its_score(self, monkeypatch):
        self._fake_run(monkeypatch, stdout='{"score": 87}')
        assert gate.score_document("roundtrip", Path("a.md"), "markdown") == (87, "", True)

    def test_a_single_element_list_is_unwrapped(self, monkeypatch):
        self._fake_run(monkeypatch, stdout='[{"score": 42}]')
        assert gate.score_document("report", Path("a.md"), "markdown")[0] == 42

    def test_a_nonzero_exit_reports_the_last_stderr_line(self, monkeypatch):
        self._fake_run(monkeypatch, returncode=4, stderr="noise\nError: Input file not found")
        score, note, _assessed = gate.score_document("roundtrip", Path("a.md"), "markdown")
        assert score is None and "not found" in note

    def test_a_silent_nonzero_exit_still_reports_something(self, monkeypatch):
        self._fake_run(monkeypatch, returncode=9, stderr="")
        score, note, _assessed = gate.score_document("roundtrip", Path("a.md"), "markdown")
        assert score is None and "exited 9" in note

    def test_unparseable_output_is_not_a_score(self, monkeypatch):
        self._fake_run(monkeypatch, stdout="not json at all")
        assert gate.score_document("roundtrip", Path("a.md"), "markdown")[0] is None

    def test_a_report_without_a_score_is_not_a_score(self, monkeypatch):
        """Must not become 0 -- that reads as a real, terrible score."""
        self._fake_run(monkeypatch, stdout='{"band": "high"}')
        score, note, _assessed = gate.score_document("roundtrip", Path("a.md"), "markdown")
        assert score is None and "no score" in note

    def test_an_empty_list_is_not_a_score(self, monkeypatch):
        self._fake_run(monkeypatch, stdout="[]")
        assert gate.score_document("report", Path("a.md"), "markdown")[0] is None

    def test_a_non_integer_score_is_rejected(self, monkeypatch):
        self._fake_run(monkeypatch, stdout='{"score": "high"}')
        assert gate.score_document("roundtrip", Path("a.md"), "markdown")[0] is None

    def test_via_is_only_passed_to_roundtrip(self, monkeypatch):
        seen: list[list[str]] = []

        import subprocess

        def capture(cmd, **kwargs):
            seen.append(cmd)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout='{"score": 100}', stderr="")

        monkeypatch.setattr(gate.subprocess, "run", capture)
        gate.score_document("roundtrip", Path("a.md"), "rst")
        gate.score_document("report", Path("a.md"), "rst")
        assert "--via" in seen[0] and "rst" in seen[0]
        assert "--via" not in seen[1]


class TestCalibrationWarning:
    """A threshold far below reality is the failure mode that looks like success."""

    def test_a_threshold_with_dead_headroom_is_flagged(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "a.md").write_text("hi")
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: (100, "", True))
        gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=80))
        assert "points of headroom" in capsys.readouterr().out

    def test_a_well_calibrated_threshold_is_not_flagged(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "a.md").write_text("hi")
        monkeypatch.setattr(gate, "score_document", lambda *a, **k: (100, "", True))
        gate.run(_args(working_directory=str(tmp_path), roundtrip_fail_under=95))
        assert "points of headroom" not in capsys.readouterr().out


class TestAgainstRealDocuments:
    """No stubs: the CLI plumbing either works here or nothing above it means anything."""

    @pytest.fixture
    def fixtures(self) -> Path:
        path = Path(__file__).resolve().parents[1] / "fixtures" / "documents"
        if not (path / "complex.docx").exists():
            pytest.skip("fixture documents not available")
        return path

    def test_a_real_document_scores_and_passes(self, fixtures):
        code = gate.main(
            [
                "run",
                "--paths",
                "basic.docx",
                "--working-directory",
                str(fixtures),
                "--roundtrip-fail-under",
                "90",
            ]
        )
        assert code == 0

    def test_a_real_document_below_the_line_fails(self, fixtures):
        """complex.docx round-trips at 99, so a threshold of 100 must go red."""
        code = gate.main(
            [
                "run",
                "--paths",
                "complex.docx",
                "--working-directory",
                str(fixtures),
                "--roundtrip-fail-under",
                "100",
            ]
        )
        assert code == 1

    def test_the_confidence_gate_refuses_a_corpus_it_cannot_assess(self, tmp_path):
        """The defect this gate exists to refuse, which it had itself.

        Markdown has no confidence detector, so `all2md report` returns a hardcoded 100
        with `band: "not_assessed"` for every one of these files -- an empty file, a valid
        file and a deliberately broken file alike. Reading only `score` made
        `--report-fail-under 100` a constant, which is how this repo's own root-docs gate
        ran for months.
        """
        (tmp_path / "empty.md").write_text("")
        (tmp_path / "fine.md").write_text("# Title\n\nBody text.\n")
        (tmp_path / "broken.md").write_text("| broken |\n|---\n\n### \n\n[x](\n")
        code = gate.main(
            [
                "run",
                "--paths",
                "*.md",
                "--working-directory",
                str(tmp_path),
                "--report-fail-under",
                "100",
            ]
        )
        # 2, not 1: this is a misconfigured gate, the same class as an empty glob, and it
        # must not read as "your documents failed".
        assert code == 2

    def test_the_confidence_gate_still_judges_a_format_that_has_detectors(self, fixtures):
        """The control: the refusal above must not have disabled the gate everywhere.

        Without this, deleting the confidence comparison outright would satisfy the test
        above and look like a fix. PDF is the control because it is the only producer with
        real instrumentation -- `basic.pdf` bands `high`, where every docx, pptx, html and
        markdown input bands `not_assessed`.
        """
        code = gate.main(
            [
                "run",
                "--paths",
                "basic.pdf",
                "--working-directory",
                str(fixtures),
                "--report-fail-under",
                "50",
            ]
        )
        assert code == 0

    def test_an_unassessed_document_is_not_rendered_as_a_hundred(self):
        """Printing the placeholder score is how a vacuous gate reads as a passing one."""
        row = gate.DocumentScores(path="a.md", scores={"report": None}, unassessed={"report"})
        summary = gate._summarise([row], {"report": 100}, [])
        assert "not assessed" in summary
        assert "100" not in summary.split("| `a.md` |")[1].split("\n")[0]

    def test_a_file_that_is_not_a_document_fails(self, tmp_path):
        """Garbage in must not score as missing data and slip through."""
        (tmp_path / "broken.docx").write_bytes(b"not a docx at all")
        code = gate.main(
            [
                "run",
                "--paths",
                "*.docx",
                "--working-directory",
                str(tmp_path),
                "--roundtrip-fail-under",
                "1",
            ]
        )
        assert code == 1


def test_resolve_version_subcommand_prints_a_pip_spec(capsys):
    assert gate.main(["resolve-version", "--action-ref", "v1.10.1"]) == 0
    assert capsys.readouterr().out.strip() == "all2md[all]==1.10.1"


def test_a_config_error_exits_two_not_one(tmp_path):
    """Separate a broken gate from a failing one, so CI can tell them apart."""
    assert gate.main(["run", "--paths", "*.md", "--working-directory", str(tmp_path)]) == 2


def test_the_script_is_importable_without_all2md():
    """It runs before the install step, so it must not import what it gates."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "import all2md" not in source
    assert "from all2md" not in source


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
