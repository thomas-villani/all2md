"""Unit tests for the list-transforms CLI command."""

import argparse
from unittest.mock import patch

import pytest

from all2md.cli.commands.transforms import (
    _create_list_transforms_parser,
    handle_list_transforms_command,
)


@pytest.mark.unit
class TestCreateListTransformsParser:
    """Test _create_list_transforms_parser() function."""

    def test_parser_creation(self):
        """Test parser is created correctly."""
        parser = _create_list_transforms_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "all2md list-transforms"

    def test_parser_no_required_args(self):
        """Test parser works with no arguments."""
        parser = _create_list_transforms_parser()
        args = parser.parse_args([])
        assert args.transform is None
        assert args.rich is False

    def test_parser_with_transform_name(self):
        """Test parser with specific transform name."""
        parser = _create_list_transforms_parser()
        args = parser.parse_args(["strip_comments"])
        assert args.transform == "strip_comments"

    def test_parser_rich_flag(self):
        """Test parser with --rich flag."""
        parser = _create_list_transforms_parser()
        args = parser.parse_args(["--rich"])
        assert args.rich is True

    def test_parser_transform_and_rich(self):
        """Test parser with both transform and --rich."""
        parser = _create_list_transforms_parser()
        args = parser.parse_args(["some_transform", "--rich"])
        assert args.transform == "some_transform"
        assert args.rich is True


@pytest.mark.unit
class TestHandleListTransformsCommand:
    """Test handle_list_transforms_command() function."""

    def test_list_all_transforms(self, capsys):
        """Test listing all transforms."""
        result = handle_list_transforms_command([])
        assert result == 0
        captured = capsys.readouterr()
        assert "Available Transforms" in captured.out
        assert "Total:" in captured.out

    def test_list_specific_transform(self, capsys):
        """Test listing a specific transform."""
        # First get a list of available transforms
        from all2md.transforms import transform_registry

        transforms = transform_registry.list_transforms()

        if transforms:
            # Use first available transform
            transform_name = transforms[0]
            result = handle_list_transforms_command([transform_name])
            assert result == 0
            captured = capsys.readouterr()
            assert transform_name in captured.out

    def test_nonexistent_transform(self, capsys):
        """Test error when transform doesn't exist."""
        result = handle_list_transforms_command(["nonexistent_transform_xyz"])
        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err
        assert "Available:" in captured.err

    def test_help_returns_zero(self):
        """Test --help returns exit code 0."""
        result = handle_list_transforms_command(["--help"])
        assert result == 0

    def test_rich_output_fallback(self, capsys, monkeypatch):
        """Test rich output falls back to plain when rich not available."""
        # Simulate rich not being importable
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("rich"):
                raise ImportError("No module named 'rich'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        result = handle_list_transforms_command(["--rich"])
        assert result == 0
        captured = capsys.readouterr()
        # Should still output something (plain text fallback)
        assert "Available Transforms" in captured.out or "Total:" in captured.out

    def test_plain_output_format(self, capsys):
        """Test plain text output contains expected sections."""
        result = handle_list_transforms_command([])
        assert result == 0
        captured = capsys.readouterr()
        assert "=" in captured.out  # Separator line
        assert "Available Transforms" in captured.out

    def test_specific_transform_details(self, capsys):
        """Test specific transform shows details."""
        from all2md.transforms import transform_registry

        transforms = transform_registry.list_transforms()

        if transforms:
            transform_name = transforms[0]
            result = handle_list_transforms_command([transform_name])
            assert result == 0
            captured = capsys.readouterr()
            assert "Description:" in captured.out
            assert "Priority:" in captured.out


@pytest.mark.unit
class TestHandleListTransformsCommandEdgeCases:
    """Test edge cases for handle_list_transforms_command."""

    def test_list_transforms_with_partial_name_match(self, capsys):
        """Test that partial transform names don't match."""
        result = handle_list_transforms_command(["strip"])  # Partial name
        # Should fail unless there's an exact match
        assert result == 1 or "not found" in capsys.readouterr().err

    def test_list_transforms_empty_registry(self, capsys):
        """Test listing when registry is empty."""
        with patch("all2md.cli.commands.transforms.transform_registry") as mock_registry:
            mock_registry.list_transforms.return_value = []
            mock_registry.get_transform_info.return_value = {}

            result = handle_list_transforms_command([])

        assert result == 0
        captured = capsys.readouterr()
        assert "Total: 0" in captured.out

    def test_list_transforms_registry_error(self, capsys):
        """Test handling of registry errors."""
        with patch("all2md.cli.commands.transforms.transform_registry") as mock_registry:
            mock_registry.list_transforms.side_effect = RuntimeError("Registry error")

            with pytest.raises(RuntimeError):
                handle_list_transforms_command([])


@pytest.mark.unit
class TestParserEdgeCases:
    """Test parser edge cases."""

    def test_parser_unknown_argument(self):
        """Test parser rejects unknown arguments."""
        parser = _create_list_transforms_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--unknown-arg"])

    def test_parser_multiple_transforms_error(self):
        """Test parser rejects multiple transform arguments."""
        parser = _create_list_transforms_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["transform1", "transform2"])

    def test_parser_help_text(self):
        """Test parser has help text."""
        parser = _create_list_transforms_parser()
        help_text = parser.format_help()

        assert "transform" in help_text.lower()
        assert "rich" in help_text.lower()
