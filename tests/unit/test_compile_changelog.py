"""Tests for the changelog fragment compiler (``scripts/compile_changelog.py``).

The compiler's job is to rewrite one file that nobody reviews line by line at
release time, so most of these tests are about what it must *not* disturb: the line
endings of the file it edits, entries someone wrote into ``## [Unreleased]`` by hand,
the sections it did not touch, and the link-reference block at the bottom. The last
test runs it over the real ``CHANGELOG.md`` in a copy, because everything above it
uses a small synthetic changelog and would pass just as happily if the compiler
tripped over the real file's two thousand lines of prose.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "compile_changelog.py"
_REAL_CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


def _load():
    """Import the script by path -- ``scripts/`` is not a package."""
    spec = importlib.util.spec_from_file_location("compile_changelog", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cc = _load()


CHANGELOG_BODY = [
    "# Changelog",
    "",
    "All notable changes to this project will be documented in this file.",
    "",
    "## [Unreleased]",
    "",
    "### Added",
    "",
    "- **A hand-written addition.** Someone edited the changelog directly.",
    "",
    "### Fixed",
    "",
    "- **A hand-written fix.** Also written directly into the file.",
    "",
    "## [1.0.0] - 2026-01-01",
    "",
    "### Added",
    "",
    "- **The first release.**",
    "",
    "[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.0.0...HEAD",
    "[1.0.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.0",
]


def _write(path: Path, lines: list[str], newline: str = "\n") -> None:
    """Write ``lines`` with an explicit newline, bypassing platform translation."""
    path.write_bytes((newline.join(lines) + newline).encode("utf-8"))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A miniature repository: a changelog and an empty ``changelog.d/``."""
    _write(tmp_path / "CHANGELOG.md", CHANGELOG_BODY)
    (tmp_path / "changelog.d").mkdir()
    return tmp_path


def _fragment(repo: Path, name: str, body: str, newline: str = "\n") -> Path:
    path = repo / "changelog.d" / name
    path.write_bytes(body.replace("\n", newline).encode("utf-8"))
    return path


def _run(repo: Path, *args: str) -> int:
    return cc.main(
        [
            *args,
            "--changelog",
            str(repo / "CHANGELOG.md"),
            "--fragments-dir",
            str(repo / "changelog.d"),
        ]
    )


def _text(repo: Path) -> str:
    return (repo / "CHANGELOG.md").read_bytes().decode("utf-8")


class TestMerging:
    """Fragments land in the right ``###`` section, beside what is already there."""

    def test_fragment_appends_to_an_existing_section(self, repo: Path) -> None:
        _fragment(repo, "thing.added.md", "- **A fragment addition.** From a PR.\n")

        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 0

        text = _text(repo)
        added = text.split("### Added")[1].split("###")[0]
        assert "- **A hand-written addition.**" in added
        assert "- **A fragment addition.**" in added
        # Appended after the hand-written entry, not before it.
        assert added.index("hand-written") < added.index("fragment addition")

    def test_hand_written_entries_survive_untouched(self, repo: Path) -> None:
        _fragment(repo, "thing.added.md", "- **A fragment addition.** From a PR.\n")

        _run(repo, "--version", "1.1.0", "--date", "2026-02-02")

        text = _text(repo)
        assert "- **A hand-written addition.** Someone edited the changelog directly." in text
        assert "- **A hand-written fix.** Also written directly into the file." in text

    def test_missing_section_is_created_in_canonical_order(self, repo: Path) -> None:
        """``Security`` does not exist yet; Keep a Changelog puts it after ``Fixed``."""
        _fragment(repo, "hole.security.md", "- **A security fix.**\n")
        _fragment(repo, "gone.removed.md", "- **A removal.**\n")

        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 0

        released = _text(repo).split("## [1.1.0]")[1].split("## [1.0.0]")[0]
        headings = [line for line in released.splitlines() if line.startswith("### ")]
        assert headings == ["### Added", "### Removed", "### Fixed", "### Security"]

    def test_several_fragments_in_one_category_are_ordered_by_filename(self, repo: Path) -> None:
        _fragment(repo, "b-second.added.md", "- **Second.**\n")
        _fragment(repo, "a-first.added.md", "- **First.**\n")

        _run(repo, "--version", "1.1.0", "--date", "2026-02-02")

        text = _text(repo)
        assert text.index("**First.**") < text.index("**Second.**")

    def test_a_fragment_may_hold_several_bullets(self, repo: Path) -> None:
        _fragment(
            repo,
            "multi.fixed.md",
            "- **One.** With a\n  continuation line.\n- **Two.**\n",
        )

        _run(repo, "--version", "1.1.0", "--date", "2026-02-02")

        fixed = _text(repo).split("### Fixed")[1].split("###")[0]
        assert "- **One.** With a\n  continuation line.\n- **Two.**" in fixed


