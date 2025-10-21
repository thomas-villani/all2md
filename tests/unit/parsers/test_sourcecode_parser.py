#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_sourcecode_ast.py
"""Unit tests for Source Code to AST converter.

Tests cover:
- CodeBlock creation with appropriate language
- Language detection from file extensions
- Language override options
- Filename comment insertion
- Comment style detection
- Edge cases with empty files

"""

import pytest

from all2md.ast import CodeBlock, Document
from all2md.options import SourceCodeOptions
from all2md.parsers.sourcecode import SourceCodeToAstConverter


@pytest.mark.unit
class TestBasicConversion:
    """Tests for basic source code conversion."""

    def test_simple_code_block(self) -> None:
        """Test converting simple source code."""
        content = "print('Hello, World!')"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert "print('Hello, World!')" in code_block.content

    def test_multiline_code(self) -> None:
        """Test converting multiline source code."""
        content = """def greet(name):
    return f'Hello, {name}!'

if __name__ == '__main__':
    print(greet('World'))"""

        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "def greet(name):" in code_block.content
        assert "return f'Hello, {name}!'" in code_block.content
        assert "if __name__ == '__main__':" in code_block.content

    def test_default_language_text(self) -> None:
        """Test default language is 'text' when no detection."""
        content = "Some content"
        options = SourceCodeOptions(detect_language=False)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content)

        code_block = doc.children[0]
        assert code_block.language == "text"


@pytest.mark.unit
class TestLanguageDetection:
    """Tests for language detection from filename."""

    def test_python_extension(self) -> None:
        """Test Python language detection."""
        content = "print('hello')"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="script.py")

        code_block = doc.children[0]
        assert code_block.language == "python"

    def test_javascript_extension(self) -> None:
        """Test JavaScript language detection."""
        content = "console.log('hello');"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="app.js")

        code_block = doc.children[0]
        assert code_block.language == "javascript"

    def test_typescript_extension(self) -> None:
        """Test TypeScript language detection."""
        content = "const x: number = 42;"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="types.ts")

        code_block = doc.children[0]
        assert code_block.language == "typescript"

    def test_cpp_extension(self) -> None:
        """Test C++ language detection."""
        content = "#include <iostream>"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="main.cpp")

        code_block = doc.children[0]
        assert code_block.language == "cpp"

    def test_rust_extension(self) -> None:
        """Test Rust language detection."""
        content = "fn main() {}"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="main.rs")

        code_block = doc.children[0]
        assert code_block.language == "rust"

    def test_go_extension(self) -> None:
        """Test Go language detection."""
        content = "package main"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="main.go")

        code_block = doc.children[0]
        assert code_block.language == "go"

    def test_java_extension(self) -> None:
        """Test Java language detection."""
        content = "public class Main {}"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="Main.java")

        code_block = doc.children[0]
        assert code_block.language == "java"

    def test_unknown_extension(self) -> None:
        """Test unknown extension defaults to text."""
        content = "Some content"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="file.unknown")

        code_block = doc.children[0]
        # Unknown extensions should default to text or empty
        assert code_block.language in ["text", ""]

    def test_detect_language_disabled(self) -> None:
        """Test language detection disabled."""
        content = "print('hello')"
        options = SourceCodeOptions(detect_language=False)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="script.py")

        code_block = doc.children[0]
        # Should use default 'text' instead of detecting 'python'
        assert code_block.language == "text"


@pytest.mark.unit
class TestLanguageOverride:
    """Tests for language override options."""

    def test_language_override_from_options(self) -> None:
        """Test language override from options."""
        content = "Some code"
        options = SourceCodeOptions(language_override="rust")
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="file.py")

        code_block = doc.children[0]
        # Should use override instead of detecting from .py extension
        assert code_block.language == "rust"

    def test_language_parameter_overrides_options(self) -> None:
        """Test language parameter overrides options."""
        content = "Some code"
        options = SourceCodeOptions(language_override="rust")
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="file.py", language="javascript")

        code_block = doc.children[0]
        # Explicit language parameter should take highest priority
        assert code_block.language == "javascript"

    def test_language_parameter_overrides_detection(self) -> None:
        """Test explicit language parameter overrides detection."""
        content = "print('hello')"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="script.py", language="ruby")

        code_block = doc.children[0]
        # Should use explicit language instead of detecting from .py
        assert code_block.language == "ruby"


