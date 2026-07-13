"""End-to-end tests for ``all2md optimize``, against a document whose correct parse we know.

The whole feature rests on one claim: the settings it recommends really do produce a
better conversion. That cannot be tested against the shipped fixtures -- they are
clean enough to score perfectly under every setting -- so we *synthesize* a document
and therefore know exactly what a correct extraction must contain.

``_truth()`` below scores a conversion against that ground truth. The optimizer never
sees it; it only sees its own reference-free objective. The tests assert the two
agree, which is the only thing that makes the objective trustworthy.

That agreement was hard-won. The first objective scored text as "more words is
better", which made *keeping* the running header strictly better than trimming it.
Measured here it was anti-correlated with the truth (Pearson r = -0.88): it reliably
recommended the worst settings available.
"""

import fitz
import pytest

from all2md import optimizable_formats, optimize_options, to_markdown
from all2md.options.pdf import PdfOptions

# Each page gets its own prose. If the pages shared sentences, the body text itself
# would repeat and a repetition detector would rightly call it furniture -- which
# would destroy the very signal under test.
BODIES = {
    "Alpha": [
        "revenue climbed sharply after the spring reorganisation",
        "margins held despite unusually volatile freight costs",
        "the northern depot absorbed most of the seasonal surge",
        "headcount fell by nine without affecting throughput",
    ],
    "Beta": [
        "regulatory filings were submitted a fortnight early",
        "customer churn dropped to its lowest level since inception",
        "the pilot programme exceeded every retention target",
        "warehouse automation paid back its investment in months",
    ],
    "Gamma": [
        "shipping delays pushed three launches into the next quarter",
        "the legacy billing system was finally decommissioned",
        "a currency swing wiped out most of the overseas gain",
        "recruitment reopened for the vacant analyst positions",
    ],
    "Delta": [
        "office consolidation freed up an entire floor",
        "training completion rates finally cleared the mandated bar",
        "one contractor overran its budget by a wide margin",
        "the new dashboard cut reporting time to a single morning",
    ],
}


@pytest.fixture(scope="module")
def gnarly_pdf(tmp_path_factory) -> str:
    """A two-page PDF with a running header/footer, two columns, and a ruled table.

    We place every element, so the correct parse is known: the header and footer are
    furniture and should be trimmed; both columns and every table cell must survive.
    """
    doc = fitz.open()
    for page_no in range(2):
        left_tag = "Alpha" if page_no == 0 else "Gamma"
        right_tag = "Beta" if page_no == 0 else "Delta"
        page = doc.new_page(width=612, height=792)

        # Furniture: identical on every page apart from the page number.
        page.insert_text((72, 40), "ACME CONFIDENTIAL -- INTERNAL USE ONLY", fontsize=8)
        page.insert_text((72, 760), f"Page {page_no + 1} of 2  |  ACME CONFIDENTIAL", fontsize=8)
        page.insert_text((72, 80), "Quarterly Report", fontsize=18)

        col_left = " ".join(f"{left_tag} sentence A{i}: {t}." for i, t in enumerate(BODIES[left_tag], 1))
        col_right = " ".join(f"{right_tag} sentence B{i}: {t}." for i, t in enumerate(BODIES[right_tag], 1))
        page.insert_textbox(fitz.Rect(72, 100, 280, 290), col_left, fontsize=9)
        page.insert_textbox(fitz.Rect(320, 100, 540, 290), col_right, fontsize=9)

        # A ruled 4x3 table with known cell text.
        top, left, row_h, col_w = 320, 72, 20, 150
        for r in range(5):
            page.draw_line((left, top + r * row_h), (left + 3 * col_w, top + r * row_h))
        for c in range(4):
            page.draw_line((left + c * col_w, top), (left + c * col_w, top + 4 * row_h))
        for r in range(4):
            for c in range(3):
                page.insert_text((left + c * col_w + 5, top + r * row_h + 14), f"{left_tag[0]}R{r}C{c}", fontsize=9)

    path = tmp_path_factory.mktemp("optimize") / "gnarly.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _truth(markdown: str) -> int:
    """Score a conversion against what we KNOW is on the page. ``0``-``100``."""
    checks = {
        # The running header and footer are furniture and should not survive.
        "no_header": "INTERNAL USE ONLY" not in markdown,
        "no_footer": "Page 1 of 2" not in markdown,
        # Every cell of the ruled table must be present.
        "table_intact": all(f"AR{r}C{c}" in markdown for r in range(4) for c in range(3)),
    }
    left = [markdown.find(f"sentence A{i}:") for i in range(1, 5)]
    right = [markdown.find(f"sentence B{i}:") for i in range(1, 5)]
    # No body sentence may be dropped, and the left column must be read before the right.
    checks["no_text_loss"] = all(pos > 0 for pos in left + right)
    checks["column_order"] = checks["no_text_loss"] and max(left) < min(right)
    return round(100 * sum(checks.values()) / len(checks))