class TestReleaseShape:
    """The compiled file has to look like the ones a human produced before it."""

    def test_no_fragments_only_moves_the_unreleased_heading(self, repo: Path) -> None:
        """The historical release commit added exactly two lines to the body."""
        before = _text(repo)

        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 0

        after = _text(repo)
        added = [line for line in after.splitlines() if line not in before.splitlines()]
        assert added == [
            "## [1.1.0] - 2026-02-02",
            "[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.1.0...HEAD",
            "[1.1.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.1.0",
        ]

    def test_empty_unreleased_skeleton_is_left_on_top(self, repo: Path) -> None:
        _run(repo, "--version", "1.1.0", "--date", "2026-02-02")

        text = _text(repo)
        assert "## [Unreleased]\n\n## [1.1.0] - 2026-02-02\n\n### Added\n" in text

    def test_link_references_are_updated_and_extended(self, repo: Path) -> None:
        _run(repo, "--version", "1.1.0", "--date", "2026-02-02")

        text = _text(repo)
        assert "[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.1.0...HEAD" in text
        assert "[1.1.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.1.0" in text
        assert "[1.0.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.0" in text
        # The old compare link is gone rather than duplicated.
        assert "compare/v1.0.0...HEAD" not in text
        # The new tag link sits directly under the Unreleased one, as in the file.
        assert (
            "[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.1.0...HEAD\n"
            "[1.1.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.1.0\n"
            "[1.0.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.0\n"
        ) in text

    def test_the_date_defaults_to_today(self, repo: Path) -> None:
        assert _run(repo, "--version", "1.1.0") == 0
        assert f"## [1.1.0] - {dt.date.today().isoformat()}" in _text(repo)

    def test_a_second_run_at_the_same_version_refuses(self, repo: Path) -> None:
        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 0
        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 1


class TestNewlinePreservation:
    """The compiler edits a file it does not own the formatting of."""

    @pytest.mark.parametrize("newline", ["\r\n", "\n"])
    def test_line_endings_are_preserved_byte_for_byte(self, tmp_path: Path, newline: str) -> None:
        changelog = tmp_path / "CHANGELOG.md"
        _write(changelog, CHANGELOG_BODY, newline)
        (tmp_path / "changelog.d").mkdir()
        # The fragment is written with the *other* newline on purpose: its content is
        # normalised to the changelog's, not copied in as it was found.
        other = "\n" if newline == "\r\n" else "\r\n"
        _fragment(tmp_path, "thing.added.md", "- **A fragment addition.**\n", other)
        before = changelog.read_bytes()

        assert _run(tmp_path, "--version", "1.1.0", "--date", "2026-02-02") == 0

        after = changelog.read_bytes()
        foreign = b"\n" if newline == "\r\n" else b"\r"
        if newline == "\r\n":
            assert after.count(b"\r\n") == after.count(b"\n")
        else:
            assert foreign not in after
        # Every pre-existing line is still present with its original ending, and only
        # the lines the release logically adds are new.
        old_lines = before.split(newline.encode())
        new_lines = after.split(newline.encode())
        assert [line for line in old_lines if line not in new_lines] == [
            b"[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.0.0...HEAD"
        ]

    def test_the_diff_touches_only_the_lines_it_changes(self, tmp_path: Path) -> None:
        """A CRLF file gains exactly the release's lines -- not a rewritten file."""
        changelog = tmp_path / "CHANGELOG.md"
        _write(changelog, CHANGELOG_BODY, "\r\n")
        (tmp_path / "changelog.d").mkdir()
        before = changelog.read_bytes()

        _run(tmp_path, "--version", "1.1.0", "--date", "2026-02-02")

        after = changelog.read_bytes()
        assert len(after.split(b"\r\n")) == len(before.split(b"\r\n")) + 3
        # Byte-level: the untouched prefix is identical up to the insertion point.
        prefix = before.split(b"## [Unreleased]\r\n")[0] + b"## [Unreleased]\r\n"
        assert after.startswith(prefix)
        assert after[len(prefix) :].startswith(b"\r\n## [1.1.0] - 2026-02-02\r\n\r\n### Added\r\n")


