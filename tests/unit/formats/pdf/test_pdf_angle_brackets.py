"""A PDF's ``<`` reaches the AST as ``<``, not as ``&lt;`` (#441).

The span builder used to rewrite ``<`` and ``>`` into HTML character references
before wrapping them in a ``Text`` node, so the entity lived in the AST itself.
A markdown renderer hides that, which is why it went unnoticed for so long --
but every consumer that reads nodes instead of a rendered page saw it, and
``p < 0.05`` is ubiquitous in the scientific corpus. On the held-out corpus this
put 382 stray references into 61 of 110 articles.

Escaping for markdown's sake belongs to the markdown renderer, which knows which
``<`` a re-parse would read as a tag; the parser's job is to report the page.
"""

import pymupdf
import pytest

from all2md import to_markdown
from all2md.ast.utils import extract_text
from all2md.parsers.markdown import markdown_to_ast

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


def _pdf_with(tmp_path, lines: list[str], name: str = "angles.pdf") -> str:
    """Write one line of text per ``insert_text`` call and return the path."""
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 100 + 20 * i), line, fontsize=11)
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


class TestAngleBracketsFromPdf:
    def test_comparison_operator_is_not_an_entity(self, tmp_path):
        """The regression: this used to come out as ``p &lt; 0.05``."""
        path = _pdf_with(tmp_path, ["Treated animals differed (p < 0.05) from controls."])
        markdown = to_markdown(path)
        assert "p < 0.05" in markdown
        assert "&lt;" not in markdown

    def test_greater_than_is_not_an_entity(self, tmp_path):
        """``845G--> A`` is a real allele spelling from the corpus."""
        path = _pdf_with(tmp_path, ["The 845G--> A (C282Y) HFE variant was absent."])
        markdown = to_markdown(path)
        assert "845G--> A" in markdown
        assert "&gt;" not in markdown

    def test_text_survives_reparsing_its_own_markdown(self, tmp_path):
        """The round trip is the point: the AST must agree with the page.

        A tag-like ``<sup>`` is the case that needs the renderer's escape -- left
        raw it would be read back as HTML and the text would simply vanish.
        """
        lines = [
            "Treated animals differed (p < 0.05) from controls.",
            "Written <sup> as printed, and q > 3 besides.",
        ]
        path = _pdf_with(tmp_path, lines)
        markdown = to_markdown(path)
        recovered = extract_text(markdown_to_ast(markdown), joiner="")
        for fragment in ("p < 0.05", "<sup> as printed", "q > 3"):
            assert fragment in recovered
