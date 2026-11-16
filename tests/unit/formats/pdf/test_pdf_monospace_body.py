"""A document typed in a monospaced font is prose, not code.

The wide tier (``benchmarks/pdfword/wide.py``) found letters and memos set entirely in Courier New
coming out of the PDF as one code block: monospace was read as a sign of code even when it was the
body font.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md import to_ast, to_markdown
from all2md.ast.nodes import Code, CodeBlock
from all2md.options.pdf import PdfOptions

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

LETTER = [
    "Dear Sir or Madam,",
    "My name is Lisa and I live in Novato. I have worked as an adoption",
    "facilitator since 1993 for two different agencies in the region.",
    "I have read the proposed regulations and would like to comment.",
    "Yours sincerely,",
]


def _pdf(path: Path, lines: list[tuple[str, str]]) -> Path:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    for index, (font, text) in enumerate(lines):
        page.insert_text((72, 90 + index * 16), text, fontname=font, fontsize=11)
    document.save(path)
    return path


def _nodes(path: Path) -> list:
    doc = to_ast(str(path), parser_options=PdfOptions(layout_analysis_mode="disabled"))
    found: list = []

    def walk(node: object) -> None:
        found.append(node)
        for child in getattr(node, "children", None) or getattr(node, "content", None) or []:
            if not isinstance(child, str):
                walk(child)

    walk(doc)
    return found


def test_a_letter_in_courier_is_prose(tmp_path: Path) -> None:
    source = _pdf(tmp_path / "letter.pdf", [("cour", text) for text in LETTER])
    nodes = _nodes(source)
    assert not [n for n in nodes if isinstance(n, (CodeBlock, Code))]
    assert "facilitator since 1993" in to_markdown(
        str(source), parser_options=PdfOptions(layout_analysis_mode="disabled")
    )


def test_a_code_line_in_a_proportional_document_is_still_code(tmp_path: Path) -> None:
    lines = [("helv", text) for text in LETTER]
    lines.insert(3, ("cour", "print(convert(path))"))
    nodes = _nodes(_pdf(tmp_path / "mixed.pdf", lines))
    assert [n for n in nodes if isinstance(n, (CodeBlock, Code))]
