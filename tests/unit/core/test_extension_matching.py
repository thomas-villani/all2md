"""Tests for :func:`all2md.converter_registry.match_extension`.

``Path.suffix`` sees only the last dot-separated component, so a plain
membership test cannot recognise ``.tar.gz`` -- the CLI rejected every
two-part archive extension as a result (#306). These cover the matcher that
replaced it.
"""

import pytest

from all2md.converter_registry import match_extension, registry

KNOWN = {".pdf", ".md", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".gz"}


@pytest.mark.unit
class TestMultiPartExtensionsMatch:
    """A two-part extension is found even though ``Path.suffix`` cannot see it."""

    @pytest.mark.parametrize("name", ["a.tar.gz", "a.tar.bz2", "a.tar.xz"])
    def test_two_part_extension_is_matched(self, name):
        expected = "." + name.split(".", 1)[1]
        assert match_extension(name, KNOWN) == expected

    def test_the_longest_match_wins(self):
        # Both ".gz" and ".tar.gz" are declared here; the specific one must win,
        # otherwise the file routes to the wrong converter.
        assert match_extension("a.tar.gz", KNOWN) == ".tar.gz"

    def test_single_part_extension_still_matches(self):
        assert match_extension("report.pdf", KNOWN) == ".pdf"


@pytest.mark.unit
class TestShorterTailsAreStillTried:
    """A dotted stem must not mask the real extension."""

    def test_dotted_stem(self):
        assert match_extension("report.2024.pdf", KNOWN) == ".pdf"

    def test_many_dots(self):
        assert match_extension("my.long.file.name.pdf", KNOWN) == ".pdf"

    def test_version_like_stem_on_an_archive(self):
        assert match_extension("release.1.2.tar.gz", KNOWN) == ".tar.gz"


@pytest.mark.unit
class TestNonMatches:
    """Names carrying no known extension return ``None``."""

    @pytest.mark.parametrize("name", ["notes.xyz", "noextension", "a.tar.gz.bak"])
    def test_unknown_returns_none(self, name):
        assert match_extension(name, KNOWN) is None

    def test_empty_candidate_set(self):
        assert match_extension("report.pdf", set()) is None

    def test_dotfile_has_no_extension(self):
        # Path semantics: ".gitignore" is a name, not an extension. Matching it
        # would make every dot-file look like a document.
        assert match_extension(".pdf", KNOWN) is None


@pytest.mark.unit
class TestCaseAndPathHandling:
    """Case folding, and only the final path component is considered."""

    def test_case_insensitive(self):
        assert match_extension("A.TAR.GZ", KNOWN) == ".tar.gz"

    def test_uppercase_candidates(self):
        assert match_extension("a.tar.gz", {".TAR.GZ"}) == ".tar.gz"

    def test_dots_in_parent_directories_are_ignored(self):
        assert match_extension("/some.dir/v1.0/report.pdf", KNOWN) == ".pdf"


@pytest.mark.unit
class TestEveryRegisteredExtensionIsMatchable:
    """Parity with the registry, so a future multi-part extension cannot regress.

    The bug was not that ``.tar.gz`` was special; it was that the matcher could
    only see one-part extensions. Asserting over the live registry means any
    newly declared multi-part extension is covered without editing this test.
    """

    def test_all_declared_extensions_round_trip(self):
        known = registry.get_all_extensions()
        unmatched = [ext for ext in sorted(known) if match_extension(f"sample{ext}", known) != ext.lower()]
        assert unmatched == []

    def test_registry_convenience_wrapper(self):
        multi_part = sorted(e for e in registry.get_all_extensions() if e.count(".") > 1)
        # Guard the guard: if this is ever empty the parity test above proves nothing.
        assert multi_part, "registry declares no multi-part extensions"
        for ext in multi_part:
            assert registry.match_extension(f"bundle{ext}") == ext
