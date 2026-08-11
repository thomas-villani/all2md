#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Every registered format's options class must be exported from both surfaces.

Issue #184: the two export surfaces - ``all2md.options.__all__`` and
``all2md.__all__`` - had drifted apart and away from the converter registry. Some
formats were exported from both, some from one, some from neither, and the split
did not track anything: ``ArxivPackagerOptions`` was importable from ``all2md``
but not from ``all2md.options``, which is backwards from every sibling.

Nobody noticed because adding a format means touching a parser, a manifest entry
and two hand-maintained tables, and only the first two break anything if you
forget. These tests make the last two break too. The rule they encode:

    every options class a registered converter uses is public from both places;
    base classes, mixins, shared option groups, the sentinel and the clone helper
    are the listed exceptions.

The registry is the ground truth rather than a second hand-written list, so
adding a format cannot silently add an exception.
"""

from __future__ import annotations

import pytest

import all2md
from all2md import options
from all2md._converter_manifest import _MANIFEST_RECORDS

pytestmark = pytest.mark.unit


def _registered_options_classes() -> set[str]:
    """Names of the options classes referenced by built-in converter metadata."""
    names: set[str] = set()
    for record in _MANIFEST_RECORDS:
        for ref in (record.parser_options_class, record.renderer_options_class):
            if isinstance(ref, str):
                names.add(ref.rsplit(".", 1)[1])
    return names


# Exported from ``all2md.options`` but not tied to any one format.
_NOT_FORMAT_OPTIONS = frozenset(
    {
        "BaseParserOptions",
        "BaseRendererOptions",
        "LocalFileAccessOptions",
        "NetworkFetchOptions",
        "UNSET",
        "create_updated_options",
    }
)


def test_the_registry_actually_names_options_classes() -> None:
    """Guard the guard: an empty ground truth would make every check below vacuous."""
    registered = _registered_options_classes()
    assert len(registered) > 50, f"only {len(registered)} options classes in the manifest; is it stale?"


@pytest.mark.parametrize("name", sorted(_registered_options_classes()))
def test_registered_options_class_is_exported_from_the_options_package(name: str) -> None:
    assert name in options.__all__, (
        f"{name} is used by a registered converter but is not in all2md.options.__all__; "
        "add it to __all__ and _LAZY_EXPORTS"
    )


@pytest.mark.parametrize("name", sorted(_registered_options_classes()))
def test_registered_options_class_is_exported_from_the_top_level(name: str) -> None:
    assert (
        name in all2md.__all__
    ), f"{name} is used by a registered converter but is not in all2md.__all__; add it to __all__ and _lazy_options"


def test_the_two_surfaces_carry_the_same_format_options() -> None:
    """Neither surface may be a strict subset of the other - that is how #184 started."""
    from_options = set(options.__all__) - _NOT_FORMAT_OPTIONS
    from_top_level = {name for name in all2md.__all__ if name.endswith("Options")} - _NOT_FORMAT_OPTIONS
    # RemoteInputOptions is an input-source concern, not a converter's.
    from_top_level.discard("RemoteInputOptions")

    assert from_options == from_top_level


def test_no_unexplained_extras_in_the_options_surface() -> None:
    """A new non-format export has to be named here, not slipped in."""
    extras = set(options.__all__) - _registered_options_classes()
    assert extras == _NOT_FORMAT_OPTIONS
