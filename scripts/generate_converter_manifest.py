#!/usr/bin/env python3
"""Generate the converter manifest from the live parser/renderer modules.

The manifest (``src/all2md/_converter_manifest.py``) is a leaf module of pure
literals that lets ``ConverterRegistry.auto_discover()`` register all built-in
converter metadata WITHOUT importing every parser/renderer module at startup —
the big CLI/import startup cost. The parser/renderer/options classes and content
detectors are imported lazily on first use instead.

This script scans the live modules (the slow path) and serializes their
``CONVERTER_METADATA`` to source, normalizing every class spec to a
fully-qualified dotted string and converting each ``content_detector`` callable
to a ``content_detector_path`` string.

Usage:
    python scripts/generate_converter_manifest.py --validate  # Check if in sync
    python scripts/generate_converter_manifest.py --update    # Regenerate the file
    python scripts/generate_converter_manifest.py --dry-run   # Print without writing
    python scripts/generate_converter_manifest.py --stage     # --update + git add
"""

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = PROJECT_ROOT / "src" / "all2md" / "_converter_manifest.py"

# Ensure we import the in-tree package.
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _scan_records() -> list:
    """Scan the live parser/renderer modules and return built-in metadata records.

    Uses a fresh ConverterRegistry (bypassing the singleton) so the result is
    exactly the built-in converters discovered by importing each module — no
    plugins, no pre-registered manifest state.
    """
    from all2md.converter_registry import ConverterRegistry

    reg = object.__new__(ConverterRegistry)
    reg._converters = {}
    reg._initialized = False
    reg.discover_by_scanning()

    records = []
    for metadata_list in reg._converters.values():
        records.extend(metadata_list)
    return records


def _normalize_content_detector(metadata) -> str | None:
    """Return a fully-qualified dotted path for the content detector, or None.

    Raises if the detector is not an importable module-level function (e.g. a
    lambda or functools.partial) so the problem surfaces at generation time
    rather than silently dropping detection behavior.
    """
    detector = metadata.content_detector
    if detector is None:
        return metadata.content_detector_path
    if not isinstance(detector, types.FunctionType) or "<lambda>" in detector.__qualname__:
        raise ValueError(
            f"content_detector for format '{metadata.format_name}' is not a module-level "
            f"function ({detector!r}); the manifest can only serialize importable functions. "
            f"Define it as a named function in the parser module."
        )
    if "." in detector.__qualname__:
        raise ValueError(
            f"content_detector for format '{metadata.format_name}' is nested ({detector.__qualname__}); "
            f"move it to module level so it has an importable path."
        )
    return f"{detector.__module__}.{detector.__qualname__}"


def _assert_resolvable(dotted: str | None, what: str, fmt: str) -> None:
    """Import-and-getattr a dotted path to fail fast on a bad normalization."""
    if dotted is None:
        return
    module_path, name = dotted.rsplit(".", 1)
    try:
        # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
        module = importlib.import_module(module_path)
        getattr(module, name)
    except (ImportError, AttributeError) as exc:
        # Missing optional dependency is fine (the class is dep-gated); only a
        # genuinely wrong path (AttributeError on an imported module / bad module
        # that isn't an optional dep) should fail generation.
        if isinstance(exc, AttributeError):
            raise ValueError(f"{what} path for format '{fmt}' does not resolve: {dotted}") from exc
        # ImportError: likely an uninstalled optional dependency — accept the path.


def _record_to_kwargs(metadata) -> dict:
    """Convert a live ConverterMetadata to manifest constructor kwargs (literals)."""
    from all2md.converter_metadata import ConverterMetadata

    fmt = metadata.format_name
    parser_class = ConverterMetadata.normalize_class_spec(metadata.parser_class, f"all2md.parsers.{fmt}")
    renderer_class = ConverterMetadata.normalize_class_spec(metadata.renderer_class, f"all2md.renderers.{fmt}")
    parser_options_class = ConverterMetadata.normalize_class_spec(metadata.parser_options_class, "all2md.options")
    renderer_options_class = ConverterMetadata.normalize_class_spec(metadata.renderer_options_class, "all2md.options")
    content_detector_path = _normalize_content_detector(metadata)

    for dotted, what in (
        (parser_class, "parser_class"),
        (renderer_class, "renderer_class"),
        (parser_options_class, "parser_options_class"),
        (renderer_options_class, "renderer_options_class"),
        (content_detector_path, "content_detector"),
    ):
        _assert_resolvable(dotted, what, fmt)

    return {
        "format_name": fmt,
        "extensions": list(metadata.extensions),
        "mime_types": list(metadata.mime_types),
        "magic_bytes": list(metadata.magic_bytes),
        "content_detector_path": content_detector_path,
        "parser_class": parser_class,
        "renderer_class": renderer_class,
        "parser_required_packages": list(metadata.parser_required_packages),
        "renderer_required_packages": list(metadata.renderer_required_packages),
        "renders_as_string": metadata.renders_as_string,
        "optional_packages": list(metadata.optional_packages),
        "import_error_message": metadata.import_error_message,
        "parser_options_class": parser_options_class,
        "renderer_options_class": renderer_options_class,
        "description": metadata.description,
        "priority": metadata.priority,
    }


