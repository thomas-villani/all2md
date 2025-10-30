"""Integration tests for Jupyter Notebook (ipynb) renderer.

Tests cover:
- End-to-end ipynb rendering workflows
- Markdown cells with various formatting
- Code cells with different languages
- Mixed cell types
- Complete document conversion
"""

import json

import pytest

from all2md import from_ast, to_ast
from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Text,
)
from all2md.renderers.ipynb import IpynbRenderer


def create_sample_document():
    """Create a sample AST document for testing.

    Returns
    -------
    Document
        A sample document with various elements for testing ipynb rendering.

    """
    return Document(
        metadata={"title": "Jupyter Notebook Test"},
        children=[
            Heading(level=1, content=[Text(content="Notebook Title")]),
            Paragraph(
                content=[
                    Text(content="This is a paragraph with "),
                    Strong(content=[Text(content="bold text")]),
                    Text(content="."),
                ]
            ),
            CodeBlock(content='print("Hello from Python")\nx = 42\nprint(f"x = {x}")', language="python"),
            Heading(level=2, content=[Text(content="Lists Example")]),
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="First item")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Second item")])]),
                ],
            ),
        ],
    )


@pytest.mark.integration
def test_ipynb_renderer_basic(tmp_path):
    """Test basic ipynb rendering."""
    doc = create_sample_document()
    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    # Parse the JSON output
    notebook = json.loads(result)

    assert "cells" in notebook
    assert "metadata" in notebook
    assert "nbformat" in notebook
    assert len(notebook["cells"]) > 0


@pytest.mark.integration
def test_ipynb_renderer_markdown_cells(tmp_path):
    """Test ipynb with markdown cells."""
    doc = Document(
        children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Paragraph text.")]),
        ]
    )

    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    cells = notebook["cells"]

    # Check for markdown cells
    markdown_cells = [c for c in cells if c["cell_type"] == "markdown"]
    assert len(markdown_cells) > 0


@pytest.mark.integration
def test_ipynb_renderer_code_cells(tmp_path):
    """Test ipynb roundtrip with code cells."""
    # Create an ipynb file with code cells
    original_notebook = {
        "cells": [
            {"cell_type": "code", "source": ['print("Hello")'], "metadata": {}, "execution_count": None, "outputs": []},
            {
                "cell_type": "code",
                "source": ["x = 42\nprint(x)"],
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    ipynb_file = tmp_path / "test.ipynb"
    ipynb_file.write_text(json.dumps(original_notebook), encoding="utf-8")

    # Roundtrip: ipynb -> AST -> ipynb
    doc = to_ast(ipynb_file)
    result = from_ast(doc, "ipynb")

    notebook = json.loads(result)
    cells = notebook["cells"]

    # Check for code cells preserved
    code_cells = [c for c in cells if c["cell_type"] == "code"]
    assert len(code_cells) == 2
    assert 'print("Hello")' in cells[0]["source"][0]


@pytest.mark.integration
def test_ipynb_renderer_mixed_cells(tmp_path):
    """Test ipynb roundtrip with mixed markdown and code cells."""
    original_notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Mixed Cells\n", "Introduction text."], "metadata": {}},
            {
                "cell_type": "code",
                "source": ["x = 10\nprint(x)"],
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            },
            {"cell_type": "markdown", "source": ["More explanation."], "metadata": {}},
            {
                "cell_type": "code",
                "source": ["y = x * 2\nprint(y)"],
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    ipynb_file = tmp_path / "test.ipynb"
    ipynb_file.write_text(json.dumps(original_notebook), encoding="utf-8")

    # Roundtrip
    doc = to_ast(ipynb_file)
    result = from_ast(doc, "ipynb")

    notebook = json.loads(result)
    cells = notebook["cells"]

    assert len(cells) == 4
    markdown_cells = [c for c in cells if c["cell_type"] == "markdown"]
    code_cells = [c for c in cells if c["cell_type"] == "code"]
    assert len(markdown_cells) == 2
    assert len(code_cells) == 2


@pytest.mark.integration
def test_ipynb_renderer_empty_document(tmp_path):
    """Test ipynb rendering with empty document."""
    doc = Document(children=[])

    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    assert "cells" in notebook
    assert isinstance(notebook["cells"], list)


@pytest.mark.integration
def test_ipynb_renderer_formatting(tmp_path):
    """Test ipynb rendering with various markdown formatting."""
    doc = Document(
        children=[
            Paragraph(
                content=[
                    Text(content="Text with "),
                    Strong(content=[Text(content="bold")]),
                    Text(content=" and "),
                    Link(url="https://example.com", content=[Text(content="link")]),
                ]
            ),
        ]
    )

    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    assert len(notebook["cells"]) > 0


@pytest.mark.integration
def test_ipynb_renderer_with_lists(tmp_path):
    """Test ipynb rendering with lists."""
    doc = Document(
        children=[
            Heading(level=2, content=[Text(content="List Example")]),
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Item 3")])]),
                ],
            ),
        ]
    )

    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    cells = notebook["cells"]
    assert len(cells) > 0


@pytest.mark.integration
def test_ipynb_renderer_code_language(tmp_path):
    """Test ipynb roundtrip with different code languages."""
    original_notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": ['print("Python")'],
                "metadata": {},
                "execution_count": None,
                "outputs": [],
            },
            {"cell_type": "code", "source": ['puts "Ruby"'], "metadata": {}, "execution_count": None, "outputs": []},
            {"cell_type": "code", "source": ['echo "Bash"'], "metadata": {}, "execution_count": None, "outputs": []},
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    ipynb_file = tmp_path / "test.ipynb"
    ipynb_file.write_text(json.dumps(original_notebook), encoding="utf-8")

    # Roundtrip
    doc = to_ast(ipynb_file)
    result = from_ast(doc, "ipynb")

    notebook = json.loads(result)
    code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) == 3


