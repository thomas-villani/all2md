"""Compile ``changelog.d/`` fragments into ``CHANGELOG.md`` at release time.

Every pull request used to edit ``CHANGELOG.md`` under ``## [Unreleased]``, which
made that one file a guaranteed merge conflict in any sweep landing more than one
branch. Instead a PR now drops a small file into ``changelog.d/`` named
``<slug>.<category>.md``, and this script folds those fragments into the changelog
when a release is cut.

Two modes:

``--check``
    Validate every fragment and write nothing. Non-zero exit on a bad category, an
    empty fragment, or content that does not start with a Markdown bullet.

``--version X.Y.Z [--date YYYY-MM-DD]``
    Roll ``## [Unreleased]`` -- both the fragments and anything written into the
    section by hand -- into a new ``## [X.Y.Z] - DATE`` section, refresh the link
    reference block at the bottom of the file, and delete the consumed fragments.

This is a hand-rolled compiler rather than towncrier or scriv on purpose. The
changelog's entries are long Keep a Changelog prose bullets, and the third-party
tools rewrite the whole file with their own wrapping, ordering and newline opinions
-- which would turn a two-line release edit into a several-thousand-line diff and
flatten the entries. Every line this script does not logically change is passed
through byte for byte, *including its original line ending*: the repository normalises
to LF through ``.gitattributes``, but a Windows checkout, an editor or a future
attribute change can put CRLF in front of this script, and rewriting all of them
would bury the release in a whole-file diff. Nothing here goes through text-mode I/O
or ``str.splitlines`` for that reason.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = REPO_ROOT / "CHANGELOG.md"
DEFAULT_FRAGMENTS_DIR = REPO_ROOT / "changelog.d"

#: Fragment categories, in the order Keep a Changelog gives their sections. A new
#: ``### Section`` is created at the position this order implies.
CATEGORIES: tuple[str, ...] = (
    "added",
    "changed",
    "deprecated",
    "removed",
    "fixed",
    "security",
)
SECTION_TITLES: dict[str, str] = {category: category.capitalize() for category in CATEGORIES}
CANONICAL_ORDER: tuple[str, ...] = tuple(SECTION_TITLES[category] for category in CATEGORIES)

_UNRELEASED_HEADING = re.compile(r"^## \[Unreleased\]\s*$")
_ANY_HEADING = re.compile(r"^## ")
_SECTION_HEADING = re.compile(r"^### (.+?)\s*$")
_LINK_REFERENCE = re.compile(r"^\[[^\]]+\]:\s")
_UNRELEASED_LINK = re.compile(r"^\[Unreleased\]:\s*(?P<prefix>\S*/compare/)v(?P<previous>\S+?)\.\.\.HEAD\s*$")
_VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.]+)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Splits on CRLF, LF or CR and keeps each line's own ending attached to it, so that
# "".join(lines) reproduces the input exactly. str.splitlines() is not usable here:
# it also breaks on form feeds, vertical tabs and U+2028, and would silently rewrite
# any of those into the file's dominant newline on the way out.
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r|$)")


class CompileError(Exception):
    """A condition the caller has to fix before a release can be compiled."""


def split_lines(text: str) -> list[str]:
    """Split ``text`` into lines that each keep their own trailing newline."""
    lines = _LINE.findall(text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def detect_newline(text: str) -> str:
    """Return the newline the file is written with, LF when it has none."""
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def read_text(path: Path) -> str:
    """Read ``path`` without letting the platform translate its line endings."""
    return path.read_bytes().decode("utf-8")


def write_text(path: Path, text: str) -> None:
    """Write ``path`` without letting the platform translate its line endings."""
    path.write_bytes(text.encode("utf-8"))


class Fragment:
    """One ``changelog.d/<slug>.<category>.md`` file."""

    def __init__(self, path: Path, category: str, bullets: list[str]) -> None:
        """Record a validated fragment's path, category and bullet lines."""
        self.path = path
        self.category = category
        self.bullets = bullets

    @property
    def section(self) -> str:
        """The ``###`` heading this fragment's bullets belong under."""
        return SECTION_TITLES[self.category]


