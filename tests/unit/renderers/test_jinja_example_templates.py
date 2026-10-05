#  Copyright (c) 2025 Tom Villani, Ph.D.
"""The example Jinja templates render with the default options.

The renderer's ``strict_undefined`` is on by default, and every example template
read ``metadata.title`` (and ``author``, ``date``) as attributes, so each one
failed on any document without a title with "'dict object' has no attribute
'title'" -- including ``ansi-terminal``, which the README and templates guide
present as the way to print a document to the terminal. The templates now use
``metadata.get(...)``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.options.jinja import JinjaRendererOptions
from all2md.renderers.jinja import JinjaRenderer

TEMPLATES = sorted(
    (Path(__file__).resolve().parents[3] / "examples" / "templates" / "jinja-templates").glob("*.jinja2")
)

DOCUMENT = Document(
    children=[
        Heading(level=1, content=[Text(content="Overview")]),
        Paragraph(content=[Text(content="Body text.")]),
    ]
)


@pytest.mark.unit
def test_the_examples_are_found():
    assert len(TEMPLATES) >= 4


@pytest.mark.unit
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda path: path.name)
@pytest.mark.parametrize(
    "metadata", [{}, {"title": "Report", "author": "A. Writer", "date": "2026-10-04"}], ids=["bare", "titled"]
)
def test_example_template_renders_with_defaults(template, metadata):
    document = Document(children=DOCUMENT.children, metadata=metadata)
    output = JinjaRenderer(JinjaRendererOptions(template_file=str(template))).render_to_string(document)
    assert "Overview" in output
    if metadata:
        assert "Report" in output.replace("REPORT", "Report")
