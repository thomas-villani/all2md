#  Copyright (c) 2025 Tom Villani, Ph.D.
"""The ``all2md.options`` package re-exports lazily; these tests keep it honest.

``options/__init__.py`` used to import every submodule eagerly, so ``__all__``
could not drift out of sync with reality - a name was either imported at the top
or it did not exist. Replacing those imports with a ``_LAZY_EXPORTS`` table buys
startup time and gives that guarantee away: a name can now sit in ``__all__``
pointing at nothing, and nobody finds out until a user imports it.

These tests buy the guarantee back. They are the reason the lazy table is safe to
hand-maintain.
"""

from __future__ import annotations

import importlib

import pytest

from all2md import options
from all2md.options import _LAZY_EXPORTS

pytestmark = pytest.mark.unit


# Names ``options/__init__.py`` defines itself rather than re-exporting.
_DEFINED_LOCALLY = frozenset({"create_updated_options"})


@pytest.mark.parametrize("name", sorted(_LAZY_EXPORTS))
def test_every_lazy_export_resolves_to_the_real_object(name: str) -> None:
    # A wrong submodule in the table is invisible until someone imports the name,
    # so resolve every one and check it is the same object a direct import gives.
    module = importlib.import_module(f"all2md.options.{_LAZY_EXPORTS[name]}")
    assert getattr(options, name) is getattr(module, name)


def test_all_and_the_lazy_table_agree() -> None:
    # Either direction is a bug: a name in __all__ with no table entry raises
    # AttributeError on import, and a table entry missing from __all__ is a class
    # that `from all2md.options import *` silently will not deliver.
    declared = set(options.__all__)
    provided = set(_LAZY_EXPORTS) | _DEFINED_LOCALLY

    assert declared - provided == set(), "in __all__ but not resolvable"
    assert provided - declared == set(), "resolvable but missing from __all__"


def test_the_package_init_pulls_in_no_submodules_of_its_own() -> None:
    # The point of the exercise. Measured as a *delta*, because `import
    # all2md.options` necessarily imports `all2md` first, and the parent legitimately
    # reaches for a few submodules on its own - attributing those here would make
    # this test fail for someone else's reason. Guards the mechanism only;
    # test_eager_imports.py owns the absolute count.
    import subprocess
    import sys

    probe = (
        "import sys\n"
        "import all2md\n"
        "before = {m for m in sys.modules if m.startswith('all2md.options.')}\n"
        "import all2md.options\n"
        "after = {m for m in sys.modules if m.startswith('all2md.options.')}\n"
        "print(len(after - before))\n"
    )
    added = int(subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True).stdout)
    assert added == 0, f"all2md/options/__init__.py imported {added} submodules; the lazy table is being bypassed"


def test_an_unknown_attribute_still_raises_attribute_error() -> None:
    # __getattr__ must not swallow typos into ImportError or None.
    with pytest.raises(AttributeError, match="no attribute 'NotAnOptionsClass'"):
        options.NotAnOptionsClass  # noqa: B018


def test_dir_includes_the_lazy_names() -> None:
    # Without __dir__, tab-completion and introspection would show only whatever
    # happened to have been resolved already - which varies by import order.
    assert set(_LAZY_EXPORTS) <= set(dir(options))
