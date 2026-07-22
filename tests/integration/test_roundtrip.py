#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for round-trip fidelity scoring (D2).

Covers the ``roundtrip_report`` API against real converters and the
``all2md roundtrip`` CLI.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from all2md import roundtrip_report, roundtrippable_formats, to_ast
from all2md.exceptions import FormatError
from all2md.roundtrip import RoundTripReport

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "documents"
BASIC_MD = FIXTURES / "basic.md"

#: A document exercising every scored dimension: headings, nested lists, a table,
#: a code block, a blockquote, inline formatting, a link and an image.
RICH_MARKDOWN = """# Title

Intro with **bold**, *italic*, `code`, and a [link](https://example.com).

## Section

- bullet one
- bullet two
  - nested

1. first
2. second

| a | b |
|---|---|
| 1 | 2 |

> quote

```python
print("hi")
```

![img](pic.png)
"""


#: Raw inline HTML the Markdown parser has no node for, so it survives as an
#: HTMLInline and is escaped on the way back out. ``<u>``/``<ins>`` deliberately
#: do *not* belong here -- they parse into Underline nodes and roundtrip cleanly.
ESCAPING_HTML_MARKDOWN = """# Title

Here is some <span class="highlight">raw inline HTML</span> text.
"""


@pytest.fixture
def rich_md(tmp_path) -> Path:
    path = tmp_path / "rich.md"
    path.write_text(RICH_MARKDOWN, encoding="utf-8")
    return path


@pytest.fixture
def escaping_html_md(tmp_path) -> Path:
    path = tmp_path / "escaping_html.md"
    path.write_text(ESCAPING_HTML_MARKDOWN, encoding="utf-8")
    return path


def _run_cli(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "all2md", "roundtrip", *args],
        capture_output=True,
        text=stdin is None,
        input=stdin,
    )


@pytest.mark.integration
class TestRoundTripApi:
    def test_markdown_through_markdown_is_lossless(self, rich_md):
        """The anchor of the whole metric: a clean document must score exactly 100.

        If this drifts, the score is measuring noise rather than fidelity.
        """
        report = roundtrip_report(rich_md)
        assert report.score == 100
        assert report.band == "high"
        assert report.deltas == []
        assert set(report.metrics) == {"structure", "text", "inline", "tables", "references"}

    @pytest.mark.html
    def test_markdown_through_html_is_lossless(self, rich_md):
        assert roundtrip_report(rich_md, via="html").score == 100

    def test_report_labels_the_pipeline(self, rich_md):
        report = roundtrip_report(rich_md, via="rst")
        assert report.source_format == "markdown"
        assert report.via == "rst"

    def test_accepts_a_prebuilt_document(self):
        source = to_ast(RICH_MARKDOWN.encode(), source_format="markdown")
        assert roundtrip_report(source).score == 100

    def test_accepts_raw_bytes_with_explicit_format(self):
        report = roundtrip_report(RICH_MARKDOWN.encode(), source_format="markdown")
        assert report.score == 100

    def test_escaped_inline_html_is_priced_as_a_real_loss(self, escaping_html_md):
        """Escaped raw HTML costs fidelity, and the score says so.

        The Markdown renderer escapes raw HTML by default
        (``html_passthrough_mode="escape"``, a security posture), so a document
        carrying a tag with no AST equivalent (``<span>``) cannot round trip
        perfectly -- and the score reports that rather than quietly forgiving it.
        """
        report = roundtrip_report(escaping_html_md)
        assert report.score < 100
        assert {delta.kind for delta in report.deltas} == {"inline_lost", "text_lost"}
        assert any(delta.detail == "htmlinline" for delta in report.deltas)

    def test_underline_html_roundtrips_losslessly(self):
        """``<u>`` is not "raw HTML" to the scorer -- it is an Underline node.

        ``basic.md`` contains ``<u>underlined text</u>``. The Markdown parser
        reads that back into the AST, so it survives the round trip intact even
        under the default escaping policy (#113).
        """
        report = roundtrip_report(BASIC_MD)
        assert report.score == 100
        assert report.deltas == []

    def test_score_responds_to_converter_options(self, escaping_html_md):
        """The score must move when converter options move.

        This is what makes it usable as the ``optimize`` capstone's fitness
        function: flipping one renderer option recovers the lost points.
        """
        escaped = roundtrip_report(escaping_html_md)
        passed_through = roundtrip_report(escaping_html_md, html_passthrough_mode="pass-through")

        assert passed_through.score == 100
        assert passed_through.deltas == []
        assert passed_through.score > escaped.score

    def test_unknown_via_format_is_rejected(self, rich_md):
        with pytest.raises(FormatError, match="needs both a renderer and a parser"):
            roundtrip_report(rich_md, via="not-a-format")

    def test_render_only_via_format_is_rejected(self, rich_md):
        """``via`` needs a parser to come back through, not just a renderer."""
        assert "xlsx" not in roundtrippable_formats()
        with pytest.raises(FormatError):
            roundtrip_report(rich_md, via="xlsx")

    def test_roundtrippable_formats_are_sorted_and_bidirectional(self):
        formats = roundtrippable_formats()
        assert formats == sorted(formats)
        assert {"markdown", "html", "docx", "rst"} <= set(formats)

    @pytest.mark.docx
    def test_docx_round_trip_reports_the_title_demotion(self, rich_md):
        """A DOCX round trip loses structure, and the score surfaces it.

        Rendering to DOCX promotes a leading H1 to Word's Title style, and the DOCX
        parser has no inverse for it, so the heading comes back as a paragraph.
        This asymmetry is the kind of thing the score exists to find; the assertion
        pins the *detection*, not the (currently lossy) behaviour.
        """
        report = roundtrip_report(rich_md, via="docx")
        assert report.score < 100
        assert report.metrics["structure"] < report.metrics["text"]
        assert any(delta.kind in {"block_lost", "block_changed"} for delta in report.deltas)

    def test_json_round_trip_of_the_report(self, rich_md):
        report = roundtrip_report(rich_md, via="rst")
        assert RoundTripReport.from_dict(json.loads(json.dumps(report.to_dict()))) == report


