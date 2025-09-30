#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for sourcecode2markdown converter."""

import io
import tempfile
from pathlib import Path

import pytest

from all2md.converters.sourcecode2markdown import (
    EXTENSION_TO_LANGUAGE,
    _detect_language_from_extension,
    _format_sourcecode_content,
    sourcecode_to_markdown,
)
from all2md.exceptions import MarkdownConversionError
from all2md.options import SourceCodeOptions


class TestLanguageDetection:
    """Test language detection from file extensions."""

    def test_python_detection(self):
        """Test Python file detection."""
        assert _detect_language_from_extension("script.py") == "python"
        assert _detect_language_from_extension("module.pyx") == "python"
        assert _detect_language_from_extension("/path/to/script.py") == "python"

    def test_javascript_detection(self):
        """Test JavaScript file detection."""
        assert _detect_language_from_extension("app.js") == "javascript"
        assert _detect_language_from_extension("module.mjs") == "javascript"
        assert _detect_language_from_extension("component.jsx") == "jsx"

    def test_typescript_detection(self):
        """Test TypeScript file detection."""
        assert _detect_language_from_extension("app.ts") == "typescript"
        assert _detect_language_from_extension("component.tsx") == "tsx"

    def test_c_cpp_detection(self):
        """Test C/C++ file detection."""
        assert _detect_language_from_extension("program.c") == "c"
        assert _detect_language_from_extension("header.h") == "c"
        assert _detect_language_from_extension("program.cpp") == "cpp"
        assert _detect_language_from_extension("header.hpp") == "cpp"

    def test_web_languages(self):
        """Test web technology detection."""
        assert _detect_language_from_extension("index.html") == "html"
        assert _detect_language_from_extension("styles.css") == "css"
        assert _detect_language_from_extension("styles.scss") == "scss"

    def test_config_files(self):
        """Test configuration file detection."""
        assert _detect_language_from_extension("config.yaml") == "yaml"
        assert _detect_language_from_extension("data.json") == "json"
        assert _detect_language_from_extension("config.toml") == "toml"
        assert _detect_language_from_extension("settings.ini") == "ini"

    def test_shell_scripts(self):
        """Test shell script detection."""
        assert _detect_language_from_extension("script.sh") == "bash"
        assert _detect_language_from_extension("script.bash") == "bash"
        assert _detect_language_from_extension("script.ps1") == "powershell"

    def test_special_files(self):
        """Test special files without extensions."""
        assert _detect_language_from_extension("Dockerfile") == "dockerfile"
        assert _detect_language_from_extension("Jenkinsfile") == "groovy"
        assert _detect_language_from_extension("Makefile") == "makefile"

    def test_objective_c_matlab_ambiguity(self):
        """Test handling of .m extension ambiguity."""
        # Default should be objective-c
        assert _detect_language_from_extension("MyClass.m") == "objective-c"

        # Files with "matlab" in name should be detected as matlab
        assert _detect_language_from_extension("matlab_script.m") == "matlab"
        assert _detect_language_from_extension("function_matlab.m") == "matlab"

    def test_unknown_extension(self):
        """Test handling of unknown extensions."""
        assert _detect_language_from_extension("file.unknown") == "text"
        assert _detect_language_from_extension("file") == "text"

    def test_empty_filename(self):
        """Test handling of empty filename."""
        assert _detect_language_from_extension("") == "text"
        assert _detect_language_from_extension(None) == "text"

    def test_case_insensitive(self):
        """Test case-insensitive extension detection."""
        assert _detect_language_from_extension("Script.PY") == "python"
        assert _detect_language_from_extension("APP.JS") == "javascript"


class TestContentFormatting:
    """Test source code content formatting."""

    def test_basic_formatting(self):
        """Test basic code block formatting."""
        content = "print('Hello, World!')"
        result = _format_sourcecode_content(content, "python")
        expected = "```python\nprint('Hello, World!')\n```"
        assert result == expected

    def test_formatting_with_filename(self):
        """Test formatting with filename comment."""
        content = "console.log('Hello');"
        result = _format_sourcecode_content(content, "javascript", "app.js", include_filename=True)
        expected = "```javascript\n// app.js\nconsole.log('Hello');\n```"
        assert result == expected

    def test_different_comment_styles(self):
        """Test different comment styles for different languages."""
        content = "SELECT * FROM users;"

        # SQL uses -- comments
        result = _format_sourcecode_content(content, "sql", "query.sql", include_filename=True)
        expected = "```sql\n-- query.sql\nSELECT * FROM users;\n```"
        assert result == expected

        # HTML uses <!-- --> comments
        html_content = "<h1>Title</h1>"
        result = _format_sourcecode_content(html_content, "html", "index.html", include_filename=True)
        expected = "```html\n<!-- index.html -->\n<h1>Title</h1>\n```"
        assert result == expected

    def test_multiline_content(self):
        """Test formatting of multiline content."""
        content = """def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)"""

        result = _format_sourcecode_content(content, "python")
        expected = f"```python\n{content}\n```"
        assert result == expected

    def test_content_stripping(self):
        """Test that content whitespace is properly stripped."""
        content = "\n\n  print('test')  \n\n"
        result = _format_sourcecode_content(content, "python")
        expected = "```python\nprint('test')\n```"
        assert result == expected


