#!/usr/bin/env python3
"""Generate reStructuredText documentation for all2md options."""
from __future__ import annotations

import argparse
import inspect
import sys
from dataclasses import MISSING, Field, fields, is_dataclass
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Dict,
    Iterable,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

# Ensure project src directory is importable when run standalone
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from all2md.converter_registry import registry  # noqa: E402
from all2md.options.base import BaseParserOptions, BaseRendererOptions  # noqa: E402
from all2md.options.common import LocalFileAccessOptions, NetworkFetchOptions  # noqa: E402
from all2md.options.markdown import MarkdownOptions  # noqa: E402

# Type alias for clarity
DataclassType = Type[Any]


def snake_to_kebab(name: str) -> str:
    """Convert snake_case to kebab-case for CLI flag formatting."""
    return name.replace("_", "-")


def unwrap_optional(annotation: Any) -> Tuple[Any, bool]:
    """Return underlying type if annotation is Optional[...]."""
    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721
        if len(args) == 1:
            return args[0], True
    return annotation, False


def format_literal(values: Iterable[Any]) -> str:
    """Format Literal values for display."""
    formatted = []
    for value in values:
        if isinstance(value, str):
            formatted.append(repr(value))
        else:
            formatted.append(str(value))
    return ", ".join(formatted)


def format_type(annotation: Any) -> str:
    """Convert a typing annotation into a readable string."""
    if isinstance(annotation, str):
        return annotation

    origin = get_origin(annotation)
    if origin is None:
        if hasattr(annotation, "__name__"):
            return annotation.__name__  # type: ignore[attr-defined]
        if hasattr(annotation, "__qualname__"):
            return annotation.__qualname__  # type: ignore[attr-defined]
        return repr(annotation)

    args = get_args(annotation)

    if origin is Union:
        parts = []
        for arg in args:
            if arg is type(None):  # noqa: E721
                parts.append("None")
            else:
                parts.append(format_type(arg))
        # Preserve order but remove duplicates
        seen: set[str] = set()
        ordered = []
        for part in parts:
            if part not in seen:
                ordered.append(part)
                seen.add(part)
        return " | ".join(ordered)

    if origin is list:
        inner = format_type(args[0]) if args else "Any"
        return f"list[{inner}]"

    if origin is tuple:
        if args and args[-1] is Ellipsis:
            inner = format_type(args[0])
            return f"tuple[{inner}, ...]"
        inner = ", ".join(format_type(arg) for arg in args)
        return f"tuple[{inner}]"

    if origin is dict:
        key = format_type(args[0]) if args else "Any"
        value = format_type(args[1]) if len(args) > 1 else "Any"
        return f"dict[{key}, {value}]"

    if origin is set:
        inner = format_type(args[0]) if args else "Any"
        return f"set[{inner}]"

    if origin is frozenset:
        inner = format_type(args[0]) if args else "Any"
        return f"frozenset[{inner}]"

    if origin is Literal:
        return f"Literal[{format_literal(args)}]"

    if origin is Annotated:
        # Annotated[T, ...] -> just display T
        base = args[0] if args else Any
        return format_type(base)

    # Fallback for other typing constructs
    name = getattr(origin, "__name__", repr(origin))
    args_repr = ", ".join(format_type(arg) for arg in args)
    return f"{name}[{args_repr}]" if args_repr else name


def get_type_hints_safe(cls: DataclassType) -> Dict[str, Any]:
    """Safely resolve type hints for a dataclass, handling forward references."""
    module = sys.modules.get(cls.__module__)
    globalns = vars(module) if module else None
    try:
        return get_type_hints(cls, globalns=globalns, include_extras=True)
    except Exception:
        # Fall back to field.type if resolution fails
        return {field.name: field.type for field in fields(cls)}


def get_field_default(field: Field[Any]) -> Tuple[Optional[Any], Optional[str]]:
    """Return default value or factory information for a dataclass field."""
    if field.default is not MISSING:
        return field.default, None
    if field.default_factory is not MISSING:  # type: ignore[attr-defined]
        factory = field.default_factory  # type: ignore[attr-defined]
        if hasattr(factory, "__qualname__"):
            return None, factory.__qualname__  # type: ignore[assignment]
        return None, repr(factory)
    return None, None


