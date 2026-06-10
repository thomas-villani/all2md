"""Unit tests for all2md install-skills and llm-help commands.

The bundled skills use a single ``all2md`` skill (progressive-disclosure
layout): a top-level ``SKILL.md`` overview plus per-task guides under
``references/``. ``install-skills`` copies that skill tree; ``llm-help`` maps
each reference file to a topic.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS
from all2md.cli.commands import dispatch_command
from all2md.cli.commands.skills import (
    _discover_reference_topics,
    _discover_skills,
    _get_bundled_skills_dir,
    _primary_skill_dir,
    _read_skill_description,
    _reference_title,
    _strip_frontmatter,
    handle_install_skills_command,
    handle_llm_help_command,
)

# The single bundled skill and its reference topics.
PRIMARY_SKILL = "all2md"
EXPECTED_TOPICS = ["convert", "diff", "generate", "grep", "read", "search"]


@pytest.mark.unit
class TestGetBundledSkillsDir:
    """Test _get_bundled_skills_dir()."""

    def test_returns_existing_directory(self):
        """Test that bundled skills directory is found."""
        skills_dir = _get_bundled_skills_dir()
        assert skills_dir.is_dir()

    def test_contains_primary_skill(self):
        """Test that the bundled skills dir contains the all2md skill."""
        skills_dir = _get_bundled_skills_dir()
        assert (skills_dir / PRIMARY_SKILL / "SKILL.md").is_file()
        assert (skills_dir / PRIMARY_SKILL / "references").is_dir()


@pytest.mark.unit
class TestDiscoverSkills:
    """Test _discover_skills()."""

    def test_discovers_primary_skill(self):
        """Test that the single all2md skill is discovered."""
        skills_dir = _get_bundled_skills_dir()
        assert _discover_skills(skills_dir) == [PRIMARY_SKILL]

    def test_ignores_directories_without_skill_md(self, tmp_path):
        """Test that directories without SKILL.md are ignored."""
        (tmp_path / "has-skill").mkdir()
        (tmp_path / "has-skill" / "SKILL.md").write_text("---\nname: has-skill\n---\n")
        (tmp_path / "no-skill").mkdir()
        (tmp_path / "just-a-file.txt").write_text("not a skill")

        skills = _discover_skills(tmp_path)
        assert skills == ["has-skill"]

    def test_returns_sorted_names(self, tmp_path):
        """Test that discovered skills are sorted."""
        for name in ["z-skill", "a-skill", "m-skill"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n")

        skills = _discover_skills(tmp_path)
        assert skills == ["a-skill", "m-skill", "z-skill"]


@pytest.mark.unit
class TestDiscoverReferenceTopics:
    """Test _discover_reference_topics()."""

    def test_discovers_bundled_topics(self):
        """Test that the bundled reference topics are discovered, sorted."""
        skill_dir = _primary_skill_dir(_get_bundled_skills_dir())
        assert _discover_reference_topics(skill_dir) == EXPECTED_TOPICS

    def test_returns_empty_without_references_dir(self, tmp_path):
        """Test that a skill without references/ yields no topics."""
        (tmp_path / "SKILL.md").write_text("---\nname: x\n---\n")
        assert _discover_reference_topics(tmp_path) == []

    def test_reference_title_reads_first_heading(self):
        """Test that _reference_title returns the reference's first H1."""
        skill_dir = _primary_skill_dir(_get_bundled_skills_dir())
        assert _reference_title(skill_dir, "read") == "Reading Documents with all2md"