def parse_fragment(path: Path) -> Fragment:
    """Load and validate one fragment file.

    Raises
    ------
    CompileError
        If the filename carries no known category, or the body is empty or does
        not start with a Markdown bullet.

    """
    parts = path.name.split(".")
    if len(parts) < 3 or parts[-1] != "md":
        raise CompileError(
            f"{path.name}: expected a name of the form '<slug>.<category>.md' "
            f"(category one of: {', '.join(CATEGORIES)})"
        )
    category = parts[-2].lower()
    if category not in CATEGORIES:
        raise CompileError(f"{path.name}: unknown category {parts[-2]!r} (expected one of: {', '.join(CATEGORIES)})")

    try:
        text = read_text(path)
    except UnicodeDecodeError as exc:  # pragma: no cover - defensive
        raise CompileError(f"{path.name}: not valid UTF-8 ({exc})") from exc

    bullets = [line.rstrip("\r\n") for line in split_lines(text)]
    while bullets and not bullets[-1].strip():
        bullets.pop()
    while bullets and not bullets[0].strip():
        bullets.pop(0)
    if not bullets:
        raise CompileError(f"{path.name}: fragment is empty")
    if not bullets[0].startswith("- "):
        raise CompileError(
            f"{path.name}: fragment must start with a Markdown bullet ('- '), "
            f"got {bullets[0][:40]!r}. Write the entry exactly as it should read "
            f"in CHANGELOG.md."
        )
    return Fragment(path, category, bullets)


