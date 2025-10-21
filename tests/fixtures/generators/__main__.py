"""CLI utilities for generating deterministic fixture files on disk.

Usage examples
--------------
Generate every supported fixture into ``tests/fixtures/documents/generated``::

    wslvenv/bin/python -m fixtures.generators

Generate only the CSV fixtures, overwriting existing files::

    wslvenv/bin/python -m fixtures.generators csv --force

List available fixture targets::

    wslvenv/bin/python -m fixtures.generators --list

The CLI skips targets whose optional dependencies (e.g. ``odfpy`` or
``ebooklib``) are not installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

# Ensure the project sources (./src) are importable when running this module directly.
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
TESTS_DIR = REPO_ROOT / "tests"
for candidate in (SRC_DIR, TESTS_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from all2md.exceptions import DependencyError
from fixtures.generators.csv_fixtures import (
    create_basic_csv,
    create_csv_with_special_characters,
    create_csv_with_unicode,
)
from fixtures.generators.eml_fixtures import (
    create_email_with_html_and_attachment,
    create_email_with_thread_headers,
    create_simple_email,
    email_to_bytes,
)
from fixtures.generators.epub_fixtures import create_epub_with_images, create_simple_epub
from fixtures.generators.ipynb_fixtures import (
    create_notebook_with_images,
    create_simple_notebook,
)
from fixtures.generators.latex_fixtures import (
    create_basic_latex_document,
    create_latex_with_math,
)
from fixtures.generators.markdown_fixtures import (
    create_markdown_with_code_and_lists,
    create_markdown_with_tables,
)
from fixtures.generators.mhtml_fixtures import (
    create_mhtml_with_image,
    create_simple_mhtml,
)
from fixtures.generators.odf_fixtures import (
    create_odp_with_slides,
    create_ods_with_sheet,
    create_odt_with_formatting,
    create_odt_with_lists,
    save_odp_to_bytes,
    save_ods_to_bytes,
    save_odt_to_bytes,
)
from fixtures.generators.org_fixtures import create_org_agenda_document
from fixtures.generators.plaintext_fixtures import (
    create_plaintext_with_code_block,
    create_plaintext_with_sections,
)
from fixtures.generators.rst_fixtures import create_rst_with_directives
from fixtures.generators.rtf_fixtures import (
    create_basic_rtf_document,
    create_rtf_with_code_block,
)
from fixtures.generators.sourcecode_fixtures import (
    create_markdown_embedded_snippet,
    create_python_module,
)
from fixtures.generators.xlsx_fixtures import (
    create_xlsx_basic_table,
    create_xlsx_with_chart,
    create_xlsx_with_image,
    create_xlsx_with_multiple_sheets,
)
from fixtures.generators.zip_fixtures import (
    create_simple_zip,
    create_zip_with_binary_assets,
    create_zip_with_subarchives,
)

BASE_DIR = Path(__file__).resolve().parent.parent / "documents" / "generated"


@dataclass(frozen=True)
class FixtureTarget:
    """Description of a disk-backed fixture that can be generated."""

    name: str
    filename: str
    builder: Callable[[], bytes]
    description: str
    optional_dependency: str | None = None

    @property
    def path(self) -> Path:
        return BASE_DIR / self.filename


def _text_builder(func: Callable[[], str]) -> Callable[[], bytes]:
    def builder() -> bytes:
        return func().encode("utf-8")

    return builder


def _ipynb_builder(func: Callable[[], dict]) -> Callable[[], bytes]:
    def builder() -> bytes:
        return json.dumps(func(), indent=2).encode("utf-8")

    return builder


def _epub_builder(func: Callable[[], bytes]) -> Callable[[], bytes]:
    def builder() -> bytes:
        return func()

    return builder


def _eml_builder(func: Callable[[], object]) -> Callable[[], bytes]:
    def builder() -> bytes:
        return email_to_bytes(func())

    return builder


def _odt_builder(func: Callable[[], object]) -> Callable[[], bytes]:
    def builder() -> bytes:
        doc = func()
        return save_odt_to_bytes(doc)

    return builder


def _ods_builder(func: Callable[[], object]) -> Callable[[], bytes]:
    def builder() -> bytes:
        doc = func()
        return save_ods_to_bytes(doc)

    return builder


def _odp_builder(func: Callable[[], object]) -> Callable[[], bytes]:
    def builder() -> bytes:
        doc = func()
        return save_odp_to_bytes(doc)

    return builder


FIXTURE_SPECS: list[FixtureTarget] = [
    FixtureTarget(
        name="csv-basic",
        filename="csv-basic.csv",
        builder=_text_builder(create_basic_csv),
        description="CSV with headers and numeric values.",
    ),
    FixtureTarget(
        name="csv-special",
        filename="csv-special-chars.csv",
        builder=_text_builder(create_csv_with_special_characters),
        description="CSV containing commas, quotes, and multiline fields.",
    ),
    FixtureTarget(
        name="csv-unicode",
        filename="csv-unicode.csv",
        builder=_text_builder(create_csv_with_unicode),
        description="CSV covering extended UTF-8 characters.",
    ),
    FixtureTarget(
        name="plaintext-sections",
        filename="plaintext-sections.txt",
        builder=_text_builder(create_plaintext_with_sections),
        description="Plain text with simulated headings and lists.",
    ),
    FixtureTarget(
        name="plaintext-log",
        filename="plaintext-log.txt",
        builder=_text_builder(create_plaintext_with_code_block),
        description="Plain text resembling a log with code-like content.",
    ),
    FixtureTarget(
        name="markdown-tables",
        filename="markdown-tables.md",
        builder=_text_builder(create_markdown_with_tables),
        description="Markdown with table syntax and emphasis.",
    ),
    FixtureTarget(
        name="markdown-setup",
        filename="markdown-setup.md",
        builder=_text_builder(create_markdown_with_code_and_lists),
        description="Markdown featuring nested lists and fenced code.",
    ),
    FixtureTarget(
        name="latex-basic",
        filename="latex-basic.tex",
        builder=_text_builder(create_basic_latex_document),
        description="LaTeX article with sections, lists, and tables.",
        optional_dependency="pylatexenc",
    ),
    FixtureTarget(
        name="latex-math",
        filename="latex-math.tex",
        builder=_text_builder(create_latex_with_math),
        description="LaTeX heavy in inline and display mathematics.",
        optional_dependency="pylatexenc",
    ),
    FixtureTarget(
        name="rst-directives",
        filename="rst-directives.rst",
        builder=_text_builder(create_rst_with_directives),
        description="reStructuredText using directives, lists, and tables.",
    ),
    FixtureTarget(
        name="org-agenda",
        filename="org-agenda.org",
        builder=_text_builder(create_org_agenda_document),
        description="Org-mode agenda with TODOs, tables, and metadata.",
    ),
    FixtureTarget(
        name="rtf-basic",
        filename="rtf-basic.rtf",
        builder=_text_builder(create_basic_rtf_document),
        description="RTF with formatted paragraphs and tables.",
    ),
    FixtureTarget(
        name="rtf-code",
        filename="rtf-code-block.rtf",
        builder=_text_builder(create_rtf_with_code_block),
        description="RTF example containing monospace code content.",
    ),
    FixtureTarget(
        name="source-python",
        filename="source-python.py",
        builder=_text_builder(create_python_module),
        description="Python source demonstrating classes and functions.",
    ),
    FixtureTarget(
        name="source-comments",
        filename="source-with-comments.c",
        builder=_text_builder(create_markdown_embedded_snippet),
        description="C-style source file with markdown in block comments.",
    ),
    FixtureTarget(
        name="epub-simple",
        filename="epub-simple.epub",
        builder=_epub_builder(create_simple_epub),
        description="EPUB with multiple chapters and basic formatting.",
        optional_dependency="ebooklib",
    ),
    FixtureTarget(
        name="epub-images",
        filename="epub-images.epub",
        builder=_epub_builder(create_epub_with_images),
        description="EPUB embedding an inline PNG asset.",
        optional_dependency="ebooklib",
    ),
    FixtureTarget(
        name="ipynb-simple",
        filename="ipynb-simple.ipynb",
        builder=_ipynb_builder(create_simple_notebook),
        description="Jupyter notebook with markdown and code cells.",
    ),
    FixtureTarget(
        name="ipynb-images",
        filename="ipynb-images.ipynb",
        builder=_ipynb_builder(create_notebook_with_images),
        description="Notebook emitting base64 image outputs.",
    ),
    FixtureTarget(
        name="xlsx-basic",
        filename="xlsx-basic.xlsx",
        builder=create_xlsx_basic_table,
        description="XLSX workbook with a single data table.",
        optional_dependency="openpyxl",
    ),
    FixtureTarget(
        name="xlsx-chart",
        filename="xlsx-chart.xlsx",
        builder=create_xlsx_with_chart,
        description="XLSX workbook containing a bar chart.",
        optional_dependency="openpyxl",
    ),
    FixtureTarget(
        name="xlsx-image",
        filename="xlsx-image.xlsx",
        builder=create_xlsx_with_image,
        description="XLSX workbook embedding a PNG image.",
        optional_dependency="openpyxl",
    ),
    FixtureTarget(
        name="xlsx-multi",
        filename="xlsx-multi-sheet.xlsx",
        builder=create_xlsx_with_multiple_sheets,
        description="XLSX workbook with multiple worksheets.",
        optional_dependency="openpyxl",
    ),
    FixtureTarget(
        name="odt-formatting",
        filename="odt-formatting.odt",
        builder=_odt_builder(create_odt_with_formatting),
        description="ODT document demonstrating text styling.",
        optional_dependency="odfpy",
    ),
    FixtureTarget(
        name="odt-lists",
        filename="odt-lists.odt",
        builder=_odt_builder(create_odt_with_lists),
        description="ODT document featuring nested lists.",
        optional_dependency="odfpy",
    ),
    FixtureTarget(
        name="ods-sheet",
        filename="ods-sheet.ods",
        builder=_ods_builder(create_ods_with_sheet),
        description="ODS spreadsheet with regional sales data.",
        optional_dependency="odfpy",
    ),
    FixtureTarget(
        name="odp-slides",
        filename="odp-slides.odp",
        builder=_odp_builder(create_odp_with_slides),
        description="ODP presentation with two text slides.",
        optional_dependency="odfpy",
    ),
    FixtureTarget(
        name="mhtml-simple",
        filename="mhtml-simple.mht",
        builder=create_simple_mhtml,
        description="MHTML archive containing basic HTML content.",
    ),
    FixtureTarget(
        name="mhtml-image",
        filename="mhtml-image.mht",
        builder=create_mhtml_with_image,
        description="MHTML archive embedding a PNG asset.",
    ),
    FixtureTarget(
        name="eml-simple",
        filename="email-simple.eml",
        builder=_eml_builder(create_simple_email),
        description="Plain-text email message.",
    ),
    FixtureTarget(
        name="eml-html",
        filename="email-html-attachment.eml",
        builder=_eml_builder(create_email_with_html_and_attachment),
        description="Multipart email with HTML alternative and image attachment.",
    ),
    FixtureTarget(
        name="eml-thread",
        filename="email-thread.eml",
        builder=_eml_builder(create_email_with_thread_headers),
        description="Threaded reply email with In-Reply-To headers.",
    ),
    FixtureTarget(
        name="zip-simple",
        filename="archive-simple.zip",
        builder=create_simple_zip,
        description="ZIP archive containing a pair of text files.",
    ),
    FixtureTarget(
        name="zip-binary",
        filename="archive-binary.zip",
        builder=create_zip_with_binary_assets,
        description="ZIP archive mixing CSV, scripts, and PNG assets.",
    ),
    FixtureTarget(
        name="zip-nested",
        filename="archive-nested.zip",
        builder=create_zip_with_subarchives,
        description="ZIP archive that embeds another archive.",
    ),
]

FIXTURE_MAP = {spec.name: spec for spec in FIXTURE_SPECS}

GROUPS: dict[str, tuple[str, ...]] = {
    "textual": (
        "plaintext-sections",
        "plaintext-log",
        "markdown-tables",
        "markdown-setup",
        "latex-basic",
        "latex-math",
        "rst-directives",
        "org-agenda",
        "rtf-basic",
        "rtf-code",
        "source-python",
        "source-comments",
    ),
    "structured": (
        "csv-basic",
        "csv-special",
        "csv-unicode",
        "ipynb-simple",
        "ipynb-images",
        "epub-simple",
        "epub-images",
        "xlsx-basic",
        "xlsx-chart",
        "xlsx-image",
        "xlsx-multi",
        "odt-formatting",
        "odt-lists",
        "ods-sheet",
        "odp-slides",
    ),
    "archives": (
        "zip-simple",
        "zip-binary",
        "zip-nested",
        "mhtml-simple",
        "mhtml-image",
    ),
    "messaging": (
        "eml-simple",
        "eml-html",
        "eml-thread",
    ),
}


def _resolve_targets(requested: Iterable[str]) -> list[FixtureTarget]:
    names: list[str]
    requested = list(requested)
    if not requested:
        names = [spec.name for spec in FIXTURE_SPECS]
    else:
        names = []
        for name in requested:
            if name == "all":
                return [spec for spec in FIXTURE_SPECS]
            if name in GROUPS:
                names.extend(GROUPS[name])
            elif name in FIXTURE_MAP:
                names.append(name)
            elif name == "list":
                continue
            else:
                raise SystemExit(f"Unknown fixture or group: {name}")
    # Preserve definition order while removing duplicates
    seen: set[str] = set()
    resolved: list[FixtureTarget] = []
    for spec in FIXTURE_SPECS:
        if spec.name in names and spec.name not in seen:
            resolved.append(spec)
            seen.add(spec.name)
    return resolved


def _ensure_base_dir() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_fixture(spec: FixtureTarget, force: bool) -> tuple[str, str]:
    path = spec.path
    if path.exists() and not force:
        return (spec.name, "skipped (exists)")

    try:
        data = spec.builder()
    except ImportError as exc:
        dep = spec.optional_dependency or "dependency"
        return (spec.name, f"skipped (missing {dep}: {exc})")
    except DependencyError as exc:  # type: ignore[name-defined]
        return (spec.name, f"skipped ({exc})")
    except Exception as exc:  # pragma: no cover - surface unexpected errors
        return (spec.name, f"failed ({exc})")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return (spec.name, f"wrote {path.relative_to(Path.cwd())}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic fixture files.")
    parser.add_argument(
        "targets",
        nargs="*",
        help="Fixture names or groups. Use 'list' to show options or omit for all.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files instead of skipping.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available fixtures and groups without generating anything.",
    )
    args = parser.parse_args(argv)

    if args.list or (args.targets and args.targets[0] == "list"):
        print("Available fixtures:")
        for spec in FIXTURE_SPECS:
            print(f"  {spec.name:18} -> {spec.filename}")
        if GROUPS:
            print("\nGroups:")
            for group, members in GROUPS.items():
                print(f"  {group}: {', '.join(members)}")
        return 0

    targets = _resolve_targets(args.targets)
    if not targets:
        print("No fixtures requested.")
        return 0

    _ensure_base_dir()

    results = [_generate_fixture(spec, args.force) for spec in targets]

    for name, status in results:
        print(f"{name:18} {status}")

    # Non-zero exit if any failed
    if any(status.startswith("failed") for _, status in results):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
