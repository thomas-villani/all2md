#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Configuration file discovery and loading for all2md CLI.

This module handles automatic discovery of configuration files, loading
configs from JSON or TOML format, and merging configurations with proper
priority handling.
"""

import argparse
import json
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]
from typing import Any, Dict, Optional

import yaml

CONFIG_FILENAMES = [".all2md.toml", ".all2md.yaml", ".all2md.yml", ".all2md.json", "pyproject.toml"]


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