@pytest.mark.integration
def test_ipynb_renderer_metadata_preservation(tmp_path):
    """Test that document metadata is preserved in notebook."""
    doc = Document(
        metadata={"title": "Test Notebook", "author": "Test Author"},
        children=[Paragraph(content=[Text(content="Content")])],
    )

    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    assert "metadata" in notebook


@pytest.mark.integration
def test_ipynb_from_markdown_file(tmp_path):
    """Test converting a Markdown file to ipynb."""
    md_content = """# Jupyter Notebook from Markdown

This is a test notebook created from Markdown.

## Code Example

```python
def hello():
    print("Hello, World!")
```

## More Content

Some more text here."""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    # Convert MD -> AST -> IPYNB
    doc = to_ast(md_file)
    ipynb_content = from_ast(doc, "ipynb")

    # Verify it's valid JSON
    notebook = json.loads(ipynb_content)
    assert "cells" in notebook
    assert len(notebook["cells"]) > 0


@pytest.mark.integration
def test_ipynb_roundtrip_conversion(tmp_path):
    """Test ipynb -> MD -> ipynb roundtrip."""
    # Create original notebook
    original_notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Title\n", "Text content."], "metadata": {}},
            {"cell_type": "code", "source": ['print("Hello")'], "metadata": {}, "execution_count": None, "outputs": []},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    ipynb_file = tmp_path / "original.ipynb"
    ipynb_file.write_text(json.dumps(original_notebook), encoding="utf-8")

    # Convert to AST
    doc = to_ast(ipynb_file)

    # Convert back to ipynb
    result = from_ast(doc, "ipynb")
    new_notebook = json.loads(result)

    # Verify structure is maintained
    assert "cells" in new_notebook
    assert len(new_notebook["cells"]) > 0


@pytest.mark.integration
def test_ipynb_long_content(tmp_path):
    """Test ipynb with long content."""
    paragraphs = [Paragraph(content=[Text(content=f"Paragraph {i}: Long content here.")]) for i in range(50)]

    doc = Document(children=paragraphs)
    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    assert len(notebook["cells"]) > 0


@pytest.mark.integration
def test_ipynb_unicode_content(tmp_path):
    """Test ipynb with Unicode characters."""
    doc = Document(
        children=[
            Heading(level=1, content=[Text(content="Unicode Test \U0001f600")]),
            Paragraph(content=[Text(content="Chinese: \U00004e2d\U00006587")]),
            CodeBlock(content='print("\U0001f600")', language="python"),
        ]
    )

    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    assert len(notebook["cells"]) > 0


@pytest.mark.integration
def test_ipynb_multiline_code_blocks(tmp_path):
    """Test ipynb roundtrip with multiline code blocks."""
    code_content = """import numpy as np
import pandas as pd

def process_data(data):
    result = data * 2
    return result

data = np.array([1, 2, 3])
processed = process_data(data)
print(processed)"""

    original_notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Data Processing"], "metadata": {}},
            {"cell_type": "code", "source": [code_content], "metadata": {}, "execution_count": None, "outputs": []},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    ipynb_file = tmp_path / "test.ipynb"
    ipynb_file.write_text(json.dumps(original_notebook), encoding="utf-8")

    # Roundtrip
    doc = to_ast(ipynb_file)
    result = from_ast(doc, "ipynb")

    notebook = json.loads(result)
    code_cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) == 1
    assert "import numpy" in code_cells[0]["source"][0]


@pytest.mark.integration
def test_ipynb_from_html_file(tmp_path):
    """Test converting HTML to ipynb."""
    html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>HTML to Notebook</h1>
    <p>Converting HTML content to Jupyter notebook.</p>
    <pre><code class="language-python">print("From HTML")</code></pre>
</body>
</html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    # Convert HTML -> AST -> IPYNB
    doc = to_ast(html_file)
    ipynb_content = from_ast(doc, "ipynb")

    notebook = json.loads(ipynb_content)
    assert "cells" in notebook


@pytest.mark.integration
def test_ipynb_save_to_file(tmp_path):
    """Test saving ipynb output to file."""
    doc = create_sample_document()
    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    output_file = tmp_path / "output.ipynb"
    output_file.write_text(result, encoding="utf-8")

    assert output_file.exists()

    # Verify it's valid JSON
    with open(output_file, "r", encoding="utf-8") as f:
        notebook = json.load(f)
    assert "cells" in notebook


@pytest.mark.integration
def test_ipynb_cell_source_format(tmp_path):
    """Test that cell sources are properly formatted."""
    doc = Document(
        children=[
            Paragraph(content=[Text(content="Line 1\nLine 2\nLine 3")]),
        ]
    )

    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)
    cells = notebook["cells"]

    # Check that source is present and properly formatted
    for cell in cells:
        assert "source" in cell
        assert isinstance(cell["source"], (list, str))


@pytest.mark.integration
def test_ipynb_nbformat_version(tmp_path):
    """Test that nbformat version is specified."""
    doc = create_sample_document()
    renderer = IpynbRenderer()
    result = renderer.render_to_string(doc)

    notebook = json.loads(result)

    assert "nbformat" in notebook
    assert "nbformat_minor" in notebook
    assert notebook["nbformat"] >= 4  # Modern notebook format