@pytest.mark.unit
class TestFilenameComments:
    """Tests for filename comment insertion."""

    def test_include_filename_python(self) -> None:
        """Test filename comment for Python files."""
        content = "print('hello')"
        options = SourceCodeOptions(include_filename=True)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="/path/to/script.py", language="python")

        code_block = doc.children[0]
        # Should have filename comment with # prefix
        assert "# script.py" in code_block.content
        assert "print('hello')" in code_block.content

    def test_include_filename_javascript(self) -> None:
        """Test filename comment for JavaScript files."""
        content = "console.log('hello');"
        options = SourceCodeOptions(include_filename=True)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="app.js", language="javascript")

        code_block = doc.children[0]
        # Should have filename comment with // prefix
        assert "// app.js" in code_block.content
        assert "console.log('hello');" in code_block.content

    def test_include_filename_html(self) -> None:
        """Test filename comment for HTML files."""
        content = "<html></html>"
        options = SourceCodeOptions(include_filename=True)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="index.html", language="html")

        code_block = doc.children[0]
        # Should have filename comment with <!-- --> prefix
        assert "<!-- index.html -->" in code_block.content

    def test_include_filename_css(self) -> None:
        """Test filename comment for CSS files."""
        content = "body { margin: 0; }"
        options = SourceCodeOptions(include_filename=True)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="style.css", language="css")

        code_block = doc.children[0]
        # Should have filename comment with /* */ prefix
        assert "/* style.css */" in code_block.content

    def test_include_filename_sql(self) -> None:
        """Test filename comment for SQL files."""
        content = "SELECT * FROM users;"
        options = SourceCodeOptions(include_filename=True)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="query.sql", language="sql")

        code_block = doc.children[0]
        # Should have filename comment with -- prefix
        assert "-- query.sql" in code_block.content

    def test_include_filename_disabled(self) -> None:
        """Test filename comment not included when disabled."""
        content = "print('hello')"
        options = SourceCodeOptions(include_filename=False)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="script.py", language="python")

        code_block = doc.children[0]
        # Should not have filename comment
        assert "script.py" not in code_block.content
        assert "print('hello')" in code_block.content

    def test_include_filename_no_filename(self) -> None:
        """Test filename comment when no filename provided."""
        content = "print('hello')"
        options = SourceCodeOptions(include_filename=True)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename=None)

        code_block = doc.children[0]
        # Should not raise error, just not include filename
        assert "print('hello')" in code_block.content


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_content(self) -> None:
        """Test converting empty source code."""
        content = ""
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        code_block = doc.children[0]
        assert code_block.content == ""

    def test_whitespace_only_content(self) -> None:
        """Test converting whitespace-only content."""
        content = "   \n\n   "
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        code_block = doc.children[0]
        # Whitespace should be stripped
        assert code_block.content == ""

    def test_content_with_trailing_whitespace(self) -> None:
        """Test content with trailing whitespace is stripped."""
        content = "print('hello')   \n\n"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        code_block = doc.children[0]
        # Trailing whitespace should be stripped
        assert code_block.content.endswith(")")

    def test_content_with_leading_whitespace(self) -> None:
        """Test content with leading whitespace is stripped."""
        content = "\n\n   print('hello')"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        code_block = doc.children[0]
        # Leading whitespace should be stripped
        assert code_block.content.startswith("print")

    def test_code_with_special_characters(self) -> None:
        """Test code with special characters."""
        content = "s = 'Hello <world> & \"friends\"'"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        code_block = doc.children[0]
        # Special characters should be preserved
        assert "<world>" in code_block.content
        assert "&" in code_block.content
        assert '"friends"' in code_block.content

    def test_very_long_code(self) -> None:
        """Test handling very long source code."""
        content = "\n".join([f"line_{i} = {i}" for i in range(1000)])
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "line_0 = 0" in code_block.content
        assert "line_999 = 999" in code_block.content


@pytest.mark.unit
class TestMetadata:
    """Tests for metadata handling."""

    def test_metadata_contains_filename(self) -> None:
        """Test that metadata contains filename when provided."""
        content = "print('hello')"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename="test.py")

        code_block = doc.children[0]
        assert hasattr(code_block, "metadata")
        if code_block.metadata:
            assert "filename" in code_block.metadata
            assert code_block.metadata["filename"] == "test.py"

    def test_metadata_empty_when_no_filename(self) -> None:
        """Test that metadata is empty or None when no filename."""
        content = "print('hello')"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content, filename=None)

        code_block = doc.children[0]
        if hasattr(code_block, "metadata"):
            if code_block.metadata:
                assert "filename" not in code_block.metadata or code_block.metadata["filename"] is None


@pytest.mark.unit
class TestOptionsConfiguration:
    """Tests for SourceCodeOptions configuration."""

    def test_default_options(self) -> None:
        """Test conversion with default options."""
        content = "code"
        converter = SourceCodeToAstConverter()
        doc = converter.convert_to_ast(content)

        assert isinstance(doc, Document)
        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)

    def test_all_options_enabled(self) -> None:
        """Test with all options enabled."""
        content = "print('hello')"
        options = SourceCodeOptions(detect_language=True, include_filename=True, language_override=None)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="script.py")

        code_block = doc.children[0]
        assert code_block.language == "python"
        assert "script.py" in code_block.content

    def test_all_options_disabled(self) -> None:
        """Test with options disabled."""
        content = "print('hello')"
        options = SourceCodeOptions(detect_language=False, include_filename=False)
        converter = SourceCodeToAstConverter(options)
        doc = converter.convert_to_ast(content, filename="script.py")

        code_block = doc.children[0]
        assert code_block.language == "text"
        assert "script.py" not in code_block.content
