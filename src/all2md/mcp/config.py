"""Configuration management for MCP server.

This module handles configuration from environment variables and CLI arguments,
with CLI arguments taking precedence over environment variables.

All configuration is set at server startup and cannot be changed per-tool-call
for security reasons.

Classes
-------
- MCPConfig: Server configuration with security settings

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import logging
import os
import tempfile
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import cast

from all2md.options.base import CloneFrozenMixin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPConfig(CloneFrozenMixin):
    """MCP server configuration.

    All settings are immutable after server startup for security.

    Attributes
    ----------
    enable_to_md : bool
        Whether to enable convert_to_markdown tool (default: True)
    enable_from_md : bool
        Whether to enable render_from_markdown tool (default: False for security)
    enable_doc_edit : bool
        Whether to enable edit_document tool (default: False for security)
    read_allowlist : list[str | Path] | None
        List of allowed read directory paths. Initially strings from env/CLI,
        then converted to resolved Path objects by prepare_allowlist_dirs.
    write_allowlist : list[str | Path] | None
        List of allowed write directory paths. Initially strings from env/CLI,
        then converted to resolved Path objects by prepare_allowlist_dirs.
    include_images : bool
        Whether to include images in the output for vLLM visibility.
        - True: Images embedded as base64 (vLLMs can see them)
        - False: Images replaced with alt text only
        Default: False (opt-in for vision-enabled LLMs).
        Note: With disable_network=True (default), only works for embedded
        images (PDF, DOCX, PPTX), not for external HTML images that require fetching.
    flavor : str
        Markdown flavor/dialect to use (gfm, commonmark, multimarkdown, pandoc, kramdown, markdown_plus).
        Default: "gfm" (GitHub Flavored Markdown)
    disable_network : bool
        Whether to disable network access globally. When True (default), prevents
        fetching external images from HTML files, but embedded images in PDF/DOCX/PPTX
        will still work with base64 mode.
    log_level : str
        Logging level (DEBUG|INFO|WARNING|ERROR)

    """

    enable_to_md: bool = True
    enable_from_md: bool = False  # Disabled by default for security (writing)
    enable_doc_edit: bool = False  # Disabled by default for security (document manipulation)
    read_allowlist: list[str | Path] | None = None  # Will be set to CWD if None, then to Path objects
    write_allowlist: list[str | Path] | None = None  # Will be set to CWD if None, then to Path objects
    include_images: bool = False  # Enable for vision-enabled LLMs
    flavor: str = "gfm"  # Default to GitHub Flavored Markdown
    disable_network: bool = True
    log_level: str = "INFO"

    def validate(self) -> None:
        """Validate configuration consistency.

        Raises
        ------
        ValueError
            If configuration is invalid

        """
        # Validate flavor
        allowed_flavors = ("gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus")
        if self.flavor not in allowed_flavors:
            raise ValueError(f"Invalid flavor: {self.flavor}. " f"Must be one of: {', '.join(allowed_flavors)}")

        # At least one tool must be enabled
        if not self.enable_to_md and not self.enable_from_md and not self.enable_doc_edit:
            raise ValueError("At least one tool must be enabled (to_md, from_md, or doc_edit)")


def _parse_semicolon_list(value: str | None) -> list[str] | None:
    """Parse semicolon-separated list from environment variable or CLI.

    Parameters
    ----------
    value : str | None
        Semicolon-separated string or None

    Returns
    -------
    list[str] | None
        List of strings, or None if value was None or empty

    """
    if not value:
        return None

    parts = [p.strip() for p in value.split(";") if p.strip()]
    return parts if parts else None


def _str_to_bool(value: str | None, default: bool = False) -> bool:
    """Convert string to boolean.

    Parameters
    ----------
    value : str | None
        String value (True iif: "true", "t", "1", "yes", "on")
    default : bool, default False
        Default value if input is None

    Returns
    -------
    bool
        Boolean value

    """
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "t", "on")


def _validate_log_level(value: str | None, default: str = "INFO") -> str:
    """Validate and normalize log level string.

    Parameters
    ----------
    value : str | None
        Log level string
    default : str, default "INFO"
        Default value if input is None

    Returns
    -------
    str
        Validated and uppercase log level

    Raises
    ------
    ValueError
        If value is not a valid log level

    """
    if value is None:
        return default

    # Normalize to uppercase
    normalized = value.upper().strip()

    # Valid log levels
    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    if normalized not in valid_levels:
        raise ValueError(f"Invalid log level: {value!r}. " f"Must be one of: {', '.join(valid_levels)}")

    return normalized


def _validate_flavor(value: str | None, default: str = "gfm") -> str:
    """Validate and normalize markdown flavor string.

    Parameters
    ----------
    value : str | None
        Markdown flavor string
    default : str, default "gfm"
        Default value if input is None

    Returns
    -------
    str
        Validated and lowercase flavor

    Raises
    ------
    ValueError
        If value is not a valid flavor

    """
    if value is None:
        return default

    # Normalize to lowercase
    normalized = value.lower().strip()

    # Valid flavors
    valid_flavors = ("gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus")

    if normalized not in valid_flavors:
        raise ValueError(f"Invalid markdown flavor: {value!r}. " f"Must be one of: {', '.join(valid_flavors)}")

    return normalized


def load_config_from_env() -> MCPConfig:
    """Load configuration from environment variables.

    Returns
    -------
    MCPConfig
        Configuration loaded from environment

    """
    # Get allowlists from env, defaulting to CWD if not specified
    read_allowlist_strs = _parse_semicolon_list(os.getenv("ALL2MD_MCP_ALLOWED_READ_DIRS"))
    write_allowlist_strs = _parse_semicolon_list(os.getenv("ALL2MD_MCP_ALLOWED_WRITE_DIRS"))

    # Default to CWD if no allowlists specified
    cwd = os.getcwd()
    if read_allowlist_strs is None:
        read_allowlist_strs = [cwd]
    if write_allowlist_strs is None:
        write_allowlist_strs = [cwd]

    return MCPConfig(
        enable_to_md=_str_to_bool(os.getenv("ALL2MD_MCP_ENABLE_TO_MD"), default=True),
        enable_from_md=_str_to_bool(os.getenv("ALL2MD_MCP_ENABLE_FROM_MD"), default=False),  # Disabled by default
        enable_doc_edit=_str_to_bool(os.getenv("ALL2MD_MCP_ENABLE_DOC_EDIT"), default=False),  # Disabled by default
        # Will be validated and converted to Path objects by prepare_allowlist_dirs
        read_allowlist=cast(list[str | Path], read_allowlist_strs),
        # Will be validated and converted to Path objects by prepare_allowlist_dirs
        write_allowlist=cast(list[str | Path], write_allowlist_strs),
        include_images=_str_to_bool(os.getenv("ALL2MD_MCP_INCLUDE_IMAGES"), default=False),
        flavor=_validate_flavor(os.getenv("ALL2MD_MCP_FLAVOR"), default="gfm"),
        disable_network=_str_to_bool(os.getenv("ALL2MD_DISABLE_NETWORK"), default=True),
        log_level=_validate_log_level(os.getenv("ALL2MD_MCP_LOG_LEVEL"), default="INFO"),
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create argument parser for MCP server CLI.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser

    """
    parser = argparse.ArgumentParser(
        prog="all2md-mcp",
        description="MCP server for all2md document conversion library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  ALL2MD_MCP_ENABLE_TO_MD          Enable convert_to_markdown tool (default: true)
  ALL2MD_MCP_ENABLE_FROM_MD        Enable render_from_markdown tool (default: false)
  ALL2MD_MCP_ENABLE_DOC_EDIT       Enable edit_document tool (default: false)
  ALL2MD_MCP_ALLOWED_READ_DIRS     Semicolon-separated read allowlist paths
  ALL2MD_MCP_ALLOWED_WRITE_DIRS    Semicolon-separated write allowlist paths
  ALL2MD_MCP_INCLUDE_IMAGES        Include images in output for vLLM visibility (default: false)
  ALL2MD_MCP_FLAVOR                Markdown flavor: gfm, commonmark, multimarkdown, pandoc, kramdown,
                                   markdown_plus (default: gfm)
  ALL2MD_DISABLE_NETWORK           Disable network access (default: true)
  ALL2MD_MCP_LOG_LEVEL             Logging level (default: INFO)

Examples:
  # Basic usage (defaults to current working directory)
  all2md-mcp

  # With specific read/write directories
  all2md-mcp --enable-from-md --read-dirs "/home/user/documents" --write-dirs "/home/user/output"

  # Create temporary workspace (recommended for LLM usage)
  all2md-mcp --temp

  # Disable image inclusion (use alt text only)
  all2md-mcp --temp --no-include-images

  # Enable writing/rendering (disabled by default)
  all2md-mcp --temp --enable-from-md
        """,
    )

    # Version flag
    try:
        version_string = f'all2md-mcp {version("all2md")}'
    except Exception:
        version_string = "all2md-mcp (version unknown)"

    parser.add_argument("--version", action="version", version=version_string)

    # Workspace setup
    parser.add_argument(
        "--temp",
        action="store_true",
        help="Create temporary workspace directory for LLM (sets read/write allowlists to temp dir)",
    )

    # Tool toggles
    to_md_group = parser.add_mutually_exclusive_group()
    to_md_group.add_argument(
        "--enable-to-md",
        action="store_true",
        dest="enable_to_md",
        help="Enable convert_to_markdown tool (default: true unless --no-to-md)",
    )
    to_md_group.add_argument(
        "--no-to-md", action="store_false", dest="enable_to_md", help="Disable convert_to_markdown tool"
    )
    parser.set_defaults(enable_to_md=None)  # None = use env default

    from_md_group = parser.add_mutually_exclusive_group()
    from_md_group.add_argument(
        "--enable-from-md",
        action="store_true",
        dest="enable_from_md",
        help="Enable render_from_markdown tool (default: false for security)",
    )
    from_md_group.add_argument(
        "--no-from-md", action="store_false", dest="enable_from_md", help="Disable render_from_markdown tool"
    )
    parser.set_defaults(enable_from_md=None)  # None = use env default

    doc_edit_group = parser.add_mutually_exclusive_group()
    doc_edit_group.add_argument(
        "--enable-doc-edit",
        action="store_true",
        dest="enable_doc_edit",
        help="Enable edit_document tool for document manipulation (default: false for security)",
    )
    doc_edit_group.add_argument(
        "--no-doc-edit", action="store_false", dest="enable_doc_edit", help="Disable edit_document tool"
    )
    parser.set_defaults(enable_doc_edit=None)  # None = use env default

    # Path allowlists
    parser.add_argument(
        "--read-dirs", type=str, metavar="PATHS", help="Semicolon-separated list of allowed read directories"
    )

    parser.add_argument(
        "--write-dirs", type=str, metavar="PATHS", help="Semicolon-separated list of allowed write directories"
    )

    # Image inclusion settings (server-level only, not per-call)
    include_images_group = parser.add_mutually_exclusive_group()
    include_images_group.add_argument(
        "--include-images",
        action="store_true",
        dest="include_images",
        help="Include images in output for vLLM visibility (default: false)",
    )
    include_images_group.add_argument(
        "--no-include-images",
        action="store_false",
        dest="include_images",
        help="Do not include images, use alt text only",
    )
    parser.set_defaults(include_images=None)  # None = use env default

    # Markdown flavor
    parser.add_argument(
        "--flavor",
        type=str,
        choices=["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"],
        help="Markdown flavor/dialect to use (default: gfm)",
    )

    # Network control
    network_group = parser.add_mutually_exclusive_group()
    network_group.add_argument(
        "--allow-network",
        action="store_false",
        dest="disable_network",
        help="Allow network access (default: network disabled)",
    )
    network_group.add_argument(
        "--disable-network", action="store_true", dest="disable_network", help="Disable network access (default: true)"
    )
    parser.set_defaults(disable_network=None)  # None = use env default

    # Logging
    parser.add_argument(
        "--log-level", type=str, help="Logging level: DEBUG, INFO, WARNING, ERROR (case-insensitive, default: INFO)"
    )

    return parser


def load_config_from_args(args: argparse.Namespace) -> MCPConfig:
    """Load configuration from parsed CLI arguments, using env as fallback.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments

    Returns
    -------
    MCPConfig
        Merged configuration (CLI overrides env)

    """
    # Start with env config as base
    config = load_config_from_env()

    updated_kwargs: dict[str, object] = {}

    # Handle --temp flag first (creates temporary workspace)
    if hasattr(args, "temp") and args.temp:
        # Create temporary directory for workspace
        temp_dir = tempfile.mkdtemp(prefix="all2md-mcp-workspace-")
        logger.info(f"Created temporary workspace: {temp_dir}")

        # Set both read and write allowlists to temp directory
        updated_kwargs.update(read_allowlist=[temp_dir], write_allowlist=[temp_dir])

    # Override with explicit CLI args (only if provided, takes precedence over --temp)
    if args.enable_to_md is not None:
        updated_kwargs.update(enable_to_md=args.enable_to_md)

    if args.enable_from_md is not None:
        updated_kwargs.update(enable_from_md=args.enable_from_md)

    if args.enable_doc_edit is not None:
        updated_kwargs.update(enable_doc_edit=args.enable_doc_edit)

    if args.read_dirs is not None:
        updated_kwargs.update(read_allowlist=_parse_semicolon_list(args.read_dirs))

    if args.write_dirs is not None:
        updated_kwargs.update(write_allowlist=_parse_semicolon_list(args.write_dirs))

    if args.include_images is not None:
        updated_kwargs.update(include_images=args.include_images)

    if hasattr(args, "flavor") and args.flavor is not None:
        updated_kwargs.update(flavor=_validate_flavor(args.flavor))

    if args.disable_network is not None:
        updated_kwargs.update(disable_network=args.disable_network)

    if args.log_level is not None:
        updated_kwargs.update(log_level=_validate_log_level(args.log_level))

    if updated_kwargs:
        config = config.create_updated(**updated_kwargs)

    return config


def load_config() -> MCPConfig:
    """Load and validate configuration from CLI args and environment.

    Returns
    -------
    MCPConfig
        Validated configuration

    Raises
    ------
    ValueError
        If configuration is invalid

    """
    parser = create_argument_parser()
    args = parser.parse_args()
    config = load_config_from_args(args)
    config.validate()

    return config
