"""Golden tests for structured data formats (CSV, XLSX, EPUB, etc.)."""

from __future__ import annotations

import json
from io import BytesIO

import pytest
from fixtures.generators.csv_fixtures import (
    create_basic_csv,
    create_csv_with_special_characters,
    create_csv_with_unicode,
    csv_bytes_io,
)
from fixtures.generators.epub_fixtures import create_epub_with_images, create_simple_epub
from fixtures.generators.ipynb_fixtures import (
    create_notebook_with_images,
    create_simple_notebook,
)
from fixtures.generators.odf_fixtures import (
    HAS_ODFPY,
    create_odp_with_slides,
    create_ods_with_sheet,
    create_odt_with_formatting,
    create_odt_with_lists,
    save_odp_to_bytes,
    save_ods_to_bytes,
    save_odt_to_bytes,
)
from fixtures.generators.xlsx_fixtures import (
    create_xlsx_basic_table,
    create_xlsx_with_chart,
    create_xlsx_with_image,
    create_xlsx_with_multiple_sheets,
)

from all2md import to_markdown
from all2md.exceptions import DependencyError


@pytest.mark.golden
@pytest.mark.unit
class TestCsvGolden:
    """Golden tests for CSV conversion."""

    def test_csv_basic(self, snapshot):
        stream = csv_bytes_io(create_basic_csv())
        result = to_markdown(stream, source_format="csv")
        assert result == snapshot

    def test_csv_with_special_characters(self, snapshot):
        stream = csv_bytes_io(create_csv_with_special_characters())
        result = to_markdown(stream, source_format="csv")
        assert result == snapshot

    def test_csv_with_unicode(self, snapshot):
        stream = csv_bytes_io(create_csv_with_unicode())
        result = to_markdown(stream, source_format="csv")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.ipynb
@pytest.mark.unit
class TestIpynbGolden:
    """Golden tests for Jupyter Notebook conversion."""

    def test_ipynb_simple_notebook(self, snapshot):
        notebook = create_simple_notebook()
        stream = BytesIO(json.dumps(notebook).encode("utf-8"))
        result = to_markdown(stream, source_format="ipynb")
        assert result == snapshot

    def test_ipynb_with_images(self, snapshot):
        notebook = create_notebook_with_images()
        stream = BytesIO(json.dumps(notebook).encode("utf-8"))
        result = to_markdown(stream, source_format="ipynb")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.epub
@pytest.mark.unit
class TestEpubGolden:
    """Golden tests for EPUB conversion."""

    def test_epub_simple_document(self, snapshot):
        try:
            epub_bytes = create_simple_epub()
        except ImportError as exc:
            pytest.skip(str(exc))

        try:
            result = to_markdown(BytesIO(epub_bytes), source_format="epub")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot

    def test_epub_with_images(self, snapshot):
        try:
            epub_bytes = create_epub_with_images()
        except ImportError as exc:
            pytest.skip(str(exc))

        try:
            result = to_markdown(BytesIO(epub_bytes), source_format="epub")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestXlsxGolden:
    """Golden tests for XLSX conversion."""

    def test_xlsx_basic_table(self, snapshot):
        try:
            xlsx_bytes = create_xlsx_basic_table()
        except ImportError as exc:
            pytest.skip(str(exc))

        result = to_markdown(BytesIO(xlsx_bytes), source_format="xlsx")
        assert result == snapshot

    def test_xlsx_with_chart(self, snapshot):
        try:
            xlsx_bytes = create_xlsx_with_chart()
        except ImportError as exc:
            pytest.skip(str(exc))

        result = to_markdown(BytesIO(xlsx_bytes), source_format="xlsx")
        assert result == snapshot

    def test_xlsx_with_image(self, snapshot):
        try:
            xlsx_bytes = create_xlsx_with_image()
        except ImportError as exc:
            pytest.skip(str(exc))

        result = to_markdown(BytesIO(xlsx_bytes), source_format="xlsx")
        assert result == snapshot

    def test_xlsx_multiple_sheets(self, snapshot):
        try:
            xlsx_bytes = create_xlsx_with_multiple_sheets()
        except ImportError as exc:
            pytest.skip(str(exc))

        result = to_markdown(BytesIO(xlsx_bytes), source_format="xlsx")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.odf
@pytest.mark.unit
class TestOdfGolden:
    """Golden tests for ODF (ODT/ODS/ODP) conversion."""

    def test_odt_with_formatting(self, snapshot):
        if not HAS_ODFPY:
            pytest.skip("odfpy not installed")

        odt_doc = create_odt_with_formatting()
        odt_bytes = save_odt_to_bytes(odt_doc)
        result = to_markdown(BytesIO(odt_bytes), source_format="odt")
        assert result == snapshot

    def test_odt_with_lists(self, snapshot):
        if not HAS_ODFPY:
            pytest.skip("odfpy not installed")

        odt_doc = create_odt_with_lists()
        odt_bytes = save_odt_to_bytes(odt_doc)
        result = to_markdown(BytesIO(odt_bytes), source_format="odt")
        assert result == snapshot

    def test_ods_with_sheet(self, snapshot):
        if not HAS_ODFPY:
            pytest.skip("odfpy not installed")

        ods_doc = create_ods_with_sheet()
        ods_bytes = save_ods_to_bytes(ods_doc)
        result = to_markdown(BytesIO(ods_bytes), source_format="ods")
        assert result == snapshot

    def test_odp_with_slides(self, snapshot):
        if not HAS_ODFPY:
            pytest.skip("odfpy not installed")

        odp_doc = create_odp_with_slides()
        odp_bytes = save_odp_to_bytes(odp_doc)
        try:
            result = to_markdown(BytesIO(odp_bytes), source_format="odp")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot
