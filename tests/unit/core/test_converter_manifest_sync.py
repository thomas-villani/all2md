"""Guard that the generated converter manifest matches the live modules.

``src/all2md/_converter_manifest.py`` is generated from each parser/renderer
module's ``CONVERTER_METADATA`` by ``scripts/generate_converter_manifest.py``.
It lets the registry register format metadata without importing every module at
startup (the CLI/import startup optimization). If a contributor adds or edits a
converter without regenerating the manifest, detection/registration silently
drifts — these tests fail loudly in that case.

The check is tolerant of optional dependencies: a module that can't be imported
in this environment is simply absent from the scan, so we assert the scan is a
field-exact subset of the manifest (scan ⊆ manifest) rather than strict
equality. The generator's ``--validate`` (run in a full-deps CI) is the strict,
byte-for-byte gate.
"""

import pytest

from all2md.converter_metadata import ConverterMetadata
from all2md.converter_registry import ConverterRegistry

# Default modules used to normalize class specs, mirroring _load_class.
_OPTIONS_MODULE = "all2md.options"


def _scan_records() -> list[ConverterMetadata]:
    """Scan the live parser/renderer modules on a fresh (non-singleton) registry."""
    reg = object.__new__(ConverterRegistry)
    reg._converters = {}
    reg._initialized = False
    reg.discover_by_scanning()
    return [m for metadata_list in reg._converters.values() for m in metadata_list]


def _normalized_view(metadata: ConverterMetadata, *, from_scan: bool) -> dict:
    """Return a comparable dict with class specs normalized to dotted strings.

    For scanned records the content detector is a live callable (converted to its
    dotted path); for manifest records it is already a ``content_detector_path``.
    """
    fmt = metadata.format_name
    if from_scan and metadata.content_detector is not None:
        detector = metadata.content_detector
        content_detector_path = f"{detector.__module__}.{detector.__qualname__}"
    else:
        content_detector_path = metadata.content_detector_path

    return {
        "format_name": fmt,
        "extensions": list(metadata.extensions),
        "mime_types": list(metadata.mime_types),
        "magic_bytes": list(metadata.magic_bytes),
        "content_detector_path": content_detector_path,
        "parser_class": ConverterMetadata.normalize_class_spec(metadata.parser_class, f"all2md.parsers.{fmt}"),
        "renderer_class": ConverterMetadata.normalize_class_spec(metadata.renderer_class, f"all2md.renderers.{fmt}"),
        "parser_options_class": ConverterMetadata.normalize_class_spec(metadata.parser_options_class, _OPTIONS_MODULE),
        "renderer_options_class": ConverterMetadata.normalize_class_spec(
            metadata.renderer_options_class, _OPTIONS_MODULE
        ),
        "parser_required_packages": list(metadata.parser_required_packages),
        "renderer_required_packages": list(metadata.renderer_required_packages),
        "renders_as_string": metadata.renders_as_string,
        "optional_packages": list(metadata.optional_packages),
        "import_error_message": metadata.import_error_message,
        "description": metadata.description,
        "priority": metadata.priority,
    }


@pytest.mark.unit
def test_manifest_matches_scanned_modules():
    """Every converter discoverable by scanning must appear, field-exact, in the manifest.

    Uses multiset containment (match-and-remove) rather than keying, because a
    few formats register two near-identical records (a parser module plus a
    standalone renderer module) that differ only in a single field.
    """
    from all2md._converter_manifest import get_manifest_records

    remaining = [_normalized_view(m, from_scan=False) for m in get_manifest_records()]

    problems: list[str] = []
    for scanned in _scan_records():
        view = _normalized_view(scanned, from_scan=True)
        if view in remaining:
            remaining.remove(view)
            continue
        # Not an exact match — report the closest same-format manifest record(s).
        candidates = [m for m in remaining if m["format_name"] == view["format_name"]]
        if not candidates:
            problems.append(f"{view['format_name']} (priority={view['priority']}): absent from manifest")
        else:
            diffs = [
                {field: (view[field], cand[field]) for field in view if view[field] != cand[field]}
                for cand in candidates
            ]
            problems.append(f"{view['format_name']}: no manifest record matches; nearest diffs={diffs}")

    assert not problems, (
        "Converter manifest is out of sync with the live modules. "
        "Regenerate with: python scripts/generate_converter_manifest.py --update\n" + "\n".join(problems)
    )


@pytest.mark.unit
def test_manifest_non_empty_and_has_core_formats():
    """The manifest must contain the always-available core formats."""
    from all2md._converter_manifest import get_manifest_records

    records = get_manifest_records()
    assert records, "manifest is empty"
    formats = {m.format_name for m in records}
    for core in ("markdown", "html", "plaintext", "json"):
        assert core in formats, f"core format '{core}' missing from manifest"


@pytest.mark.unit
def test_manifest_records_are_independent_lists():
    """get_manifest_records() must return a fresh list so callers can sort/filter safely."""
    from all2md._converter_manifest import get_manifest_records

    assert get_manifest_records() is not get_manifest_records()
