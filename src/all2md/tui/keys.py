"""The viewer's key bindings, as data.

A preset maps key names, in Wijjit's spelling (``"pagedown"``, ``"ctrl+d"``,
``"shift+tab"``, a printable character as itself), to the action they run.
Keys are case-sensitive: ``g`` and ``G`` are different keys. The viewer
looks keys up here and never hard-codes one, so a preset can be added or
changed without touching the app.

``default`` uses the keys anyone would try first. ``vim`` adds the keys of
less and vim (``j``/``k``, ``b``, ``g``/``G``, Ctrl+D/Ctrl+U...) on top, so
nothing from the default stops working.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping


class Action(str, Enum):
    """Something the viewer can do from the keyboard."""

    LINE_DOWN = "line_down"
    LINE_UP = "line_up"
    PAGE_DOWN = "page_down"
    PAGE_UP = "page_up"
    HALF_PAGE_DOWN = "half_page_down"
    HALF_PAGE_UP = "half_page_up"
    TOP = "top"
    BOTTOM = "bottom"
    NEXT_HEADING = "next_heading"
    PREVIOUS_HEADING = "previous_heading"
    TOGGLE_OUTLINE = "toggle_outline"
    LINKS = "links"
    BACK = "back"
    FORWARD = "forward"
    HELP = "help"
    QUIT = "quit"


#: What each action does, for the help screen.
DESCRIPTIONS: Mapping[Action, str] = MappingProxyType(
    {
        Action.LINE_DOWN: "Scroll down a line",
        Action.LINE_UP: "Scroll up a line",
        Action.PAGE_DOWN: "Scroll down a page",
        Action.PAGE_UP: "Scroll up a page",
        Action.HALF_PAGE_DOWN: "Scroll down half a page",
        Action.HALF_PAGE_UP: "Scroll up half a page",
        Action.TOP: "Go to the top",
        Action.BOTTOM: "Go to the bottom",
        Action.NEXT_HEADING: "Go to the next heading",
        Action.PREVIOUS_HEADING: "Go to the previous heading",
        Action.TOGGLE_OUTLINE: "Show or hide the outline",
        Action.LINKS: "List the links on screen",
        Action.BACK: "Go back to where a link was followed from",
        Action.FORWARD: "Go forward again",
        Action.HELP: "Show these keys",
        Action.QUIT: "Quit",
    }
)

_DEFAULT: dict[str, Action] = {
    "down": Action.LINE_DOWN,
    "up": Action.LINE_UP,
    "pagedown": Action.PAGE_DOWN,
    "space": Action.PAGE_DOWN,
    "pageup": Action.PAGE_UP,
    "home": Action.TOP,
    "end": Action.BOTTOM,
    "]": Action.NEXT_HEADING,
    "[": Action.PREVIOUS_HEADING,
    "o": Action.TOGGLE_OUTLINE,
    "l": Action.LINKS,
    "backspace": Action.BACK,
    "alt+left": Action.BACK,
    "alt+right": Action.FORWARD,
    "?": Action.HELP,
    "q": Action.QUIT,
}

_VIM: dict[str, Action] = {
    **_DEFAULT,
    "j": Action.LINE_DOWN,
    "k": Action.LINE_UP,
    "f": Action.PAGE_DOWN,
    "ctrl+f": Action.PAGE_DOWN,
    "b": Action.PAGE_UP,
    "ctrl+b": Action.PAGE_UP,
    "d": Action.HALF_PAGE_DOWN,
    "ctrl+d": Action.HALF_PAGE_DOWN,
    "u": Action.HALF_PAGE_UP,
    "ctrl+u": Action.HALF_PAGE_UP,
    "g": Action.TOP,
    "G": Action.BOTTOM,
    "ctrl+o": Action.BACK,
    "Q": Action.QUIT,
}

#: The presets by name.
PRESETS: Mapping[str, Mapping[str, Action]] = MappingProxyType(
    {"default": MappingProxyType(_DEFAULT), "vim": MappingProxyType(_VIM)}
)


def keymap(preset: str = "default") -> Mapping[str, Action]:
    """Return a preset's key-to-action map.

    Parameters
    ----------
    preset : str, default "default"
        A name from ``PRESETS``.

    Returns
    -------
    Mapping of str to Action

    Raises
    ------
    ValueError
        If there is no such preset.

    """
    try:
        return PRESETS[preset]
    except KeyError:
        raise ValueError(f"Unknown key preset {preset!r}; choose from {', '.join(sorted(PRESETS))}") from None


def bindings(preset: str = "default") -> list[tuple[Action, list[str]]]:
    """Return each action with the keys that run it, for the help screen.

    Parameters
    ----------
    preset : str, default "default"
        A name from ``PRESETS``.

    Returns
    -------
    list of (Action, list of str)
        In the order of ``Action``; actions with no key are left out, and each
        action's keys are in the order the preset lists them.

    """
    keys: dict[Action, list[str]] = {}
    for key, action in keymap(preset).items():
        keys.setdefault(action, []).append(key)
    return [(action, keys[action]) for action in Action if action in keys]