@pytest.mark.unit
class TestReadSkillDescription:
    """Test _read_skill_description()."""

    def test_reads_description_from_frontmatter(self, tmp_path):
        """Test reading description from SKILL.md frontmatter."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text('---\nname: test-skill\ndescription: "A test skill"\n---\n# Test\n')

        desc = _read_skill_description(skill_md)
        assert desc == "A test skill"

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Test that missing file returns empty string."""
        desc = _read_skill_description(tmp_path / "nonexistent.md")
        assert desc == ""

    def test_returns_empty_for_no_description(self, tmp_path):
        """Test that missing description field returns empty string."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\n---\n# Test\n")

        desc = _read_skill_description(skill_md)
        assert desc == ""

    def test_truncates_long_description(self, tmp_path):
        """Test that long descriptions are truncated."""
        long_desc = "x" * 200
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(f'---\nname: test-skill\ndescription: "{long_desc}"\n---\n')

        desc = _read_skill_description(skill_md)
        assert len(desc) == 120
        assert desc.endswith("...")


@pytest.mark.unit
class TestHandleInstallSkillsCommand:
    """Test handle_install_skills_command()."""

    def test_list_skills(self, capsys):
        """Test --list prints the bundled skill."""
        result = handle_install_skills_command(["--list"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert PRIMARY_SKILL in output

    def test_install_to_target(self, tmp_path, capsys):
        """Test installing skills to explicit target directory, including references."""
        target = tmp_path / "skills"
        result = handle_install_skills_command(["--target", str(target)])
        assert result == EXIT_SUCCESS

        assert (target / PRIMARY_SKILL / "SKILL.md").is_file()
        for topic in EXPECTED_TOPICS:
            assert (target / PRIMARY_SKILL / "references" / f"{topic}.md").is_file()

        output = capsys.readouterr().out
        assert "Installed 1" in output

    def test_install_does_not_overwrite_without_force(self, tmp_path, capsys):
        """Test that existing skills are skipped without --force."""
        target = tmp_path / "skills"

        handle_install_skills_command(["--target", str(target)])
        result = handle_install_skills_command(["--target", str(target)])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "Skipped" in output

    def test_install_overwrites_with_force(self, tmp_path, capsys):
        """Test that --force overwrites existing skills."""
        target = tmp_path / "skills"

        handle_install_skills_command(["--target", str(target)])
        result = handle_install_skills_command(["--target", str(target), "--force"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "Installed 1" in output
        assert "Skipped" not in output

    def test_uninstall(self, tmp_path, capsys):
        """Test --uninstall removes the skill."""
        target = tmp_path / "skills"

        handle_install_skills_command(["--target", str(target)])
        assert (target / PRIMARY_SKILL / "SKILL.md").is_file()

        result = handle_install_skills_command(["--uninstall", "--target", str(target)])
        assert result == EXIT_SUCCESS
        assert not (target / PRIMARY_SKILL).exists()

        output = capsys.readouterr().out
        assert "Removed 1" in output

    def test_uninstall_nonexistent_directory(self, tmp_path, capsys):
        """Test --uninstall on nonexistent directory returns error."""
        target = tmp_path / "nonexistent"
        result = handle_install_skills_command(["--uninstall", "--target", str(target)])
        assert result == EXIT_ERROR

    def test_install_creates_target_directory(self, tmp_path):
        """Test that install creates the target directory if needed."""
        target = tmp_path / "deep" / "nested" / "skills"
        result = handle_install_skills_command(["--target", str(target)])
        assert result == EXIT_SUCCESS
        assert target.is_dir()

    def test_install_local_flag(self, tmp_path, monkeypatch):
        """Test --local installs to ./.agents/skills/."""
        monkeypatch.chdir(tmp_path)
        result = handle_install_skills_command(["--local"])
        assert result == EXIT_SUCCESS

        local_dir = tmp_path / ".agents" / "skills"
        assert (local_dir / PRIMARY_SKILL / "SKILL.md").is_file()

    def test_install_global_flag(self, tmp_path, monkeypatch):
        """Test --global installs to ~/.agents/skills/."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        result = handle_install_skills_command(["--global"])
        assert result == EXIT_SUCCESS

        global_dir = tmp_path / ".agents" / "skills"
        assert (global_dir / PRIMARY_SKILL / "SKILL.md").is_file()