class TestFragmentLifecycle:
    """Consumed fragments are deleted; the README beside them is not."""

    def test_fragments_are_deleted_after_a_release(self, repo: Path) -> None:
        first = _fragment(repo, "one.added.md", "- **One.**\n")
        second = _fragment(repo, "two.fixed.md", "- **Two.**\n")

        _run(repo, "--version", "1.1.0", "--date", "2026-02-02")

        assert not first.exists()
        assert not second.exists()

    def test_the_readme_is_not_a_fragment(self, repo: Path) -> None:
        readme = repo / "changelog.d" / "README.md"
        readme.write_bytes(b"# changelog.d\n\nNot a fragment.\n")

        assert _run(repo, "--check") == 0
        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 0
        assert readme.exists()
        assert "Not a fragment." not in _text(repo)

    def test_dry_run_writes_nothing_and_deletes_nothing(self, repo: Path) -> None:
        fragment = _fragment(repo, "one.added.md", "- **One.**\n")
        before = _text(repo)

        assert _run(repo, "--version", "1.1.0", "--dry-run") == 0

        assert fragment.exists()
        assert _text(repo) == before

    def test_a_missing_fragments_directory_is_not_an_error(self, repo: Path) -> None:
        (repo / "changelog.d").rmdir()

        assert _run(repo, "--check") == 0
        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 0