def load_fragments(fragments_dir: Path) -> tuple[list[Fragment], list[str]]:
    """Load every fragment in ``fragments_dir``, sorted by filename.

    Returns the fragments that parsed and the error messages for those that did
    not, so ``--check`` can report all of a branch's problems in one run.
    """
    if not fragments_dir.is_dir():
        return [], []
    fragments: list[Fragment] = []
    errors: list[str] = []
    for path in sorted(fragments_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        try:
            fragments.append(parse_fragment(path))
        except CompileError as exc:
            errors.append(str(exc))
    return fragments, errors


def _section_rank(title: str) -> int:
    """Sort key placing known sections in canonical order and unknown ones last."""
    try:
        return CANONICAL_ORDER.index(title)
    except ValueError:
        return len(CANONICAL_ORDER)


def _split_unreleased(body: list[str]) -> tuple[list[str], list[list[str]]]:
    """Split the Unreleased body into its leading lines and its ``###`` sections."""
    first = len(body)
    for index, line in enumerate(body):
        if _SECTION_HEADING.match(line):
            first = index
            break
    preamble = body[:first]
    sections: list[list[str]] = []
    for line in body[first:]:
        if _SECTION_HEADING.match(line):
            sections.append([line])
        else:
            sections[-1].append(line)
    return preamble, sections


def _append_bullets(section: list[str], bullets: list[str], newline: str) -> list[str]:
    """Append ``bullets`` to an existing section, keeping its trailing blank lines."""
    heading, rest = section[0], section[1:]
    end = len(rest)
    while end > 0 and not rest[end - 1].strip():
        end -= 1
    trailing = rest[end:] or [newline]
    return [heading, *rest[:end], *(bullet + newline for bullet in bullets), *trailing]


def _new_section(title: str, bullets: list[str], newline: str) -> list[str]:
    """Build a section that does not exist in the Unreleased body yet."""
    return [
        f"### {title}{newline}",
        newline,
        *(bullet + newline for bullet in bullets),
        newline,
    ]


def merge_fragments(sections: list[list[str]], fragments: list[Fragment], newline: str) -> list[list[str]]:
    """Fold every fragment into the section its category names.

    An existing section gains the bullets at its end; a missing one is created at
    the position :data:`CANONICAL_ORDER` gives it, before the first section that
    sorts after it.
    """
    merged = [list(section) for section in sections]
    by_section: dict[str, list[str]] = {}
    for fragment in fragments:
        by_section.setdefault(fragment.section, []).extend(fragment.bullets)

    for title in CANONICAL_ORDER:
        bullets = by_section.get(title)
        if not bullets:
            continue
        existing = next(
            (i for i, section in enumerate(merged) if _heading_title(section[0]) == title),
            None,
        )
        if existing is not None:
            merged[existing] = _append_bullets(merged[existing], bullets, newline)
            continue
        rank = _section_rank(title)
        insert_at = next(
            (i for i, section in enumerate(merged) if _section_rank(_heading_title(section[0])) > rank),
            len(merged),
        )
        merged.insert(insert_at, _new_section(title, bullets, newline))
    return merged


def _heading_title(line: str) -> str:
    match = _SECTION_HEADING.match(line)
    return match.group(1) if match else ""


def _update_link_references(lines: list[str], version: str, newline: str) -> list[str]:
    """Point ``[Unreleased]`` at the new tag and add the released version's link."""
    for index in range(len(lines) - 1, -1, -1):
        match = _UNRELEASED_LINK.match(lines[index])
        if not match:
            continue
        prefix = match.group("prefix")
        base = prefix[: -len("/compare/")]
        updated = list(lines)
        updated[index] = f"[Unreleased]: {prefix}v{version}...HEAD{newline}"
        updated.insert(index + 1, f"[{version}]: {base}/releases/tag/v{version}{newline}")
        return updated
    raise CompileError(
        "no '[Unreleased]: .../compare/vX.Y.Z...HEAD' link reference found; "
        "the link block at the bottom of the changelog is how released versions "
        "are addressed and cannot be regenerated from the headings alone"
    )


def compile_release(
    changelog: Path,
    fragments: list[Fragment],
    version: str,
    date: str,
) -> str:
    """Return the changelog text with Unreleased plus ``fragments`` rolled into ``version``."""
    if not _VERSION.fullmatch(version):
        raise CompileError(f"{version!r} is not a version of the form X.Y.Z")
    if not _DATE.fullmatch(date):
        raise CompileError(f"{date!r} is not a date of the form YYYY-MM-DD")

    text = read_text(changelog)
    newline = detect_newline(text)
    lines = split_lines(text)

    heading = next((i for i, line in enumerate(lines) if _UNRELEASED_HEADING.match(line)), None)
    if heading is None:
        raise CompileError(f"{changelog.name}: no '## [Unreleased]' heading found")
    if any(line.startswith(f"## [{version}]") for line in lines):
        raise CompileError(f"{changelog.name}: a '## [{version}]' section already exists")

    end = next(
        (i for i in range(heading + 1, len(lines)) if _ANY_HEADING.match(lines[i]) or _LINK_REFERENCE.match(lines[i])),
        len(lines),
    )
    preamble, sections = _split_unreleased(lines[heading + 1 : end])
    if not sections and not fragments:
        raise CompileError(
            "nothing to release: '## [Unreleased]' has no '###' sections and " "changelog.d/ holds no fragments"
        )
    if not preamble:
        preamble = [newline]

    merged = merge_fragments(sections, fragments, newline)
    rolled = [
        *lines[: heading + 1],
        newline,
        f"## [{version}] - {date}{newline}",
        *preamble,
        *(line for section in merged for line in section),
        *lines[end:],
    ]
    return "".join(_update_link_references(rolled, version, newline))


def run_check(fragments_dir: Path) -> int:
    """Validate every fragment without writing anything."""
    fragments, errors = load_fragments(fragments_dir)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        print(
            f"\n{len(errors)} malformed fragment(s) in {fragments_dir}. "
            f"See {fragments_dir / 'README.md'} for the format.",
            file=sys.stderr,
        )
        return 1
    print(f"{len(fragments)} fragment(s) in {fragments_dir}: all well-formed")
    return 0


def run_compile(changelog: Path, fragments_dir: Path, version: str, date: str, dry_run: bool) -> int:
    """Roll Unreleased and the fragments into a released section."""
    fragments, errors = load_fragments(fragments_dir)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print("\nrefusing to compile a release with malformed fragments", file=sys.stderr)
        return 1

    compiled = compile_release(changelog, fragments, version, date)
    if dry_run:
        print(f"would write {changelog} and delete {len(fragments)} fragment(s):")
        for fragment in fragments:
            print(f"  {fragment.path.name} -> ### {fragment.section}")
        return 0

    write_text(changelog, compiled)
    for fragment in fragments:
        fragment.path.unlink()
    print(f"wrote {changelog}: [{version}] - {date}, {len(fragments)} fragment(s) consumed and deleted")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="compile_changelog.py",
        description="Compile changelog.d/ fragments into CHANGELOG.md.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="validate the fragments and write nothing",
    )
    mode.add_argument(
        "--version",
        metavar="X.Y.Z",
        help="roll Unreleased and the fragments into this released version",
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        default=None,
        help="release date for the new section (default: today)",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=DEFAULT_CHANGELOG,
        help=f"path to the changelog (default: {DEFAULT_CHANGELOG})",
    )
    parser.add_argument(
        "--fragments-dir",
        type=Path,
        default=DEFAULT_FRAGMENTS_DIR,
        help=f"directory holding the fragments (default: {DEFAULT_FRAGMENTS_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --version, report what would happen without writing or deleting",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the requested mode and return the process exit status."""
    args = build_parser().parse_args(argv)
    try:
        if args.check:
            return run_check(args.fragments_dir)
        date = args.date or dt.date.today().isoformat()
        return run_compile(args.changelog, args.fragments_dir, args.version, date, args.dry_run)
    except CompileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
