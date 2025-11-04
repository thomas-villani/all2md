#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands/config.py
"""Configuration management commands for all2md CLI.

This module provides subcommands for generating, viewing, and validating
configuration files for the all2md document conversion tool. It supports
multiple configuration formats (TOML, JSON, YAML) and handles configuration
priority resolution from multiple sources.
"""
import argparse
import json
import logging
import os
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from all2md.cli.builder import DynamicCLIBuilder
from all2md.cli.config import get_config_search_paths, load_config_file, load_config_with_priority
from all2md.options.search import SearchOptions

logger = logging.getLogger(__name__)


def _serialize_config_value(value: Any) -> Any:
    """Convert dataclass default values into config-friendly primitives."""
    if is_dataclass(value):
        result: Dict[str, Any] = {}
        for field in fields(value):
            serialized = _serialize_config_value(getattr(value, field.name))
            if serialized is None:
                continue
            result[field.name] = serialized
        return result

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        items = {}
        for k, v in value.items():
            serialized = _serialize_config_value(v)
            if serialized is None:
                continue
            items[str(k)] = serialized
        return items

    if isinstance(value, (list, tuple, set)):
        serialized_items = [_serialize_config_value(v) for v in value]
        return [item for item in serialized_items if item is not None]

    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        try:
            return _serialize_config_value(value.value)
        except AttributeError:  # pragma: no cover - defensive
            pass

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def _collect_defaults_from_options_class(options_class: Optional[type]) -> Dict[str, Any]:
    """Instantiate an options dataclass and extract CLI-relevant defaults."""
    if options_class is None or not is_dataclass(options_class):
        return {}

    try:
        instance = options_class()
    except (TypeError, ValueError):
        logger.debug("Skipping %s: could not instantiate without arguments", options_class)
        return {}

    defaults: Dict[str, Any] = {}

    for field in fields(instance):
        metadata: Dict[str, Any] = dict(field.metadata) if field.metadata else {}
        if metadata.get("exclude_from_cli", False):
            continue

        serialized = _serialize_config_value(getattr(instance, field.name))
        if serialized is None:
            continue

        if isinstance(serialized, dict) and not serialized:
            continue

        if isinstance(serialized, list) and not serialized:
            continue

        defaults[field.name] = serialized

    return defaults


def _build_default_config_data() -> Dict[str, Any]:
    """Assemble default configuration from registered option classes."""
    builder = DynamicCLIBuilder()
    options_map = builder.get_options_class_map()
    config: Dict[str, Any] = {}

    base_defaults = _collect_defaults_from_options_class(options_map.get("base"))
    config.update(base_defaults)

    ordered_keys = sorted(options_map.keys())
    for key in ordered_keys:
        if key == "base":
            continue

        defaults = _collect_defaults_from_options_class(options_map.get(key))
        if defaults:
            config[key] = defaults

    config["search"] = _serialize_config_value(SearchOptions())

    return config


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        items = ", ".join(_format_toml_value(item) for item in value)
        return f"[{items}]"
    if isinstance(value, dict):
        # Should not hit here; dicts are handled at section level
        return "{}"
    return f'"{value}"'


def _emit_toml_section(name: str, data: Dict[str, Any]) -> List[str]:
    lines: List[str] = [f"[{name}]"]

    scalar_keys = [k for k, v in data.items() if not isinstance(v, dict)]
    for key in sorted(scalar_keys):
        lines.append(f"{key} = {_format_toml_value(data[key])}")

    nested_keys = [k for k, v in data.items() if isinstance(v, dict)]
    for key in sorted(nested_keys):
        lines.append("")
        nested_name = f"{name}.{key}"
        lines.extend(_emit_toml_section(nested_name, data[key]))

    return lines


def _format_config_as_toml(config: Dict[str, Any]) -> str:
    lines = [
        "# all2md configuration file",
        "# Generated from current converter defaults",
        "# Edit values as needed and remove sections you do not use.",
    ]

    scalar_keys = [k for k, v in config.items() if not isinstance(v, dict)]
    for key in sorted(scalar_keys):
        lines.append(f"{key} = {_format_toml_value(config[key])}")

    section_keys = [k for k, v in config.items() if isinstance(v, dict)]
    for key in sorted(section_keys):
        lines.append("")
        lines.extend(_emit_toml_section(key, config[key]))

    return "\n".join(lines)


