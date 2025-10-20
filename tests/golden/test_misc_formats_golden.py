"""Golden tests for container and communication formats (ZIP, EML, MHTML)."""

from __future__ import annotations

from io import BytesIO

import pytest

from all2md import to_markdown
from all2md.exceptions import DependencyError
from fixtures.generators.eml_fixtures import (
    create_email_with_html_and_attachment,
    create_email_with_thread_headers,
    create_simple_email,
    email_bytes_io,
)
from fixtures.generators.mhtml_fixtures import (
    create_mhtml_with_image,
    create_simple_mhtml,
)
from fixtures.generators.zip_fixtures import (
    create_simple_zip,
    create_zip_with_binary_assets,
    create_zip_with_subarchives,
)


@pytest.mark.golden
@pytest.mark.unit
class TestEmlGolden:
    """Golden tests for EML conversion."""

    def test_simple_email(self, snapshot):
        stream = email_bytes_io(create_simple_email())
        result = to_markdown(stream, source_format="eml")
        assert result == snapshot

    def test_email_with_html_and_attachment(self, snapshot):
        stream = email_bytes_io(create_email_with_html_and_attachment())
        result = to_markdown(stream, source_format="eml")
        assert result == snapshot

    def test_email_with_thread_headers(self, snapshot):
        stream = email_bytes_io(create_email_with_thread_headers())
        result = to_markdown(stream, source_format="eml")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.mhtml
@pytest.mark.unit
class TestMhtmlGolden:
    """Golden tests for MHTML conversion."""

    def test_simple_mhtml(self, snapshot):
        stream = BytesIO(create_simple_mhtml())
        result = to_markdown(stream, source_format="mhtml")
        assert result == snapshot

    def test_mhtml_with_image(self, snapshot):
        stream = BytesIO(create_mhtml_with_image())
        result = to_markdown(stream, source_format="mhtml")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestZipGolden:
    """Golden tests for ZIP archive conversion."""

    def test_simple_zip(self, snapshot):
        stream = BytesIO(create_simple_zip())
        result = to_markdown(stream, source_format="zip")
        assert result == snapshot

    def test_zip_with_binary_assets(self, snapshot):
        stream = BytesIO(create_zip_with_binary_assets())
        try:
            result = to_markdown(stream, source_format="zip")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot

    def test_zip_with_nested_archive(self, snapshot):
        stream = BytesIO(create_zip_with_subarchives())
        try:
            result = to_markdown(stream, source_format="zip")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot
