#  Copyright (c) 2025 Tom Villani, Ph.D.
"""A nested options type must be as public as the options class that declares it.

``test_options_export_surface.py`` derives its expectation from the converter
manifest, which names only *format* options classes. That structurally cannot see
a class which is not any converter's options but is the declared type of a field
on one - so two of them were unreachable from either public surface:

* ``OCROptions``, the type of ``PdfOptions.ocr``. Configuring OCR from the Python
  API meant importing from ``all2md.options.common``, and passing a plain dict
  instead failed deep inside parsing with ``'dict' object has no attribute
  'enabled'`` rather than at the call.
* ``MetadataRenderPolicy``, the type of ``BaseRendererOptions.metadata_policy`` -
  so it reaches *every* renderer's options class.

The rule below is derived, not listed: walk the resolved type hints of every
publicly exported options class, and require any dataclass found in one to be
exported too. Adding a nested options group cannot quietly skip the export.

The annotations must be *resolved* to check this at all. This package uses
``from __future__ import annotations``, so 91% of these fields carry their type as
a plain string, and a probe that reads ``dataclasses.Field.type`` directly sees
almost nothing and reports success. ``test_the_probe_resolves_string_annotations``
exists to keep that failure from coming back silently.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest

import all2md
from all2md import options

pytestmark = pytest.mark.unit


def _public_option_classes() -> dict[str, type]:
    """Every dataclass reachable from ``all2md.options.__all__``."""
    found: dict[str, type] = {}
    for name in options.__all__:
        value = getattr(options, name, None)
        if inspect.isclass(value) and dataclasses.is_dataclass(value):
            found[name] = value
    return found


def _nested_dataclasses(cls: type) -> set[type]:
    """Dataclasses appearing in ``cls``'s resolved field annotations."""
    hints = typing.get_type_hints(cls)
    nested: set[type] = set()
    for field in dataclasses.fields(cls):
        annotation = hints.get(field.name)
        # Unwrap Optional[X] / X | None / list[X] one level, which is as deep as
        # any options field currently nests.
        candidates = (annotation, *(getattr(annotation, "__args__", ()) or ()))
        for candidate in candidates:
            if inspect.isclass(candidate) and dataclasses.is_dataclass(candidate):
                nested.add(candidate)
    return nested


def _all_nested() -> dict[type, list[str]]:
    """Nested dataclass -> the ``Class.field`` paths that declare it."""
    declared: dict[type, list[str]] = {}
    for name, cls in _public_option_classes().items():
        for nested in _nested_dataclasses(cls):
            declared.setdefault(nested, []).append(f"{name}.{cls.__name__}")
    return declared


_EXPORTED_CLASSES = {getattr(options, n) for n in options.__all__ if inspect.isclass(getattr(options, n, None))}
_NESTED = _all_nested()
_NESTED_NAMES = sorted({cls.__name__ for cls in _NESTED})


def test_the_probe_resolves_string_annotations() -> None:
    """Guard the guard: unresolved annotations make every check below vacuous.

    Reading ``Field.type`` without resolving finds 89 of 982 fields. If this ever
    drops toward zero the suite would pass while checking almost nothing.
    """
    raw_strings = 0
    resolved = 0
    for cls in _public_option_classes().values():
        hints = typing.get_type_hints(cls)
        for field in dataclasses.fields(cls):
            if isinstance(field.type, str):
                raw_strings += 1
                if not isinstance(hints.get(field.name), str):
                    resolved += 1

    assert raw_strings > 500, f"expected most fields to be string annotations, got {raw_strings}"
    assert resolved == raw_strings, f"{raw_strings - resolved} annotations did not resolve"


def test_the_probe_finds_nested_dataclasses_at_all() -> None:
    """Guard the guard: if the walk found nothing, the parametrised test is empty."""
    assert len(_NESTED) >= 2, f"expected the walk to find nested options types, found {_NESTED_NAMES}"


@pytest.mark.parametrize("name", _NESTED_NAMES)
def test_nested_options_type_is_exported_from_both_surfaces(name: str) -> None:
    """A type a caller must construct has to be importable from the public API."""
    assert name in options.__all__, f"{name} is a field type on a public options class but missing from all2md.options"
    assert name in all2md.__all__, f"{name} is a field type on a public options class but missing from all2md"
    assert getattr(options, name) is getattr(all2md, name), f"{name} resolves to different objects on the two surfaces"


@pytest.mark.parametrize("name", ["OCROptions", "MetadataRenderPolicy"])
def test_the_two_classes_that_were_missing_import_and_construct(name: str) -> None:
    """The specific regression, pinned by name so a refactor cannot lose it quietly."""
    cls = getattr(all2md, name)
    assert cls is getattr(options, name)
    assert dataclasses.is_dataclass(cls)
    cls()  # constructible with no arguments, as every options class is


def test_ocr_options_configures_a_pdf_parse() -> None:
    """The end the export exists for: reach OCR settings without a private import."""
    from all2md import OCROptions, PdfOptions

    parsed = PdfOptions(ocr=OCROptions(enabled=True, mode="force", dpi=150))
    assert parsed.ocr.enabled is True
    assert parsed.ocr.dpi == 150


def test_metadata_policy_configures_a_renderer() -> None:
    """``metadata_policy`` is on BaseRendererOptions, so this covers every renderer."""
    from all2md import MarkdownRendererOptions, MetadataRenderPolicy

    rendered = MarkdownRendererOptions(metadata_policy=MetadataRenderPolicy(visibility="core"))
    assert rendered.metadata_policy.visibility == "core"
