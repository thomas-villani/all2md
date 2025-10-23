"""Enhanced help formatter for the all2md CLI.

This module builds a structured catalog of CLI options using the existing
DynamicCLIBuilder configuration and renders tiered help output
(quick/full/section specific) with importance filtering. Rich output is
supported when the ``rich`` package is available and requested.
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable, Literal, Optional, Sequence

if TYPE_CHECKING:
    from rich.text import Text

from all2md.cli.builder import DynamicCLIBuilder, create_parser
from all2md.cli.custom_actions import TrackingStoreFalseAction, TrackingStoreTrueAction
from all2md.options.base import UNSET

OptionImportance = Literal["core", "advanced", "security"]


def _ensure_text(text: Optional[str]) -> str:
    """Return ``text`` or an empty string when ``None``.

    ``argparse`` frequently stores help/description values as ``None``. Using
    an empty string simplifies formatting logic in renderers.
    """
    return text or ""


def _expand_help_text(action: argparse.Action) -> str:
    """Expand help text for an action, handling percent-formatting like argparse does.

    Parameters
    ----------
    action : argparse.Action
        The action whose help text to expand

    Returns
    -------
    str
        Expanded help text with percent-formatting applied

    """
    help_text = action.help
    if not help_text:
        return ""

    # Build params dict like argparse does in HelpFormatter._expand_help
    params = dict(vars(action))
    # Remove SUPPRESS values
    for name in list(params):
        if params[name] is argparse.SUPPRESS:
            del params[name]
    # Convert callable names to strings
    for name in list(params):
        if hasattr(params[name], '__name__'):
            params[name] = params[name].__name__
    # Format choices as comma-separated string
    if params.get('choices') is not None:
        params['choices'] = ', '.join(map(str, params['choices']))

    # Apply percent-formatting
    try:
        return help_text % params
    except (KeyError, ValueError, TypeError):
        # If formatting fails, return the raw help text
        return help_text


@dataclass(slots=True)
class OptionEntry:
    """Resolved CLI option metadata for rendering."""

    option_strings: tuple[str, ...]
    dest: str
    help_text: str
    default: Any
    metavar: Optional[str]
    choices: Optional[Sequence[Any]]
    importance: OptionImportance
    is_flag: bool
    group_title: str

    @property
    def is_nested(self) -> bool:
        """Return True if the destination represents a nested option."""
        return "." in self.dest


@dataclass(slots=True)
class HelpSection:
    """Logical grouping of CLI options for help rendering."""

    key: str
    title: str
    description: str
    options: list[OptionEntry]
    category: str
    format_name: Optional[str]

    def iter_core_options(self) -> Iterable[OptionEntry]:
        """Yield options marked as ``core`` importance."""
        return (opt for opt in self.options if opt.importance == "core")


@dataclass(slots=True)
class HelpCatalog:
    """Structured representation of CLI options and related metadata."""

    usage: str
    description: str
    epilog: str
    sections: list[HelpSection]
    section_lookup: Dict[str, HelpSection]
    format_sections: Dict[str, list[HelpSection]]
    subcommands: Sequence[tuple[str, str]]

    def get_section(self, selector: str) -> Optional[HelpSection]:
        """Return the section that matches *selector* (case-insensitive)."""
        key = selector.lower()
        if key in self.section_lookup:
            return self.section_lookup[key]

        # Allow matching on raw titles (e.g. "PDF options")
        for section in self.sections:
            if section.title.lower() == key:
                return section
        return None

    def get_sections_for_format(self, selector: str) -> list[HelpSection]:
        """Return parser/renderer sections for a format selector."""
        return self.format_sections.get(selector.lower(), [])


_SUBCOMMAND_SUMMARIES: Sequence[tuple[str, str]] = (
    ("help", "Show tiered CLI help (all2md help [section])"),
    ("config", "Configuration utilities (generate/show/validate)"),
    ("list-formats", "List available input formats"),
    ("list-transforms", "List registered AST transforms"),
    ("check-deps", "Check optional dependencies for converters"),
)


def _determine_section_key(title: str) -> str:
    """Normalize a group title to a lookup key."""
    normalized = title.strip().lower()
    if normalized.endswith(" options"):
        normalized = normalized[: -len(" options")]
    return normalized.replace(" ", "-")


def _classify_section_title(title: str) -> str:
    """Return category for a section title (parser, renderer, or global)."""
    lowered = title.lower()

    if "renderer" in lowered:
        return "renderer"

    if "markdown" in lowered and "option" in lowered:
        return "renderer"

    first_token = title.split()[0]
    if first_token.isupper():
        return "parser"

    return "global"


def _lookup_importance(builder: DynamicCLIBuilder, dest: str) -> OptionImportance:
    resolved = builder.resolve_option_field(dest)
    if not resolved:
        return "core"
    _field, metadata = resolved
    return metadata.get("importance", "core")


def _format_default(value: Any) -> Optional[str]:
    """Return human-readable default representation or ``None`` when omitted."""
    if value is argparse.SUPPRESS:
        return None
    if value is None:
        return None
    if value is UNSET:
        return "unset"
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, (list, tuple, set)):
        return repr(value)
    if callable(value):
        return getattr(value, "__name__", str(value))
    return repr(value) if isinstance(value, (dict,)) else str(value)


def build_catalog(parser: argparse.ArgumentParser, builder: DynamicCLIBuilder) -> HelpCatalog:
    """Create a help catalog from the configured parser."""
    sections: list[HelpSection] = []
    section_lookup: Dict[str, HelpSection] = {}
    format_sections: Dict[str, list[HelpSection]] = {}

    for group in parser._action_groups:  # pragma: no cover - interacts with argparse internals
        title = group.title or "Options"
        key = _determine_section_key(title)
        description = _ensure_text(group.description)
        category = _classify_section_title(title)

        options: list[OptionEntry] = []
        for action in group._group_actions:
            # Skip positional-only or help actions
            if not getattr(action, "option_strings", ()):  # pragma: no cover - positionals (none currently)
                continue
            if isinstance(action, argparse._HelpAction):
                continue

            option_strings = tuple(action.option_strings)
            if not option_strings:
                continue

            dest = getattr(action, "dest", option_strings[0].lstrip("-"))
            importance = _lookup_importance(builder, dest)

            nargs = getattr(action, "nargs", None)
            is_flag_action = isinstance(
                action,
                (
                    TrackingStoreTrueAction,
                    TrackingStoreFalseAction,
                    argparse._StoreTrueAction,
                    argparse._StoreFalseAction,
                ),
            )

            entry = OptionEntry(
                option_strings=option_strings,
                dest=dest,
                help_text=_expand_help_text(action),
                default=getattr(action, "default", None),
                metavar=getattr(action, "metavar", None),
                choices=getattr(action, "choices", None),
                importance=importance,
                is_flag=nargs == 0 or is_flag_action,
                group_title=title,
            )
            options.append(entry)

        if not options:
            continue

        format_name: Optional[str] = None
        if category in {"parser", "renderer"}:
            first_token = title.split()[0].lower()
            format_name = first_token

        section = HelpSection(
            key=key,
            title=title,
            description=description,
            options=options,
            category=category,
            format_name=format_name,
        )
        sections.append(section)
        section_lookup[key] = section

        if format_name:
            format_sections.setdefault(format_name, []).append(section)

    usage = parser.format_usage().strip()
    description = parser.description or ""
    epilog = parser.epilog or ""
    return HelpCatalog(
        usage=usage,
        description=description,
        epilog=epilog,
        sections=sections,
        section_lookup=section_lookup,
        format_sections=format_sections,
        subcommands=_SUBCOMMAND_SUMMARIES,
    )


class HelpRenderer:
    """Render help output from a catalog using quick/full/section filters."""

    WRAP_WIDTH = 100
    CATEGORY_ORDER = ("global", "parser", "renderer")
    CATEGORY_LABELS = {
        "global": "Global options",
        "parser": "Parser options",
        "renderer": "Renderer options",
    }

    def __init__(self, catalog: HelpCatalog, *, use_rich: bool = False) -> None:
        """Initialize the help renderer with a catalog.

        Parameters
        ----------
        catalog : HelpCatalog
            Structured help content to render.
        use_rich : bool, default False
            Enable rich formatting when available.

        """
        self.catalog = catalog
        self.use_rich = use_rich and _rich_available()

    def render(self, selector: str = "quick") -> str:
        """Render help text for the specified selector.

        Parameters
        ----------
        selector : str, default "quick"
            Help level: "quick", "full", or a specific section/format name.

        Returns
        -------
        str
            Rendered help text.

        """
        selector = selector.lower()
        if selector in {"", "quick"}:
            return self._render_quick()
        if selector == "full":
            return self._render_full()

        format_sections = self.catalog.get_sections_for_format(selector)
        if format_sections:
            return self._render_format_sections(format_sections)

        section = self.catalog.get_section(selector)
        if section:
            return self._render_section(section)

        # Unknown selector fallback
        known = ", ".join(sorted(self.catalog.section_lookup.keys()))
        return f"Unknown help section '{selector}'. Available sections: {known}"

    # Rendering helpers -------------------------------------------------

    def _render_quick(self) -> str:
        lines = []

        if self.catalog.description:
            lines.append(self.catalog.description)

        lines.append(self.catalog.usage)
        lines.append("")
        lines.append("Subcommands:")
        for name, summary in self.catalog.subcommands:
            lines.append(f"  {name:<15} {summary}")

        lines.append("")
        lines.append("Core options:")
        for category in self.CATEGORY_ORDER:
            cat_sections = [s for s in self.catalog.sections if s.category == category]
            rendered = self._render_sections(cat_sections, core_only=True)
            if rendered:
                lines.append("")
                lines.append(f"{self.CATEGORY_LABELS[category]}:")
                lines.extend(rendered)

        lines.append(
            "\nNote: showing only core options. Most parsers/renderers have advanced/security options as well."
            "\nRun 'all2md help full' for every option or 'all2md help <section>' for a specific format."
        )

        if self.catalog.epilog:
            lines.append("")
            lines.append(self.catalog.epilog.strip())

        return "\n".join(lines)

    def _render_full(self) -> str:
        lines = []

        if self.catalog.description:
            lines.append(self.catalog.description)

        lines.append(self.catalog.usage)
        lines.append("")
        lines.append("Subcommands:")
        for name, summary in self.catalog.subcommands:
            lines.append(f"  {name:<15} {summary}")

        for category in self.CATEGORY_ORDER:
            cat_sections = [s for s in self.catalog.sections if s.category == category]
            rendered = self._render_sections(cat_sections, core_only=False)
            if rendered:
                lines.append("")
                lines.append(f"{self.CATEGORY_LABELS[category]}:")
                lines.extend(rendered)

        if self.catalog.epilog:
            lines.append("")
            lines.append(self.catalog.epilog.strip())

        return "\n".join(lines)

    def _render_section(self, section: HelpSection) -> str:
        lines = self._render_section_block(section, section.options, indent_section="")
        return "\n".join(lines)

    def _render_format_sections(self, sections: Sequence[HelpSection]) -> str:
        lines: list[str] = []

        for section in sorted(sections, key=lambda s: (s.category, s.title)):
            lines.extend(self._render_section_block(section, section.options, indent_section=""))
            lines.append("")

        if lines:
            lines.pop()

        return "\n".join(lines)

    def _render_sections(
            self,
            sections: Sequence[HelpSection],
            *,
            core_only: bool,
    ) -> list[str]:
        lines: list[str] = []

        for section in sections:
            if core_only:
                core_options = [opt for opt in section.options if opt.importance == "core"]
                # non_core_options = [opt for opt in section.options if opt.importance != 'core']

                if core_options:
                    block = self._render_section_block(section, core_options, indent_section="  ")
                    # if len(non_core_options) > 0:
                    #     block.append("   Note: advanced/security options not shown.")
                elif section.options:
                    block = self._render_section_placeholder(section, indent_section="  ")
                else:
                    continue
            else:
                block = self._render_section_block(section, section.options, indent_section="  ")

            lines.extend(block)
            lines.append("")

        if lines:
            lines.pop()  # Remove trailing blank line

        return lines

    def _render_section_block(
            self,
            section: HelpSection,
            options: Sequence[OptionEntry],
            *,
            indent_section: str,
    ) -> list[str]:
        lines: list[str] = []
        section_prefix = indent_section
        option_indent = indent_section + "  "
        desc_indent = indent_section + "    "

        lines.append(f"{section_prefix}{section.title}:")
        if section.description:
            wrapper = textwrap.TextWrapper(
                width=self.WRAP_WIDTH,
                initial_indent=section_prefix + "  ",
                subsequent_indent=section_prefix + "  ",
            )
            lines.extend(wrapper.wrap(section.description))

        for option in options:
            lines.extend(self._format_option_line(option, option_indent, desc_indent))

        return lines

    def _render_section_placeholder(
            self,
            section: HelpSection,
            *,
            indent_section: str,
    ) -> list[str]:
        lines: list[str] = []
        section_prefix = indent_section
        placeholder_indent = indent_section + "    "

        lines.append(f"{section_prefix}{section.title}:")
        if section.description:
            wrapper = textwrap.TextWrapper(
                width=self.WRAP_WIDTH,
                initial_indent=section_prefix + "  ",
                subsequent_indent=section_prefix + "  ",
            )
            lines.extend(wrapper.wrap(section.description))

        hint_selector = section.format_name or section.key
        lines.append(
            f"{placeholder_indent}(All options are advanced/security. Run 'all2md help {hint_selector}' for details.)"
        )

        return lines

    def _format_option_line(
            self,
            option: OptionEntry,
            option_indent: str,
            desc_indent: str,
    ) -> list[str]:
        option_strings = ", ".join(option.option_strings)
        header = f"{option_indent}{option_strings}"
        details: list[str] = []

        if option.choices:
            choices = ", ".join(str(choice) for choice in option.choices)
            details.append(f"choices: {choices}")

        formatted_default = _format_default(option.default)
        if formatted_default is not None:
            details.append(f"default: {formatted_default}")

        if option.importance != "core":
            details.append(f"[{option.importance}]")

        info = f" ({'; '.join(details)})" if details else ""

        help_text = option.help_text or ""
        description = f"{header}{info}"
        wrapper = textwrap.TextWrapper(
            width=self.WRAP_WIDTH,
            initial_indent=desc_indent,
            subsequent_indent=desc_indent,
        )
        wrapped = wrapper.wrap(help_text) if help_text else []
        return [description, *wrapped]

    def print(self, selector: str = "quick", *, stream: Optional[Any] = None) -> None:
        """Print formatted help output to the specified stream.

        Parameters
        ----------
        selector : str, default "quick"
            Help level: "quick", "full", or a specific section/format name.
        stream : file-like, optional
            Output stream. Defaults to stdout.

        """
        output = self.render(selector)
        if self.use_rich:
            from rich.console import Console

            target = stream or sys.stdout
            console = Console(file=target, force_terminal=True)
            for line in output.splitlines():
                console.print(self._style_line(line), soft_wrap=True)
        else:
            target = stream or sys.stdout
            print(output, file=target)

    def _style_line(self, line: str) -> "Text":
        from rich.text import Text

        if not line:
            return Text("")

        indent_len = len(line) - len(line.lstrip(" "))
        indent = " " * indent_len
        stripped = line.strip()

        text = Text(indent)

        if not stripped:
            return text

        if stripped.startswith("usage:"):
            text.append("usage:", style="bold yellow")
            text.append(stripped[len("usage:"):], style="white")
            return text

        if stripped.lower().startswith("subcommands"):
            text.append(stripped, style="bold violet")
            return text

        if (stripped.endswith("options:") or stripped.endswith("customization:")) and not stripped.startswith("--"):
            text.append(stripped, style="bold bright_white")
            return text

        if stripped.startswith("(") and stripped.endswith(")"):
            text.append(stripped, style="italic dim")
            return text

        if stripped.startswith("--") or (stripped.startswith("-") and not stripped.startswith("--")):
            parts = stripped.split(" ", 1)
            flag_part = parts[0]
            remainder = parts[1] if len(parts) > 1 else ""
            text.append(flag_part, style="bold cyan")
            if remainder:
                remainder_text = Text(" " + remainder)
                self._highlight_metadata(remainder_text)
                text += remainder_text
            return text

        content = Text(stripped)
        self._highlight_metadata(content)
        text += content
        return text

    def _highlight_metadata(self, text: "Text") -> None:
        text.highlight_regex(r"default: [^);]+", style="green")
        text.highlight_regex(r"choices?: [^);]+", style="magenta")
        text.highlight_regex(r"\[[^\]]+\]", style="dim")


def _rich_available() -> bool:
    try:  # pragma: no cover - runtime check
        import rich  # noqa: F401

        return True
    except ImportError:  # pragma: no cover - runtime check
        return False


def build_help_renderer(*, use_rich: bool = False) -> HelpRenderer:
    """Build a complete help renderer with parser and catalog."""
    # Use create_parser() to get the full parser with all top-level options
    # (e.g., --rich, --progress, --output-dir, --parallel, etc.)
    parser = create_parser()
    # We still need a builder instance for resolve_option_field() in build_catalog()
    builder = DynamicCLIBuilder()
    catalog = build_catalog(parser, builder)
    return HelpRenderer(catalog, use_rich=use_rich)


def display_help(
        selector: str = "quick",
        *,
        use_rich: Optional[bool] = None,
        stream: Optional[Any] = None,
) -> None:
    """Render help for ``selector`` to stdout (or ``stream``) with optional rich output.

    When ``use_rich`` is ``None`` the renderer automatically enables rich output when
    supported, the target stream is a TTY, and color has not been disabled via
    ``NO_COLOR`` or a ``dumb`` terminal.
    """
    resolved_use_rich = _should_enable_rich(use_rich=use_rich, stream=stream)
    renderer = build_help_renderer(use_rich=resolved_use_rich)

    if resolved_use_rich and not renderer.use_rich:
        warning_target = stream or sys.stderr
        print(
            "Rich output requested but the 'rich' package is not installed. Falling back to plain text.",
            file=warning_target,
        )

    renderer.print(selector, stream=stream)


def _should_enable_rich(*, use_rich: Optional[bool], stream: Optional[Any]) -> bool:
    """Return ``True`` when rich output should be used for help rendering."""
    if use_rich is False:
        return False

    if not _rich_available():
        return False

    if os.environ.get("NO_COLOR"):
        return False

    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False

    # Explicit request overrides TTY checks when color is otherwise permitted.
    if use_rich is True:
        return True

    target = stream or sys.stdout
    isatty = getattr(target, "isatty", None)
    if callable(isatty):
        try:
            if isatty():
                return True
        except Exception:  # pragma: no cover - defensive: respect failures
            return False

    return False


__all__ = [
    "HelpRenderer",
    "HelpCatalog",
    "HelpSection",
    "OptionEntry",
    "build_help_renderer",
    "display_help",
]
