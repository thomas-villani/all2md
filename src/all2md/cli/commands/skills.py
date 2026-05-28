#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/commands/skills.py
"""Bundled agent-skill commands for the all2md CLI.

This module provides two commands built on the bundled agent skills:

- ``install-skills`` copies the bundled skills to a local or global skills
  directory for use by agent harnesses.
- ``llm-help`` prints those same skills to stdout as a single CLI guide, so an
  LLM or agent driving ``all2md`` from a terminal can read the reference
  without installing anything.
"""

import argparse
import shutil
import sys
from pathlib import Path

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS


def _get_bundled_skills_dir() -> Path:
    """Locate the bundled skills directory using importlib.resources.

    Returns
    -------
    Path
        Path to the bundled skills directory.

    Raises
    ------
    FileNotFoundError
        If the bundled skills directory cannot be found.

    """
    import importlib.resources  # nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2

    skills_ref = importlib.resources.files("all2md") / "skills"
    # Traverse into the actual filesystem path
    skills_path = Path(str(skills_ref))
    if not skills_path.is_dir():
        msg = f"Bundled skills directory not found at {skills_path}"
        raise FileNotFoundError(msg)
    return skills_path


def _discover_skills(skills_dir: Path) -> list[str]:
    """Discover skill directories (those containing SKILL.md).

    Parameters
    ----------
    skills_dir : Path
        Root skills directory to search.

    Returns
    -------
    list[str]
        Sorted list of skill directory names.

    """
    skills = []
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            skills.append(child.name)
    return skills


def _resolve_target_dir(args: argparse.Namespace) -> Path:
    """Resolve the target directory for skill installation.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments with target, local, and global_ fields.

    Returns
    -------
    Path
        Resolved target directory.

    """
    if args.target:
        return Path(args.target)
    if args.local:
        return Path("./.agents/skills")
    if args.global_:
        return Path.home() / ".agents" / "skills"

    # Default: local if .agents/skills exists, else global
    local_dir = Path("./.agents/skills")
    if local_dir.is_dir():
        return local_dir
    return Path.home() / ".agents" / "skills"


def handle_install_skills_command(args: list[str] | None = None) -> int:
    """Handle install-skills command to copy bundled skills.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'install-skills').

    Returns
    -------
    int
        Exit code (0 for success).

    """
    parser = argparse.ArgumentParser(
        prog="all2md install-skills",
        description="Install bundled agent skills to a skills directory.",
    )
    parser.add_argument("--target", default=None, help="Explicit target directory for skills")
    parser.add_argument("--local", action="store_true", help="Install to ./.agents/skills/")
    parser.add_argument("--global", dest="global_", action="store_true", help="Install to ~/.agents/skills/")
    parser.add_argument("--force", action="store_true", help="Overwrite existing skills without warning")
    parser.add_argument("--list", dest="list_", action="store_true", help="List bundled skills without installing")
    parser.add_argument("--uninstall", action="store_true", help="Remove all2md-* skills from target")

    parsed = parser.parse_args(args)

    try:
        skills_dir = _get_bundled_skills_dir()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR

    skill_names = _discover_skills(skills_dir)

    if not skill_names:
        print("Error: No bundled skills found.", file=sys.stderr)
        return EXIT_ERROR

    # --list: just print skills and exit
    if parsed.list_:
        print(f"Bundled skills ({len(skill_names)}):")
        for name in skill_names:
            # Read description from SKILL.md frontmatter
            skill_md = skills_dir / name / "SKILL.md"
            description = _read_skill_description(skill_md)
            print(f"  {name}: {description}")
        return EXIT_SUCCESS

    target_dir = _resolve_target_dir(parsed)

    # --uninstall: remove all2md-* directories from target
    if parsed.uninstall:
        return _uninstall_skills(target_dir, skill_names)

    # Install skills
    return _install_skills(skills_dir, target_dir, skill_names, force=parsed.force)


def _read_skill_description(skill_md: Path) -> str:
    """Read the description from a SKILL.md frontmatter.

    Parameters
    ----------
    skill_md : Path
        Path to the SKILL.md file.

    Returns
    -------
    str
        Description string, or empty string if not found.

    """
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return ""

    # Simple YAML frontmatter parser — look for description field
    in_frontmatter = False
    for line in text.splitlines():
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break
        if in_frontmatter and line.startswith("description:"):
            desc = line[len("description:") :].strip().strip('"').strip("'")
            # Truncate for display
            if len(desc) > 120:
                desc = desc[:117] + "..."
            return desc
    return ""


def _skill_topic(skill_name: str) -> str:
    """Return the short topic alias for a skill directory.

    Drops the ``all2md-`` prefix so ``all2md-read`` becomes ``read``. Names
    without the prefix are returned unchanged.

    Parameters
    ----------
    skill_name : str
        Skill directory name (e.g. ``all2md-read``).

    Returns
    -------
    str
        Short topic alias (e.g. ``read``).

    """
    prefix = "all2md-"
    return skill_name[len(prefix) :] if skill_name.startswith(prefix) else skill_name


def _strip_frontmatter(text: str) -> str:
    """Return the Markdown body of a SKILL.md, dropping any leading YAML frontmatter.

    Parameters
    ----------
    text : str
        Full SKILL.md contents.

    Returns
    -------
    str
        The body following the closing ``---`` fence, or the original text when
        no frontmatter block is present.

    """
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                body = "\n".join(lines[index + 1 :])
                return body.lstrip("\n")
    return text


