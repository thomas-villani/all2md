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


# The bundled skill is a single ``all2md`` skill whose per-task guides live in a
# ``references/`` subdirectory (progressive-disclosure layout). ``llm-help``
# topics map one-to-one to those reference files.
_PRIMARY_SKILL = "all2md"
_OVERVIEW_TOPIC = "overview"


def _primary_skill_dir(skills_dir: Path) -> Path:
    """Return the directory of the single bundled ``all2md`` skill."""
    return skills_dir / _PRIMARY_SKILL


def _discover_reference_topics(skill_dir: Path) -> list[str]:
    """List the reference topics bundled with a skill.

    Parameters
    ----------
    skill_dir : Path
        The skill directory (e.g. ``.../skills/all2md``).

    Returns
    -------
    list[str]
        Sorted reference-file stems (e.g. ``["convert", "diff", ...]``), or an
        empty list when the skill has no ``references/`` directory.

    """
    ref_dir = skill_dir / "references"
    if not ref_dir.is_dir():
        return []
    return sorted(path.stem for path in ref_dir.glob("*.md"))


def _reference_path(skill_dir: Path, topic: str) -> Path:
    """Return the path to a reference file for a topic."""
    return skill_dir / "references" / f"{topic}.md"


def _reference_title(skill_dir: Path, topic: str) -> str:
    """Return a short title for a reference topic (its first ``# `` heading)."""
    try:
        text = _reference_path(skill_dir, topic).read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


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


def _build_llm_help_guide(skill_dir: Path, topics: list[str]) -> str:
    """Build the concatenated CLI guide printed by ``all2md llm-help``.

    The guide leads with the skill's SKILL.md overview, then appends each
    reference topic in order.

    Parameters
    ----------
    skill_dir : Path
        Directory of the bundled ``all2md`` skill.
    topics : list[str]
        Reference topics to include, in order.

    Returns
    -------
    str
        A single Markdown document combining the overview and every reference.

    """
    divider = "-" * 76

    parts: list[str] = [
        "# all2md - CLI guide for LLMs and agents",
        "",
        "all2md converts between 40+ document formats and Markdown from the command line. "
        "This guide leads with an overview, then concatenates the per-task references listed below.",
        "",
        f"Topics: {', '.join(topics)}",
        "  - Print one topic:      all2md llm-help <topic>",
        "  - List topics:          all2md llm-help --list",
        "  - Full flag reference:  all2md --help full",
        "",
        divider,
        f"OVERVIEW  (print alone with: all2md llm-help {_OVERVIEW_TOPIC})",
        divider,
        "",
        _read_skill_body(skill_dir / "SKILL.md"),
    ]

    for topic in topics:
        body = _reference_path(skill_dir, topic).read_text(encoding="utf-8").strip()
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

    With no TOPIC, prints the overview followed by every reference concatenated
    into one guide. With a TOPIC (e.g. ``read``, ``convert``, ``diff``,
    ``grep``, ``search``, ``generate``), prints just that reference; ``overview``
    prints the SKILL.md overview. ``--list`` lists available topics.

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
            "With no TOPIC, prints the full guide (overview + all topics concatenated)."
        ),
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        metavar="TOPIC",
        help="Optional topic to print on its own (e.g. read, convert, generate, grep, search, diff, overview).",
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

    skill_dir = _primary_skill_dir(skills_dir)
    topics = _discover_reference_topics(skill_dir)
    if not skill_dir.is_dir() or not topics:
        print("Error: No bundled CLI guide found.", file=sys.stderr)
        return EXIT_ERROR

    if parsed.list_:
        print(f"Available llm-help topics ({len(topics)}):")
        print(f"  {_OVERVIEW_TOPIC}: all2md overview and index")
        for topic in topics:
            print(f"  {topic}: {_reference_title(skill_dir, topic)}")
        print("\nPrint one topic with:  all2md llm-help <topic>")
        print("Print everything with: all2md llm-help")
        return EXIT_SUCCESS

    if parsed.topic is not None:
        requested = parsed.topic.lower()
        if requested in (_OVERVIEW_TOPIC, _PRIMARY_SKILL):
            print(_read_skill_body(skill_dir / "SKILL.md"))
            return EXIT_SUCCESS
        if requested not in topics:
            available = ", ".join([_OVERVIEW_TOPIC, *topics])
            print(f"Error: Unknown topic '{parsed.topic}'. Available topics: {available}", file=sys.stderr)
            return EXIT_ERROR
        print(_reference_path(skill_dir, requested).read_text(encoding="utf-8").strip())
        return EXIT_SUCCESS

    print(_build_llm_help_guide(skill_dir, topics))
    return EXIT_SUCCESS
