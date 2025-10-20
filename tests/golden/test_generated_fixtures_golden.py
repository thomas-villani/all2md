"""Golden tests for converters using generated on-disk fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md import to_markdown
from all2md.exceptions import DependencyError

GENERATED_ROOT = Path("tests/fixtures/documents/generated")


def _case(source_format: str, filename: str, *marks: pytest.MarkDecorator) -> pytest.ParameterSet:
    mark_list = list(marks)
    # Always mark as integration for these disk-based tests
    mark_list.append(pytest.mark.integration)
    return pytest.param(source_format, GENERATED_ROOT / filename, marks=mark_list, id=filename)


GENERATED_FIXTURES = [
    _case("csv", "csv-basic.csv"),
    _case("csv", "csv-special-chars.csv"),
    _case("csv", "csv-unicode.csv"),
    _case("plaintext", "plaintext-sections.txt", pytest.mark.plaintext),
    _case("plaintext", "plaintext-log.txt", pytest.mark.plaintext),
    _case("markdown", "markdown-tables.md"),
    _case("markdown", "markdown-setup.md"),
    _case("latex", "latex-basic.tex"),
    _case("latex", "latex-math.tex"),
    _case("rst", "rst-directives.rst"),
    _case("org", "org-agenda.org"),
    _case("rtf", "rtf-basic.rtf", pytest.mark.rtf),
    _case("rtf", "rtf-code-block.rtf", pytest.mark.rtf),
    _case("sourcecode", "source-python.py"),
    _case("sourcecode", "source-with-comments.c"),
    _case("epub", "epub-simple.epub", pytest.mark.epub),
    _case("epub", "epub-images.epub", pytest.mark.epub),
    _case("ipynb", "ipynb-simple.ipynb", pytest.mark.ipynb),
    _case("ipynb", "ipynb-images.ipynb", pytest.mark.ipynb),
    _case("xlsx", "xlsx-basic.xlsx"),
    _case("xlsx", "xlsx-chart.xlsx"),
    _case("xlsx", "xlsx-image.xlsx"),
    _case("xlsx", "xlsx-multi-sheet.xlsx"),
    _case("odt", "odt-formatting.odt", pytest.mark.odf),
    _case("odt", "odt-lists.odt", pytest.mark.odf),
    _case("ods", "ods-sheet.ods", pytest.mark.odf),
    _case("odp", "odp-slides.odp", pytest.mark.odf),
    _case("mhtml", "mhtml-simple.mht", pytest.mark.mhtml),
    _case("mhtml", "mhtml-image.mht", pytest.mark.mhtml),
    _case("eml", "email-simple.eml", pytest.mark.eml),
    _case("eml", "email-html-attachment.eml", pytest.mark.eml),
    _case("eml", "email-thread.eml", pytest.mark.eml),
    _case("zip", "archive-simple.zip"),
    _case("zip", "archive-binary.zip"),
    _case("zip", "archive-nested.zip"),
]


@pytest.mark.golden
@pytest.mark.parametrize("source_format, fixture_path", GENERATED_FIXTURES)
def test_generated_fixture(snapshot, source_format: str, fixture_path: Path) -> None:
    """Convert generated fixtures and compare against stored snapshots."""
    if not fixture_path.exists():
        pytest.skip(f"Generated fixture missing: {fixture_path} (run python -m fixtures.generators)")

    try:
        with fixture_path.open("rb") as handle:
            result = to_markdown(handle, source_format=source_format)
    except (ImportError, DependencyError) as exc:  # pragma: no cover - dependency missing
        pytest.skip(str(exc))

    assert result == snapshot
