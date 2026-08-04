"""Unrecognized keyword arguments must warn from every public entry point.

Regression tests for #273. ``to_markdown`` warned on unknown kwargs but ``to_ast``
and ``from_ast`` dropped them silently, so a typo (or a plausible-but-nonexistent
parameter such as ``filename``) produced a valid-looking result with no diagnostic.
"""

import warnings

import pytest

from all2md import from_ast, to_ast, to_markdown

MARKDOWN_SRC = "# Heading\n\nBody text.\n"


def _warnings_from(func, *args, **kwargs):
    """Return the UserWarnings raised by a call, ignoring everything else."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        func(*args, **kwargs)
    return [w for w in caught if issubclass(w.category, UserWarning) and "Unrecognized keyword" in str(w.message)]


@pytest.mark.unit
class TestUnrecognizedKwargsWarn:
    """Unknown kwargs are reported, not swallowed."""

    @pytest.mark.parametrize("bad_kwarg", ["filename", "bogus_xyz", "exract_title"])
    def test_to_ast_warns(self, bad_kwarg):
        found = _warnings_from(to_ast, MARKDOWN_SRC, **{bad_kwarg: "value"})
        assert found, f"to_ast silently ignored {bad_kwarg!r}"
        assert bad_kwarg in str(found[0].message)

    @pytest.mark.parametrize("bad_kwarg", ["filename", "bogus_xyz", "exract_title"])
    def test_to_markdown_warns(self, bad_kwarg):
        found = _warnings_from(to_markdown, MARKDOWN_SRC, **{bad_kwarg: "value"})
        assert found, f"to_markdown silently ignored {bad_kwarg!r}"
        assert bad_kwarg in str(found[0].message)

    def test_from_ast_warns(self):
        doc = to_ast(MARKDOWN_SRC, source_format="markdown")
        found = _warnings_from(from_ast, doc, "markdown", bogus_xyz=1)
        assert found, "from_ast silently ignored an unknown renderer kwarg"
        assert "bogus_xyz" in str(found[0].message)

    def test_entry_points_agree(self):
        """The whole point of #273: the same bad kwarg behaves the same everywhere."""
        to_ast_warned = bool(_warnings_from(to_ast, MARKDOWN_SRC, filename="x.md"))
        to_markdown_warned = bool(_warnings_from(to_markdown, MARKDOWN_SRC, filename="x.md"))
        assert to_ast_warned == to_markdown_warned == True  # noqa: E712

    def test_warning_points_at_the_caller(self):
        """A warning attributed past the caller's frame is useless and dedups wrongly."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            to_ast(MARKDOWN_SRC, bogus_xyz=1)
        assert caught
        assert caught[0].filename == __file__, f"warning attributed to {caught[0].filename}, not the caller"


@pytest.mark.unit
class TestValidKwargsStaySilent:
    """The warning must not fire for kwargs the options classes actually accept."""

    def test_markdown_parser_kwarg(self):
        assert not _warnings_from(to_ast, MARKDOWN_SRC, source_format="markdown", parse_footnotes=True)

    def test_renderer_kwarg(self):
        assert not _warnings_from(to_markdown, MARKDOWN_SRC, flavor="commonmark")

    def test_nested_dataclass_kwarg(self):
        """Fields of nested options dataclasses (e.g. network) are valid, not unmatched."""
        assert not _warnings_from(to_markdown, "<p>x</p>", source_format="html", allow_remote_fetch=False)

    def test_no_kwargs_at_all(self):
        assert not _warnings_from(to_ast, MARKDOWN_SRC, source_format="markdown")


@pytest.mark.unit
class TestKnownOptionForAnotherFormatStaysQuiet:
    """A real option that this format ignores is not a typo, and must not warn.

    ``to_ast``/``from_ast`` see only one options class, so they cannot tell "bogus"
    from "valid elsewhere". The library itself injects such options -- the CLI
    packager forces ``attachment_mode``, the MCP server sets it from server config,
    ``convert`` injects its ``flavor`` shorthand -- so warning here would blame the
    caller for something they never passed.
    """

    @pytest.mark.parametrize("option_name", ["attachment_mode", "flavor", "pages"])
    def test_real_option_from_another_format_is_silent(self, option_name):
        assert not _warnings_from(to_ast, MARKDOWN_SRC, source_format="markdown", **{option_name: "base64"})

    def test_library_injected_flavor_does_not_blame_the_caller(self):
        """from_markdown documents `flavor`; converting to HTML must not call it bogus."""
        from all2md import from_markdown

        assert not _warnings_from(from_markdown, MARKDOWN_SRC, "html", flavor="gfm")

    def test_typo_of_a_real_option_still_warns(self):
        """The safety net still catches the case that motivated #273."""
        assert _warnings_from(to_ast, MARKDOWN_SRC, source_format="markdown", atachment_mode="base64")


@pytest.mark.unit
class TestUnknownKwargsStillApplyTheGoodOnes:
    """Warning about one bad kwarg must not discard the valid ones alongside it."""

    def test_valid_kwarg_survives(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            out = to_markdown(MARKDOWN_SRC, source_format="markdown", flavor="commonmark", bogus_xyz=1)
        assert "Heading" in out
