#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for sourcecode converter with the main all2md interface."""

import tempfile
from pathlib import Path

import pytest

from all2md import MarkdownOptions, SourceCodeOptions, to_markdown
from all2md.converter_registry import registry


class TestSourceCodeIntegration:
    """Test sourcecode converter integration with main interface."""

    def test_auto_format_detection(self):
        """Test that source code files are automatically detected."""
        # Test Python file
        python_content = """def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(10))"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(python_content)
            temp_path = f.name

        try:
            result = to_markdown(temp_path)
            assert result.startswith("```python\n")
            assert "def fibonacci(n):" in result
            assert result.endswith("\n```")
        finally:
            Path(temp_path).unlink()

    def test_explicit_format_specification(self):
        """Test explicitly specifying sourcecode format."""
        content = "function add(a, b) { return a + b; }"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = to_markdown(temp_path, source_format="sourcecode")
            assert result.startswith("```javascript\n")
            assert content in result
        finally:
            Path(temp_path).unlink()

    def test_options_integration(self):
        """Test integration with SourceCodeOptions."""
        content = "body { font-family: Arial; }"
        options = SourceCodeOptions(language_override="css", include_filename=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = to_markdown(temp_path, parser_options=options)
            assert result.startswith("```css\n")
            filename = Path(temp_path).name
            assert filename in result
        finally:
            Path(temp_path).unlink()

    def test_options_kwargs_interface(self):
        """Test passing options as kwargs."""
        content = "SELECT name FROM users WHERE age > 18;"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = to_markdown(temp_path, include_filename=True)
            assert result.startswith("```sql\n")
            filename = Path(temp_path).name
            assert filename in result
            assert "-- " in result  # SQL comment style
        finally:
            Path(temp_path).unlink()

    def test_mixed_options_and_kwargs(self):
        """Test combining options object with kwargs overrides."""
        content = "import pandas as pd\ndf = pd.DataFrame()"
        base_options = SourceCodeOptions(include_filename=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Override language while keeping filename inclusion
            result = to_markdown(temp_path, parser_options=base_options, language_override="text")
            assert result.startswith("```text\n")  # Language overridden
            filename = Path(temp_path).name
            assert filename in result  # Filename still included from base_options
        finally:
            Path(temp_path).unlink()

    def test_bytes_input_integration(self):
        """Test integration with bytes input."""
        content = "#!/usr/bin/env python3\nprint('Hello from bytes')"
        result = to_markdown(content.encode("utf-8"))

        # Without filename context, should fall back to plain text (not sourcecode)
        # This is the expected behavior since there's no way to detect the language
        assert result == content  # Should be plain text, not wrapped in code block

        # However, if we explicitly specify sourcecode format, it should work
        result_explicit = to_markdown(content.encode("utf-8"), source_format="sourcecode")
        assert result_explicit.startswith("```text\n")  # Default to text language
        assert "print('Hello from bytes')" in result_explicit

    def test_file_object_integration(self):
        """Test integration with file-like objects."""
        content = 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("Hello, Go!")\n}'

        # Create file with .go extension
        with tempfile.NamedTemporaryFile(mode="w", suffix=".go", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Open as file object
            with open(temp_path, "rb") as file_obj:
                result = to_markdown(file_obj)
                assert result.startswith("```go\n")
                assert "func main()" in result
        finally:
            Path(temp_path).unlink()

    def test_registry_integration(self):
        """Test that sourcecode converter is properly registered."""
        # Ensure auto-discovery has run
        registry.auto_discover()

        # Check that sourcecode format is registered
        assert "sourcecode" in registry.list_formats()

        # Get converter info
        metadata = registry.get_format_info("sourcecode")[0]

        assert metadata is not None
        assert metadata.format_name == "sourcecode"
        assert ".py" in metadata.extensions
        assert ".js" in metadata.extensions

        # Test parser retrieval (new AST system uses parsers instead of converters)
        parser_class = registry.get_parser("sourcecode")
        assert parser_class is not None

    def test_priority_over_txt_fallback(self):
        """Test that sourcecode converter has priority over txt fallback."""
        # Python files should be detected as sourcecode, not txt
        content = "print('This should be Python, not text')"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = to_markdown(temp_path)
            # Should be detected as Python sourcecode
            assert result.startswith("```python\n")
            # Should NOT be plain text
            assert not result.startswith("```text\n")
            assert not result == content  # Should be wrapped in code block
        finally:
            Path(temp_path).unlink()

    def test_multiple_file_formats(self):
        """Test detection of various source code formats."""
        test_files = [
            ("test.py", "print('Python')", "python"),
            ("test.js", "console.log('JavaScript');", "javascript"),
            ("test.java", "public class Test {}", "java"),
            ("test.cpp", "#include <iostream>", "cpp"),
            ("test.go", "package main", "go"),
            ("test.rs", "fn main() {}", "rust"),
            ("test.css", "body { margin: 0; }", "css"),
            ("test.yaml", "key: value", "yaml"),
            ("test.json", '{"key": "value"}', "json"),
            ("test.lua", "print('Hello Lua')", "lua"),
            ("test.pl", "print 'Hello Perl';", "perl"),
        ]

        for filename, content, expected_lang in test_files:
            with tempfile.NamedTemporaryFile(mode="w", suffix=f".{filename.split('.')[-1]}", delete=False) as f:
                f.write(content)
                temp_path = f.name

            try:
                # Explicitly use sourcecode format to bypass other parsers
                result = to_markdown(temp_path, source_format="sourcecode")
                assert result.startswith(f"```{expected_lang}\n"), f"Failed for {filename}: expected {expected_lang}"
                assert content in result
            finally:
                Path(temp_path).unlink()

    def test_markdown_options_integration(self):
        """Test integration with MarkdownOptions."""
        from all2md.options import MarkdownOptions

        content = "def greet(name):\n    return f'Hello, {name}!'"

        # Create options with metadata extraction and frontmatter enabled
        parser_options = SourceCodeOptions(extract_metadata=True)
        renderer_options = MarkdownOptions(emphasis_symbol="_", metadata_frontmatter=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = to_markdown(temp_path, parser_options=parser_options, renderer_options=renderer_options)
            # Should have code block (metadata extraction may or may not work)
            assert "```python\n" in result or "```python" in result
            assert "def greet(name)" in result
        finally:
            Path(temp_path).unlink()

    def test_error_handling_integration(self):
        """Test error handling through main interface."""
        from all2md.exceptions import ParsingError

        # Test with non-existent file
        with pytest.raises(ParsingError):
            to_markdown("/nonexistent/file.py")

        # Test with directory
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ParsingError):
                to_markdown(temp_dir, source_format="sourcecode")

    def test_format_detection_edge_cases(self):
        """Test edge cases in format detection."""
        # Test file without extension
        content = "#!/bin/bash\necho 'Hello'"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Without extension, should fall back to txt handling
            result = to_markdown(temp_path)
            # This will likely be plain text since no extension
            assert isinstance(result, str)
            assert content in result
        finally:
            Path(temp_path).unlink()

    def test_special_files_detection(self):
        """Test detection of special files like Dockerfile when using sourcecode format explicitly."""
        content = """FROM python:3.9