def compute_cli_flag(
    field: Field[Any],
    metadata: Dict[str, Any],
    format_prefix: Optional[str],
    resolved_type: Any,
) -> Optional[str]:
    """Compute the CLI flag associated with a dataclass field."""
    if metadata.get("exclude_from_cli"):
        return None

    cli_name = metadata.get("cli_name")
    default_value, _ = get_field_default(field)
    underlying_type, _ = unwrap_optional(resolved_type)

    is_bool = underlying_type is bool
    bool_default_true = is_bool and isinstance(default_value, bool) and default_value is True

    if cli_name:
        if format_prefix:
            return f"--{format_prefix}-{cli_name}"
        return f"--{cli_name}"

    name_component = snake_to_kebab(field.name)

    if is_bool and bool_default_true:
        if format_prefix:
            return f"--{format_prefix}-no-{name_component}"
        return f"--no-{name_component}"

    if format_prefix:
        return f"--{format_prefix}-{name_component}"

    return f"--{name_component}"


def heading(text: str, level: int) -> str:
    """Return an RST heading string at the requested level."""
    underline_map = {1: "=", 2: "-", 3: "~", 4: "^", 5: "+", 6: "`"}
    char = underline_map.get(level, "-")
    return f"{text}\n{char * len(text)}\n"


SECTION_BREAK_HEADINGS = {
    "Parameters",
    "Returns",
    "Yields",
    "Attributes",
    "Raises",
    "Examples",
    "See Also",
    "Notes",
}


def format_docstring(cls: DataclassType) -> list[str]:
    """Return formatted docstring synopsis for a dataclass.

    Only the summary portion (up to the first section heading such as
    ``Parameters``) is returned to avoid duplicating the generated field tables
    and to prevent nested section under/overline issues in the output.
    """
    doc = inspect.getdoc(cls)
    if not doc:
        return []

    raw_lines = [line.rstrip() for line in doc.splitlines()]

    # Trim trailing blank lines first
    while raw_lines and not raw_lines[-1]:
        raw_lines.pop()

    cut_index = None
    for idx, line in enumerate(raw_lines):
        if line.strip() in SECTION_BREAK_HEADINGS:
            cut_index = idx
            break
        # Support Google-style "Parameters" headings with preceding blank line
        if idx + 1 < len(raw_lines) and raw_lines[idx + 1].startswith("-") and line.strip() in SECTION_BREAK_HEADINGS:
            cut_index = idx
            break

    if cut_index is not None:
        lines = raw_lines[:cut_index]
    else:
        lines = raw_lines

    # Remove trailing empties again post-slice
    while lines and not lines[-1]:
        lines.pop()

    return lines


class OptionsRenderer:
    """Render dataclass options into RST sections."""

    def __init__(self) -> None:
        """Initialize the options renderer with empty visited set."""
        self.visited: set[tuple[DataclassType, Optional[str]]] = set()

    def render_dataclass(
        self,
        cls: DataclassType,
        title: str,
        level: int,
        format_prefix: Optional[str],
        include_docstring: bool = True,
    ) -> list[str]:
        """Render a dataclass and its fields into RST lines."""
        key = (cls, format_prefix)
        if key in self.visited:
            return []
        self.visited.add(key)

        lines: list[str] = [heading(title, level)]

        if include_docstring:
            doc_lines = format_docstring(cls)
            if doc_lines:
                lines.extend(doc_lines)
                lines.append("")

        type_hints = get_type_hints_safe(cls)

        for field in fields(cls):
            metadata: Dict[str, Any] = dict(field.metadata) if field.metadata else {}

            if metadata.get("exclude_from_cli"):
                continue

            resolved_type = type_hints.get(field.name, field.type)
            underlying_type, _ = unwrap_optional(resolved_type)

            if metadata.get("cli_flatten") and is_dataclass(underlying_type):
                kebab = snake_to_kebab(field.name)
                nested_prefix = f"{format_prefix}-{kebab}" if format_prefix else kebab
                nested_title = f"{field.name.replace('_', ' ').title()} Options"
                lines.extend(
                    self.render_dataclass(
                        underlying_type,
                        nested_title,
                        level + 1,
                        nested_prefix,
                    )
                )
                continue

            if field.name == "markdown_options" and underlying_type is MarkdownOptions:
                lines.append(f"**{field.name}**")
                lines.append("")
                lines.append(
                    "   Embed additional Markdown formatting controls. "
                    "See the ``Markdown Options`` section below."
                )
                lines.append("")
                continue

            lines.extend(
                self.render_field(
                    field=field,
                    metadata=metadata,
                    resolved_type=resolved_type,
                    format_prefix=format_prefix,
                )
            )

        return lines

    def render_field(
        self,
        field: Field[Any],
        metadata: Dict[str, Any],
        resolved_type: Any,
        format_prefix: Optional[str],
    ) -> list[str]:
        """Render an individual field as a definition block."""
        lines: list[str] = [f"**{field.name}**", ""]

        description = metadata.get("help")
        if description:
            lines.append(f"   {description}")
            lines.append("")

        type_repr = format_type(resolved_type)
        lines.append(f"   :Type: ``{type_repr}``")

        cli_flag = compute_cli_flag(field, metadata, format_prefix, resolved_type)
        if cli_flag:
            lines.append(f"   :CLI flag: ``{cli_flag}``")

        default_value, factory_name = get_field_default(field)
        if default_value is not None:
            lines.append(f"   :Default: ``{default_value!r}``")
        elif factory_name:
            lines.append(f"   :Default factory: ``{factory_name}``")
        elif field.default is None:
            lines.append("   :Default: ``None``")

        choices = metadata.get("choices")
        if choices:
            formatted_choices = ", ".join(f"``{choice}``" for choice in choices)
            lines.append(f"   :Choices: {formatted_choices}")

        action = metadata.get("action")
        if action:
            lines.append(f"   :CLI action: ``{action}``")

        importance = metadata.get("importance")
        if importance:
            lines.append(f"   :Importance: {importance}")

        lines.append("")
        return lines


