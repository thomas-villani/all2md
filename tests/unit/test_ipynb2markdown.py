import json
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from all2md.parsers.ipynb2markdown import (
    _collapse_output,
    _get_source,
    ipynb_to_markdown,
)
from all2md.exceptions import InputError, MarkdownConversionError
from all2md.options import IpynbOptions


class TestCollapseOutput:
    """Tests for the _collapse_output helper function."""

    @pytest.mark.unit
    def test_collapse_output_no_limit(self):
        text = "Line 1\nLine 2\nLine 3\nLine 4"
        result = _collapse_output(text, None, "... truncated ...")
        assert result == text

    @pytest.mark.unit
    def test_collapse_output_under_limit(self):
        text = "Line 1\nLine 2\nLine 3"
        result = _collapse_output(text, 5, "... truncated ...")
        assert result == text

    @pytest.mark.unit
    def test_collapse_output_over_limit(self):
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        result = _collapse_output(text, 3, "... truncated ...")
        expected = "Line 1\nLine 2\nLine 3... truncated ..."
        assert result == expected

    @pytest.mark.unit
    def test_collapse_output_empty_text(self):
        result = _collapse_output("", 3, "... truncated ...")
        assert result == ""

    @pytest.mark.unit
    def test_collapse_output_none_text(self):
        result = _collapse_output(None, 3, "... truncated ...")
        assert result is None

    @pytest.mark.unit
    def test_collapse_output_single_line_no_truncation(self):
        text = "Single line"
        result = _collapse_output(text, 5, "... truncated ...")
        assert result == text


class TestGetSource:
    """Tests for the _get_source helper function."""

    @pytest.mark.unit
    def test_get_source_list(self):
        cell = {"source": ["line 1", "line 2", "line 3"]}
        result = _get_source(cell)
        assert result == "line 1line 2line 3"

    @pytest.mark.unit
    def test_get_source_string(self):
        cell = {"source": "single string source"}
        result = _get_source(cell)
        assert result == "single string source"

    @pytest.mark.unit
    def test_get_source_missing(self):
        cell = {}
        result = _get_source(cell)
        assert result == ""

    @pytest.mark.unit
    def test_get_source_none(self):
        cell = {"source": None}
        result = _get_source(cell)
        assert result == "None"

    @pytest.mark.unit
    def test_get_source_number(self):
        cell = {"source": 123}
        result = _get_source(cell)
        assert result == "123"

    @pytest.mark.unit
    def test_get_source_empty_list(self):
        cell = {"source": []}
        result = _get_source(cell)
        assert result == ""