def _format_config_as_yaml(config: Dict[str, Any]) -> str:
    """Format configuration dictionary as YAML string.

    Parameters
    ----------
    config : dict
        Configuration dictionary to format

    Returns
    -------
    str
        YAML-formatted configuration string

    """
    header = (
        "# all2md configuration file\n"
        "# Generated from current converter defaults\n"
        "# Edit values as needed and remove sections you do not use.\n\n"
    )

    yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=True, allow_unicode=True, indent=2)

    return header + yaml_content


def save_config_to_file(args: argparse.Namespace, config_path: str) -> None:
    """Save CLI arguments to a JSON configuration file.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments
    config_path : str
        Path to save the configuration file

    Raises
    ------
    Exception
        If the configuration file cannot be written

    """
    # Exclude special arguments that shouldn't be saved
    exclude_args = {
        "input",
        "out",
        "save_config",
        "about",
        "version",
        "dry_run",
        "format",
        "_env_checked",
        "_provided_args",
    }
    # Note: 'exclude' is intentionally NOT excluded so it can be saved in config

    # Get set of explicitly provided arguments from tracking actions
    provided_args: set[str] = getattr(args, "_provided_args", set())

    # Convert namespace to dict and filter
    args_dict = vars(args)
    config = {}

    for key, value in args_dict.items():
        if key not in exclude_args and value is not None:
            # Only include arguments that were explicitly provided by the user
            # This prevents saving default values that may change in future versions
            if key not in provided_args:
                continue

            # Skip empty lists
            if isinstance(value, list) and not value:
                continue
            # Skip sentinel values that aren't JSON serializable
            # Check for dataclasses._MISSING_TYPE
            if hasattr(value, "__class__") and value.__class__.__name__ == "_MISSING_TYPE":
                continue
            # Check for plain object() sentinels (used for UNSET in MarkdownRendererOptions)
            if type(value) is object:
                continue
            # Skip non-serializable types
            if isinstance(value, (set, frozenset)):
                continue

            # Include the explicitly provided value
            config[key] = value

    # Write to file
    config_path_obj = Path(config_path)
    config_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path_obj, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Configuration saved to {config_path}")


def handle_config_generate_command(args: list[str] | None = None) -> int:
    """Handle ``config generate`` to create default configuration files."""
    parser = argparse.ArgumentParser(
        prog="all2md config generate",
        description="Generate a default configuration file with all available options.",
    )
    parser.add_argument(
        "--format",
        choices=("toml", "json", "yaml"),
        default="toml",
        help="Output format for the generated configuration (default: toml).",
    )
    parser.add_argument(
        "--out",
        dest="out",
        help="Write configuration to the given path instead of stdout.",
    )

    try:
        parsed_args = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    config_data = _build_default_config_data()

    if parsed_args.format == "toml":
        output_text = _format_config_as_toml(config_data)
    elif parsed_args.format == "yaml":
        output_text = _format_config_as_yaml(config_data)
    else:
        output_text = json.dumps(config_data, indent=2, ensure_ascii=False, sort_keys=True)

    if parsed_args.out:
        try:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_text, encoding="utf-8")
            print(f"Configuration written to {parsed_args.out}")
        except Exception as exc:
            print(f"Error writing configuration file: {exc}", file=sys.stderr)
            return 1
        return 0

    print(output_text)
    return 0


