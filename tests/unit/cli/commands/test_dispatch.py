"""Unit tests for all2md CLI command dispatch functionality.

This module tests the dispatch_command function that routes
commands to their appropriate handlers.
"""

from unittest.mock import patch

import pytest

from all2md.cli.commands import dispatch_command


@pytest.mark.unit
class TestDispatchCommand:
    """Test dispatch_command() function."""

    def test_dispatch_empty_args_returns_none(self):
        """Test dispatch with empty args returns None."""
        result = dispatch_command([])
        assert result is None

    def test_dispatch_none_args_uses_sys_argv(self, monkeypatch):
        """Test dispatch with None args uses sys.argv."""
        monkeypatch.setattr("sys.argv", ["all2md"])
        result = dispatch_command(None)
        assert result is None

    def test_dispatch_unknown_command_returns_none(self):
        """Test dispatch with unknown command returns None."""
        result = dispatch_command(["unknown_cmd", "arg1"])
        assert result is None

    def test_dispatch_completion_command(self):
        """Test dispatch routes completion command."""
        with patch("all2md.cli.commands.completion.handle_completion_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["completion", "bash"])

            mock_handler.assert_called_once()
            assert result == 0

    def test_dispatch_config_command(self):
        """Test dispatch routes config command."""
        with patch("all2md.cli.commands.config.handle_config_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["config", "show"])

            mock_handler.assert_called_once()
            assert result == 0

    def test_dispatch_view_command(self):
        """Test dispatch routes view command."""
        with patch("all2md.cli.commands.view.handle_view_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["view", "test.pdf"])

            mock_handler.assert_called_once_with(["test.pdf"])
            assert result == 0

    def test_dispatch_serve_command(self):
        """Test dispatch routes serve command."""
        with patch("all2md.cli.commands.server.handle_serve_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["serve", "directory"])

            mock_handler.assert_called_once_with(["directory"])
            assert result == 0

    def test_dispatch_generate_site_command(self):
        """Test dispatch routes generate-site command."""
        with patch("all2md.cli.commands.generate_site.handle_generate_site_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["generate-site", "--out", "docs"])

            mock_handler.assert_called_once_with(["--out", "docs"])
            assert result == 0

    def test_dispatch_search_command(self):
        """Test dispatch routes search command."""
        with patch("all2md.cli.commands.search.handle_search_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["search", "query", "file.md"])

            mock_handler.assert_called_once_with(["query", "file.md"])
            assert result == 0

    def test_dispatch_grep_command(self):
        """Test dispatch routes grep command."""
        with patch("all2md.cli.commands.search.handle_grep_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["grep", "pattern", "file.md"])

            mock_handler.assert_called_once_with(["pattern", "file.md"])
            assert result == 0

    def test_dispatch_diff_command(self):
        """Test dispatch routes diff command."""
        with patch("all2md.cli.commands.diff.handle_diff_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["diff", "file1.md", "file2.md"])

            mock_handler.assert_called_once_with(["file1.md", "file2.md"])
            assert result == 0

    def test_dispatch_list_formats_command(self):
        """Test dispatch routes list-formats command."""
        with patch("all2md.cli.commands.formats.handle_list_formats_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["list-formats"])

            mock_handler.assert_called_once_with([])
            assert result == 0

    def test_dispatch_formats_alias(self):
        """Test dispatch routes formats alias."""
        with patch("all2md.cli.commands.formats.handle_list_formats_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["formats"])

            mock_handler.assert_called_once_with([])
            assert result == 0

    def test_dispatch_list_transforms_command(self):
        """Test dispatch routes list-transforms command."""
        with patch("all2md.cli.commands.transforms.handle_list_transforms_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["list-transforms"])

            mock_handler.assert_called_once_with([])
            assert result == 0

    def test_dispatch_transforms_alias(self):
        """Test dispatch routes transforms alias."""
        with patch("all2md.cli.commands.transforms.handle_list_transforms_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["transforms"])

            mock_handler.assert_called_once_with([])
            assert result == 0

    def test_dispatch_check_deps_command(self):
        """Test dispatch routes check-deps command."""
        with patch("all2md.dependencies.main") as mock_deps_main:
            mock_deps_main.return_value = 0
            result = dispatch_command(["check-deps"])

            mock_deps_main.assert_called_once()
            assert result == 0

    def test_dispatch_check_deps_with_format(self):
        """Test dispatch check-deps with format argument."""
        with patch("all2md.dependencies.main") as mock_deps_main:
            mock_deps_main.return_value = 0
            result = dispatch_command(["check-deps", "pdf"])

            mock_deps_main.assert_called_once()
            call_args = mock_deps_main.call_args[0][0]
            assert "--format" in call_args
            assert "pdf" in call_args
            assert result == 0

    def test_dispatch_check_deps_with_json(self):
        """Test dispatch check-deps with --json flag."""
        with patch("all2md.dependencies.main") as mock_deps_main:
            mock_deps_main.return_value = 0
            result = dispatch_command(["check-deps", "--json"])

            mock_deps_main.assert_called_once()
            call_args = mock_deps_main.call_args[0][0]
            assert "--json" in call_args
            assert result == 0

    def test_dispatch_check_deps_with_rich(self):
        """Test dispatch check-deps with --rich flag."""
        with patch("all2md.dependencies.main") as mock_deps_main:
            mock_deps_main.return_value = 0
            result = dispatch_command(["check-deps", "--rich"])

            mock_deps_main.assert_called_once()
            call_args = mock_deps_main.call_args[0][0]
            assert "--rich" in call_args
            assert result == 0

    def test_dispatch_check_deps_with_help(self):
        """Test dispatch check-deps with --help flag."""
        with patch("all2md.dependencies.main") as mock_deps_main:
            mock_deps_main.return_value = 0
            result = dispatch_command(["check-deps", "--help"])

            mock_deps_main.assert_called_once()
            call_args = mock_deps_main.call_args[0][0]
            assert "--help" in call_args
            assert result == 0

    def test_dispatch_check_deps_combined_flags(self):
        """Test dispatch check-deps with format and flags."""
        with patch("all2md.dependencies.main") as mock_deps_main:
            mock_deps_main.return_value = 0
            result = dispatch_command(["check-deps", "docx", "--json", "--rich"])

            mock_deps_main.assert_called_once()
            call_args = mock_deps_main.call_args[0][0]
            assert "check" in call_args
            assert "--format" in call_args
            assert "docx" in call_args
            assert "--json" in call_args
            assert "--rich" in call_args
            assert result == 0


@pytest.mark.unit
class TestDispatchCommandWithArgs:
    """Test dispatch_command with various argument patterns."""

    def test_dispatch_preserves_args_order(self):
        """Test that argument order is preserved."""
        with patch("all2md.cli.commands.search.handle_search_command") as mock_handler:
            mock_handler.return_value = 0
            dispatch_command(["search", "query", "file1.md", "file2.md", "--recursive"])

            args_passed = mock_handler.call_args[0][0]
            assert args_passed == ["query", "file1.md", "file2.md", "--recursive"]

    def test_dispatch_view_strips_command(self):
        """Test that view command strips 'view' from args."""
        with patch("all2md.cli.commands.view.handle_view_command") as mock_handler:
            mock_handler.return_value = 0
            dispatch_command(["view", "document.pdf", "--no-browser"])

            args_passed = mock_handler.call_args[0][0]
            assert args_passed == ["document.pdf", "--no-browser"]
            assert "view" not in args_passed

    def test_dispatch_serve_strips_command(self):
        """Test that serve command strips 'serve' from args."""
        with patch("all2md.cli.commands.server.handle_serve_command") as mock_handler:
            mock_handler.return_value = 0
            dispatch_command(["serve", ".", "--port", "9000"])

            args_passed = mock_handler.call_args[0][0]
            assert args_passed == [".", "--port", "9000"]
            assert "serve" not in args_passed


@pytest.mark.unit
class TestDispatchCommandReturnValues:
    """Test dispatch_command return value handling."""

    def test_dispatch_returns_handler_exit_code(self):
        """Test dispatch returns handler's exit code."""
        with patch("all2md.cli.commands.view.handle_view_command") as mock_handler:
            mock_handler.return_value = 42
            result = dispatch_command(["view", "test.pdf"])
            assert result == 42

    def test_dispatch_returns_none_for_non_command(self):
        """Test dispatch returns None for non-command arguments."""
        # Arguments that look like file paths, not commands
        result = dispatch_command(["test.pdf", "--out", "output.md"])
        assert result is None

    def test_dispatch_handles_handler_exception(self):
        """Test that dispatch doesn't catch handler exceptions."""
        with patch("all2md.cli.commands.view.handle_view_command") as mock_handler:
            mock_handler.side_effect = ValueError("Test error")

            with pytest.raises(ValueError, match="Test error"):
                dispatch_command(["view", "test.pdf"])