class TestSourceCodeToMarkdown:
    """Test the main sourcecode_to_markdown function."""

    def test_string_path_conversion(self):
        """Test conversion from file path string."""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def hello():\n    print('Hello, World!')")
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path)
            assert result.startswith("```python\n")
            assert "def hello():" in result
            assert result.endswith("\n```")
        finally:
            Path(temp_path).unlink()

    def test_path_object_conversion(self):
        """Test conversion from Path object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write("console.log('Hello');")
            temp_path = Path(f.name)

        try:
            result = sourcecode_to_markdown(temp_path)
            assert result.startswith("```javascript\n")
            assert "console.log('Hello');" in result
        finally:
            temp_path.unlink()

    def test_bytes_input(self):
        """Test conversion from bytes input."""
        content = "print('Hello from bytes')"
        result = sourcecode_to_markdown(content.encode("utf-8"))

        # Without filename, should default to text
        assert result.startswith("```text\n")
        assert content in result

    def test_file_like_object(self):
        """Test conversion from file-like object."""
        content = "function greet() { return 'Hello'; }"
        file_obj = io.BytesIO(content.encode("utf-8"))
        file_obj.name = "greet.js"  # Set name for language detection

        result = sourcecode_to_markdown(file_obj)
        assert result.startswith("```javascript\n")
        assert content in result

    def test_default_options(self):
        """Test conversion with default options."""
        content = "def test(): pass"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path)
            assert result.startswith("```python\n")
            assert content in result
            # Default options should not include filename
            assert f.name.split("/")[-1] not in result
        finally:
            Path(temp_path).unlink()

    def test_custom_options(self):
        """Test conversion with custom options."""
        content = "print('test')"
        options = SourceCodeOptions(language_override="text", include_filename=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path, options=options)
            # Should use language override
            assert result.startswith("```text\n")
            # Should include filename
            filename = Path(temp_path).name
            assert filename in result
        finally:
            Path(temp_path).unlink()

    def test_language_override(self):
        """Test language override option."""
        content = "SELECT * FROM table;"
        options = SourceCodeOptions(language_override="sql")

        # Use .txt extension but override to SQL
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path, options=options)
            assert result.startswith("```sql\n")
        finally:
            Path(temp_path).unlink()

    def test_detect_language_disabled(self):
        """Test with language detection disabled."""
        content = "print('test')"
        options = SourceCodeOptions(detect_language=False)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path, options=options)
            # Should default to text when detection is disabled
            assert result.startswith("```text\n")
        finally:
            Path(temp_path).unlink()

    def test_include_filename_option(self):
        """Test filename inclusion option."""
        content = "body { margin: 0; }"
        options = SourceCodeOptions(include_filename=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".css", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path, options=options)
            filename = Path(temp_path).name
            assert filename in result
            # CSS should use /* */ comments
            assert f"/* {filename} */" in result
        finally:
            Path(temp_path).unlink()

    def test_metadata_extraction(self):
        """Test metadata extraction option."""
        content = "#!/bin/bash\necho 'Hello'"
        options = SourceCodeOptions(extract_metadata=True)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path, options=options)
            # Should include metadata header
            assert "---" in result
            assert "format: sourcecode" in result
            assert "language: bash" in result
        finally:
            Path(temp_path).unlink()

    def test_encoding_error_handling(self):
        """Test handling of encoding errors."""
        # Create a file with invalid UTF-8
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            # Write some invalid UTF-8 bytes
            f.write(b"\xff\xfe\x00\x00invalid utf-8")
            temp_path = f.name

        try:
            # Should handle encoding errors gracefully
            result = sourcecode_to_markdown(temp_path)
            assert result.startswith("```python\n")
            # Content should be present (with replacement characters if needed)
            assert len(result) > 20  # More than just the code fence
        finally:
            Path(temp_path).unlink()

    def test_empty_file(self):
        """Test handling of empty files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Write empty content
            f.write("")
            temp_path = f.name

        try:
            result = sourcecode_to_markdown(temp_path)
            assert result == "```python\n\n```"
        finally:
            Path(temp_path).unlink()


class TestExtensionCoverage:
    """Test that all expected extensions are covered."""

    def test_extension_mapping_completeness(self):
        """Test that key extensions are mapped."""
        # Test some common extensions that should be present
        expected_extensions = [
            ".py",
            ".js",
            ".ts",
            ".java",
            ".cpp",
            ".c",
            ".go",
            ".rs",
            ".html",
            ".css",
            ".sql",
            ".yaml",
            ".json",
            ".md",
            ".sh",
        ]

        for ext in expected_extensions:
            assert ext in EXTENSION_TO_LANGUAGE, f"Extension {ext} not in mapping"

    def test_no_duplicate_python_mapping(self):
        """Test that Python extension is only mapped once."""
        # Check that we don't have conflicting Python mappings
        py_mappings = [k for k, v in EXTENSION_TO_LANGUAGE.items() if v == "python"]
        assert ".py" in py_mappings


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling scenarios."""

    def test_invalid_file_path(self):
        """Test handling of invalid file paths."""
        with pytest.raises(MarkdownConversionError):
            sourcecode_to_markdown("/nonexistent/file.py")

    def test_none_input(self):
        """Test handling of None input."""
        with pytest.raises((MarkdownConversionError, TypeError)):
            sourcecode_to_markdown(None)

    def test_directory_input(self):
        """Test handling of directory input."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(MarkdownConversionError):
                sourcecode_to_markdown(temp_dir)