def _install_skills(skills_dir: Path, target_dir: Path, skill_names: list[str], *, force: bool = False) -> int:
    """Install skills by copying directories.

    Parameters
    ----------
    skills_dir : Path
        Source bundled skills directory.
    target_dir : Path
        Target installation directory.
    skill_names : list[str]
        List of skill names to install.
    force : bool
        Whether to overwrite existing skills.

    Returns
    -------
    int
        Exit code.

    """
    target_dir.mkdir(parents=True, exist_ok=True)

    installed = 0
    skipped = 0

    for name in skill_names:
        src = skills_dir / name
        dest = target_dir / name

        if dest.exists() and not force:
            print(f"  Skipped {name} (already exists, use --force to overwrite)")
            skipped += 1
            continue

        if dest.exists():
            shutil.rmtree(dest)

        shutil.copytree(src, dest)
        print(f"  Installed {name}")
        installed += 1

    print(f"\nInstalled {installed} skill(s) to {target_dir}")
    if skipped:
        print(f"Skipped {skipped} skill(s) (use --force to overwrite)")

    return EXIT_SUCCESS


def _uninstall_skills(target_dir: Path, skill_names: list[str]) -> int:
    """Remove all2md skills from target directory.

    Parameters
    ----------
    target_dir : Path
        Target directory to remove skills from.
    skill_names : list[str]
        List of skill names to remove.

    Returns
    -------
    int
        Exit code.

    """
    if not target_dir.is_dir():
        print(f"Error: Target directory does not exist: {target_dir}", file=sys.stderr)
        return EXIT_ERROR

    removed = 0
    for name in skill_names:
        dest = target_dir / name
        if dest.is_dir():
            shutil.rmtree(dest)
            print(f"  Removed {name}")
            removed += 1

    if removed:
        print(f"\nRemoved {removed} skill(s) from {target_dir}")
    else:
        print(f"No all2md skills found in {target_dir}")

    return EXIT_SUCCESS


def _read_skill_body(skill_md: Path) -> str:
    """Read a SKILL.md and return its Markdown body without frontmatter.

    Parameters
    ----------
    skill_md : Path
        Path to the SKILL.md file.

    Returns
    -------
    str
        The Markdown body of the skill.

    """
    return _strip_frontmatter(skill_md.read_text(encoding="utf-8"))


def _build_llm_help_guide(skills_dir: Path, skill_names: list[str]) -> str:
    """Build the concatenated CLI guide printed by ``all2md llm-help``.

    Parameters
    ----------
    skills_dir : Path
        Directory containing the bundled skills.
    skill_names : list[str]
        Skill directory names to include, in order.

    Returns
    -------
    str
        A single Markdown document combining every skill body.

    """
    topics = [_skill_topic(name) for name in skill_names]
    divider = "-" * 76

    parts: list[str] = [
        "# all2md - CLI guide for LLMs and agents",
        "",
        "all2md converts between 40+ document formats and Markdown from the command line. "
        "This guide concatenates the bundled task references listed below.",
        "",
        f"Topics: {', '.join(topics)}",
        "  - Print one topic:      all2md llm-help <topic>",
        "  - List topics:          all2md llm-help --list",
        "  - Full flag reference:  all2md --help full",
    ]

    for name in skill_names:
        topic = _skill_topic(name)
        body = _read_skill_body(skills_dir / name / "SKILL.md")
        parts.extend(
            [
                "",
                divider,
                f"TOPIC: {topic}  (print alone with: all2md llm-help {topic})",
                divider,
                "",
                body,
            ]
        )

    return "\n".join(parts)


def handle_llm_help_command(args: list[str] | None = None) -> int:
    """Print the bundled all2md CLI guide for LLMs/agents to stdout.

    With no TOPIC, prints every bundled skill concatenated into one guide.
    With a TOPIC (e.g. ``read``, ``convert``, ``diff``, ``grep``, ``search``,
    ``generate``), prints just that skill. ``--list`` lists available topics.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond ``llm-help``).

    Returns
    -------
    int
        Exit code (0 for success).

    """
    parser = argparse.ArgumentParser(
        prog="all2md llm-help",
        description=(
            "Print the all2md CLI guide for LLMs and agents to stdout. "
            "With no TOPIC, prints the full guide (all topics concatenated)."
        ),
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        metavar="TOPIC",
        help="Optional topic to print on its own (e.g. read, convert, diff, grep, search, generate).",
    )
    parser.add_argument(
        "--list",
        dest="list_",
        action="store_true",
        help="List available topics instead of printing the guide.",
    )

    parsed = parser.parse_args(args)

    try:
        skills_dir = _get_bundled_skills_dir()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR

    skill_names = _discover_skills(skills_dir)
    if not skill_names:
        print("Error: No bundled CLI guide found.", file=sys.stderr)
        return EXIT_ERROR

    # Map both short aliases ("read") and full names ("all2md-read") to skill dirs.
    topic_to_skill = {_skill_topic(name): name for name in skill_names}
    topic_to_skill.update({name: name for name in skill_names})

    if parsed.list_:
        print(f"Available llm-help topics ({len(skill_names)}):")
        for name in skill_names:
            description = _read_skill_description(skills_dir / name / "SKILL.md")
            print(f"  {_skill_topic(name)}: {description}")
        print("\nPrint one topic with:  all2md llm-help <topic>")
        print("Print everything with: all2md llm-help")
        return EXIT_SUCCESS

    if parsed.topic is not None:
        skill_name = topic_to_skill.get(parsed.topic.lower())
        if skill_name is None:
            topics = ", ".join(sorted(_skill_topic(name) for name in skill_names))
            print(f"Error: Unknown topic '{parsed.topic}'. Available topics: {topics}", file=sys.stderr)
            return EXIT_ERROR
        print(_read_skill_body(skills_dir / skill_name / "SKILL.md"))
        return EXIT_SUCCESS

    print(_build_llm_help_guide(skills_dir, skill_names))
    return EXIT_SUCCESS
