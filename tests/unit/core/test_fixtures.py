"""Verification tests for the new test architecture.

These tests verify that our new test structure and fixtures work correctly
before attempting to run the full test suite.
"""

from pathlib import Path

import pytest

from fixtures.generators.docx_fixtures import create_minimal_docx, save_docx_to_bytes
from fixtures.generators.html_fixtures import create_minimal_html
from fixtures.generators.pdf_test_fixtures import create_pdf_with_figures
from fixtures.generators.pptx_fixtures import create_minimal_pptx, save_pptx_to_bytes


@pytest.mark.unit
def test_html_fixture_generation():
    """Test that HTML fixture generation works correctly."""
    html_content = create_minimal_html("Test Title", "Test content")

    assert isinstance(html_content, str)
    assert "Test Title" in html_content
    assert "Test content" in html_content
    assert "<html" in html_content


@pytest.mark.unit
def test_docx_fixture_generation():
    """Test that DOCX fixture generation works correctly."""
    doc = create_minimal_docx("Test Document", "Test content")
    docx_bytes = save_docx_to_bytes(doc)

    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0
    # DOCX files should have the ZIP signature
    assert docx_bytes[:4] == b"PK\x03\x04"


@pytest.mark.unit
def test_pptx_fixture_generation():
    """Test that PPTX fixture generation works correctly."""
    prs = create_minimal_pptx("Test Presentation", "Test content")
    pptx_bytes = save_pptx_to_bytes(prs)

    assert isinstance(pptx_bytes, bytes)
    assert len(pptx_bytes) > 0
    # PPTX files should have the ZIP signature
    assert pptx_bytes[:4] == b"PK\x03\x04"


@pytest.mark.unit
def test_pdf_fixture_generation():
    """Test that PDF fixture generation works correctly."""
    doc = create_pdf_with_figures()

    try:
        assert doc.page_count > 0
        page = doc[0]
        assert page is not None
    finally:
        doc.close()


@pytest.mark.unit
def test_temp_dir_fixture(temp_dir):
    """Test that the temp_dir fixture works correctly."""
    assert isinstance(temp_dir, Path)
    assert temp_dir.exists()
    assert temp_dir.is_dir()

    # Should be able to create files in it
    test_file = temp_dir / "test.txt"
    test_file.write_text("test content")
    assert test_file.exists()
    assert test_file.read_text() == "test content"


@pytest.mark.unit
def test_pytest_markers_work():
    """Test that pytest markers are properly configured."""
    # This test just verifies it can run with the @pytest.mark.unit decorator
    assert True


@pytest.mark.integration
def test_integration_marker_work():
    """Test that integration marker is properly configured."""
    # This test verifies integration marker works
    assert True


@pytest.mark.e2e
def test_e2e_marker_work():
    """Test that e2e marker is properly configured."""
    # This test verifies e2e marker works
    assert True
