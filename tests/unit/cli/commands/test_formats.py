"""Unit tests for all2md CLI list-formats command handlers.

This module tests the list-formats command handler directly,
providing coverage for argument parsing and helper functions.
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from all2md.cli.commands.formats import (
    _create_list_formats_parser,
    _gather_format_info_data,
    _render_plain_detailed_format,
    _render_plain_summary_formats,
    handle_list_formats_command,
)


@pytest.mark.unit
class TestCreateListFormatsParser:
    """Test _create_list_formats_parser() function."""

    def test_parser_creation(self):
        """Test parser is created correctly."""
        parser = _create_list_formats_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "all2md list-formats"

    def test_parser_no_required_args(self):
        """Test parser works with no arguments."""
        parser = _create_list_formats_parser()
        args = parser.parse_args([])
        assert args.format is None
        assert args.available_only is False
        assert args.rich is False

    def test_parser_with_format_name(self):
        """Test parser with specific format name."""
        parser = _create_list_formats_parser()
        args = parser.parse_args(["pdf"])
        assert args.format == "pdf"

    def test_parser_available_only_flag(self):
        """Test parser with --available-only flag."""
        parser = _create_list_formats_parser()
        args = parser.parse_args(["--available-only"])
        assert args.available_only is True

    def test_parser_rich_flag(self):
        """Test parser with --rich flag."""
        parser = _create_list_formats_parser()
        args = parser.parse_args(["--rich"])
        assert args.rich is True

    def test_parser_all_flags_combined(self):
        """Test parser with format and flags."""
        parser = _create_list_formats_parser()
        args = parser.parse_args(["html", "--available-only", "--rich"])
        assert args.format == "html"
        assert args.available_only is True
        assert args.rich is True


@pytest.mark.unit
class TestGatherFormatInfoData:
    """Test _gather_format_info_data() function."""

    def test_gather_format_info_empty_list(self):
        """Test gathering info with empty format list."""
        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = []
            result = _gather_format_info_data([], available_only=False)
        assert result == []

    def test_gather_format_info_with_format(self):
        """Test gathering info for a format."""
        mock_metadata = MagicMock()
        mock_metadata.parser_required_packages = []
        mock_metadata.renderer_required_packages = []
        mock_metadata.parser_class = None
        mock_metadata.renderer_class = None

        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = [mock_metadata]
            result = _gather_format_info_data(["test_format"], available_only=False)

        assert len(result) == 1
        assert result[0]["name"] == "test_format"

    def test_gather_format_info_available_only_filters(self):
        """Test that available_only filters unavailable formats."""
        mock_metadata = MagicMock()
        # Simulate missing package
        mock_metadata.parser_required_packages = [("missing_pkg", "missing_pkg", None)]
        mock_metadata.renderer_required_packages = []
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = None

        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = [mock_metadata]
            with patch("all2md.cli.commands.formats.get_package_version", return_value=None):
                result = _gather_format_info_data(["test_format"], available_only=True)

        # Should be filtered out since dependency is missing
        assert len(result) == 0

    def test_gather_format_info_includes_available(self):
        """Test that available formats are included when available_only=True."""
        mock_metadata = MagicMock()
        mock_metadata.parser_required_packages = []
        mock_metadata.renderer_required_packages = []
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = MagicMock()

        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = [mock_metadata]
            result = _gather_format_info_data(["test_format"], available_only=True)

        assert len(result) == 1

    def test_gather_format_info_with_version_requirement(self):
        """Test gathering info with version requirement."""
        mock_metadata = MagicMock()
        mock_metadata.parser_required_packages = [("package", "package", ">=1.0")]
        mock_metadata.renderer_required_packages = []
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = None

        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = [mock_metadata]
            with patch("all2md.cli.commands.formats.check_version_requirement", return_value=(True, "1.5.0")):
                result = _gather_format_info_data(["test_format"], available_only=False)

        assert len(result) == 1
        assert result[0]["parser_available"] is True

    def test_gather_format_info_version_mismatch(self):
        """Test gathering info with version mismatch."""
        mock_metadata = MagicMock()
        mock_metadata.parser_required_packages = [("package", "package", ">=2.0")]
        mock_metadata.renderer_required_packages = []
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = None

        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = [mock_metadata]
            with patch(
                "all2md.cli.commands.formats.check_version_requirement",
                return_value=(False, "1.5.0"),  # Installed but wrong version
            ):
                result = _gather_format_info_data(["test_format"], available_only=False)

        assert len(result) == 1
        assert result[0]["parser_available"] is False
        # Should have mismatch status
        assert any(status == "mismatch" for _, _, status, _ in result[0]["parser_dep_status"])


@pytest.mark.unit
class TestRenderPlainDetailedFormat:
    """Test _render_plain_detailed_format() function."""

    def test_render_plain_detailed_basic(self, capsys):
        """Test basic detailed format rendering."""
        mock_metadata = MagicMock()
        mock_metadata.description = "Test format description"
        mock_metadata.extensions = [".test", ".tst"]
        mock_metadata.mime_types = ["application/test"]
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = None
        mock_metadata.priority = 100
        mock_metadata.get_parser_display_name.return_value = "TestParser"
        mock_metadata.get_renderer_display_name.return_value = "N/A"
        mock_metadata.parser_required_packages = []
        mock_metadata.renderer_required_packages = []

        info = {
            "name": "test",
            "metadata": mock_metadata,
            "parser_available": True,
            "renderer_available": False,
            "parser_dep_status": [],
            "renderer_dep_status": [],
        }

        _render_plain_detailed_format(info)
        captured = capsys.readouterr()

        assert "TEST Format" in captured.out
        assert "Test format description" in captured.out
        assert ".test" in captured.out
        assert "application/test" in captured.out

    def test_render_plain_detailed_with_dependencies(self, capsys):
        """Test detailed format rendering with dependencies."""
        mock_metadata = MagicMock()
        mock_metadata.description = "Format with deps"
        mock_metadata.extensions = [".test"]
        mock_metadata.mime_types = []
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = None
        mock_metadata.priority = 50
        mock_metadata.get_parser_display_name.return_value = "TestParser"
        mock_metadata.get_renderer_display_name.return_value = "N/A"
        mock_metadata.parser_required_packages = [("required_pkg", "required_pkg", ">=1.0")]
        mock_metadata.renderer_required_packages = []

        info = {
            "name": "test",
            "metadata": mock_metadata,
            "parser_available": True,
            "renderer_available": False,
            "parser_dep_status": [("required_pkg", ">=1.0", "ok", "1.5.0")],
            "renderer_dep_status": [],
        }

        _render_plain_detailed_format(info)
        captured = capsys.readouterr()

        assert "Parser Dependencies:" in captured.out
        assert "required_pkg" in captured.out
        assert "[OK]" in captured.out

    def test_render_plain_detailed_missing_dependency(self, capsys):
        """Test detailed format rendering with missing dependency."""
        mock_metadata = MagicMock()
        mock_metadata.description = "Format with missing dep"
        mock_metadata.extensions = [".test"]
        mock_metadata.mime_types = []
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = None
        mock_metadata.priority = 50
        mock_metadata.get_parser_display_name.return_value = "TestParser"
        mock_metadata.get_renderer_display_name.return_value = "N/A"
        mock_metadata.parser_required_packages = [("missing_pkg", "missing_pkg", None)]
        mock_metadata.renderer_required_packages = []

        info = {
            "name": "test",
            "metadata": mock_metadata,
            "parser_available": False,
            "renderer_available": False,
            "parser_dep_status": [("missing_pkg", None, "missing", None)],
            "renderer_dep_status": [],
        }

        _render_plain_detailed_format(info)
        captured = capsys.readouterr()

        assert "[MISSING]" in captured.out
        assert "pip install" in captured.out

    def test_render_plain_detailed_no_parser_or_renderer(self, capsys):
        """Test detailed format rendering with no parser or renderer."""
        mock_metadata = MagicMock()
        mock_metadata.description = "Empty format"
        mock_metadata.extensions = []
        mock_metadata.mime_types = []
        mock_metadata.parser_class = None
        mock_metadata.renderer_class = None
        mock_metadata.priority = 0
        mock_metadata.get_parser_display_name.return_value = "N/A"
        mock_metadata.get_renderer_display_name.return_value = "N/A"
        mock_metadata.parser_required_packages = []
        mock_metadata.renderer_required_packages = []

        info = {
            "name": "empty",
            "metadata": mock_metadata,
            "parser_available": False,
            "renderer_available": False,
            "parser_dep_status": [],
            "renderer_dep_status": [],
        }

        _render_plain_detailed_format(info)
        captured = capsys.readouterr()

        assert "No parser or renderer implemented" in captured.out


@pytest.mark.unit
class TestRenderPlainSummaryFormats:
    """Test _render_plain_summary_formats() function."""

    def test_render_plain_summary_empty(self, capsys):
        """Test summary rendering with empty list."""
        _render_plain_summary_formats([])
        captured = capsys.readouterr()

        assert "All2MD Supported Formats" in captured.out
        assert "Total: 0 formats" in captured.out

    def test_render_plain_summary_with_formats(self, capsys):
        """Test summary rendering with formats."""
        mock_metadata1 = MagicMock()
        mock_metadata1.extensions = [".pdf"]
        mock_metadata1.parser_class = MagicMock()
        mock_metadata1.renderer_class = MagicMock()

        mock_metadata2 = MagicMock()
        mock_metadata2.extensions = [".html", ".htm"]
        mock_metadata2.parser_class = MagicMock()
        mock_metadata2.renderer_class = None

        format_info_list = [
            {
                "name": "pdf",
                "metadata": mock_metadata1,
                "parser_available": True,
                "renderer_available": True,
                "parser_dep_status": [],
                "renderer_dep_status": [],
            },
            {
                "name": "html",
                "metadata": mock_metadata2,
                "parser_available": True,
                "renderer_available": False,
                "parser_dep_status": [],
                "renderer_dep_status": [],
            },
        ]

        _render_plain_summary_formats(format_info_list)
        captured = capsys.readouterr()

        assert "PDF" in captured.out
        assert "HTML" in captured.out
        assert "Total: 2 formats" in captured.out

    def test_render_plain_summary_shows_extensions(self, capsys):
        """Test summary rendering shows file extensions."""
        mock_metadata = MagicMock()
        mock_metadata.extensions = [".doc", ".docx", ".docm", ".dotx", ".dotm"]
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = None

        format_info_list = [
            {
                "name": "docx",
                "metadata": mock_metadata,
                "parser_available": True,
                "renderer_available": False,
                "parser_dep_status": [],
                "renderer_dep_status": [],
            },
        ]

        _render_plain_summary_formats(format_info_list)
        captured = capsys.readouterr()

        # Should show first 4 extensions and indicate more
        assert ".doc" in captured.out
        assert "+1" in captured.out  # Indicates 1 more extension


@pytest.mark.unit
class TestHandleListFormatsCommand:
    """Test handle_list_formats_command() function."""

    def test_list_all_formats(self, capsys):
        """Test listing all formats."""
        result = handle_list_formats_command([])
        assert result == 0
        captured = capsys.readouterr()
        assert "All2MD Supported Formats" in captured.out
        assert "Total:" in captured.out

    def test_list_specific_format(self, capsys):
        """Test listing a specific format."""
        # Use a format that should always exist
        result = handle_list_formats_command(["markdown"])
        assert result == 0
        captured = capsys.readouterr()
        assert "MARKDOWN" in captured.out or "markdown" in captured.out.lower()

    def test_nonexistent_format(self, capsys):
        """Test error when format doesn't exist."""
        result = handle_list_formats_command(["nonexistent_format_xyz"])
        assert result != 0
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_help_returns_zero(self):
        """Test --help returns exit code 0."""
        result = handle_list_formats_command(["--help"])
        assert result == 0

    def test_available_only_flag(self, capsys):
        """Test --available-only flag filters formats."""
        result = handle_list_formats_command(["--available-only"])
        assert result == 0
        captured = capsys.readouterr()
        # Should still show some output
        assert "Total:" in captured.out or "formats" in captured.out.lower()

    def test_rich_output_fallback(self, capsys, monkeypatch):
        """Test rich output falls back to plain when rich not available."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("rich"):
                raise ImportError("No module named 'rich'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        result = handle_list_formats_command(["--rich"])
        assert result == 0
        captured = capsys.readouterr()
        # Should still output something (plain text fallback)
        assert "All2MD Supported Formats" in captured.out or "Total:" in captured.out

    def test_plain_output_format(self, capsys):
        """Test plain text output contains expected sections."""
        result = handle_list_formats_command([])
        assert result == 0
        captured = capsys.readouterr()
        assert "=" in captured.out  # Separator line
        assert "Format" in captured.out  # Column header

    def test_specific_format_details(self, capsys):
        """Test specific format shows details."""
        # Use a common format
        result = handle_list_formats_command(["html"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Description:" in captured.out or "Extensions:" in captured.out

    def test_formats_alias_works(self, capsys):
        """Test that list-formats command works."""
        result = handle_list_formats_command([])
        assert result == 0


@pytest.mark.unit
class TestFormatInfoDataStructure:
    """Test format info data structure correctness."""

    def test_format_info_has_required_keys(self):
        """Test that gathered format info has all required keys."""
        mock_metadata = MagicMock()
        mock_metadata.parser_required_packages = []
        mock_metadata.renderer_required_packages = []
        mock_metadata.parser_class = MagicMock()
        mock_metadata.renderer_class = MagicMock()

        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = [mock_metadata]
            result = _gather_format_info_data(["test"], available_only=False)

        assert len(result) == 1
        info = result[0]

        # Check all required keys exist
        required_keys = [
            "name",
            "metadata",
            "all_available",
            "parser_available",
            "renderer_available",
            "parser_dep_status",
            "renderer_dep_status",
            "dep_status",  # Combined for backward compatibility
        ]
        for key in required_keys:
            assert key in info, f"Missing key: {key}"

    def test_format_info_no_metadata_returns_empty(self):
        """Test that format with no metadata returns empty list."""
        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = []
            result = _gather_format_info_data(["unknown_format"], available_only=False)

        assert result == []

    def test_format_info_none_metadata_returns_empty(self):
        """Test that format with None metadata returns empty list."""
        with patch("all2md.cli.commands.formats.registry") as mock_registry:
            mock_registry.get_format_info.return_value = None
            result = _gather_format_info_data(["unknown_format"], available_only=False)

        assert result == []
