"""Tests for enhanced CLI help handling."""

import pytest

from all2md.cli import create_parser, handle_help_command


@pytest.mark.unit
@pytest.mark.parametrize("subcommand", ["install-skills", "edit", "lint", "arxiv"])
def test_help_lists_previously_hidden_subcommands(capsys, subcommand):
    """Previously hidden subcommands appear in the quick-help listing."""
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])

    captured = capsys.readouterr()
    assert subcommand in captured.out


def test_tiered_help_action_quick(capsys):
    """Invoking --help without selector prints quick help and exits."""
    parser = create_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--help"])

    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "Subcommands:" in captured.out
    assert "Run: `all2md help full`" in captured.out
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


@pytest.mark.unit
@pytest.mark.parametrize("selector", ["quick", "full"])
def test_help_advertises_llm_help(capsys, selector):
    """Quick and full help surface the prominent llm-help callout and subcommand."""
    args = ["--help"] if selector == "quick" else ["--help", "full"]
    parser = create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(args)

    captured = capsys.readouterr()
    # Prominent callout near the top...
    assert "run `all2md llm-help`" in captured.out
    # ...and a discoverable subcommand listing.
    assert "llm-help" in captured.out


@pytest.mark.unit
def test_help_attachments_alias_matches_global_attachment(capsys):
    """`help attachments` is an alias for the non-obvious `global-attachment` topic."""
    handle_help_command(["help", "attachments"])
    alias_out = capsys.readouterr().out

    handle_help_command(["help", "global-attachment"])
    canonical_out = capsys.readouterr().out

    assert alias_out == canonical_out
    assert "--attachment-mode" in alias_out


@pytest.mark.unit
@pytest.mark.parametrize("alias", ["markdown", "md"])
def test_help_markdown_alias_matches_common_markdown_formatting(alias, capsys):
    """`help markdown`/`help md` alias the verbose `common-markdown-formatting` topic."""
    handle_help_command(["help", alias])
    alias_out = capsys.readouterr().out

    handle_help_command(["help", "common-markdown-formatting"])
    canonical_out = capsys.readouterr().out

    assert alias_out == canonical_out
    assert "Common Markdown formatting options" in alias_out
    assert "Unknown help section" not in alias_out


@pytest.mark.unit
def test_help_batch_topic_lists_batch_flags(capsys):
    """`help batch` surfaces the batch-processing flags as a dedicated topic."""
    handle_help_command(["help", "batch"])
    out = capsys.readouterr().out
    assert "--preserve-structure" in out
    assert "--output-dir" in out
    assert "--parallel" in out


@pytest.mark.unit
def test_help_cheatsheet_prints(capsys):
    """`all2md help cheatsheet` prints the bundled quick reference."""
    rc = handle_help_command(["help", "cheatsheet"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "all2md CLI Cheatsheet" in out
    assert "## Chunk for RAG" in out
    assert "all2md chunk" in out
    assert "all2md grep" in out


@pytest.mark.unit
def test_cheatsheet_bundled_resource_loads():
    """The cheatsheet ships as a package resource and has the expected sections."""
    from all2md.cli.commands.help import _read_cheatsheet

    text = _read_cheatsheet()
    assert text.strip()
    for section in ("## Convert", "## Search", "## Chunk for RAG", "## Utilities"):
        assert section in text


@pytest.mark.unit
def test_quick_help_points_at_cheatsheet(capsys):
    """The quick-help footer advertises `all2md help cheatsheet`."""
    handle_help_command(["help"])
    out = capsys.readouterr().out
    assert "all2md help cheatsheet" in out


@pytest.mark.unit
def test_help_cheatsheet_rich_does_not_crash(capsys):
    """The --rich path renders without error (falls back to plain if rich is absent)."""
    rc = handle_help_command(["help", "cheatsheet", "--rich"])
    assert rc == 0
    assert capsys.readouterr().out.strip()
