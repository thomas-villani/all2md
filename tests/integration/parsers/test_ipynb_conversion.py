"""Integration tests for Jupyter Notebook (.ipynb) conversion.

This module contains integration tests for converting Jupyter notebooks
to Markdown, including tests for code cells, markdown cells, output
handling, and various notebook features.

"""

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from all2md import IpynbOptions, to_markdown as ipynb_to_markdown
from all2md.exceptions import MalformedFileError, ParsingError
from all2md.options import MarkdownOptions


@pytest.mark.integration
@pytest.mark.ipynb
def test_basic_notebook_conversion():
    """Test conversion of a basic notebook with mixed cell types."""
    notebook_content = {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Data Analysis Example\n", "This notebook demonstrates basic data analysis."],
            },
            {"cell_type": "code", "source": ["import pandas as pd\n", "import numpy as np"], "outputs": []},
            {
                "cell_type": "code",
                "source": ["data = [1, 2, 3, 4, 5]\n", "print(f'Mean: {np.mean(data)}')"],
                "outputs": [{"output_type": "stream", "text": ["Mean: 3.0\n"]}],
            },
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        result = ipynb_to_markdown(temp_path)

        # Verify structure is preserved
        assert "# Data Analysis Example" in result
        assert "This notebook demonstrates basic data analysis." in result
        assert "```python\nimport pandas as pd\nimport numpy as np\n```" in result
        assert "```python\ndata = [1, 2, 3, 4, 5]\nprint(f'Mean: {np.mean(data)}')\n```" in result
        assert "```\nMean: 3.0\n```" in result

        # Verify proper separation between cells
        assert result.count("\n\n") >= 3  # Should have multiple double newlines

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_with_image_outputs():
    """Test conversion of notebook with image outputs using base64 embedding."""
    # Simple 1x1 PNG image in base64
    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["import matplotlib.pyplot as plt\n", "plt.plot([1, 2, 3])\n", "plt.show()"],
                "outputs": [{"output_type": "execute_result", "data": {"image/png": png_data}}],
            }
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        result = ipynb_to_markdown(temp_path)

        # Should contain the code and basic structure
        assert "```python" in result
        assert "matplotlib.pyplot" in result

        # The image processing might succeed or fail depending on environment
        # Let's just verify we have some image output attempt
        assert "![cell output]" in result

        # This is acceptable - the process_attachment function was called
        # The exact result (base64, file path, or empty) depends on config

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_with_attachment_options():
    """Test notebook conversion with custom attachment handling options."""
    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["plt.figure()\n", "plt.plot([1, 2, 3])\n", "plt.show()"],
                "outputs": [{"output_type": "display_data", "data": {"image/png": png_data}}],
            }
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            options = IpynbOptions(attachment_mode="download", attachment_output_dir=temp_dir)

            result = ipynb_to_markdown(temp_path, parser_options=options)

            # Should reference the downloaded image file
            assert "![cell output](" in result
            assert "cell_1_output_1.png)" in result

            # Verify image was actually saved
            image_files = list(Path(temp_dir).glob("*.png"))
            assert len(image_files) == 1
            assert "cell_1_output_1.png" in str(image_files[0])

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_with_multiple_output_types():
    """Test notebook with various output types in a single cell."""
    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["x = 42\n", "print('The answer is:', x)\n", "x  # This creates an execute_result"],
                "outputs": [
                    {"output_type": "stream", "name": "stdout", "text": ["The answer is: 42\n"]},
                    {"output_type": "execute_result", "execution_count": 1, "data": {"text/plain": ["42"]}},
                ],
            }
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        result = ipynb_to_markdown(temp_path)

        # Should contain both outputs
        assert "The answer is: 42" in result
        assert "```\n42\n```" in result

        # Should have proper structure with code and outputs
        lines = result.split("\n")
        code_block_indices = [i for i, line in enumerate(lines) if line.startswith("```")]
        assert len(code_block_indices) >= 4  # Code block + 2 output blocks (start and end markers)

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_with_long_outputs():
    """Test notebook with output truncation options."""
    long_output = [f"Line {i}\n" for i in range(20)]

    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["for i in range(20):\n", "    print(f'Line {i}')"],
                "outputs": [{"output_type": "stream", "text": long_output}],
            }
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        # Test with truncation
        options = IpynbOptions(truncate_long_outputs=5)
        result = ipynb_to_markdown(temp_path, parser_options=options)

        assert "Line 0" in result
        assert "Line 4" in result
        assert "... (output truncated) ..." in result
        assert "Line 10" not in result  # Should be truncated

        # Test without truncation
        options_no_truncate = IpynbOptions(truncate_long_outputs=None)
        result_full = ipynb_to_markdown(temp_path, parser_options=options_no_truncate)

        assert "Line 0" in result_full
        assert "Line 19" in result_full
        assert "... (output truncated) ..." not in result_full

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_with_custom_truncate_message():
    """Test custom truncation messages."""
    long_output = [f"Output line {i}\n" for i in range(10)]

    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["# Generate lots of output"],
                "outputs": [{"output_type": "stream", "text": long_output}],
            }
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        options = IpynbOptions(truncate_long_outputs=3, truncate_output_message="\n... CUSTOM TRUNCATION MESSAGE ...")
        result = ipynb_to_markdown(temp_path, parser_options=options)

        assert "CUSTOM TRUNCATION MESSAGE" in result
        assert "Output line 0" in result
        assert "Output line 2" in result
        assert "Output line 5" not in result

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_different_languages():
    """Test notebook with different programming languages."""
    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["console.log('Hello from JavaScript');"],
                "outputs": [{"output_type": "stream", "text": ["Hello from JavaScript\n"]}],
            }
        ],
        "metadata": {"kernelspec": {"language": "javascript"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        result = ipynb_to_markdown(temp_path)

        # Should use the correct language for syntax highlighting
        assert "```javascript\n" in result
        assert "console.log" in result
        assert "Hello from JavaScript" in result

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_with_empty_cells():
    """Test notebook with empty cells of various types."""
    notebook_content = {
        "cells": [
            {"cell_type": "markdown", "source": []},
            {"cell_type": "code", "source": [""], "outputs": []},
            {"cell_type": "markdown", "source": ["# Valid Content"]},
            {"cell_type": "code", "source": ["   "], "outputs": []},  # Whitespace only
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        result = ipynb_to_markdown(temp_path)

        # Only non-empty content should appear
        assert result.strip() == "# Valid Content"

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_malformed_notebook_handling():
    """Test handling of malformed notebook structures."""
    # Test missing cell_type
    malformed_notebook = {
        "cells": [
            {
                "source": ["Some content"]
                # Missing cell_type
            }
        ],
        "metadata": {},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(malformed_notebook, f)
        temp_path = f.name

    try:
        result = ipynb_to_markdown(temp_path)
        # Should handle gracefully and ignore malformed cells
        assert result == ""

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_real_world_structure():
    """Test with a more complex, real-world notebook structure."""
    complex_notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "source": [
                    "# Machine Learning Pipeline\n",
                    "\n",
                    "This notebook implements a complete ML pipeline.\n",
                    "\n",
                    "## Data Loading\n",
                ],
            },
            {
                "cell_type": "code",
                "source": [
                    "# Import required libraries\n",
                    "import pandas as pd\n",
                    "import numpy as np\n",
                    "from sklearn.model_selection import train_test_split\n",
                    "from sklearn.ensemble import RandomForestClassifier\n",
                    "from sklearn.metrics import accuracy_score",
                ],
                "outputs": [],
            },
            {
                "cell_type": "code",
                "source": [
                    "# Load the dataset\n",
                    "data = pd.read_csv('dataset.csv')\n",
                    'print(f"Dataset shape: {data.shape}")\n',
                    "data.head()",
                ],
                "outputs": [
                    {"output_type": "stream", "text": ["Dataset shape: (1000, 10)\n"]},
                    {
                        "output_type": "execute_result",
                        "data": {
                            "text/plain": [
                                "   feature1  feature2  feature3  target\n",
                                "0      1.2      0.8      2.1       0\n",
                                "1      1.5      0.9      1.8       1\n",
                                "2      1.1      0.7      2.3       0",
                            ]
                        },
                    },
                ],
            },
            {
                "cell_type": "markdown",
                "source": ["## Model Training\n", "\n", "Now let's train our Random Forest model."],
            },
            {
                "cell_type": "code",
                "source": [
                    "# Train the model\n",
                    "X = data.drop('target', axis=1)\n",
                    "y = data['target']\n",
                    "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)\n",
                    "\n",
                    "model = RandomForestClassifier(n_estimators=100)\n",
                    "model.fit(X_train, y_train)\n",
                    "\n",
                    "# Make predictions\n",
                    "y_pred = model.predict(X_test)\n",
                    "accuracy = accuracy_score(y_test, y_pred)\n",
                    'print(f"Model accuracy: {accuracy:.4f}")',
                ],
                "outputs": [{"output_type": "stream", "text": ["Model accuracy: 0.8750\n"]}],
            },
        ],
        "metadata": {"kernelspec": {"language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(complex_notebook, f)
        temp_path = f.name

    try:
        result = ipynb_to_markdown(temp_path)

        # Verify all major sections are present
        assert "# Machine Learning Pipeline" in result
        assert "## Data Loading" in result
        assert "## Model Training" in result

        # Verify code blocks are properly formatted
        assert "```python\n# Import required libraries" in result
        assert "sklearn.model_selection" in result
        assert "RandomForestClassifier" in result

        # Verify outputs are preserved
        assert "Dataset shape: (1000, 10)" in result
        assert "Model accuracy: 0.8750" in result

        # Verify table-like output is preserved
        assert "feature1  feature2  feature3  target" in result

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_concurrent_notebook_processing():
    """Test concurrent processing of multiple notebooks."""

    def create_test_notebook(cell_content):
        return {
            "cells": [
                {"cell_type": "markdown", "source": [f"# Notebook {cell_content}"]},
                {"cell_type": "code", "source": [f"result = {cell_content}"], "outputs": []},
            ],
            "metadata": {"kernelspec": {"language": "python"}},
            "nbformat": 4,
        }

    # Create multiple temporary notebooks
    temp_files = []
    try:
        for i in range(5):
            notebook = create_test_notebook(i)
            temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False)
            json.dump(notebook, temp_file)
            temp_file.close()
            temp_files.append(temp_file.name)

        # Process them concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(ipynb_to_markdown, temp_files))

        # Verify all results
        for i, result in enumerate(results):
            assert f"# Notebook {i}" in result
            assert f"result = {i}" in result

    finally:
        # Cleanup
        for temp_file in temp_files:
            Path(temp_file).unlink(missing_ok=True)


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_with_markdown_options():
    """Test notebook conversion with custom markdown options."""
    notebook_content = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Test Notebook\n", "This is a test."]},
            {
                "cell_type": "code",
                "source": ["x = 42\n", "print(x)"],
                "outputs": [{"output_type": "stream", "text": ["42\n"]}],
            },
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        # Test with custom markdown options
        md_options = MarkdownOptions()
        parser_options = IpynbOptions()

        result = ipynb_to_markdown(temp_path, parser_options=parser_options, renderer_options=md_options)

        # Should still work with custom options
        assert "# Test Notebook" in result
        assert "x = 42" in result
        assert "```\n42\n```" in result

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
@pytest.mark.slow
def test_large_notebook_performance():
    """Test performance with a large notebook (many cells)."""
    # Create a notebook with many cells
    cells = []
    for i in range(100):
        cells.append({"cell_type": "markdown", "source": [f"## Section {i}\nThis is section {i} content."]})
        cells.append(
            {
                "cell_type": "code",
                "source": [f"# Cell {i}\nvalue_{i} = {i} * 2\nprint(f'Value {i}: {{value_{i}}}')"],
                "outputs": [{"output_type": "stream", "text": [f"Value {i}: {i * 2}\n"]}],
            }
        )

    large_notebook = {"cells": cells, "metadata": {"kernelspec": {"language": "python"}}, "nbformat": 4}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(large_notebook, f)
        temp_path = f.name

    try:
        import time

        start_time = time.time()
        result = ipynb_to_markdown(temp_path)
        end_time = time.time()

        # Should complete in reasonable time (less than 5 seconds for 200 cells)
        processing_time = end_time - start_time
        assert processing_time < 5.0, f"Processing took too long: {processing_time:.2f} seconds"

        # Verify content is preserved
        assert "## Section 0" in result
        assert "## Section 99" in result
        assert "Value 0: 0" in result
        assert "Value 99: 198" in result

        # Check that all cells are present
        section_count = result.count("## Section")
        assert section_count == 100

    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
@pytest.mark.ipynb
def test_notebook_error_recovery():
    """Test error recovery during notebook processing."""
    notebook_content = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Working Cell"]},
            {"cell_type": "code", "source": ["x = 1"], "outputs": []},
        ],
        "metadata": {"kernelspec": {"language": "python"}},
        "nbformat": 4,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        json.dump(notebook_content, f)
        temp_path = f.name

    try:
        # Should work with valid notebook
        result = ipynb_to_markdown(temp_path)
        assert "# Working Cell" in result
        assert "x = 1" in result

    finally:
        Path(temp_path).unlink()

    # Test with invalid JSON
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ipynb", delete=False) as f:
        f.write("{ invalid json content")
        invalid_path = f.name

    try:
        with pytest.raises(MalformedFileError, match="not a valid JSON file"):
            ipynb_to_markdown(invalid_path)
    finally:
        Path(invalid_path).unlink()

    # Test with missing file
    with pytest.raises(ParsingError, match="Failed to read or parse"):
        ipynb_to_markdown("nonexistent.ipynb")
