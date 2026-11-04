"""Exercise merged HTML tables through the public API and real CSV CLI."""

import csv
import io
import subprocess
import sys
from pathlib import Path

import pytest

from all2md import convert
from all2md.constants import CsvQuotingMode, MergedCellHandling
from all2md.options.csv import CsvRendererOptions

pytestmark = [pytest.mark.e2e, pytest.mark.html, pytest.mark.table]

HTML = """<!doctype html><html><body>
<h1>Unrelated</h1><table><tr><td>ignore</td></tr></table>
<h1>Results</h1><table>
<tr><th rowspan="2" colspan="2">Group; &quot;A&quot;</th><th>Value</th></tr>
<tr><td>First</td></tr>
<tr><td>Left</td><td>Middle</td><td>Last</td></tr>
</table></body></html>"""


def _expected(mode: MergedCellHandling) -> list[list[str]]:
    """Expected records, including every position of the header merge."""
    continuation = {"repeat": 'Group; "A"', "blank": "", "placeholder": "[merged]"}[mode]
    return [['Group; "A"', continuation, "Value"], [continuation, continuation, "First"], ["Left", "Middle", "Last"]]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
@pytest.mark.parametrize("selection", [{"table_index": 1}, {"table_heading": "results"}])
def test_html_to_csv_api(mode: MergedCellHandling, selection: dict) -> None:
    """Real HTML parsing keeps combined spans and table selection intact."""
    output = convert(
        HTML.encode(),
        source_format="html",
        target_format="csv",
        renderer_options=CsvRendererOptions(handle_merged_cells=mode, delimiter=";", quoting="all", **selection),
    )
    assert isinstance(output, str)
    assert list(csv.reader(io.StringIO(output), delimiter=";")) == _expected(mode)
    assert output.startswith('"Group; ""A""";')


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
@pytest.mark.parametrize("quoting", ["minimal", "all", "nonnumeric", "none"])
def test_csv_dialect_with_rowspan(mode: MergedCellHandling, quoting: CsvQuotingMode) -> None:
    """Quoting and escaping still round-trip the same merged cell text."""
    output = convert(
        HTML.encode(),
        source_format="html",
        target_format="csv",
        renderer_options=CsvRendererOptions(
            handle_merged_cells=mode, table_index=1, delimiter=";", quote_char="'", escape_char="\\", quoting=quoting
        ),
    )
    assert isinstance(output, str)
    reader_quoting = csv.QUOTE_NONE if quoting == "none" else csv.QUOTE_MINIMAL
    assert list(
        csv.reader(io.StringIO(output), delimiter=";", quotechar="'", escapechar="\\", quoting=reader_quoting)
    ) == (_expected(mode))


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_multiple_tables_have_independent_spans(mode: MergedCellHandling) -> None:
    """Exporting all tables neither drops a table nor carries spans between them."""
    html = HTML.replace("</body>", "<table><tr><td>after</td></tr></table></body>")
    output = convert(
        html.encode(),
        source_format="html",
        target_format="csv",
        renderer_options=CsvRendererOptions(
            handle_merged_cells=mode, table_index=None, multi_table_mode="all", table_separator=""
        ),
    )
    assert isinstance(output, str)
    assert list(csv.reader(io.StringIO(output))) == [["ignore"], *_expected(mode), ["after"]]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_html_to_csv_cli(tmp_path: Path, mode: MergedCellHandling) -> None:
    """A subprocess converts an HTML file and writes correctly aligned CSV."""
    source = tmp_path / "merged.html"
    output = tmp_path / "merged.csv"
    source.write_text(HTML, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "all2md",
            str(source),
            "--to",
            "csv",
            "-o",
            str(output),
            "--csv-renderer-table-heading",
            "Results",
            "--csv-renderer-handle-merged-cells",
            mode,
            "--csv-renderer-delimiter",
            ";",
            "--csv-renderer-quoting",
            "all",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    with output.open(encoding="utf-8", newline="") as stream:
        assert list(csv.reader(stream, delimiter=";")) == _expected(mode)