def discover_format_options() -> list[tuple[str, DataclassType | None, DataclassType | None]]:
    """Discover parser and renderer options classes for every registered format."""
    registry.auto_discover()

    format_entries: list[tuple[str, DataclassType | None, DataclassType | None]] = []

    for format_name in sorted(registry.list_formats()):
        parser_cls: DataclassType | None = None
        renderer_cls: DataclassType | None = None

        try:
            parser_cls = registry.get_parser_options_class(format_name)
        except Exception:
            parser_cls = None

        try:
            renderer_cls = registry.get_renderer_options_class(format_name)
        except Exception:
            renderer_cls = None

        format_entries.append((format_name, parser_cls, renderer_cls))

    return format_entries


def generate_reference_section() -> list[str]:
    """Generate the auto-discovered options reference section."""
    renderer = OptionsRenderer()
    lines: list[str] = [
        heading("Generated Reference", 2),
        "This section is generated automatically from the options dataclasses.",
        "",
    ]

    format_entries = discover_format_options()

    for format_name, parser_cls, renderer_cls in format_entries:
        if not parser_cls and not renderer_cls:
            continue

        section_title = f"{format_name.upper()} Options"
        lines.append(heading(section_title, 3))
        lines.append("")

        if parser_cls:
            parser_title = f"{format_name.upper()} Parser Options"
            lines.extend(
                renderer.render_dataclass(
                    parser_cls,
                    parser_title,
                    level=4,
                    format_prefix=format_name,
                )
            )

        if renderer_cls:
            renderer_title = f"{format_name.upper()} Renderer Options"
            renderer_prefix = f"{format_name}-renderer"
            lines.extend(
                renderer.render_dataclass(
                    renderer_cls,
                    renderer_title,
                    level=4,
                    format_prefix=renderer_prefix,
                )
            )

    shared_sections = [
        ("Base Parser Options", BaseParserOptions, None),
        ("Base Renderer Options", BaseRendererOptions, "renderer"),
        ("Markdown Options", MarkdownOptions, "markdown"),
        ("Network Fetch Options", NetworkFetchOptions, "network"),
        ("Local File Access Options", LocalFileAccessOptions, "local"),
    ]

    lines.append(heading("Shared Options", 3))
    lines.append("")

    for title, cls, prefix in shared_sections:
        lines.extend(renderer.render_dataclass(cls, title, level=4, format_prefix=prefix, include_docstring=True))

    return lines


def build_document(narrative_path: Path, reference_lines: Iterable[str]) -> str:
    """Combine narrative preamble with generated reference."""
    narrative = narrative_path.read_text(encoding="utf-8")
    parts = [narrative.rstrip(), "", *reference_lines]
    return "\n".join(parts).rstrip() + "\n"


def generate_options_document(output_path: Path, narrative_path: Optional[Path] = None) -> str:
    """Generate options documentation and write to disk."""
    if narrative_path is None:
        narrative_path = output_path.with_name("options-narrative.rst")

    reference_lines = generate_reference_section()
    document = build_document(narrative_path, reference_lines)
    if output_path.exists():
        current = output_path.read_text(encoding="utf-8")
        if current == document:
            return document

    output_path.write_text(document, encoding="utf-8")
    return document


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate options.rst documentation.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "options.rst",
        help="Output .rst path (defaults to docs/source/options.rst)",
    )
    parser.add_argument(
        "-n",
        "--narrative",
        type=Path,
        default=Path(__file__).resolve().parent / "_options-narrative.rst",
        help="Narrative preface file",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    """Generate options documentation and print status.

    Parameters
    ----------
    argv : Optional[list[str]], optional
        Command line arguments, defaults to sys.argv if None.

    """
    args = parse_args(argv)
    document = generate_options_document(args.output, args.narrative)
    print(f"Generated documentation with {len(document.splitlines())} lines -> {args.output}")


if __name__ == "__main__":
    main()
