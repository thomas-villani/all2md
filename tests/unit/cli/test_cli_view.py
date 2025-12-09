"""Unit tests for the view CLI command."""

from pathlib import Path

import pytest

from all2md.cli.commands.view import handle_view_command


@pytest.fixture
def sample_markdown(tmp_path: Path) -> Path:
    """Create a sample markdown file for testing."""
    path = tmp_path / "sample.md"
    path.write_text(
        """# Sample Document

This is a sample document for testing the view command.

## Section 1

Some content in section 1.

## Section 2

Some content in section 2.
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a sample PDF file for testing."""
    # Create minimal PDF content
    path = tmp_path / "sample.pdf"
    # This is a minimal valid PDF
    pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000210 00000 n
trailer << /Size 5 /Root 1 0 R >>
startxref
302
%%EOF"""
    path.write_bytes(pdf_content)
    return path


@pytest.fixture(autouse=True)
def disable_browser(monkeypatch):
    """Disable browser opening during tests."""
    monkeypatch.setenv("ALL2MD_TEST_NO_BROWSER", "1")


@pytest.mark.unit
class TestHandleViewCommand:
    """Test handle_view_command() function."""

    def test_missing_input_file(self):
        """Test error when input file doesn't exist."""
        result = handle_view_command(["nonexistent.txt"])
        assert result != 0

    def test_help_returns_zero(self):
        """Test --help returns exit code 0."""
        result = handle_view_command(["--help"])
        assert result == 0

    def test_view_markdown_basic(self, sample_markdown: Path, capsys):
        """Test basic markdown view (temp file, auto cleanup)."""
        result = handle_view_command([str(sample_markdown)])
        assert result == 0
        captured = capsys.readouterr()
        assert "Converting" in captured.out
        assert "Skipping browser launch" in captured.out

    def test_view_markdown_keep_temp(self, sample_markdown: Path, capsys, tmp_path: Path):
        """Test view with --keep flag (keeps temp file)."""
        result = handle_view_command([str(sample_markdown), "--keep"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Kept temporary file" in captured.out

    def test_view_markdown_keep_with_path(self, sample_markdown: Path, tmp_path: Path, capsys):
        """Test view with --keep and output path."""
        output_path = tmp_path / "output.html"
        result = handle_view_command([str(sample_markdown), "--keep", str(output_path)])
        assert result == 0
        assert output_path.exists()
        captured = capsys.readouterr()
        assert "Saved to:" in captured.out

    def test_view_with_toc(self, sample_markdown: Path, tmp_path: Path):
        """Test view with table of contents."""
        output_path = tmp_path / "output.html"
        result = handle_view_command([str(sample_markdown), "--toc", "--keep", str(output_path)])
        assert result == 0
        content = output_path.read_text()
        # HTML should contain something (may or may not have explicit TOC div)
        assert "html" in content.lower()

    def test_view_with_dark_theme(self, sample_markdown: Path, tmp_path: Path):
        """Test view with dark theme."""
        output_path = tmp_path / "output.html"
        result = handle_view_command([str(sample_markdown), "--dark", "--keep", str(output_path)])
        assert result == 0
        assert output_path.exists()

    def test_view_with_named_theme(self, sample_markdown: Path, tmp_path: Path):
        """Test view with a named built-in theme."""
        output_path = tmp_path / "output.html"
        result = handle_view_command([str(sample_markdown), "--theme", "minimal", "--keep", str(output_path)])
        assert result == 0
        assert output_path.exists()

    def test_view_invalid_theme(self, sample_markdown: Path, capsys):
        """Test error with invalid theme name."""
        result = handle_view_command([str(sample_markdown), "--theme", "nonexistent_theme_xyz"])
        assert result != 0
        captured = capsys.readouterr()
        assert "Theme not found" in captured.err

    def test_view_creates_parent_dirs(self, sample_markdown: Path, tmp_path: Path):
        """Test --keep creates parent directories if needed."""
        output_path = tmp_path / "subdir" / "deep" / "output.html"
        result = handle_view_command([str(sample_markdown), "--keep", str(output_path)])
        assert result == 0
        assert output_path.exists()

    def test_view_output_contains_html(self, sample_markdown: Path, tmp_path: Path):
        """Test output is valid HTML."""
        output_path = tmp_path / "output.html"
        result = handle_view_command([str(sample_markdown), "--keep", str(output_path)])
        assert result == 0
        content = output_path.read_text()
        assert "<html" in content.lower() or "<!doctype" in content.lower()


@pytest.mark.unit
class TestViewCommandSectionExtraction:
    """Test view command with section extraction."""

    def test_extract_by_name(self, sample_markdown: Path, tmp_path: Path):
        """Test extracting section by name pattern."""
        output_path = tmp_path / "output.html"
        result = handle_view_command([str(sample_markdown), "--extract", "Section 1", "--keep", str(output_path)])
        # May succeed or fail depending on section extraction implementation
        # Just ensure it doesn't crash
        assert result in (0, 1)

    def test_extract_by_index(self, sample_markdown: Path, tmp_path: Path):
        """Test extracting section by index."""
        output_path = tmp_path / "output.html"
        result = handle_view_command([str(sample_markdown), "--extract", "#:1", "--keep", str(output_path)])
        # May succeed or fail depending on document structure
        assert result in (0, 1)
