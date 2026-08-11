"""Dropped keyword arguments must warn from every public entry point.

Regression tests for #273. ``to_markdown`` warned on unknown kwargs but ``to_ast``
and ``from_ast`` dropped them silently, so a typo (or a plausible-but-nonexistent
parameter such as ``filename``) produced a valid-looking result with no diagnostic.

Extended for #275, which split the diagnosis three ways. A dropped name is either a
typo, a real option that this conversion's formats have no field for, or something
all2md injected itself -- and only the first two are the caller's business.
"""

import warnings

import pytest

from all2md import from_ast, to_ast, to_markdown

MARKDOWN_SRC = "# Heading\n\nBody text.\n"

# Both diagnoses open this way; the wording after it is what tells them apart.
ANY_DROP = "were ignored"
TYPO = "Unrecognized keyword"
WRONG_FORMAT = "not for the formats in this conversion"


def _warnings_from(func, *args, **kwargs):
    """Return the UserWarnings raised by a call, ignoring everything else."""
    return _warnings_matching(ANY_DROP, func, *args, **kwargs)


def _warnings_matching(fragment, func, *args, **kwargs):
    """Return the UserWarnings whose message contains ``fragment``."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        func(*args, **kwargs)
    return [w for w in caught if issubclass(w.category, UserWarning) and fragment in str(w.message)]


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
class TestARealOptionForAnotherFormatIsDiagnosedDifferently:
    """A misspelled name and a misplaced one are not the same mistake.

    Both end in a dropped kwarg, and #273 gave both the same message: check your
    parameter names. For ``pages`` on a markdown parse that sends the caller hunting
    for a typo they did not make, so the wording splits (#275).
    """

    @pytest.mark.parametrize("entry_point", [to_ast, to_markdown])
    def test_it_warns_without_calling_the_name_unrecognized(self, entry_point):
        found = _warnings_matching(WRONG_FORMAT, entry_point, MARKDOWN_SRC, source_format="markdown", pages="1-3")

        assert found, "a real option this format has no use for was dropped silently"
        assert "pages" in str(found[0].message)
        assert TYPO not in str(found[0].message)

    def test_a_typo_is_still_called_unrecognized(self):
        found = _warnings_matching(TYPO, to_ast, MARKDOWN_SRC, source_format="markdown", atachment_mode="base64")

        assert found, "the case that motivated #273 must still warn"
        assert WRONG_FORMAT not in str(found[0].message)

    def test_both_diagnoses_can_arrive_from_one_call(self):
        """One bad name and one misplaced name are two problems, reported as two."""
        found = _warnings_from(to_ast, MARKDOWN_SRC, source_format="markdown", pages="1-3", bogus_xyz=1)

        typo = [str(w.message) for w in found if TYPO in str(w.message)]
        misplaced = [str(w.message) for w in found if WRONG_FORMAT in str(w.message)]

        assert typo and "bogus_xyz" in typo[0] and "pages" not in typo[0]
        assert misplaced and "pages" in misplaced[0] and "bogus_xyz" not in misplaced[0]

    @pytest.mark.parametrize("entry_point", [to_ast, to_markdown])
    def test_the_entry_points_agree(self, entry_point):
        """#275's other half: to_ast used to stay silent here while to_markdown warned."""
        assert _warnings_from(entry_point, MARKDOWN_SRC, source_format="markdown", attachment_mode="base64")


@pytest.mark.unit
class TestOptionsAll2mdInjectedItselfStayQuiet:
    """A warning must not blame the caller for a kwarg the library added (#275).

    ``all2md *.md --package out.zip`` warned that ``attachment_mode`` was
    unrecognized. The user never passed it -- the packager forces it so attachments
    stay in memory, and markdown has no such option, so it was dropped.
    """

    def test_packaging_does_not_warn_about_its_own_attachment_mode(self, tmp_path):
        from all2md.cli.input_items import CLIInputItem
        from all2md.cli.packaging import create_package_from_conversions

        source = tmp_path / "note.md"
        source.write_text(MARKDOWN_SRC, encoding="utf-8")
        item = CLIInputItem(raw_input=source, kind="local_file", display_name="note.md", path_hint=source)

        found = _warnings_from(create_package_from_conversions, [item], tmp_path / "out.zip")

        assert not found, f"packaging blamed the caller: {[str(w.message) for w in found]}"

    def test_the_package_is_still_written(self, tmp_path):
        """Silencing the warning must not mean skipping the work it accompanied."""
        import zipfile

        from all2md.cli.input_items import CLIInputItem
        from all2md.cli.packaging import create_package_from_conversions

        source = tmp_path / "note.md"
        source.write_text(MARKDOWN_SRC, encoding="utf-8")
        item = CLIInputItem(raw_input=source, kind="local_file", display_name="note.md", path_hint=source)
        zip_path = tmp_path / "out.zip"

        create_package_from_conversions([item], zip_path)

        with zipfile.ZipFile(zip_path) as archive:
            assert archive.namelist() == ["note.md"]
            assert b"Heading" in archive.read("note.md")

    def test_a_caller_supplied_attachment_mode_is_still_the_callers(self, tmp_path):
        """The packager only marks what it injected, so an explicit one still warns."""
        from all2md.cli.input_items import CLIInputItem
        from all2md.cli.packaging import create_package_from_conversions

        source = tmp_path / "note.md"
        source.write_text(MARKDOWN_SRC, encoding="utf-8")
        item = CLIInputItem(raw_input=source, kind="local_file", display_name="note.md", path_hint=source)

        found = _warnings_from(
            create_package_from_conversions,
            [item],
            tmp_path / "out.zip",
            options={"attachment_mode": "base64"},
        )

        assert found, "an attachment_mode the caller chose is theirs to hear about"

    def test_the_flavor_shorthand_does_not_blame_the_caller(self):
        """``flavor`` is a named parameter of convert(); we push it into renderer kwargs."""
        from all2md import from_markdown

        assert not _warnings_from(from_markdown, MARKDOWN_SRC, "html", flavor="gfm")

    def test_the_mark_does_not_outlive_the_call(self):
        """A ContextVar left set would silence the same name for everyone afterwards."""
        from all2md.api import library_injected_options

        with library_injected_options("attachment_mode"):
            assert not _warnings_from(to_ast, MARKDOWN_SRC, source_format="markdown", attachment_mode="base64")

        assert _warnings_from(to_ast, MARKDOWN_SRC, source_format="markdown", attachment_mode="base64")

    def test_marks_nest_rather_than_replace(self):
        from all2md.api import library_injected_options

        with library_injected_options("attachment_mode"), library_injected_options("pages"):
            assert not _warnings_from(
                to_ast, MARKDOWN_SRC, source_format="markdown", attachment_mode="base64", pages="1-3"
            )

    def test_an_injected_mark_does_not_hide_a_typo(self):
        """Marking one name best-effort must not silence the bad kwarg beside it."""
        from all2md.api import library_injected_options

        with library_injected_options("attachment_mode"):
            found = _warnings_from(
                to_ast, MARKDOWN_SRC, source_format="markdown", attachment_mode="base64", bogus_xyz=1
            )

        assert found
        messages = " ".join(str(w.message) for w in found)
        assert "bogus_xyz" in messages
        assert "attachment_mode" not in messages


@pytest.mark.unit
class TestUnknownKwargsStillApplyTheGoodOnes:
    """Warning about one bad kwarg must not discard the valid ones alongside it."""

    def test_valid_kwarg_survives(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            out = to_markdown(MARKDOWN_SRC, source_format="markdown", flavor="commonmark", bogus_xyz=1)
        assert "Heading" in out
