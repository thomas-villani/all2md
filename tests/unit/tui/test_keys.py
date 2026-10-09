"""Tests for the viewer's key presets."""

from __future__ import annotations

import pytest

from all2md.tui.keys import DESCRIPTIONS, PRESETS, Action, bindings, keymap


@pytest.mark.unit
class TestPresets:
    def test_every_action_has_a_description(self):
        assert set(DESCRIPTIONS) == set(Action)

    @pytest.mark.parametrize("preset", sorted(PRESETS))
    def test_every_action_except_half_pages_has_a_key(self, preset):
        bound = set(keymap(preset).values())
        missing = set(Action) - bound
        assert missing <= {Action.HALF_PAGE_DOWN, Action.HALF_PAGE_UP}

    def test_vim_keeps_every_default_key(self):
        default, vim = keymap("default"), keymap("vim")
        assert {key: vim[key] for key in default} == dict(default)

    def test_vim_has_all_actions(self):
        assert set(keymap("vim").values()) == set(Action)

    def test_keys_are_case_sensitive(self):
        vim = keymap("vim")
        assert (vim["g"], vim["G"]) == (Action.TOP, Action.BOTTOM)

    @pytest.mark.parametrize("preset", sorted(PRESETS))
    def test_key_names_are_wijjit_spelling(self, preset):
        for key in keymap(preset):
            assert key == key.strip() and key
            if len(key) > 1:
                assert key == key.lower(), key

    def test_presets_are_read_only(self):
        with pytest.raises(TypeError):
            keymap()["x"] = Action.QUIT  # type: ignore[index]

    def test_unknown_preset(self):
        with pytest.raises(ValueError, match="default, vim"):
            keymap("emacs")


@pytest.mark.unit
class TestBindings:
    def test_actions_in_order_with_their_keys(self):
        listed = bindings("default")
        assert [action for action, _ in listed] == [a for a in Action if a in set(keymap().values())]
        assert dict(listed)[Action.PAGE_DOWN] == ["pagedown", "space"]

    def test_vim_lists_both_spellings(self):
        assert dict(bindings("vim"))[Action.HALF_PAGE_DOWN] == ["d", "ctrl+d"]


@pytest.mark.unit
class TestHelpRows:
    def test_default_ends_with_the_fixed_keys(self):
        from all2md.tui.keys import FIXED_KEYS, help_rows

        rows = help_rows("default")
        assert rows[0] == ("Down", "Scroll down a line")
        assert rows[-len(FIXED_KEYS) :] == list(FIXED_KEYS)

    def test_only_what_vim_adds(self):
        from all2md.tui.keys import help_rows

        rows = {description: keys for keys, description in help_rows("vim", only_new=True)}
        assert rows["Scroll down a line"] == "j"
        assert "Show these keys" not in rows
        assert "Tab" not in rows.values()
