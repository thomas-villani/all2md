#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Configuration file discovery and loading for all2md CLI.

This module handles automatic discovery of configuration files, loading
configs from JSON or TOML format, and merging configurations with proper
priority handling.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

CONFIG_FILENAMES = [".all2md.toml", ".all2md.yaml", ".all2md.yml", ".all2md.json", "pyproject.toml"]

# Subcommands whose flags can be set from a same-named config section
# (e.g. ``[view]``, ``[serve]``). Each section is applied to that command's
# argparse parser via ``apply_config_to_parser``; ``config generate`` emits a
# template section for each. Keep this in sync with the wired handlers.
SUBCOMMAND_CONFIG_SECTIONS: tuple[str, ...] = (
    "view",
    "serve",
    "edit",
    "diff",
    "arxiv",
    "generate-site",
    "chunk",
)


def _load_pyproject_all2md_section(pyproject_path: Path) -> Dict[str, Any]:
    """Load [tool.all2md] section from pyproject.toml file.

    Parameters
    ----------
    pyproject_path : Path
        Path to pyproject.toml file

    Returns
    -------
    dict
        Configuration dictionary from [tool.all2md] section, or empty dict if not found

    Raises
    ------
    argparse.ArgumentTypeError
        If pyproject.toml cannot be parsed

    """
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        # Extract [tool.all2md] section if it exists
        if "tool" in data and "all2md" in data["tool"]:
            config = data["tool"]["all2md"]
            if not isinstance(config, dict):
                raise argparse.ArgumentTypeError(
                    f"[tool.all2md] section in {pyproject_path} must be a table, got {type(config).__name__}"
                )
            return config

        # No [tool.all2md] section found
        return {}

    except tomllib.TOMLDecodeError as e:
        raise argparse.ArgumentTypeError(f"Invalid TOML in pyproject.toml {pyproject_path}: {e}") from e
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading pyproject.toml {pyproject_path}: {e}") from e


