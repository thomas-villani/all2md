"""Unit tests for all2md install-skills command.

This module tests the install-skills CLI command that copies
bundled agent skills to a target directory.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS
from all2md.cli.commands import dispatch_command
from all2md.cli.commands.skills import (
    _discover_skills,
    _get_bundled_skills_dir,
    _read_skill_description,
    _skill_topic,
    _strip_frontmatter,
    handle_install_skills_command,
    handle_llm_help_command,
)

EXPECTED_SKILLS = [
    "all2md-convert",
    "all2md-diff",
    "all2md-generate",
    "all2md-grep",
    "all2md-read",
    "all2md-search",
]


@pytest.mark.unit
class TestGetBundledSkillsDir:
    """Test _get_bundled_skills_dir()."""

    def test_returns_existing_directory(self):
        """Test that bundled skills directory is found."""
        skills_dir = _get_bundled_skills_dir()
        assert skills_dir.is_dir()

    def test_contains_skill_subdirectories(self):
        """Test that bundled skills dir contains skill subdirectories."""
        skills_dir = _get_bundled_skills_dir()
        for name in EXPECTED_SKILLS:
            assert (skills_dir / name).is_dir(), f"Missing skill: {name}"


@pytest.mark.unit
class TestDiscoverSkills:
    """Test _discover_skills()."""

    def test_discovers_all_bundled_skills(self):
        """Test that all 6 bundled skills are discovered."""
        skills_dir = _get_bundled_skills_dir()
        skills = _discover_skills(skills_dir)
        assert skills == EXPECTED_SKILLS

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
        """Test --list prints all 6 skills."""
        result = handle_install_skills_command(["--list"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "6" in output
        for name in EXPECTED_SKILLS:
            assert name in output

    def test_install_to_target(self, tmp_path, capsys):
        """Test installing skills to explicit target directory."""
        target = tmp_path / "skills"
        result = handle_install_skills_command(["--target", str(target)])
        assert result == EXIT_SUCCESS

        for name in EXPECTED_SKILLS:
            assert (target / name / "SKILL.md").is_file()

        output = capsys.readouterr().out
        assert "Installed 6" in output

    def test_install_does_not_overwrite_without_force(self, tmp_path, capsys):
        """Test that existing skills are skipped without --force."""
        target = tmp_path / "skills"

        # First install
        handle_install_skills_command(["--target", str(target)])

        # Second install without --force
        result = handle_install_skills_command(["--target", str(target)])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "Skipped" in output

    def test_install_overwrites_with_force(self, tmp_path, capsys):
        """Test that --force overwrites existing skills."""
        target = tmp_path / "skills"

        # First install
        handle_install_skills_command(["--target", str(target)])

        # Second install with --force
        result = handle_install_skills_command(["--target", str(target), "--force"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "Installed 6" in output
        assert "Skipped" not in output

    def test_uninstall(self, tmp_path, capsys):
        """Test --uninstall removes skills."""
        target = tmp_path / "skills"

        # Install first
        handle_install_skills_command(["--target", str(target)])
        assert (target / "all2md-read" / "SKILL.md").is_file()

        # Uninstall
        result = handle_install_skills_command(["--uninstall", "--target", str(target)])
        assert result == EXIT_SUCCESS

        for name in EXPECTED_SKILLS:
            assert not (target / name).exists()

        output = capsys.readouterr().out
        assert "Removed 6" in output

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
        for name in EXPECTED_SKILLS:
            assert (local_dir / name / "SKILL.md").is_file()

    def test_install_global_flag(self, tmp_path, monkeypatch):
        """Test --global installs to ~/.agents/skills/."""
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        result = handle_install_skills_command(["--global"])
        assert result == EXIT_SUCCESS

        global_dir = tmp_path / ".agents" / "skills"
        for name in EXPECTED_SKILLS:
            assert (global_dir / name / "SKILL.md").is_file()


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
    """Validate SKILL.md frontmatter for all bundled skills."""

    def test_all_skills_have_valid_name(self):
        """Test that each SKILL.md has a name matching its directory."""
        skills_dir = _get_bundled_skills_dir()
        for name in EXPECTED_SKILLS:
            skill_md = skills_dir / name / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            assert f"name: {name}" in text, f"{name}/SKILL.md has wrong name"

    def test_all_skills_have_description(self):
        """Test that each SKILL.md has a description."""
        skills_dir = _get_bundled_skills_dir()
        for name in EXPECTED_SKILLS:
            skill_md = skills_dir / name / "SKILL.md"
            desc = _read_skill_description(skill_md)
            assert desc, f"{name}/SKILL.md has no description"

    def test_all_descriptions_under_1024_chars(self):
        """Test that each description is under 1024 characters."""
        skills_dir = _get_bundled_skills_dir()
        for name in EXPECTED_SKILLS:
            skill_md = skills_dir / name / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            # Extract full description (not truncated)
            in_fm = False
            for line in text.splitlines():
                if line.strip() == "---":
                    if not in_fm:
                        in_fm = True
                        continue
                    else:
                        break
                if in_fm and line.startswith("description:"):
                    desc = line[len("description:") :].strip().strip('"').strip("'")
                    assert len(desc) < 1024, f"{name} description is {len(desc)} chars (max 1024)"

    def test_all_skills_under_500_lines(self):
        """Test that each SKILL.md body is under 500 lines."""
        skills_dir = _get_bundled_skills_dir()
        for name in EXPECTED_SKILLS:
            skill_md = skills_dir / name / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            line_count = len(text.splitlines())
            assert line_count < 500, f"{name}/SKILL.md has {line_count} lines (max 500)"


# Short topic aliases (the skill name without the "all2md-" prefix).
EXPECTED_TOPICS = [name[len("all2md-") :] for name in EXPECTED_SKILLS]


@pytest.mark.unit
class TestSkillTopic:
    """Test _skill_topic()."""

    def test_strips_all2md_prefix(self):
        """Test that the all2md- prefix is dropped."""
        assert _skill_topic("all2md-read") == "read"
        assert _skill_topic("all2md-generate") == "generate"

    def test_leaves_unprefixed_names_unchanged(self):
        """Test that names without the prefix are returned as-is."""
        assert _skill_topic("read") == "read"
        assert _skill_topic("custom-skill") == "custom-skill"


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
        """Test that no args prints every topic concatenated."""
        result = handle_llm_help_command([])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "CLI guide for LLMs and agents" in output
        # Every topic appears as a divider header...
        for topic in EXPECTED_TOPICS:
            assert f"TOPIC: {topic}" in output
        # ...and content from multiple distinct skills is present.
        assert "Reading Documents with all2md" in output
        assert "Format Conversion with all2md" in output

    def test_default_has_no_yaml_frontmatter(self, capsys):
        """Test that the concatenated guide strips per-skill YAML frontmatter."""
        handle_llm_help_command([])
        output = capsys.readouterr().out
        assert "metadata:" not in output
        assert "author: all2md" not in output

    def test_single_topic_short_alias(self, capsys):
        """Test that a short topic alias prints just that skill's body."""
        result = handle_llm_help_command(["read"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "Reading Documents with all2md" in output
        # Other skills are not included.
        assert "Format Conversion with all2md" not in output
        # Frontmatter is stripped.
        assert not output.startswith("---")

    def test_single_topic_full_name(self, capsys):
        """Test that the full skill name also resolves as a topic."""
        result = handle_llm_help_command(["all2md-diff"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "Comparing Documents with all2md" in output

    def test_topic_is_case_insensitive(self, capsys):
        """Test that topic matching ignores case."""
        result = handle_llm_help_command(["READ"])
        assert result == EXIT_SUCCESS
        assert "Reading Documents with all2md" in capsys.readouterr().out

    def test_list_topics(self, capsys):
        """Test that --list prints all topics with descriptions."""
        result = handle_llm_help_command(["--list"])
        assert result == EXIT_SUCCESS

        output = capsys.readouterr().out
        assert "6" in output
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
