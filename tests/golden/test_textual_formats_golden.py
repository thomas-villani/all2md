"""Golden tests for textual formats (AsciiDoc, plain text, RST, etc.)."""

from __future__ import annotations

from io import BytesIO

import pytest

from all2md import to_markdown
from all2md.exceptions import DependencyError
from fixtures.generators.asciidoc_fixtures import (
    create_asciidoc_with_formatting,
    create_asciidoc_with_lists,
)
from fixtures.generators.latex_fixtures import (
    create_basic_latex_document,
    create_latex_with_math,
    latex_bytes_io,
)
from fixtures.generators.org_fixtures import (
    create_org_agenda_document,
    org_bytes_io,
)
from fixtures.generators.plaintext_fixtures import (
    create_plaintext_with_code_block,
    create_plaintext_with_sections,
    plaintext_bytes_io,
)
from fixtures.generators.rst_fixtures import (
    create_rst_with_directives,
    rst_bytes_io,
)
from fixtures.generators.rtf_fixtures import (
    create_basic_rtf_document,
    create_rtf_with_code_block,
    rtf_bytes_io,
)
from fixtures.generators.sourcecode_fixtures import (
    create_markdown_embedded_snippet,
    create_python_module,
    sourcecode_bytes_io,
)


@pytest.mark.golden
@pytest.mark.asciidoc
@pytest.mark.unit
class TestAsciiDocGolden:
    """Golden tests for AsciiDoc conversion."""

    def test_asciidoc_with_formatting(self, snapshot):
        asciidoc = create_asciidoc_with_formatting().encode("utf-8")
        result = to_markdown(BytesIO(asciidoc), source_format="asciidoc")
        assert result == snapshot

    def test_asciidoc_with_lists(self, snapshot):
        asciidoc = create_asciidoc_with_lists().encode("utf-8")
        result = to_markdown(BytesIO(asciidoc), source_format="asciidoc")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.plaintext
@pytest.mark.unit
class TestPlainTextGolden:
    """Golden tests for plain text conversion."""

    def test_plaintext_sections(self, snapshot):
        stream = plaintext_bytes_io(create_plaintext_with_sections())
        result = to_markdown(stream, source_format="plaintext")
        assert result == snapshot

    def test_plaintext_with_code_block(self, snapshot):
        stream = plaintext_bytes_io(create_plaintext_with_code_block())
        result = to_markdown(stream, source_format="plaintext")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestRstGolden:
    """Golden tests for reStructuredText conversion."""

    def test_rst_with_directives(self, snapshot):
        stream = rst_bytes_io(create_rst_with_directives())
        result = to_markdown(stream, source_format="rst")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestOrgGolden:
    """Golden tests for Org-mode conversion."""

    def test_org_agenda_document(self, snapshot):
        stream = org_bytes_io(create_org_agenda_document())
        result = to_markdown(stream, source_format="org")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestRtfGolden:
    """Golden tests for RTF conversion."""

    def test_rtf_basic_document(self, snapshot):
        stream = rtf_bytes_io(create_basic_rtf_document())
        result = to_markdown(stream, source_format="rtf")
        assert result == snapshot

    def test_rtf_with_code_block(self, snapshot):
        stream = rtf_bytes_io(create_rtf_with_code_block())
        result = to_markdown(stream, source_format="rtf")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestSourceCodeGolden:
    """Golden tests for generic source code conversion."""

    def test_python_module(self, snapshot):
        stream = sourcecode_bytes_io(create_python_module())
        result = to_markdown(stream, source_format="sourcecode")
        assert result == snapshot

    def test_source_with_embedded_markdown(self, snapshot):
        stream = sourcecode_bytes_io(create_markdown_embedded_snippet())
        result = to_markdown(stream, source_format="sourcecode")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestLatexGolden:
    """Golden tests for LaTeX conversion."""

    def test_latex_basic_document(self, snapshot):
        stream = latex_bytes_io(create_basic_latex_document())
        try:
            result = to_markdown(stream, source_format="latex")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot

    def test_latex_with_math(self, snapshot):
        stream = latex_bytes_io(create_latex_with_math())
        try:
            result = to_markdown(stream, source_format="latex")
        except DependencyError as exc:
            pytest.skip(str(exc))
        assert result == snapshot
