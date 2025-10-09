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
from pathlib import Path

from all2md.constants import AttachmentMode
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
    read_allowlist : list[str]
        List of allowed read directory paths (default: current working directory)
    write_allowlist : list[str]
        List of allowed write directory paths (default: current working directory)
    attachment_mode : AttachmentMode
        How to handle attachments (skip|alt_text|download|base64)
    attachment_output_dir : str | None
        Directory for downloaded attachments (must be in write allowlist if download mode)
    disable_network : bool
        Whether to disable network access globally
    log_level : str
        Logging level (DEBUG|INFO|WARNING|ERROR)

    """

    enable_to_md: bool = True
    enable_from_md: bool = False  # Disabled by default for security (writing)
    read_allowlist: list[str] | None = None  # Will be set to CWD if None
    write_allowlist: list[str] | None = None  # Will be set to CWD if None
    attachment_mode: AttachmentMode = "alt_text"
    attachment_output_dir: str | None = None
    disable_network: bool = True
    log_level: str = "INFO"

    def validate(self) -> None:
        """Validate configuration consistency.

        Raises
        ------
        ValueError
            If configuration is invalid

        """
        # Validate attachment_mode is one of the allowed values
        allowed_attachment_modes = ('skip', 'alt_text', 'download', 'base64')
        if self.attachment_mode not in allowed_attachment_modes:
            raise ValueError(
                f"Invalid attachment_mode: {self.attachment_mode}. "
                f"Must be one of: {', '.join(allowed_attachment_modes)}"
            )

        # At least one tool must be enabled
        if not self.enable_to_md and not self.enable_from_md:
            raise ValueError("At least one tool must be enabled (to_md or from_md)")

        # Attachment output dir required for download mode
        if self.attachment_mode == "download":
            if not self.attachment_output_dir:
                raise ValueError("attachment_output_dir required when attachment_mode=download")

            # Verify it's a valid directory path
            try:
                resolved_path = Path(self.attachment_output_dir).resolve(strict=True)
            except (OSError, RuntimeError) as e:
                raise ValueError(
                    f"attachment_output_dir must exist: {self.attachment_output_dir}"
                ) from e

            # Ensure it's a directory, not a file
            if not resolved_path.is_dir():
                raise ValueError(
                    f"attachment_output_dir must be a directory, not a file: {self.attachment_output_dir}"
                )

            # If write allowlist exists, verify attachment dir is in it
            if self.write_allowlist is not None:
                attachment_dir_resolved = resolved_path
                write_dirs_resolved = [Path(p).resolve() for p in self.write_allowlist]

                in_allowlist = False
                for allowed_dir in write_dirs_resolved:
                    try:
                        attachment_dir_resolved.relative_to(allowed_dir)
                        in_allowlist = True
                        break
                    except ValueError:
                        continue

                if not in_allowlist:
                    raise ValueError(
                        f"attachment_output_dir must be within write allowlist: {self.attachment_output_dir}"
                    )


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

    parts = [p.strip() for p in value.split(';') if p.strip()]
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
    return value.lower() in ('true', '1', 'yes', 't', 'on')


def _validate_attachment_mode(value: str | None, default: AttachmentMode = "alt_text") -> AttachmentMode:
    """Validate and normalize attachment mode string.

    Parameters
    ----------
    value : str | None
        Attachment mode string
    default : AttachmentMode, default "alt_text"
        Default value if input is None

    Returns
    -------
    AttachmentMode
        Validated attachment mode

    Raises
    ------
    ValueError
        If value is not a valid attachment mode

    """
    if value is None:
        return default

    # Normalize to lowercase for case-insensitive comparison
    normalized = value.lower().strip()

    # Valid attachment modes
    valid_modes = ('skip', 'alt_text', 'download', 'base64')

    if normalized not in valid_modes:
        raise ValueError(
            f"Invalid attachment mode: {value!r}. "
            f"Must be one of: {', '.join(valid_modes)}"
        )

    return normalized  # type: ignore[return-value]


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
    valid_levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')

    if normalized not in valid_levels:
        raise ValueError(
            f"Invalid log level: {value!r}. "
            f"Must be one of: {', '.join(valid_levels)}"
        )

    return normalized


def load_config_from_env() -> MCPConfig:
    """Load configuration from environment variables.

    Returns
    -------
    MCPConfig
        Configuration loaded from environment

    """
    # Get allowlists from env, defaulting to CWD if not specified
    read_allowlist = _parse_semicolon_list(os.getenv('ALL2MD_MCP_ALLOWED_READ_DIRS'))
    write_allowlist = _parse_semicolon_list(os.getenv('ALL2MD_MCP_ALLOWED_WRITE_DIRS'))

    # Default to CWD if no allowlists specified
    cwd = os.getcwd()
    if read_allowlist is None:
        read_allowlist = [cwd]
    if write_allowlist is None:
        write_allowlist = [cwd]

    return MCPConfig(
        enable_to_md=_str_to_bool(os.getenv('ALL2MD_MCP_ENABLE_TO_MD'), default=True),
        enable_from_md=_str_to_bool(os.getenv('ALL2MD_MCP_ENABLE_FROM_MD'), default=False),  # Disabled by default
        read_allowlist=read_allowlist,
        write_allowlist=write_allowlist,
        attachment_mode=_validate_attachment_mode(os.getenv('ALL2MD_MCP_ATTACHMENT_MODE'), default='alt_text'),
        attachment_output_dir=os.getenv('ALL2MD_MCP_ATTACHMENT_OUTPUT_DIR'),
        disable_network=_str_to_bool(os.getenv('ALL2MD_DISABLE_NETWORK'), default=True),
        log_level=_validate_log_level(os.getenv('ALL2MD_MCP_LOG_LEVEL'), default='INFO'),
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create argument parser for MCP server CLI.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser

    """
    parser = argparse.ArgumentParser(
        prog='all2md-mcp',
        description='MCP server for all2md document conversion library',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  ALL2MD_MCP_ENABLE_TO_MD          Enable convert_to_markdown tool (default: true)
  ALL2MD_MCP_ENABLE_FROM_MD        Enable render_from_markdown tool (default: false)
  ALL2MD_MCP_ALLOWED_READ_DIRS     Semicolon-separated read allowlist paths
  ALL2MD_MCP_ALLOWED_WRITE_DIRS    Semicolon-separated write allowlist paths
  ALL2MD_MCP_ATTACHMENT_MODE       Attachment handling mode (default: alt_text)
  ALL2MD_MCP_ATTACHMENT_OUTPUT_DIR Directory for downloaded attachments
  ALL2MD_DISABLE_NETWORK           Disable network access (default: true)
  ALL2MD_MCP_LOG_LEVEL             Logging level (default: INFO)

Examples:
  # Basic usage (defaults to current working directory)
  all2md-mcp

  # With specific read/write directories
  all2md-mcp --enable-from-md --read-dirs "/home/user/documents" --write-dirs "/home/user/output"

  # Create temporary workspace (recommended for LLM usage)
  all2md-mcp --temp

  # Download attachments mode
  all2md-mcp --temp --attachment-mode download

  # Enable writing/rendering (disabled by default)
  all2md-mcp --temp --enable-from-md
        """
    )

    # Workspace setup
    parser.add_argument(
        '--temp',
        action='store_true',
        help='Create temporary workspace directory for LLM (sets read/write allowlists to temp dir)'
    )

    # Tool toggles
    to_md_group = parser.add_mutually_exclusive_group()
    to_md_group.add_argument(
        '--enable-to-md',
        action='store_true',
        dest='enable_to_md',
        help='Enable convert_to_markdown tool (default: true unless --no-to-md)'
    )
    to_md_group.add_argument(
        '--no-to-md',
        action='store_false',
        dest='enable_to_md',
        help='Disable convert_to_markdown tool'
    )
    parser.set_defaults(enable_to_md=None)  # None = use env default

    from_md_group = parser.add_mutually_exclusive_group()
    from_md_group.add_argument(
        '--enable-from-md',
        action='store_true',
        dest='enable_from_md',
        help='Enable render_from_markdown tool (default: true unless --no-from-md)'
    )
    from_md_group.add_argument(
        '--no-from-md',
        action='store_false',
        dest='enable_from_md',
        help='Disable render_from_markdown tool'
    )
    parser.set_defaults(enable_from_md=None)  # None = use env default

    # Path allowlists
    parser.add_argument(
        '--read-dirs',
        type=str,
        metavar='PATHS',
        help='Semicolon-separated list of allowed read directories'
    )

    parser.add_argument(
        '--write-dirs',
        type=str,
        metavar='PATHS',
        help='Semicolon-separated list of allowed write directories'
    )

    # Attachment settings (server-level only, not per-call)
    parser.add_argument(
        '--attachment-mode',
        type=str,
        choices=['skip', 'alt_text', 'download', 'base64'],
        help='How to handle attachments (default: alt_text)'
    )

    parser.add_argument(
        '--attachment-output-dir',
        type=str,
        metavar='DIR',
        help='Directory for downloaded attachments (must be in write allowlist)'
    )

    # Network control
    network_group = parser.add_mutually_exclusive_group()
    network_group.add_argument(
        '--allow-network',
        action='store_false',
        dest='disable_network',
        help='Allow network access (default: network disabled)'
    )
    network_group.add_argument(
        '--disable-network',
        action='store_true',
        dest='disable_network',
        help='Disable network access (default: true)'
    )
    parser.set_defaults(disable_network=None)  # None = use env default

    # Logging
    parser.add_argument(
        '--log-level',
        type=str,
        help='Logging level: DEBUG, INFO, WARNING, ERROR (case-insensitive, default: INFO)'
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
    if hasattr(args, 'temp') and args.temp:
        # Create temporary directory for workspace
        temp_dir = tempfile.mkdtemp(prefix="all2md-mcp-workspace-")
        logger.info(f"Created temporary workspace: {temp_dir}")

        # Set both read and write allowlists to temp directory
        updated_kwargs.update(read_allowlist=[temp_dir], write_allowlist=[temp_dir])

        # Create attachments subdirectory if in download mode
        if config.attachment_mode == "download" and not config.attachment_output_dir:
            attachment_dir = Path(temp_dir) / "attachments"
            attachment_dir.mkdir(exist_ok=True)
            updated_kwargs.update(attachment_output_dir=str(attachment_dir))
            logger.info(f"Created attachments directory: {attachment_dir}")

    # Override with explicit CLI args (only if provided, takes precedence over --temp)
    if args.enable_to_md is not None:
        updated_kwargs.update(enable_to_md=args.enable_to_md)

    if args.enable_from_md is not None:
        updated_kwargs.update(enable_from_md=args.enable_from_md)

    if args.read_dirs is not None:
        updated_kwargs.update(read_allowlist=_parse_semicolon_list(args.read_dirs))

    if args.write_dirs is not None:
        updated_kwargs.update(write_allowlist=_parse_semicolon_list(args.write_dirs))

    if args.attachment_mode is not None:
        updated_kwargs.update(attachment_mode=_validate_attachment_mode(args.attachment_mode))

    if args.attachment_output_dir is not None:
        updated_kwargs.update(attachment_output_dir=args.attachment_output_dir)

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