# Field emission order (skips defaults that are empty to keep records compact).
_FIELD_ORDER = [
    "format_name",
    "extensions",
    "mime_types",
    "magic_bytes",
    "content_detector_path",
    "parser_class",
    "renderer_class",
    "parser_required_packages",
    "renderer_required_packages",
    "renders_as_string",
    "optional_packages",
    "import_error_message",
    "parser_options_class",
    "renderer_options_class",
    "description",
    "priority",
]

# Defaults that, when matched, let us omit the field for a compact record.
_OMIT_IF = {
    "extensions": [],
    "mime_types": [],
    "magic_bytes": [],
    "content_detector_path": None,
    "parser_class": None,
    "renderer_class": None,
    "parser_required_packages": [],
    "renderer_required_packages": [],
    "renders_as_string": False,
    "optional_packages": [],
    "import_error_message": "",
    "parser_options_class": None,
    "renderer_options_class": None,
    "description": "",
    "priority": 0,
}


def _render_record(kwargs: dict) -> str:
    """Render a single ConverterMetadata(...) call as source."""
    lines = ["    ConverterMetadata("]
    for key in _FIELD_ORDER:
        value = kwargs[key]
        if key in _OMIT_IF and value == _OMIT_IF[key]:
            continue
        lines.append(f"        {key}={value!r},")
    lines.append("    ),")
    return "\n".join(lines)


def _format_with_black(source: str) -> str:
    """Run the generated source through black so it matches the committed file.

    The pre-commit black hook formats this generated module too, so the
    generator must emit black-formatted output or ``--validate`` would always
    report drift. black is a pinned dev dependency, so it is available wherever
    the generator/validator runs (locally and in CI).
    """
    import black

    return black.format_str(source, mode=black.Mode(line_length=120))


def generate_source() -> str:
    """Build the full source of the generated manifest module."""
    records = _scan_records()
    # Deterministic order for stable diffs.
    records.sort(key=lambda m: (m.format_name, -m.priority))
    kwargs_list = [_record_to_kwargs(m) for m in records]

    body = "\n".join(_render_record(k) for k in kwargs_list)
    header = '''"""Generated converter manifest — DO NOT EDIT BY HAND.

This module lists the built-in converter metadata as pure literals so the
registry can populate format-detection metadata without importing every parser
and renderer module at startup. Parser/renderer/options classes and content
detectors are imported lazily on first use.

Regenerate with:
    python scripts/generate_converter_manifest.py --update
"""
# ruff: noqa: E501  (generated file: long literal extension/mime/message lines)

from __future__ import annotations

from all2md.converter_metadata import ConverterMetadata

_MANIFEST_RECORDS: list[ConverterMetadata] = [
'''
    footer = '''
]


def get_manifest_records() -> list[ConverterMetadata]:
    """Return the built-in converter metadata records (fresh list).

    A new list of the shared record instances is returned so callers may sort
    or filter without mutating the module-level list.
    """
    return list(_MANIFEST_RECORDS)
'''
    return _format_with_black(header + body + footer)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate the converter manifest from live modules")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true", help="Exit 1 if the committed manifest is stale")
    group.add_argument("--update", action="store_true", help="Regenerate the manifest file")
    group.add_argument("--dry-run", action="store_true", help="Print generated source without writing")
    group.add_argument("--stage", action="store_true", help="--update and git add the file")

    args = parser.parse_args()

    print("Scanning converter modules...")
    new_source = generate_source()

    if args.dry_run:
        print(new_source)
        return 0

    existing = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else None

    if args.validate:
        if existing == new_source:
            print("SUCCESS: converter manifest is in sync with the live modules")
            return 0
        print("ERROR: converter manifest is out of sync with the live modules!")
        print("Run: python scripts/generate_converter_manifest.py --update")
        return 1

    # --update / --stage
    if existing == new_source:
        print("No changes needed - manifest is already up to date")
        return 0
    MANIFEST_PATH.write_text(new_source, encoding="utf-8")
    print(f"SUCCESS: wrote {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
    if args.stage:
        subprocess.run(["git", "add", str(MANIFEST_PATH)], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