RUN pip install requests
CMD ["python", "app.py"]"""

        # Create Dockerfile (no extension)
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(content)
            temp_path = f.name

        # Rename to Dockerfile
        dockerfile_path = Path(temp_path).parent / "Dockerfile"
        Path(temp_path).rename(dockerfile_path)

        try:
            # Special files like Dockerfile are only detected when explicitly using sourcecode format
            # because they don't have extensions and the main format detection defaults to txt
            result = to_markdown(str(dockerfile_path), source_format="sourcecode")
            assert result.startswith("```dockerfile\n")
            assert "FROM python:3.9" in result

            # Test that without explicit format, it falls back to plain text
            result_auto = to_markdown(str(dockerfile_path))
            assert result_auto == content  # Should be plain text, not code block
        finally:
            dockerfile_path.unlink()


@pytest.mark.integration
class TestSourceCodeE2E:
    """End-to-end tests for sourcecode converter."""

    def test_full_conversion_pipeline(self):
        """Test complete conversion pipeline from file to markdown."""
        # Create a realistic Python file
        python_code = '''#!/usr/bin/env python3
"""A simple calculator module."""

import sys
from typing import Union

Number = Union[int, float]


class Calculator:
    """A basic calculator class."""

    def __init__(self):
        """Initialize the calculator."""
        self.history = []

    def add(self, a: Number, b: Number) -> Number:
        """Add two numbers."""
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result

    def subtract(self, a: Number, b: Number) -> Number:
        """Subtract b from a."""
        result = a - b
        self.history.append(f"{a} - {b} = {result}")
        return result


def main():
    """Main function."""
    calc = Calculator()
    print(calc.add(5, 3))
    print(calc.subtract(10, 4))


if __name__ == "__main__":
    main()
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(python_code)
            temp_path = f.name

        try:
            # Test with different option combinations
            md_options = MarkdownOptions(metadata_frontmatter=True)
            parser_options = SourceCodeOptions(include_filename=True, extract_metadata=True)

            result = to_markdown(temp_path, parser_options=parser_options, renderer_options=md_options)

            # Verify structure (metadata may or may not be present)
            assert "```python\n" in result or "```python" in result
            assert "#!/usr/bin/env python3" in result
            assert "class Calculator:" in result
            assert "def add(self" in result
            assert result.endswith("\n```") or result.endswith("```")

            # Verify filename comment is present
            filename = Path(temp_path).name
            assert f"# {filename}" in result

        finally:
            Path(temp_path).unlink()

    def test_performance_with_large_file(self):
        """Test performance with a reasonably large source file."""
        # Generate a large Python file
        lines = ["# This is a large Python file"]
        lines.extend([f"def function_{i}():" for i in range(1000)])
        lines.extend([f"    return {i}" for i in range(1000)])
        large_content = "\n".join(lines)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(large_content)
            temp_path = f.name

        try:
            # Should handle large files efficiently
            result = to_markdown(temp_path)
            assert result.startswith("```python\n")
            assert "def function_999():" in result
            assert len(result) > len(large_content)  # Should include code fences
        finally:
            Path(temp_path).unlink()