@pytest.mark.integration
@pytest.mark.cli
class TestRoundTripCli:
    def test_pretty_card_reports_perfect_fidelity(self, rich_md):
        result = _run_cli(str(rich_md))
        assert result.returncode == 0
        assert "fidelity:  100/100  (HIGH)" in result.stdout
        assert "parse markdown -> render markdown -> parse markdown" in result.stdout

    def test_json_output_is_machine_readable(self, rich_md):
        result = _run_cli(str(rich_md), "--via", "rst", "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["via"] == "rst"
        assert 0 <= payload["score"] <= 100
        assert "structure" in payload["metrics"]

    def test_multiple_inputs_emit_a_json_array(self, rich_md):
        result = _run_cli(str(rich_md), str(BASIC_MD), "--json")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert isinstance(payload, list) and len(payload) == 2

    def test_fail_under_gates_on_the_worst_score(self, rich_md):
        clean = _run_cli(str(rich_md), "--fail-under", "100")
        assert clean.returncode == 0

        strict = _run_cli(str(rich_md), "--via", "latex", "--fail-under", "100")
        assert strict.returncode == 1
        assert "below --fail-under" in strict.stderr

    def test_out_of_range_fail_under_is_a_validation_error(self, rich_md):
        result = _run_cli(str(rich_md), "--fail-under", "150")
        assert result.returncode == 3

    def test_unknown_via_names_the_available_formats(self, rich_md):
        result = _run_cli(str(rich_md), "--via", "nope")
        assert result.returncode == 3
        assert "markdown" in result.stderr

    def test_missing_file_is_a_file_error(self, tmp_path):
        result = _run_cli(str(tmp_path / "absent.md"))
        assert result.returncode == 4

    def test_stdin_needs_an_explicit_format_to_be_markdown(self):
        """Piped Markdown sniffs as plaintext; --format is how a caller says otherwise."""
        sniffed = _run_cli("-", stdin=RICH_MARKDOWN.encode())
        assert sniffed.returncode == 0
        assert b"parse plaintext" in sniffed.stdout

        told = _run_cli("-", "--format", "markdown", stdin=RICH_MARKDOWN.encode())
        assert told.returncode == 0
        assert b"fidelity:  100/100" in told.stdout

    def test_max_deltas_truncates_and_says_so(self, rich_md):
        result = _run_cli(str(rich_md), "--via", "latex", "--max-deltas", "2")
        assert result.returncode == 0
        assert "... and" in result.stdout and "more" in result.stdout

    def test_out_writes_to_a_file(self, rich_md, tmp_path):
        target = tmp_path / "card.txt"
        result = _run_cli(str(rich_md), "--out", str(target))
        assert result.returncode == 0
        assert "fidelity:" in target.read_text(encoding="utf-8")