class TestIpynbToMarkdown:
    """Tests for the main ipynb_to_markdown function."""

    def create_minimal_notebook(self, cells=None):
        """Create a minimal valid notebook structure for testing."""
        if cells is None:
            cells = []
        return {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "language": "python"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }

    @pytest.mark.unit
    def test_empty_notebook(self):
        notebook = self.create_minimal_notebook([])
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == ""

    @pytest.mark.unit
    def test_markdown_cell_conversion(self):
        cells = [
            {
                "cell_type": "markdown",
                "source": ["# Test Heading\n", "This is markdown content."]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == "# Test Heading\nThis is markdown content."

    @pytest.mark.unit
    def test_code_cell_conversion(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["print('Hello, World!')"],
                "outputs": []
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == "```python\nprint('Hello, World!')\n```"

    @pytest.mark.unit
    def test_code_cell_with_custom_language(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["console.log('Hello, World!');"],
                "outputs": []
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        notebook["metadata"]["kernelspec"]["language"] = "javascript"

        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == "```javascript\nconsole.log('Hello, World!');\n```"

    @pytest.mark.unit
    def test_code_cell_empty_source(self):
        cells = [
            {
                "cell_type": "code",
                "source": [""],
                "outputs": []
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == ""

    @pytest.mark.unit
    def test_stream_output_conversion(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["print('test')"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": ["test\n"]
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            expected = "```python\nprint('test')\n```\n\n```\ntest\n```"
            assert result == expected

    @pytest.mark.unit
    def test_execute_result_text_output(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["2 + 2"],
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {
                            "text/plain": ["4"]
                        }
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            expected = "```python\n2 + 2\n```\n\n```\n4\n```"
            assert result == expected

    @pytest.mark.unit
    @patch('all2md.parsers.ipynb.process_attachment')
    def test_execute_result_image_output(self, mock_process):
        mock_process.return_value = "![cell output](image.png)"

        # Create a simple 1x1 PNG image in base64
        png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

        cells = [
            {
                "cell_type": "code",
                "source": ["import matplotlib.pyplot as plt"],
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {
                            "image/png": png_data
                        }
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")

            expected = "```python\nimport matplotlib.pyplot as plt\n```\n\n![cell output](image.png)"
            assert result == expected
            mock_process.assert_called_once()

    @pytest.mark.unit
    def test_display_data_output(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["display('Hello')"],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "text/plain": ["'Hello'"]
                        }
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            expected = "```python\ndisplay('Hello')\n```\n\n```\n'Hello'\n```"
            assert result == expected

    @pytest.mark.unit
    def test_mixed_cell_types(self):
        cells = [
            {
                "cell_type": "markdown",
                "source": ["# Introduction"]
            },
            {
                "cell_type": "code",
                "source": ["x = 1"],
                "outputs": []
            },
            {
                "cell_type": "markdown",
                "source": ["Some explanation text."]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            expected = "# Introduction\n\n```python\nx = 1\n```\n\nSome explanation text."
            assert result == expected

    @pytest.mark.unit
    def test_truncate_long_outputs(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["for i in range(10): print(i)"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [f"{i}\n" for i in range(10)]
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        options = IpynbOptions(truncate_long_outputs=3)

        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb", options)

            # Should contain first 3 lines plus truncation message
            assert "0\n1\n2\n... (output truncated) ..." in result

    @pytest.mark.unit
    def test_custom_truncate_message(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["for i in range(5): print(i)"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [f"{i}\n" for i in range(5)]
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        options = IpynbOptions(
            truncate_long_outputs=2,
            truncate_output_message="\n... CUSTOM TRUNCATION MESSAGE ..."
        )

        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb", options)

            assert "... CUSTOM TRUNCATION MESSAGE ..." in result

    @pytest.mark.unit
    def test_path_input(self):
        notebook = self.create_minimal_notebook([])
        path_input = Path("test.ipynb")

        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown(path_input)
            assert result == ""

    @pytest.mark.unit
    def test_stringio_input(self):
        notebook = self.create_minimal_notebook([])
        string_input = StringIO(json.dumps(notebook))

        result = ipynb_to_markdown(string_input)
        assert result == ""

    @pytest.mark.unit
    def test_bytesio_input(self):
        notebook = self.create_minimal_notebook([])
        bytes_input = BytesIO(json.dumps(notebook).encode('utf-8'))

        result = ipynb_to_markdown(bytes_input)
        assert result == ""

    @pytest.mark.unit
    def test_invalid_json_raises_input_error(self):
        with patch('builtins.open', mock_open(read_data="invalid json")):
            with pytest.raises(InputError, match="not a valid JSON file"):
                ipynb_to_markdown("test.ipynb")

    @pytest.mark.unit
    def test_missing_cells_raises_input_error(self):
        invalid_notebook = {"nbformat": 4}
        with patch('builtins.open', mock_open(read_data=json.dumps(invalid_notebook))):
            with pytest.raises(InputError, match="'cells' key is missing"):
                ipynb_to_markdown("test.ipynb")

    @pytest.mark.unit
    def test_cells_not_list_raises_input_error(self):
        invalid_notebook = {"cells": "not a list"}
        with patch('builtins.open', mock_open(read_data=json.dumps(invalid_notebook))):
            with pytest.raises(InputError, match="not a list"):
                ipynb_to_markdown("test.ipynb")

    @pytest.mark.unit
    def test_unsupported_input_type_raises_input_error(self):
        with pytest.raises(InputError, match="Unsupported input type"):
            ipynb_to_markdown(123)

    @pytest.mark.unit
    def test_file_read_error_raises_conversion_error(self):
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(MarkdownConversionError, match="Failed to read or parse"):
                ipynb_to_markdown("nonexistent.ipynb")

    @pytest.mark.unit
    def test_default_options_used_when_none(self):
        notebook = self.create_minimal_notebook([])
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            # Should not raise an error with None options
            result = ipynb_to_markdown("test.ipynb", options=None)
            assert result == ""

    @pytest.mark.unit
    def test_unknown_cell_type_ignored(self):
        cells = [
            {
                "cell_type": "unknown",
                "source": ["This should be ignored"]
            },
            {
                "cell_type": "markdown",
                "source": ["This should be kept"]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == "This should be kept"

    @pytest.mark.unit
    def test_empty_stream_output_ignored(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["print('')"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": [""]
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == "```python\nprint('')\n```"

    @pytest.mark.unit
    @patch('all2md.parsers.ipynb.logger')
    def test_invalid_base64_image_logs_warning(self, mock_logger):
        cells = [
            {
                "cell_type": "code",
                "source": ["plt.show()"],
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {
                            "image/png": "invalid_base64_data!!!"
                        }
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")

            # Should handle gracefully and log warning
            mock_logger.warning.assert_called()
            # Should still show the code cell
            assert "```python\nplt.show()\n```" in result

    @pytest.mark.unit
    def test_multiple_outputs_per_cell(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["print('first'); print('second')"],
                "outputs": [
                    {
                        "output_type": "stream",
                        "text": ["first\n"]
                    },
                    {
                        "output_type": "stream",
                        "text": ["second\n"]
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")

            expected = "```python\nprint('first'); print('second')\n```\n\n```\nfirst\n```\n\n```\nsecond\n```"
            assert result == expected

    @pytest.mark.unit
    @patch('all2md.parsers.ipynb.process_attachment')
    def test_attachment_options_passed_to_process_attachment(self, mock_process):
        mock_process.return_value = "![cell output](image.png)"

        png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

        cells = [
            {
                "cell_type": "code",
                "source": ["plt.show()"],
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {
                            "image/png": png_data
                        }
                    }
                ]
            }
        ]
        notebook = self.create_minimal_notebook(cells)
        options = IpynbOptions(
            attachment_mode="download",
            attachment_output_dir="/custom/dir",
            attachment_base_url="https://example.com"
        )

        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            ipynb_to_markdown("test.ipynb", options)

            # Verify process_attachment was called with correct options
            mock_process.assert_called_once()
            call_args = mock_process.call_args
            assert call_args[1]['attachment_mode'] == "download"
            assert call_args[1]['attachment_output_dir'] == "/custom/dir"
            assert call_args[1]['attachment_base_url'] == "https://example.com"
            assert call_args[1]['is_image'] is True

    @pytest.mark.unit
    def test_no_kernel_language_defaults_to_python(self):
        cells = [
            {
                "cell_type": "code",
                "source": ["x = 1"],
                "outputs": []
            }
        ]
        notebook = {
            "cells": cells,
            "metadata": {},  # No kernelspec
            "nbformat": 4
        }

        with patch('builtins.open', mock_open(read_data=json.dumps(notebook))):
            result = ipynb_to_markdown("test.ipynb")
            assert result == "```python\nx = 1\n```"