def find_config_in_parents(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find configuration file by searching parent directories.

    Walks up the directory tree from start_dir to the filesystem root,
    checking each directory for configuration files in priority order:
    1. .all2md.toml
    2. .all2md.json
    3. pyproject.toml (with [tool.all2md] section)

    Returns the first configuration file found.

    Parameters
    ----------
    start_dir : Path, optional
        Starting directory for search, defaults to current working directory

    Returns
    -------
    Path or None
        Path to first config file found, or None if not found

    Examples
    --------
    >>> config_path = find_config_in_parents()
    >>> if config_path:
    ...     print(f"Found config at: {config_path}")

    """
    if start_dir is None:
        start_dir = Path.cwd()

    current = start_dir.resolve()

    # Walk up directory tree to root
    while True:
        # Check for dedicated config files first (.all2md.toml, .all2md.yaml, .all2md.yml, .all2md.json)
        for filename in [".all2md.toml", ".all2md.yaml", ".all2md.yml", ".all2md.json"]:
            config_path = current / filename
            if config_path.exists() and config_path.is_file():
                return config_path

        # Check for pyproject.toml with [tool.all2md] section
        pyproject_path = current / "pyproject.toml"
        if pyproject_path.exists() and pyproject_path.is_file():
            try:
                # Only return pyproject.toml if it has [tool.all2md] section
                config = _load_pyproject_all2md_section(pyproject_path)
                if config:
                    return pyproject_path
            except argparse.ArgumentTypeError:
                # Invalid pyproject.toml, skip it and continue searching
                pass

        # Check if we've reached the filesystem root
        parent = current.parent
        if parent == current:
            # Reached root, stop searching
            break

        current = parent

    return None


def discover_config_file() -> Optional[Path]:
    """Discover configuration file in standard locations.

    Searches for configuration files in the following order:

    1. Parent directory search (from cwd up to filesystem root):

       - .all2md.toml (highest priority)
       - .all2md.yaml
       - .all2md.yml
       - .all2md.json
       - pyproject.toml with [tool.all2md] section

    2. User home directory:

       - .all2md.toml
       - .all2md.yaml
       - .all2md.yml
       - .all2md.json

    Returns the first configuration file found.

    Returns
    -------
    Path or None
        Path to discovered config file, or None if not found

    Examples
    --------
    >>> config_path = discover_config_file()
    >>> if config_path:
    ...     print(f"Found config at: {config_path}")

    """
    # First, search parent directories from cwd to root
    config_in_parents = find_config_in_parents()
    if config_in_parents:
        return config_in_parents

    # Fall back to user home directory
    home = Path.home()
    for filename in [".all2md.toml", ".all2md.yaml", ".all2md.yml", ".all2md.json"]:
        config_path = home / filename
        if config_path.exists() and config_path.is_file():
            return config_path

    return None


def load_config_file(config_path: Path | str) -> Dict[str, Any]:
    """Load configuration from JSON, TOML, YAML, or pyproject.toml file.

    Auto-detects format based on file extension and name:
    - .json files: Loaded as JSON
    - .toml files: Loaded as TOML
    - .yaml/.yml files: Loaded as YAML
    - pyproject.toml: Extracts [tool.all2md] section

    Parameters
    ----------
    config_path : Path or str
        Path to the configuration file

    Returns
    -------
    dict
        Configuration dictionary loaded from file

    Raises
    ------
    argparse.ArgumentTypeError
        If the file cannot be read, parsed, or has invalid format

    Examples
    --------
    >>> config = load_config_file(".all2md.toml")
    >>> print(config.get("attachment_mode"))
    save

    >>> config = load_config_file("pyproject.toml")
    >>> print(config.get("attachment_mode"))
    skip

    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise argparse.ArgumentTypeError(f"Configuration file does not exist: {config_path}")

    if not config_path.is_file():
        raise argparse.ArgumentTypeError(f"Configuration path is not a file: {config_path}")

    # Determine format from filename and extension
    filename = config_path.name.lower()
    ext = config_path.suffix.lower()

    try:
        # Handle pyproject.toml specially - extract [tool.all2md] section
        if filename == "pyproject.toml":
            return _load_pyproject_all2md_section(config_path)
        elif ext == ".toml":
            return _load_toml_config(config_path)
        elif ext in (".yaml", ".yml"):
            return _load_yaml_config(config_path)
        elif ext == ".json":
            return _load_json_config(config_path)
        else:
            raise argparse.ArgumentTypeError(f"Unsupported config file format: {ext}. Use .json, .toml, or .yaml")
    except argparse.ArgumentTypeError:
        raise
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading config file {config_path}: {e}") from e


def _load_toml_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from TOML file.

    Parameters
    ----------
    config_path : Path
        Path to TOML configuration file

    Returns
    -------
    dict
        Configuration dictionary

    Raises
    ------
    argparse.ArgumentTypeError
        If TOML file cannot be parsed

    """
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        if not isinstance(config, dict):
            raise argparse.ArgumentTypeError(
                f"TOML config file must contain a table at root level, got {type(config).__name__}"
            )

        return config

    except tomllib.TOMLDecodeError as e:
        raise argparse.ArgumentTypeError(f"Invalid TOML in config file {config_path}: {e}") from e
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading TOML config {config_path}: {e}") from e


def _load_json_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from JSON file.

    Parameters
    ----------
    config_path : Path
        Path to JSON configuration file

    Returns
    -------
    dict
        Configuration dictionary

    Raises
    ------
    argparse.ArgumentTypeError
        If JSON file cannot be parsed

    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if not isinstance(config, dict):
            raise argparse.ArgumentTypeError(f"JSON config file must contain an object, got {type(config).__name__}")

        return config

    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"Invalid JSON in config file {config_path}: {e}") from e
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading JSON config {config_path}: {e}") from e


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML file.

    Parameters
    ----------
    config_path : Path
        Path to YAML configuration file

    Returns
    -------
    dict
        Configuration dictionary

    Raises
    ------
    argparse.ArgumentTypeError
        If YAML file cannot be parsed

    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise argparse.ArgumentTypeError(f"YAML config file must contain a mapping, got {type(config).__name__}")

        return config

    except yaml.YAMLError as e:
        raise argparse.ArgumentTypeError(f"Invalid YAML in config file {config_path}: {e}") from e
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading YAML config {config_path}: {e}") from e


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configuration dictionaries with deep merging.

    The override dictionary takes precedence over base for conflicting keys.
    Nested dictionaries are merged recursively, not replaced entirely.

    Parameters
    ----------
    base : dict
        Base configuration dictionary
    override : dict
        Override configuration dictionary (higher priority)

    Returns
    -------
    dict
        Merged configuration dictionary

    Examples
    --------
    >>> base = {'pdf': {'pages': [1, 2]}, 'attachment_mode': 'skip'}
    >>> override = {'pdf': {'detect_columns': True}, 'attachment_mode': 'save'}
    >>> merged = merge_configs(base, override)
    >>> print(merged)
    {'pdf': {'pages': [1, 2], 'detect_columns': True}, 'attachment_mode': 'save'}

    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = merge_configs(result[key], value)
        else:
            # Override value
            result[key] = value

    return result


def load_config_with_priority(
    explicit_path: Optional[str] = None, env_var_path: Optional[str] = None
) -> Dict[str, Any]:
    """Load configuration with proper priority handling.

    Priority order (highest to lowest):
    1. Explicit config file path (--config flag)
    2. Environment variable config path (ALL2MD_CONFIG)
    3. Auto-discovered config file (.all2md.toml or .all2md.json in cwd or home)

    Parameters
    ----------
    explicit_path : str, optional
        Explicit config file path from --config flag
    env_var_path : str, optional
        Config file path from ALL2MD_CONFIG environment variable

    Returns
    -------
    dict
        Loaded configuration dictionary (empty dict if no config found)

    Raises
    ------
    argparse.ArgumentTypeError
        If a config file is specified but cannot be loaded

    Examples
    --------
    >>> # Load from explicit path
    >>> config = load_config_with_priority(explicit_path="my_config.toml")

    >>> # Load with auto-discovery
    >>> config = load_config_with_priority()

    """
    # Priority 1: Explicit --config flag
    if explicit_path:
        return load_config_file(explicit_path)

    # Priority 2: ALL2MD_CONFIG environment variable
    if env_var_path:
        return load_config_file(env_var_path)

    # Priority 3: Auto-discovery
    discovered_path = discover_config_file()
    if discovered_path:
        return load_config_file(discovered_path)

    # No config found - return empty dict
    return {}


def get_config_search_paths() -> list[Path]:
    """Get list of representative paths for configuration file search.

    Returns a list showing the search pattern used during config discovery.
    Note that the actual search walks up from cwd to filesystem root,
    checking each directory for config files.

    Returns
    -------
    list[Path]
        List of representative config file paths in search order

    Examples
    --------
    >>> paths = get_config_search_paths()
    >>> for path in paths:
    ...     print(path)
    /current/working/dir/.all2md.toml
    /current/working/dir/.all2md.yaml
    /current/working/dir/.all2md.yml
    /current/working/dir/.all2md.json
    /current/working/dir/pyproject.toml
    (... continues up parent directories to root ...)
    ~/.all2md.toml
    ~/.all2md.yaml
    ~/.all2md.yml
    ~/.all2md.json

    """
    paths = []

    # Show current working directory as example
    # (actual search walks up to root checking each parent)
    cwd = Path.cwd()
    for filename in [".all2md.toml", ".all2md.yaml", ".all2md.yml", ".all2md.json", "pyproject.toml"]:
        paths.append(cwd / filename)

    # Home directory (fallback after parent search)
    home = Path.home()
    for filename in [".all2md.toml", ".all2md.yaml", ".all2md.yml", ".all2md.json"]:
        paths.append(home / filename)

    return paths


def apply_config_to_parser(
    parser: argparse.ArgumentParser,
    section: str,
    *,
    explicit_path: Optional[str] = None,
    no_config: bool = False,
) -> Dict[str, Any]:
    """Apply a config-file section as argparse defaults for a subcommand.

    Loads configuration with the standard priority chain (explicit ``--config``
    path, then ``ALL2MD_CONFIG``, then auto-discovery) and applies values from
    the ``[section]`` table as defaults on ``parser``. Because they are applied
    as defaults, explicit CLI arguments still override them, and the config in
    turn overrides the parser's hard-coded defaults.

    This is the bridge that lets standalone subcommands (``view``, ``serve``,
    ``diff``) honor config files the same way the main converter command does.
    Subcommand parsers use plain argparse actions rather than the converter's
    tracking actions, so applying values as defaults before parsing is the
    correct way to get "config < CLI" precedence.

    Config keys are matched against argument *destination* names (snake_case),
    so ``--no-wait`` is configured as ``no_wait`` and ``--max-upload-size`` as
    ``max_upload_size``. Hyphens in keys are accepted and normalized to
    underscores. For flags whose dest differs from the flag spelling (e.g.
    ``--no-context`` stores ``show_context``), use the dest name. Keys that do
    not match an optional argument are logged as warnings and ignored.

    Only the named ``[section]`` table is consulted; top-level keys (which the
    main converter uses) are deliberately ignored to avoid collisions such as a
    top-level ``format`` (input format) leaking into a subcommand's ``--format``.

    Intended usage (call after all add_argument calls, before the final parse)::

        pre_args, _ = parser.parse_known_args(args)
        apply_config_to_parser(
            parser, "view", explicit_path=pre_args.config, no_config=pre_args.no_config
        )
        parsed = parser.parse_args(args)

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Parser to apply defaults to.
    section : str
        Config section name to read (e.g. ``"view"``, ``"serve"``, ``"diff"``).
    explicit_path : str, optional
        Explicit config path (typically from a ``--config`` flag).
    no_config : bool
        If True, skip all config loading and return an empty dict.

    Returns
    -------
    dict
        Mapping of dest -> value that was applied (useful for testing).

    """
    if no_config:
        return {}

    env_var_path = os.environ.get("ALL2MD_CONFIG")
    try:
        config = load_config_with_priority(explicit_path=explicit_path, env_var_path=env_var_path)
    except argparse.ArgumentTypeError as e:
        # Surface the problem but don't crash the subcommand over a bad config file.
        print(f"Warning: could not load configuration: {e}", file=sys.stderr)
        return {}

    raw_section = config.get(section)
    if not isinstance(raw_section, dict) or not raw_section:
        return {}

    # Configurable destinations are optional arguments only; positionals and
    # suppressed actions (e.g. -h/--help) are never set from config.
    dest_to_action = {
        action.dest: action for action in parser._actions if action.option_strings and action.dest != argparse.SUPPRESS
    }

    applied: Dict[str, Any] = {}
    for key, value in raw_section.items():
        dest = str(key).replace("-", "_")
        if dest in dest_to_action:
            applied[dest] = value
        else:
            logger.warning("Ignoring unknown key '%s' in [%s] config section", key, section)

    if applied:
        parser.set_defaults(**applied)
        # A config-supplied value satisfies a required option, so drop the
        # required flag; otherwise argparse would still demand it on the CLI.
        for dest in applied:
            action = dest_to_action[dest]
            if getattr(action, "required", False):
                action.required = False

    return applied
