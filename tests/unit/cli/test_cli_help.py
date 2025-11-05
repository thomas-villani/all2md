"""Tests for enhanced CLI help handling."""

import pytest

from all2md.cli import create_parser, handle_help_command


def test_tiered_help_action_quick(capsys):
    """Invoking --help without selector prints quick help and exits."""
    parser = create_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--help"])

    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "Subcommands:" in captured.out
    assert "Run 'all2md help full'" in captured.out
    assert "Global options:" in captured.out
    # Quick help should NOT show parser/renderer options
    assert "Parser options:" not in captured.out
    assert "Renderer options:" not in captured.out
    # Global options should still appear
    assert "    --out" in captured.out
    assert "      Output file path" in captured.out
    # Should guide users to format-specific help
    assert "help <format>" in captured.out
    assert captured.err == ""


def test_tiered_help_action_full_selector(capsys):
    """--help full yields the expanded help output."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help", "full"])

    captured = capsys.readouterr()
    assert "Subcommands:" in captured.out
    assert "Core options:" not in captured.out  # full view omits quick label
    assert "Global options:" in captured.out
    assert "Parser options:" in captured.out
    assert "Renderer options:" in captured.out
    assert "default: 'both'" in captured.out or "default:'both'" in captured.out


def test_help_subcommand_handles_selector(capsys):
    """`all2md help pdf` renders section-specific help."""
    exit_code = handle_help_command(["help", "pdf"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "PDF options:" in captured.out
    assert "PDF renderer options:" in captured.out
    assert "default:" in captured.out


def test_handle_help_command_passthrough():
    """Non-help commands return None so other handlers can process them."""
    assert handle_help_command(["convert"]) is None
