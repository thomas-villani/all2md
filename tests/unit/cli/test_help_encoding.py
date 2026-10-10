"""Help text must print on a cp1252 console.

A Windows console or pipe may encode stdout as cp1252, and ``all2md --help``
and ``all2md completion`` print every flag's help, so a character cp1252 lacks
(a Greek letter, a superscript) makes them fail with ``UnicodeEncodeError``.
Locally stdout is usually UTF-8, which hides it; this test does not depend on
the platform.
"""

from __future__ import annotations

import argparse

import pytest

from all2md.cli.builder import create_parser
from all2md.cli.commands.read import _create_read_parser


def _texts(parser: argparse.ArgumentParser):
    yield "description", parser.description or ""
    yield "epilog", parser.epilog or ""
    for action in parser._actions:
        yield "/".join(action.option_strings) or action.dest, action.help or ""


@pytest.mark.unit
@pytest.mark.cli
@pytest.mark.parametrize("make_parser", [create_parser, _create_read_parser], ids=["all2md", "read"])
def test_help_encodes_as_cp1252(make_parser):
    unencodable = []
    for where, text in _texts(make_parser()):
        try:
            text.encode("cp1252")
        except UnicodeEncodeError as e:
            unencodable.append(f"{where}: {text[e.start : e.end]!r}")
    assert not unencodable
