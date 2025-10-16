"""Tests for automatic options documentation generation."""
#  Copyright (c) 2025 Tom Villani, Ph.D.

from __future__ import annotations

from pathlib import Path

import pytest

from docs.source.generate_options_doc import generate_options_document


@pytest.mark.unit
def test_generate_options_document(tmp_path: Path) -> None:
    """Generated documentation should include known sections and write output."""
    output_path = tmp_path / "options.rst"
    narrative_path = Path("docs/source/_options-narrative.rst").resolve()

    document = generate_options_document(output_path, narrative_path)

    assert "Generated Reference" in document
    assert "PDF Parser Options" in document
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == document