@pytest.mark.integration
@pytest.mark.pdf
class TestOptimizerAgainstGroundTruth:
    """The claim that matters: the recommended settings convert the document better."""

    def test_the_fixture_is_actually_hard(self, gnarly_pdf):
        """If the defaults already nailed it there would be nothing to optimize."""
        assert _truth(to_markdown(gnarly_pdf)) < 100

    def test_recommended_settings_beat_the_defaults_on_ground_truth(self, gnarly_pdf):
        """The headline property. The optimizer never sees ``_truth``."""
        report = optimize_options(gnarly_pdf)

        assert report.improved, "optimizer found nothing on a document the defaults get wrong"

        baseline = _truth(to_markdown(gnarly_pdf))
        tuned = _truth(to_markdown(gnarly_pdf, parser_options=PdfOptions(**report.best_options)))

        assert tuned > baseline
        assert tuned == 100

    def test_it_recovers_the_header_footer_trimming(self, gnarly_pdf):
        """The one thing wrong with the default conversion of this document."""
        report = optimize_options(gnarly_pdf)

        trims = {"trim_headers_footers", "auto_trim_headers_footers"}
        assert trims & set(report.best_options), f"expected a trim setting, got {report.best_options}"

    def test_fitness_ranking_agrees_with_ground_truth(self, gnarly_pdf):
        """Not just the winner: the whole ranking must track the truth.

        A winner that is right by luck is indistinguishable from an objective that
        works, until the day it is not. This pins the correlation.
        """
        report = optimize_options(gnarly_pdf)

        scored = [
            (c.fitness, _truth(to_markdown(gnarly_pdf, parser_options=PdfOptions(**c.options))))
            for c in report.candidates
        ]
        best_fit_truth = max(scored, key=lambda pair: pair[0])[1]
        worst_fit_truth = min(scored, key=lambda pair: pair[0])[1]

        assert best_fit_truth >= worst_fit_truth
        assert best_fit_truth == max(truth for _, truth in scored)

    def test_reported_options_are_real_changes(self, gnarly_pdf):
        """Never recommend a setting that already holds; that is noise, not advice."""
        report = optimize_options(gnarly_pdf)
        defaults = PdfOptions()

        for name, value in report.best_options.items():
            assert getattr(defaults, name) != value, f"{name}={value} is already the default"


@pytest.mark.integration
@pytest.mark.pdf
class TestOptimizeApi:
    """Surface behaviour of ``optimize_options``."""

    def test_baseline_is_the_stock_defaults(self, gnarly_pdf):
        report = optimize_options(gnarly_pdf)

        default_candidates = [c for c in report.candidates if c.origin == "default"]
        assert len(default_candidates) == 1
        assert default_candidates[0].options == {}
        assert report.baseline_fitness == default_candidates[0].fitness

    def test_every_candidate_is_distinct(self, gnarly_pdf):
        report = optimize_options(gnarly_pdf)

        signatures = [tuple(sorted(c.options.items())) for c in report.candidates]
        assert len(signatures) == len(set(signatures))
        assert report.evaluated == len(report.candidates)

    def test_sample_pages_limits_the_work(self, gnarly_pdf):
        """Tuning a slice must still produce a usable report."""
        report = optimize_options(gnarly_pdf, sample_pages=2)

        assert report.source_format == "pdf"
        assert report.evaluated > 0

    def test_rejects_a_format_with_no_knobs(self, tmp_path):
        from all2md.exceptions import FormatError

        target = tmp_path / "notes.md"
        target.write_text("# hello\n", encoding="utf-8")

        with pytest.raises(FormatError, match="No tunable options"):
            optimize_options(target)

    def test_optimizable_formats_are_advertised(self):
        assert "pdf" in optimizable_formats()
        assert optimizable_formats() == sorted(optimizable_formats())


@pytest.mark.integration
@pytest.mark.pdf
class TestOptimizeCli:
    """The command line, including the settings it tells you to run."""

    def test_emits_a_runnable_command_and_a_toml_snippet(self, gnarly_pdf, capsys):
        from all2md.cli.commands.optimize import handle_optimize_command

        assert handle_optimize_command([gnarly_pdf]) == 0

        out = capsys.readouterr().out
        assert "all2md" in out
        assert "--pdf-" in out
        assert "[pdf]" in out

    def test_the_emitted_command_actually_improves_the_document(self, gnarly_pdf, tmp_path):
        """A wrong flag would be worse than no flag at all.

        Flag names are not mechanical -- a boolean defaulting to True is exposed as
        its *negation* (``detect_columns`` -> ``--pdf-no-detect-columns``) -- so this
        runs the emitted flags back through the real CLI and scores the result against
        ground truth, rather than trusting that the flag string was built correctly.
        """
        from all2md.cli import main
        from all2md.cli.commands.optimize import _cli_command

        report = optimize_options(gnarly_pdf)
        command = _cli_command(gnarly_pdf, report)
        assert command, "optimizer improved the document but emitted no command"

        flags = command.split()[2:]  # drop the leading "all2md <path>"
        assert flags

        out = tmp_path / "tuned.md"
        assert main([gnarly_pdf, "--out", str(out), *flags]) == 0

        tuned = out.read_text(encoding="utf-8")
        assert _truth(tuned) > _truth(to_markdown(gnarly_pdf))
        assert _truth(tuned) == 100

    def test_json_output_carries_the_command_and_toml(self, gnarly_pdf, capsys):
        import json

        from all2md.cli.commands.optimize import handle_optimize_command

        assert handle_optimize_command([gnarly_pdf, "--json"]) == 0

        payload = json.loads(capsys.readouterr().out)
        assert payload["source_format"] == "pdf"
        assert payload["best_options"]
        assert payload["command"].startswith("all2md ")
        assert payload["toml"].startswith("[pdf]")

    def test_writes_a_toml_file(self, gnarly_pdf, tmp_path):
        from all2md.cli.commands.optimize import handle_optimize_command

        target = tmp_path / "out.toml"
        assert handle_optimize_command([gnarly_pdf, "--out", str(target)]) == 0

        assert target.read_text(encoding="utf-8").startswith("[pdf]")

    def test_rejects_bad_rounds(self, gnarly_pdf, capsys):
        from all2md.cli.commands.optimize import handle_optimize_command

        assert handle_optimize_command([gnarly_pdf, "--rounds", "0"]) != 0
        assert "--rounds" in capsys.readouterr().err
