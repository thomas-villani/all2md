#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/cli/test_cli_zip_option_projection.py
"""The ``--zip`` path projects its namespaced options like every other path.

The CLI carries options fully qualified -- ``pdf.pages``, ``markdown.flavor``, and
the subcommand sections' own settings such as ``view.dark`` -- and flattens them
against the formats that will actually handle each file. Every path that writes to
disk does that per input file through ``prepare_options_for_execution``.

``--zip`` did not. It handed the whole namespaced dict to ``convert()``, which
matched none of it and told the user their parameter names were wrong:

    UserWarning: Unrecognized keyword arguments were ignored:
    ['view.no_wait', 'view.dark'].

Those are the ``[view]`` section's own settings. Nobody typed them (#303).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from all2md.cli.input_items import CLIInputItem
from all2md.cli.packaging import create_package_from_conversions
from all2md.cli.processors import prepare_options_for_execution

pytestmark = [pytest.mark.unit, pytest.mark.cli]


def _item(path: Path) -> CLIInputItem:
    return CLIInputItem(raw_input=path, kind="local_file", display_name=path.name, path_hint=path)


def _sources(tmp_path: Path) -> tuple[Path, Path]:
    """One markdown file and one HTML file -- deliberately different formats."""
    md = tmp_path / "note.md"
    md.write_text("# Alpha\n\nBody text.\n", encoding="utf-8")
    html = tmp_path / "page.html"
    html.write_text("<h1>Beta</h1><p>Other text.</p>", encoding="utf-8")
    return md, html


class _ConvertSpy:
    """Records the kwargs each conversion was given, and writes plausible output."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, *, source, output, **kwargs):
        self.calls.append(kwargs)
        output.write(b"# stub\n")

    def kwargs_for(self, index: int) -> dict:
        """The kwargs of one call, minus the ones packaging always sets."""
        recorded = dict(self.calls[index])
        for always_present in ("source_format", "target_format", "transforms", "progress_callback"):
            recorded.pop(always_present, None)
        recorded.pop("attachment_mode", None)  # packaging forces this one; see #275
        return recorded


@pytest.fixture
def spy(monkeypatch):
    replacement = _ConvertSpy()
    monkeypatch.setattr("all2md.cli.packaging.convert", replacement)
    return replacement


def _resolver(options, format_arg="auto", target_format="markdown"):
    return lambda item: prepare_options_for_execution(options, item.best_path(), format_arg, target_format)


class TestASubcommandsOwnSettingsNeverReachTheConverter:
    """The bug as reported: ``[view]`` settings arriving as conversion kwargs."""

    @pytest.mark.parametrize("leaked_key", ["view.dark", "view.no_wait", "serve.host", "rich.theme"])
    def test_a_namespaced_non_format_key_is_dropped(self, tmp_path, spy, leaked_key):
        md, _ = _sources(tmp_path)
        options = {leaked_key: True}

        create_package_from_conversions(
            [_item(md)], tmp_path / "out.zip", options=options, option_resolver=_resolver(options)
        )

        assert spy.kwargs_for(0) == {}, f"{leaked_key} reached convert()"

    def test_without_a_resolver_the_dict_is_passed_through(self, tmp_path, spy):
        """The unprojected behaviour is still available to a library caller.

        Guards the fix from the other direction: the resolver is what filters, so a
        caller that does its own projection is not silently second-guessed.
        """
        md, _ = _sources(tmp_path)

        create_package_from_conversions([_item(md)], tmp_path / "out.zip", options={"view.dark": True})

        assert spy.kwargs_for(0) == {"view.dark": True}


class TestProjectionMatchesTheToDiskPath:
    """The requirement is parity, not an ideal set of kwargs.

    Asserting what the projected dict "should" contain would encode a spec the
    to-disk paths do not follow either; the actual requirement is that packaging a
    file and converting it to disk hand ``convert()`` the same options.
    """

    @pytest.mark.parametrize(
        "options",
        [
            pytest.param({"view.dark": True}, id="non-format-namespace"),
            pytest.param({"pdf.pages": [1]}, id="another-formats-option"),
            pytest.param({"markdown.flavor": "commonmark"}, id="this-formats-option"),
            pytest.param({"attachment_base_url": "/img"}, id="unqualified-applies-everywhere"),
            pytest.param({"html.strip_dangerous_elements": True}, id="qualified-for-the-other-item"),
            pytest.param({}, id="nothing-at-all"),
        ],
    )
    def test_each_item_gets_what_the_to_disk_path_would_give_it(self, tmp_path, spy, options):
        md, html = _sources(tmp_path)
        items = [_item(md), _item(html)]

        create_package_from_conversions(
            items, tmp_path / "out.zip", options=options, option_resolver=_resolver(options)
        )

        for index, item in enumerate(items):
            expected = prepare_options_for_execution(options, item.best_path(), "auto", "markdown")
            assert spy.kwargs_for(index) == expected, f"{item.display_name} diverged from the to-disk path"

    def test_the_two_items_are_projected_separately(self, tmp_path, spy):
        """A batch is mixed-format, so one dict for the whole batch cannot be right."""
        md, html = _sources(tmp_path)
        options = {"html.strip_dangerous_elements": True}

        create_package_from_conversions(
            [_item(md), _item(html)], tmp_path / "out.zip", options=options, option_resolver=_resolver(options)
        )

        assert spy.kwargs_for(0) == {}, "an html-qualified option was applied to the markdown item"
        assert spy.kwargs_for(1) == {"strip_dangerous_elements": True}


class TestTheArchiveIsStillBuilt:
    """Projection must not cost us the conversion it was filtering options for."""

    def test_every_item_is_written(self, tmp_path):
        md, html = _sources(tmp_path)
        zip_path = tmp_path / "out.zip"
        options = {"view.dark": True}

        create_package_from_conversions(
            [_item(md), _item(html)], zip_path, options=options, option_resolver=_resolver(options)
        )

        with zipfile.ZipFile(zip_path) as archive:
            assert sorted(archive.namelist()) == ["note.md", "page.md"]
            assert b"Alpha" in archive.read("note.md")
            assert b"Beta" in archive.read("page.md")

    def test_attachment_mode_is_still_forced_to_base64(self, tmp_path, spy):
        """Projection replaced the options dict, so the base64 injection must survive."""
        md, _ = _sources(tmp_path)
        options = {"view.dark": True}

        create_package_from_conversions(
            [_item(md)], tmp_path / "out.zip", options=options, option_resolver=_resolver(options)
        )

        assert spy.calls[0]["attachment_mode"] == "base64"

    def test_an_explicit_attachment_mode_still_wins(self, tmp_path, spy):
        md, _ = _sources(tmp_path)
        options = {"attachment_mode": "skip"}

        create_package_from_conversions(
            [_item(md)], tmp_path / "out.zip", options=options, option_resolver=_resolver(options)
        )

        assert spy.calls[0]["attachment_mode"] == "skip"