def handle_config_show_command(args: list[str] | None = None) -> int:
    """Handle ``config show`` command to display effective configuration."""
    parser = argparse.ArgumentParser(
        prog="all2md config show",
        description="Display the effective configuration that all2md will use.",
    )
    parser.add_argument(
        "--format",
        choices=("toml", "json", "yaml"),
        default="toml",
        help="Output format for the configuration (default: toml).",
    )
    parser.add_argument(
        "--no-source",
        dest="show_source",
        action="store_false",
        default=True,
        help="Hide configuration source information.",
    )

    try:
        parsed_args = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    env_config_path = os.environ.get("ALL2MD_CONFIG")
    config = load_config_with_priority(
        explicit_path=None,
        env_var_path=env_config_path,
    )

    if parsed_args.show_source:
        print("Configuration Sources (in priority order):")
        print("-" * 60)

        if env_config_path:
            exists = Path(env_config_path).exists()
            status = "FOUND" if exists else "NOT FOUND"
            print(f"1. ALL2MD_CONFIG env var: {env_config_path} [{status}]")
        else:
            print("1. ALL2MD_CONFIG env var: (not set)")

        for index, path in enumerate(get_config_search_paths(), start=2):
            status = "FOUND" if path.exists() else "-"
            print(f"{index}. {path} [{status}]")

        print()

    if not config:
        print("No configuration found. Using defaults.")
        print("\nTo create a config file, run: all2md config generate --out .all2md.toml")
        return 0

    print("Effective Configuration:")
    print("=" * 60)

    if parsed_args.format == "toml":
        import tomli_w

        output_text = tomli_w.dumps(config)
    elif parsed_args.format == "yaml":
        output_text = yaml.dump(config, default_flow_style=False, sort_keys=True, allow_unicode=True, indent=2)
    else:
        output_text = json.dumps(config, indent=2, ensure_ascii=False)

    print(output_text)
    return 0


def handle_config_validate_command(args: list[str] | None = None) -> int:
    """Handle config validate command to check configuration file syntax.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'config validate')

    Returns
    -------
    int
        Exit code (0 for success, 1 for invalid config)

    """
    # Parse arguments
    config_file = None

    if args:
        for arg in args:
            if arg in ("--help", "-h"):
                print(
                    """Usage: all2md config validate <config-file>

Validate a configuration file for syntax errors.

Arguments:
  config-file        Path to configuration file (.toml or .json)

Options:
  -h, --help        Show this help message

Examples:
  all2md config validate .all2md.toml
  all2md config validate ~/.all2md.json
"""
                )
                return 0
            elif not arg.startswith("-"):
                config_file = arg
                break

    if not config_file:
        print("Error: Config file path required", file=sys.stderr)
        print("Usage: all2md config validate <config-file>", file=sys.stderr)
        return 1

    # Attempt to load and validate
    try:
        config = load_config_file(config_file)
        print(f"Configuration file is valid: {config_file}")
        print(f"Format: {Path(config_file).suffix}")
        print(f"Keys found: {', '.join(config.keys()) if config else '(empty)'}")
        return 0
    except argparse.ArgumentTypeError as e:
        print(f"Invalid configuration file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error validating configuration: {e}", file=sys.stderr)
        return 1


def handle_config_command(args: list[str] | None = None) -> int | None:
    """Handle config subcommands.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments

    Returns
    -------
    int or None
        Exit code if config command was handled, None otherwise

    """
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != "config":
        return None

    # Get subcommand
    if len(args) < 2:
        print(
            """Usage: all2md config <subcommand> [OPTIONS]

Configuration management commands.

Subcommands:
  generate           Generate a default configuration file
  show              Display effective configuration from all sources
  validate          Validate a configuration file

Use 'all2md config <subcommand> --help' for more information.

Examples:
  all2md config generate --out .all2md.toml
  all2md config show
  all2md config validate .all2md.toml
""",
            file=sys.stderr,
        )
        return 1

    subcommand = args[1]
    subcommand_args = args[2:]

    if subcommand == "generate":
        return handle_config_generate_command(subcommand_args)
    elif subcommand == "show":
        return handle_config_show_command(subcommand_args)
    elif subcommand == "validate":
        return handle_config_validate_command(subcommand_args)
    else:
        print(f"Error: Unknown config subcommand '{subcommand}'", file=sys.stderr)
        print("Valid subcommands: generate, show, validate", file=sys.stderr)
        return 1