class TestCheck:
    """``--check`` is the gate a contributor runs; it has to be able to fail."""

    def test_a_clean_directory_passes(self, repo: Path) -> None:
        _fragment(repo, "fine.added.md", "- **Fine.**\n")
        assert _run(repo, "--check") == 0

    def test_an_empty_directory_passes(self, repo: Path) -> None:
        assert _run(repo, "--check") == 0

    def test_an_unknown_category_fails(self, repo: Path) -> None:
        _fragment(repo, "oops.improved.md", "- **Improved something.**\n")
        assert _run(repo, "--check") == 1

    def test_a_name_without_a_category_fails(self, repo: Path) -> None:
        _fragment(repo, "oops.md", "- **No category at all.**\n")
        assert _run(repo, "--check") == 1

    def test_an_empty_fragment_fails(self, repo: Path) -> None:
        _fragment(repo, "empty.fixed.md", "\n   \n")
        assert _run(repo, "--check") == 1

    def test_content_that_is_not_a_bullet_fails(self, repo: Path) -> None:
        _fragment(repo, "prose.fixed.md", "Fixed the thing.\n")
        assert _run(repo, "--check") == 1

    def test_an_indented_bullet_is_not_a_bullet(self, repo: Path) -> None:
        _fragment(repo, "indented.fixed.md", "  - **Nested.**\n")
        assert _run(repo, "--check") == 1

    def test_a_leading_blank_line_is_tolerated(self, repo: Path) -> None:
        _fragment(repo, "blank.fixed.md", "\n- **Fine after a blank line.**\n")
        assert _run(repo, "--check") == 0

    def test_check_reports_every_bad_fragment_not_just_the_first(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _fragment(repo, "one.improved.md", "- **One.**\n")
        _fragment(repo, "two.fixed.md", "Not a bullet.\n")

        assert _run(repo, "--check") == 1

        stderr = capsys.readouterr().err
        assert "one.improved.md" in stderr
        assert "two.fixed.md" in stderr

    def test_a_release_refuses_to_compile_malformed_fragments(self, repo: Path) -> None:
        _fragment(repo, "bad.improved.md", "- **Bad category.**\n")
        before = _text(repo)

        assert _run(repo, "--version", "1.1.0", "--date", "2026-02-02") == 1
        assert _text(repo) == before


class TestGuards:
    """Refusals that keep a bad release out of the file rather than reporting one."""

    def test_nothing_to_release_is_an_error(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "CHANGELOG.md",
            [
                "# Changelog",
                "",
                "## [Unreleased]",
                "",
                "## [1.0.0] - 2026-01-01",
                "",
                "- **The first release.**",
                "",
                "[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.0.0...HEAD",
            ],
        )
        (tmp_path / "changelog.d").mkdir()

        assert _run(tmp_path, "--version", "1.1.0", "--date", "2026-02-02") == 1

    def test_a_missing_link_reference_block_is_an_error(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "CHANGELOG.md",
            ["# Changelog", "", "## [Unreleased]", "", "### Added", "", "- **Something.**", ""],
        )
        (tmp_path / "changelog.d").mkdir()

        assert _run(tmp_path, "--version", "1.1.0", "--date", "2026-02-02") == 1

    def test_a_missing_unreleased_heading_is_an_error(self, tmp_path: Path) -> None:
        _write(tmp_path / "CHANGELOG.md", ["# Changelog", "", "## [1.0.0] - 2026-01-01", ""])
        (tmp_path / "changelog.d").mkdir()

        assert _run(tmp_path, "--version", "1.1.0", "--date", "2026-02-02") == 1

    @pytest.mark.parametrize("version", ["1.1", "v1.1.0", "next", "1.1.0.0"])
    def test_a_malformed_version_is_an_error(self, repo: Path, version: str) -> None:
        assert _run(repo, "--version", version, "--date", "2026-02-02") == 1

    def test_a_malformed_date_is_an_error(self, repo: Path) -> None:
        assert _run(repo, "--version", "1.1.0", "--date", "02/02/2026") == 1

    def test_a_mode_is_required(self) -> None:
        with pytest.raises(SystemExit):
            cc.main([])


class TestLineSplitting:
    """``split_lines`` is the reason the whole file survives a rewrite."""

    @pytest.mark.parametrize(
        "text",
        ["a\r\nb\r\n", "a\nb", "", "\r\n", "a\rb\r", "a\r\nb\nc\r", "no newline at all"],
    )
    def test_splitting_round_trips(self, text: str) -> None:
        assert "".join(cc.split_lines(text)) == text

    def test_a_form_feed_is_not_a_line_break(self) -> None:
        """``str.splitlines`` breaks here and would rewrite the character away."""
        assert cc.split_lines("a\x0cb\n") == ["a\x0cb\n"]


class TestTheRealChangelog:
    """Everything above uses a synthetic file a dozen lines long."""

    def test_the_repository_changelog_compiles(self, tmp_path: Path) -> None:
        original = _REAL_CHANGELOG.read_bytes()
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_bytes(original)
        fragments = tmp_path / "changelog.d"
        fragments.mkdir()
        _fragment(tmp_path, "seed.changed.md", "- **A seeded entry.** For the test.\n")

        assert _run(tmp_path, "--version", "99.0.0", "--date", "2026-02-02") == 0

        after = changelog.read_bytes()
        # Nothing below the Unreleased section moved: the tail of the file, up to the
        # link block, is byte-identical.
        tail = original.split(b"## [1.12.0]", 1)[1].split(b"[Unreleased]:", 1)[0]
        assert tail in after
        assert b"## [99.0.0] - 2026-02-02" in after
        assert b"- **A seeded entry.** For the test." in after
        assert b"[99.0.0]: https://github.com/thomas-villani/all2md/releases/tag/v99.0.0" in after
        # The compiler is additive: it grows the file, it does not rewrite it.
        assert original.count(b"\n") < after.count(b"\n")

    def test_the_repositorys_own_fragments_are_well_formed(self) -> None:
        """The seeded fragment this change ships must pass its own gate."""
        assert cc.main(["--check"]) == 0
