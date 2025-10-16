#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Configuration file discovery and loading for all2md CLI.

This module handles automatic discovery of configuration files, loading
configs from JSON or TOML format, and merging configurations with proper
priority handling.
"""

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_FILENAMES = [".all2md.toml", ".all2md.json"]


def discover_config_file() -> Optional[Path]:
    """Discover configuration file in standard locations.

    Searches for configuration files in the following order:
    1. Current working directory
    2. User home directory

    For each directory, checks for .all2md.toml first, then .all2md.json.
    TOML files take precedence over JSON files.

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
    # Search in current working directory first
    cwd = Path.cwd()
    for filename in CONFIG_FILENAMES:
        config_path = cwd / filename
        if config_path.exists() and config_path.is_file():
            return config_path

    # Search in user home directory
    home = Path.home()
    for filename in CONFIG_FILENAMES:
        config_path = home / filename
        if config_path.exists() and config_path.is_file():
            return config_path

    return None


def load_config_file(config_path: Path | str) -> Dict[str, Any]:
    """Load configuration from JSON or TOML file.

    Auto-detects format based on file extension (.json or .toml).

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
    download

    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise argparse.ArgumentTypeError(f"Configuration file does not exist: {config_path}")

    if not config_path.is_file():
        raise argparse.ArgumentTypeError(f"Configuration path is not a file: {config_path}")

    # Determine format from extension
    ext = config_path.suffix.lower()

    try:
        if ext == ".toml":
            return _load_toml_config(config_path)
        elif ext == ".json":
            return _load_json_config(config_path)
        else:
            raise argparse.ArgumentTypeError(f"Unsupported config file format: {ext}. Use .json or .toml")
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
    >>> override = {'pdf': {'detect_columns': True}, 'attachment_mode': 'download'}
    >>> merged = merge_configs(base, override)
    >>> print(merged)
    {'pdf': {'pages': [1, 2], 'detect_columns': True}, 'attachment_mode': 'download'}

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
    """Get list of paths searched for configuration files.

    Returns list of all paths that are checked during config discovery,
    in priority order. Useful for debugging and showing config locations.

    Returns
    -------
    list[Path]
        List of paths checked for config files

    Examples
    --------
    >>> paths = get_config_search_paths()
    >>> for path in paths:
    ...     print(path)
    .all2md.toml
    .all2md.json
    ~/.all2md.toml
    ~/.all2md.json

    """
    paths = []

    # Current working directory
    cwd = Path.cwd()
    for filename in CONFIG_FILENAMES:
        paths.append(cwd / filename)

    # Home directory
    home = Path.home()
    for filename in CONFIG_FILENAMES:
        paths.append(home / filename)

    return paths