@pytest.mark.unit
class TestDispatchInstallSkills:
    """Test dispatch_command routes install-skills."""

    def test_dispatch_install_skills_command(self):
        """Test dispatch routes install-skills command."""
        with patch("all2md.cli.commands.skills.handle_install_skills_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["install-skills", "--list"])

            mock_handler.assert_called_once_with(["--list"])
            assert result == 0

    def test_dispatch_install_skills_strips_command(self):
        """Test that install-skills command strips 'install-skills' from args."""
        with patch("all2md.cli.commands.skills.handle_install_skills_command") as mock_handler:
            mock_handler.return_value = 0
            dispatch_command(["install-skills", "--target", "/tmp/test"])

            args_passed = mock_handler.call_args[0][0]
            assert args_passed == ["--target", "/tmp/test"]
            assert "install-skills" not in args_passed


@pytest.mark.unit
class TestSkillFrontmatter:
    """Validate SKILL.md frontmatter for the bundled all2md skill."""

    def _skill_md(self) -> Path:
        return _primary_skill_dir(_get_bundled_skills_dir()) / "SKILL.md"

    def test_skill_has_matching_name(self):
        """Test that SKILL.md declares name: all2md."""
        text = self._skill_md().read_text(encoding="utf-8")
        assert f"name: {PRIMARY_SKILL}" in text

    def test_skill_has_description(self):
        """Test that SKILL.md has a non-empty description."""
        assert _read_skill_description(self._skill_md())

    def test_description_under_1024_chars(self):
        """Test that the description is under 1024 characters."""
        text = self._skill_md().read_text(encoding="utf-8")
        in_fm = False
        for line in text.splitlines():
            if line.strip() == "---":
                if not in_fm:
                    in_fm = True
                    continue
                break
            if in_fm and line.startswith("description:"):
                desc = line[len("description:") :].strip().strip('"').strip("'")
                assert len(desc) < 1024, f"description is {len(desc)} chars (max 1024)"

    def test_skill_md_under_500_lines(self):
        """Test that the SKILL.md body is under 500 lines (best practice)."""
        line_count = len(self._skill_md().read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"SKILL.md has {line_count} lines (max 500)"

    def test_skill_md_links_every_reference(self):
        """Test that SKILL.md links to each bundled reference file."""
        text = self._skill_md().read_text(encoding="utf-8")
        for topic in EXPECTED_TOPICS:
            assert f"references/{topic}.md" in text, f"SKILL.md does not link references/{topic}.md"


@pytest.mark.unit
class TestNoStaleFlags:
    """Guard against reintroducing removed/renamed CLI flags in skill content.

    Regression guard for GitHub issue #16 (``--html-standalone``) and the
    broader flag audit.
    """

    # Substrings that must never appear in bundled skill markdown again.
    FORBIDDEN = [
        "--html-standalone",
        "--no-standalone",  # real flag is --html-renderer-no-standalone
        "--docx-template",
        "--pdf-page-size",
        "--jinja-template ",
        "--pdf-detect-tables",
        "--docx-preserve-formatting",
        "--docx-extract-comments",
        "--eml-include-attachments",
        "--eml-detect-chains",
        "--xlsx-sheet ",
        "--ipynb-include-outputs",
        "--semantic",
        "--show-snippet",
        "--mode bm25",
        "apply_transforms",
        "detect_tables=",
    ]

    def test_no_forbidden_flags_in_any_skill_markdown(self):
        """Scan every bundled skill markdown file for removed flags."""
        skills_dir = _get_bundled_skills_dir()
        offenders: list[str] = []
        for md in skills_dir.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            for needle in self.FORBIDDEN:
                if needle in text:
                    offenders.append(f"{md.relative_to(skills_dir)}: {needle!r}")
        assert not offenders, "Stale CLI references found:\n" + "\n".join(offenders)


@pytest.mark.unit
class TestStripFrontmatter:
    """Test _strip_frontmatter()."""

    def test_strips_leading_frontmatter(self):
        """Test that a leading YAML frontmatter block is removed."""
        text = "---\nname: x\ndescription: y\n---\n# Heading\n\nBody text.\n"
        assert _strip_frontmatter(text) == "# Heading\n\nBody text."

    def test_returns_text_without_frontmatter_unchanged(self):
        """Test that text with no frontmatter is returned unchanged."""
        text = "# Heading\n\nBody text."
        assert _strip_frontmatter(text) == text

    def test_handles_text_with_no_closing_fence(self):
        """Test that an unterminated frontmatter block leaves text unchanged."""
        text = "---\nname: x\nno closing fence here\n"
        assert _strip_frontmatter(text) == text


@pytest.mark.unit
class TestHandleLlmHelpCommand:
    """Test handle_llm_help_command()."""

    def test_default_dumps_full_guide(self, capsys):
        """Test that no args prints the overview plus every topic concatenated."""
        result = handle_llm_help_command([])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "CLI guide for LLMs and agents" in output
        assert "OVERVIEW" in output
        for topic in EXPECTED_TOPICS:
            assert f"TOPIC: {topic}" in output
        # Content from multiple distinct references is present.
        assert "Reading Documents with all2md" in output
        assert "Format Conversion with all2md" in output

    def test_default_has_no_yaml_frontmatter(self, capsys):
        """Test that the concatenated guide strips the SKILL.md YAML frontmatter."""
        handle_llm_help_command([])
        output = capsys.readouterr().out
        assert "metadata:" not in output
        assert "author: all2md" not in output

    def test_single_topic(self, capsys):
        """Test that a topic prints just that reference's body."""
        result = handle_llm_help_command(["read"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "Reading Documents with all2md" in output
        assert "Format Conversion with all2md" not in output
        assert not output.startswith("---")

    def test_overview_topic(self, capsys):
        """Test that the 'overview' topic prints the SKILL.md body."""
        result = handle_llm_help_command(["overview"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "# all2md" in output
        assert "Choose a reference" in output

    def test_skill_name_as_topic(self, capsys):
        """Test that the skill name 'all2md' also resolves to the overview."""
        result = handle_llm_help_command(["all2md"])
        assert result == EXIT_SUCCESS
        assert "Choose a reference" in capsys.readouterr().out

    def test_topic_is_case_insensitive(self, capsys):
        """Test that topic matching ignores case."""
        result = handle_llm_help_command(["READ"])
        assert result == EXIT_SUCCESS
        assert "Reading Documents with all2md" in capsys.readouterr().out

    def test_list_topics(self, capsys):
        """Test that --list prints all topics with titles."""
        result = handle_llm_help_command(["--list"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "overview" in output
        for topic in EXPECTED_TOPICS:
            assert topic in output

    def test_unknown_topic_errors(self, capsys):
        """Test that an unknown topic returns an error with suggestions."""
        result = handle_llm_help_command(["bogus"])
        assert result == EXIT_ERROR

        err = capsys.readouterr().err
        assert "Unknown topic 'bogus'" in err
        for topic in EXPECTED_TOPICS:
            assert topic in err


@pytest.mark.unit
class TestDispatchLlmHelp:
    """Test dispatch_command routes llm-help."""

    def test_dispatch_llm_help_command(self):
        """Test dispatch routes the llm-help command."""
        with patch("all2md.cli.commands.skills.handle_llm_help_command") as mock_handler:
            mock_handler.return_value = 0
            result = dispatch_command(["llm-help", "--list"])

            mock_handler.assert_called_once_with(["--list"])
            assert result == 0

    def test_dispatch_llm_help_strips_command(self):
        """Test that llm-help is stripped from the forwarded args."""
        with patch("all2md.cli.commands.skills.handle_llm_help_command") as mock_handler:
            mock_handler.return_value = 0
            dispatch_command(["llm-help", "read"])

            args_passed = mock_handler.call_args[0][0]
            assert args_passed == ["read"]
            assert "llm-help" not in args_passed
