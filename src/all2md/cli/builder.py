#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Dynamic CLI argument builder for all2md.

This module provides a system for automatically generating CLI arguments
from dataclass options using field metadata.
"""

import argparse
import difflib
import logging
import sys
import types
import warnings
from dataclasses import MISSING, fields, is_dataclass
from typing import Annotated, Any, Dict, Optional, Type, Union, get_args, get_origin, get_type_hints

from all2md.cli.custom_actions import (
    TrackingAppendAction,
    TrackingPositiveIntAction,
    TrackingStoreAction,
    TrackingStoreFalseAction,
    TrackingStoreTrueAction,
)
from all2md.constants import DocumentFormat
from all2md.converter_registry import registry
from all2md.options.markdown import MarkdownOptions

# Module logger for consistent warning/error reporting
logger = logging.getLogger(__name__)


class DynamicCLIBuilder:
    """Builds CLI arguments dynamically from options dataclasses.

    This class introspects converter options dataclasses and their metadata
    to automatically generate argparse arguments, eliminating the need for
    hard-coded CLI argument definitions.
    """

    def __init__(self) -> None:
        """Initialize the CLI builder."""
        self.parser: Optional[argparse.ArgumentParser] = None
        self.dest_to_cli_flag: Dict[str, str] = {}  # Maps dest names to actual CLI flags

    def _has_default(self, field: Any) -> bool:
        """Check if a dataclass field has a default value.

        Properly handles dataclasses.MISSING to avoid incorrect comparisons.

        Parameters
        ----------
        field : Field
            Dataclass field to check

        Returns
        -------
        bool
            True if field has a default value or default_factory

        """
        return field.default is not MISSING or field.default_factory is not MISSING

    def _get_default(self, field: Any) -> Any:
        """Safely get the default value from a dataclass field.

        Parameters
        ----------
        field : Field
            Dataclass field

        Returns
        -------
        Any
            Default value, or MISSING if no default

        """
        if field.default is not MISSING:
            return field.default
        elif field.default_factory is not MISSING:
            # For default_factory, we don't call it - just indicate it exists
            return field.default_factory
        return MISSING

    def _resolve_field_type(self, field: Any, options_class: Type) -> Type:
        """Resolve field type using typing.get_type_hints for robust type handling.

        This method replaces brittle string matching with proper type resolution
        that works with 'from __future__ import annotations'.

        Parameters
        ----------
        field : Field
            Dataclass field to resolve type for
        options_class : Type
            The dataclass containing the field

        Returns
        -------
        Type
            Resolved field type

        """
        try:
            # Use get_type_hints to resolve string annotations
            type_hints = get_type_hints(options_class)
            if field.name in type_hints:
                return type_hints[field.name]
        except (NameError, AttributeError):
            # Fallback if type hints can't be resolved
            pass

        # Fallback to the raw field.type
        return field.type

    def _handle_optional_type(self, field_type: Type) -> tuple[Type, bool]:
        """Handle Optional/Union types to extract the underlying type.

        Supports both typing.Union and PEP 604 unions (X | Y), as well as
        Annotated types.

        Parameters
        ----------
        field_type : Type
            Type annotation to analyze

        Returns
        -------
        tuple[Type, bool]
            Tuple of (underlying_type, is_optional)

        """
        # Handle Annotated[T, ...] by unwrapping to the underlying type
        origin = get_origin(field_type)
        if origin is Annotated:
            args = get_args(field_type)
            if args:
                # Recursively handle the unwrapped type
                return self._handle_optional_type(args[0])

        # Handle Union types (including Optional which is Union[T, None])
        # This handles both typing.Union and PEP 604 unions (X | Y -> types.UnionType)
        if origin is Union or origin is types.UnionType:
            args = get_args(field_type)
            if type(None) in args:
                # This is Optional[SomeType] (Union[SomeType, None] or SomeType | None)
                # Extract the non-None type
                underlying_type = next(arg for arg in args if arg is not type(None))
                return underlying_type, True
            else:
                # Non-Optional Union - return as-is
                return field_type, False

        # Handle other generic types with origin (like list[int])
        if origin is not None:
            return field_type, False

        # Regular type
        return field_type, False

    def _infer_argument_type_and_action(
            self, field: Any, resolved_type: Type,
            is_optional: bool, metadata: Dict[str, Any],
            cli_name: str
            ) -> Dict[str, Any]:
        """Infer argparse type and action from resolved field type.

        Parameters
        ----------
        field : Field
            Dataclass field
        resolved_type : Type
            Resolved field type
        is_optional : bool
            Whether the type is Optional
        metadata : dict
            Field metadata
        cli_name : str
            CLI argument name

        Returns
        -------
        dict
            Argparse kwargs for type and action

        """
        kwargs: Dict[str, Any] = {}

        # Handle boolean fields
        if resolved_type is bool:
            # Safely get default value, checking for MISSING
            if self._has_default(field):
                default_value = self._get_default(field)
                if default_value is True and '-no-' in cli_name:
                    # For --no-* flags (True defaults), use store_false
                    kwargs['action'] = 'store_false'
                elif default_value is False:
                    # For regular boolean flags (False defaults), use store_true
                    kwargs['action'] = 'store_true'
                else:
                    # For other boolean values, use type conversion
                    kwargs['type'] = lambda x: x.lower() in ('true', '1', 'yes')
            else:
                # No default specified - use store_true with False default
                kwargs['action'] = 'store_true'

        # Handle choices from metadata
        elif 'choices' in metadata:
            kwargs['choices'] = metadata['choices']

        # Handle list types using modern typing introspection
        elif get_origin(resolved_type) is list:
            # Get the list item type if available
            args = get_args(resolved_type)
            if args:
                item_type = args[0]
                if item_type is int:
                    # Add type function to parse comma-separated integers
                    def parse_int_list(value: str) -> list[int]:
                        try:
                            return [int(x.strip()) for x in value.split(',')]
                        except ValueError as e:
                            raise argparse.ArgumentTypeError(
                                f"Expected comma-separated integers, got: {value}"
                            ) from e
                    kwargs['type'] = parse_int_list
                    kwargs['help'] = kwargs.get('help', '') + ' (comma-separated integers)'
                else:
                    # Add type function to parse comma-separated strings
                    def parse_str_list(value: str) -> list[str]:
                        return [x.strip() for x in value.split(',') if x.strip()]
                    kwargs['type'] = parse_str_list
                    kwargs['help'] = kwargs.get('help', '') + ' (comma-separated values)'
            else:
                # Fallback for untyped lists
                def parse_str_list_fallback(value: str) -> list[str]:
                    return [x.strip() for x in value.split(',') if x.strip()]
                kwargs['type'] = parse_str_list_fallback
                kwargs['help'] = kwargs.get('help', '') + ' (comma-separated values)'

        # Handle special metadata types (legacy support for list_int)
        elif metadata.get('type') == 'list_int':
            # Add type function to parse comma-separated integers
            def parse_legacy_int_list(value: str) -> list[int]:
                try:
                    return [int(x.strip()) for x in value.split(',')]
                except ValueError as e:
                    raise argparse.ArgumentTypeError(
                        f"Expected comma-separated integers, got: {value}"
                    ) from e
            kwargs['type'] = parse_legacy_int_list
            kwargs['help'] = kwargs.get('help', '') + ' (comma-separated integers)'

        # Handle basic types
        elif resolved_type in (int, float):
            kwargs['type'] = resolved_type
        elif resolved_type is str:
            # str is default, don't specify unless needed
            pass

        return kwargs

    def snake_to_kebab(self, name: str) -> str:
        """Convert snake_case to kebab-case.

        Parameters
        ----------
        name : str
            Snake case field name

        Returns
        -------
        str
            Kebab case CLI name

        """
        return name.replace('_', '-')

    def infer_cli_name(
            self, field_name: str, format_prefix: Optional[str] = None,
            is_boolean_with_true_default: bool = False
            ) -> str:
        """Infer CLI argument name from field name.

        Parameters
        ----------
        field_name : str
            Dataclass field name
        format_prefix : str, optional
            Format prefix (e.g., 'pdf', 'html')
        is_boolean_with_true_default : bool
            Whether this is a boolean field with default=True

        Returns
        -------
        str
            CLI argument name with -- prefix

        """
        # Convert to kebab-case
        kebab_name = self.snake_to_kebab(field_name)

        # Handle boolean flags with True defaults (use --no-* form)
        if is_boolean_with_true_default:
            if not kebab_name.startswith('no-'):
                kebab_name = f"no-{kebab_name}"

        # Add format prefix if provided (after no- prefix if applicable)
        if format_prefix:
            if is_boolean_with_true_default and kebab_name.startswith('no-'):
                # Format: --format-no-field-name
                base_name = kebab_name[3:]  # Remove 'no-' prefix
                kebab_name = f"{format_prefix}-no-{base_name}"
            else:
                # Format: --format-field-name
                kebab_name = f"{format_prefix}-{kebab_name}"

        return f"--{kebab_name}"

    def get_argument_kwargs(
            self, field: Any, metadata: Dict[str, Any], cli_name: str,
            options_class: Type
            ) -> Dict[str, Any]:
        """Build argparse kwargs from field metadata using robust type resolution.

        This method replaces brittle string matching with proper type introspection
        using typing.get_type_hints and helper methods.

        Parameters
        ----------
        field : Field
            Dataclass field
        metadata : dict
            Field metadata
        cli_name : str
            CLI argument name
        options_class : Type
            The dataclass containing the field

        Returns
        -------
        dict
            Kwargs for argparse.add_argument()

        """
        kwargs = {}

        # Help text is required
        kwargs['help'] = metadata.get('help', f'Configure {field.name}')

        # Resolve field type using robust type resolution
        resolved_type = self._resolve_field_type(field, options_class)
        underlying_type, is_optional = self._handle_optional_type(resolved_type)

        # Get type-based kwargs
        type_kwargs = self._infer_argument_type_and_action(
            field, underlying_type, is_optional, metadata, cli_name
        )
        kwargs.update(type_kwargs)

        # Handle metadata-specified types that override type inference
        if metadata.get('type') in (int, float):
            kwargs['type'] = metadata['type']

        # Honor metadata-specified action (e.g., append) if present
        # This allows fields to explicitly request append behavior
        if 'action' in metadata and not kwargs.get('action'):
            kwargs['action'] = metadata['action']

        # Set default if field has one (checking for MISSING)
        if self._has_default(field) and not kwargs.get('action'):
            default_val = self._get_default(field)
            # Only set if not MISSING and not a factory
            if default_val is not MISSING and not callable(default_val):
                kwargs['default'] = default_val

        return kwargs

    def _add_options_arguments_internal(
            self, parser: Union[argparse.ArgumentParser, argparse._ArgumentGroup],
            options_class: Type, format_prefix: Optional[str] = None,
            group_name: Optional[str] = None,
            exclude_base_fields: bool = False
            ) -> None:
        """Add arguments for an options dataclass.

        This unified implementation is used by both add_options_class_arguments
        and add_format_specific_options to eliminate code duplication.

        Parameters
        ----------
        parser : ArgumentParser or _ArgumentGroup
            Parser or argument group to add arguments to
        options_class : Type
            Options dataclass type
        format_prefix : str, optional
            Prefix for argument names (e.g., 'pdf')
        group_name : str, optional
            Name for argument group
        exclude_base_fields : bool, default=False
            If True, skip fields that are defined in BaseParserOptions

        """
        if not is_dataclass(options_class):
            return

        # Get BaseOptions fields to exclude if requested
        base_field_names = set()
        if exclude_base_fields:
            from all2md.options import BaseParserOptions
            base_field_names = {f.name for f in fields(BaseParserOptions)}

        # Create argument group if requested
        group: Union[argparse.ArgumentParser, argparse._ArgumentGroup]
        if group_name:
            group = parser.add_argument_group(group_name)
        else:
            group = parser

        for field in fields(options_class):
            # Skip BaseOptions fields if exclude_base_fields is True
            if exclude_base_fields and field.name in base_field_names:
                continue

            metadata: Dict[str, Any] = dict(field.metadata) if field.metadata else {}

            # Skip excluded fields
            if metadata.get('exclude_from_cli', False):
                # Check if this is a nested dataclass we should handle
                field_type = self._resolve_field_type(field, options_class)
                field_type, _ = self._handle_optional_type(field_type)

                if is_dataclass(field_type):
                    # Handle nested dataclass by flattening its fields
                    kebab_name = self.snake_to_kebab(field.name)
                    nested_prefix = f"{format_prefix}-{kebab_name}" if format_prefix else kebab_name
                    self._add_options_arguments_internal(
                        group,  # Use parent group instead of parser
                        field_type,
                        format_prefix=nested_prefix,
                        group_name=None,  # Don't create separate groups for nested classes
                        exclude_base_fields=exclude_base_fields
                    )
                continue

            # Skip markdown_options field - handled separately
            if field.name == 'markdown_options':
                continue

            # Determine if this is a boolean with True default for --no-* handling
            # Use resolved type instead of raw field.type for robust handling
            resolved_field_type = self._resolve_field_type(field, options_class)
            underlying_field_type, _ = self._handle_optional_type(resolved_field_type)
            # Check for MISSING before accessing field.default
            is_bool_true_default = (
                underlying_field_type is bool and
                self._has_default(field) and
                self._get_default(field) is True
            )

            # Get CLI name (explicit or inferred)
            if 'cli_name' in metadata:
                cli_meta_name = metadata['cli_name']
                if cli_meta_name.startswith('no-'):
                    cli_name = f"--{format_prefix}-{cli_meta_name}" if format_prefix else f"--{cli_meta_name}"
                else:
                    cli_name = f"--{format_prefix}-{cli_meta_name}" if format_prefix else f"--{cli_meta_name}"
            else:
                cli_name = self.infer_cli_name(field.name, format_prefix, is_bool_true_default)

            # Build argument kwargs
            kwargs = self.get_argument_kwargs(field, metadata, cli_name, options_class)

            # Set dest using dot notation for better structure mapping
            # and use tracking actions for booleans and append
            if 'action' in kwargs:
                if kwargs['action'] == 'store_true':
                    kwargs['action'] = TrackingStoreTrueAction
                    if format_prefix:
                        kwargs['dest'] = f"{format_prefix}.{field.name}"
                    else:
                        kwargs['dest'] = field.name
                elif kwargs['action'] == 'store_false':
                    kwargs['action'] = TrackingStoreFalseAction
                    if format_prefix:
                        kwargs['dest'] = f"{format_prefix}.{field.name}"
                    else:
                        kwargs['dest'] = field.name
                elif kwargs['action'] == 'append':
                    kwargs['action'] = TrackingAppendAction
                    if format_prefix:
                        kwargs['dest'] = f"{format_prefix}.{field.name}"
                    else:
                        kwargs['dest'] = field.name
            else:
                # For non-boolean arguments, use TrackingStoreAction
                kwargs['action'] = TrackingStoreAction
                if format_prefix:
                    kwargs['dest'] = f"{format_prefix}.{field.name}"
                else:
                    kwargs['dest'] = field.name

            # Add the argument
            try:
                group.add_argument(cli_name, **kwargs)
                # Track mapping from dest name to actual CLI flag for better suggestions
                if 'dest' in kwargs:
                    self.dest_to_cli_flag[kwargs['dest']] = cli_name
            except Exception as e:
                logger.warning(f"Could not add argument {cli_name}: {e}")

    def add_options_class_arguments(
            self, parser: argparse.ArgumentParser,
            options_class: Type, format_prefix: Optional[str] = None,
            group_name: Optional[str] = None
            ) -> None:
        """Add arguments for an options dataclass.

        Parameters
        ----------
        parser : ArgumentParser
            Parser to add arguments to
        options_class : Type
            Options dataclass type
        format_prefix : str, optional
            Prefix for argument names (e.g., 'pdf')
        group_name : str, optional
            Name for argument group

        """
        self._add_options_arguments_internal(
            parser, options_class, format_prefix, group_name, exclude_base_fields=False
        )

    def add_format_specific_options(
            self, parser: argparse.ArgumentParser,
            options_class: Type, format_prefix: Optional[str] = None,
            group_name: Optional[str] = None
            ) -> None:
        """Add arguments for format-specific options, excluding BaseOptions fields.

        Parameters
        ----------
        parser : ArgumentParser
            Parser to add arguments to
        options_class : Type
            Options dataclass type
        format_prefix : str, optional
            Prefix for argument names (e.g., 'pdf')
        group_name : str, optional
            Name for argument group

        """
        self._add_options_arguments_internal(
            parser, options_class, format_prefix, group_name, exclude_base_fields=True
        )

    def add_transform_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add transform-related CLI arguments.

        Adds --transform flag and dynamic transform parameter arguments based
        on discovered transforms and their metadata.

        Parameters
        ----------
        parser : ArgumentParser
            Parser to add transform arguments to

        """
        try:
            from all2md.transforms import registry as transform_registry
        except ImportError:
            # Transform system not available, skip
            return

        # Add --transform flag (repeatable, ordered) with tracking
        parser.add_argument(
            '--transform', '-t',
            action=TrackingAppendAction,
            dest='transforms',
            metavar='NAME',
            help='Apply transform to AST before rendering (repeatable, order matters). '
                 'Use "all2md list-transforms" to see available transforms.'
        )

        # Create transform options group if we have transforms
        transform_names = transform_registry.list_transforms()
        if not transform_names:
            return

        transform_group = parser.add_argument_group('Transform options')

        # For each transform, add parameter arguments based on ParameterSpec
        for transform_name in transform_names:
            try:
                metadata = transform_registry.get_metadata(transform_name)

                for param_name, param_spec in metadata.parameters.items():
                    if not param_spec.cli_flag:
                        continue

                    # Build argparse kwargs from ParameterSpec
                    kwargs: Dict[str, Any] = {
                        'help': param_spec.help or f'{param_name} parameter for {transform_name}',
                    }

                    # Set type and action based on parameter type (using tracking actions)
                    if param_spec.type is bool:
                        # Boolean parameters use tracking store_true/store_false
                        if param_spec.default is False:
                            kwargs['action'] = TrackingStoreTrueAction
                        else:
                            kwargs['action'] = TrackingStoreFalseAction
                    elif param_spec.type is int:
                        kwargs['action'] = TrackingStoreAction
                        kwargs['type'] = int
                    elif param_spec.type is str:
                        kwargs['action'] = TrackingStoreAction
                        kwargs['type'] = str
                    elif param_spec.type is list:
                        kwargs['action'] = TrackingAppendAction
                        kwargs['nargs'] = '+'
                        if param_spec.default is not None:
                            kwargs['default'] = param_spec.default
                    else:
                        # Default to tracking store action for other types
                        kwargs['action'] = TrackingStoreAction

                    # Add choices if specified
                    if param_spec.choices:
                        kwargs['choices'] = param_spec.choices

                    # Add default if not a boolean action and default is set
                    if 'action' not in (TrackingStoreTrueAction, TrackingStoreFalseAction) and param_spec.default is not None:
                        if 'default' not in kwargs:  # Don't override if already set
                            kwargs['default'] = param_spec.default

                    # Add the argument
                    transform_group.add_argument(param_spec.cli_flag, **kwargs)

            except Exception as e:
                # Skip problematic transforms
                logger.warning(f"Could not add CLI args for transform {transform_name}: {e}")

    def build_parser(self) -> argparse.ArgumentParser:
        """Build the complete argument parser with dynamic arguments.

        Returns
        -------
        ArgumentParser
            Configured parser

        """
        parser = argparse.ArgumentParser(
            prog="all2md",
            description="Convert documents to Markdown format",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Supported formats:
  PDF, Word (DOCX), PowerPoint (PPTX), HTML, Email (EML), EPUB,
  RTF, Jupyter Notebook (IPYNB), OpenDocument (ODT, ODP), Excel (XLSX),
  images (PNG, JPEG, GIF), and 200+ text formats

Examples:
  # Basic conversions
  all2md document.pdf
  all2md document.docx --out output.md
  all2md presentation.pptx --markdown-emphasis-symbol "_"
  all2md notebook.ipynb --ipynb-truncate-long-outputs 20
  all2md document.odt --odf-no-preserve-tables
  all2md book.epub --epub-no-merge-chapters

  # Reading from stdin
  cat document.pdf | all2md -
  curl -s https://example.com/doc.pdf | all2md - --out output.md

  # Image handling
  all2md document.html --attachment-mode download --attachment-output-dir ./images
  all2md book.epub --attachment-mode base64

  # Using options from JSON file
  all2md document.pdf --options-json config.json
  all2md document.docx --options-json config.json --out custom.md
        """,
        )

        # Core arguments (keep these manual)
        parser.add_argument(
            "input",
            nargs="*",
            help="Input file(s) or directory(ies) to convert (use '-' for stdin)"
        )
        parser.add_argument("--out", "-o", help="Output file path (default: print to stdout)")

        # Format override option
        parser.add_argument(
            "--format", "--input-type",
            dest="format",
            choices=list(get_args(DocumentFormat)),
            default="auto",
            help="Force specific input format instead of auto-detection (default: auto)"
        )

        parser.add_argument(
            "--output-type",
            choices=list(get_args(DocumentFormat)),
            default="markdown",
            help="Target format for conversion (default: markdown)"
        )

        # Options JSON file
        parser.add_argument("--options-json", help="Path to JSON file containing conversion options")

        # Logging and verbosity options
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose output with detailed logging (equivalent to --log-level DEBUG)"
        )
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="WARNING",
            help="Set logging level for debugging (default: WARNING). Overrides --verbose if both are specified."
        )
        parser.add_argument(
            "--log-file",
            type=str,
            metavar="PATH",
            help="Write log messages to specified file in addition to console output"
        )
        parser.add_argument(
            "--trace",
            action="store_true",
            help="Enable trace mode with very verbose logging and per-stage timing information"
        )

        # Argument validation options
        parser.add_argument(
            "--strict-args",
            action="store_true",
            dest="strict_args",
            help="Fail on unknown command-line arguments instead of warning (helps catch typos)"
        )

        # Version and about options
        from all2md.cli.custom_actions import DynamicVersionAction

        def get_version() -> str:
            """Get the version of all2md package."""
            try:
                from importlib.metadata import version
                return version("all2md")
            except Exception:
                return "unknown"

        parser.add_argument("--version", "-V", action=DynamicVersionAction,
                            version_callback=lambda: f"all2md {get_version()}")
        parser.add_argument("--about", "-A", action="store_true",
                            help="Show detailed information about all2md and exit")

        # Add BaseOptions as universal options (no prefix)
        from all2md.options import BaseParserOptions
        self.add_options_class_arguments(
            parser,
            BaseParserOptions,
            format_prefix=None,
            group_name="Universal attachment options"
        )

        # Add MarkdownOptions as common options
        self.add_options_class_arguments(
            parser,
            MarkdownOptions,
            format_prefix="markdown",
            group_name="Common Markdown formatting options"
        )

        # Auto-discover parsers and add their options
        registry.auto_discover()

        for format_name in registry.list_formats():
            try:
                # Skip markdown format - we already added MarkdownOptions explicitly above
                # to avoid duplicate --markdown-flavor and other overlapping arguments
                if format_name == "markdown":
                    continue

                options_class = registry.get_parser_options_class(format_name)
                if options_class and is_dataclass(options_class):
                    # Create group name
                    group_name = f"{format_name.upper()} options"

                    # Add format-specific options (excluding BaseOptions fields)
                    self.add_format_specific_options(
                        parser,
                        options_class,
                        format_prefix=format_name,
                        group_name=group_name
                    )
            except Exception as e:
                logger.warning(f"Could not process converter {format_name}: {e}")

        # Add transform arguments (after format-specific options)
        self.add_transform_arguments(parser)

        self.parser = parser
        return parser

    def _suggest_similar_argument(self, unknown_arg: str) -> str | None:
        """Suggest similar argument name using fuzzy matching.

        Uses the dest_to_cli_flag mapping to return actual CLI flags (e.g., --pdf-pages)
        instead of incorrectly formatted suggestions (e.g., --pdf.pages).

        Parameters
        ----------
        unknown_arg : str
            Unknown argument dest name (e.g., "pdf.pages")

        Returns
        -------
        str or None
            Best matching CLI flag, or None if no good match

        """
        # Normalize the unknown argument for comparison (replace dots and hyphens with underscores)
        arg_clean = unknown_arg.replace('.', '_').replace('-', '_')

        # Build list of known dest names for matching
        known_dests = list(self.dest_to_cli_flag.keys())
        known_clean = [dest.replace('.', '_').replace('-', '_') for dest in known_dests]

        # Find close matches (similarity threshold 0.6)
        matches = difflib.get_close_matches(arg_clean, known_clean, n=1, cutoff=0.6)

        if matches:
            # Find the original dest name that matches
            matched_index = known_clean.index(matches[0])
            matched_dest = known_dests[matched_index]
            # Return the actual CLI flag from the mapping
            return self.dest_to_cli_flag[matched_dest]

        return None

    def map_args_to_options(self, parsed_args: argparse.Namespace, json_options: dict | None = None) -> dict:
        """Map CLI arguments to options using dot notation parsing.

        This simplified version uses dot notation in argument destinations
        to directly map to the nested structure of options.

        Parameters
        ----------
        parsed_args : argparse.Namespace
            Parsed command line arguments
        json_options : dict or None
            Options loaded from JSON file

        Returns
        -------
        dict
            Mapped options dictionary ready for to_markdown()

        """
        # Start with JSON options if provided, processing dot notation keys
        options = {}
        if json_options:
            # Import helpers for dot notation parsing
            from all2md.cli.custom_actions import merge_nested_dicts, parse_dot_notation

            # Process JSON options that may contain dot notation keys
            nested_config: Dict[str, Any] = {}
            for key, value in json_options.items():
                if '.' in key:
                    # Parse full dot notation into nested dict
                    # e.g., "html.network.allowed_hosts" -> {'html': {'network': {'allowed_hosts': ...}}}
                    parsed = parse_dot_notation(key, value)
                    nested_config = merge_nested_dicts(nested_config, parsed)
                else:
                    # Direct field name (no nesting)
                    options[key] = value

            # Flatten nested config into options dict, preserving full dot-notation paths
            # This prevents name collisions and ensures options are correctly mapped
            for format_key, format_opts in nested_config.items():
                if isinstance(format_opts, dict):
                    # Recursively flatten nested dicts, preserving prefixes
                    for nested_key, nested_value in format_opts.items():
                        if isinstance(nested_value, dict):
                            # Further nested (e.g., html.network.* fields)
                            # Keep fully qualified key: "html.network.allowed_hosts"
                            for field_key, field_value in nested_value.items():
                                options[f"{format_key}.{nested_key}.{field_key}"] = field_value
                        else:
                            # One level nested (e.g., pdf.pages)
                            # Keep fully qualified key: "pdf.pages"
                            options[f"{format_key}.{nested_key}"] = nested_value
                else:
                    # Top-level value (no nesting)
                    options[format_key] = format_opts
        args_dict = vars(parsed_args)

        # Get the set of explicitly provided arguments
        provided_args: set[str] = getattr(parsed_args, '_provided_args', set())

        # Auto-discover parsers to get their options classes for validation
        registry.auto_discover()

        # Collect all options classes for field validation
        options_classes: Dict[str, Type[Any]] = {}

        # Add BaseParserOptions
        from all2md.options import BaseParserOptions
        options_classes['base'] = BaseParserOptions
        options_classes['markdown'] = MarkdownOptions

        # Add converter-specific parser options
        for format_name in registry.list_formats():
            try:
                options_class = registry.get_parser_options_class(format_name)
                if options_class and is_dataclass(options_class):
                    # Don't overwrite manually-set options classes (like MarkdownOptions)
                    if format_name not in options_classes:
                        options_classes[format_name] = options_class
            except Exception:
                continue

        # Track unknown arguments for validation
        unknown_args = []

        # Define CLI-only arguments that should not be mapped to converter options
        # These are arguments handled directly by the CLI layer
        cli_only_args = {
            # Core arguments from builder.build_parser
            'input', 'out', 'format', 'output_type', 'options_json',
            'verbose', 'log_level', 'log_file', 'trace',
            'strict_args', 'version', 'about', '_provided_args',
            # Multi-file processing arguments from cli.create_parser
            'rich', 'pager', 'progress', 'output_dir', 'recursive',
            'parallel', 'skip_errors', 'preserve_structure', 'zip',
            'assets_layout', 'watch', 'watch_debounce', 'collate',
            'no_summary', 'save_config', 'dry_run', 'detect_only', 'exclude',
            # Security presets from cli.create_parser
            'strict_html_sanitize', 'safe_mode', 'paranoid_mode',
            # Transform arguments
            'transforms'
        }

        # Process each argument
        for arg_name, arg_value in args_dict.items():
            # Skip CLI-only arguments
            if arg_name in cli_only_args:
                continue

            # Only process arguments that were explicitly provided
            if arg_name not in provided_args:
                continue

            # Handle dot notation arguments (e.g., "pdf.pages")
            if '.' in arg_name:
                parts = arg_name.split('.', 1)
                format_prefix = parts[0]
                field_name = parts[1]

                # Validate field exists in the corresponding options class
                if format_prefix in options_classes:
                    options_class = options_classes[format_prefix]
                    field_found = False

                    for field in fields(options_class):
                        if field.name == field_name:
                            processed_value = self._process_argument_value(
                                field, dict(field.metadata) if field.metadata else {}, arg_value, arg_name,
                                was_provided=True
                            )
                            if processed_value is not None:
                                options[field.name] = processed_value
                            field_found = True
                            break

                    if not field_found and arg_value is not None:
                        # Track unknown argument
                        unknown_args.append(arg_name)
            else:
                # Handle non-dot notation arguments (BaseOptions fields)
                if 'base' in options_classes:
                    base_options = options_classes['base']
                    field_found = False

                    for field in fields(base_options):
                        if field.name == arg_name:
                            processed_value = self._process_argument_value(
                                field, dict(field.metadata) if field.metadata else {}, arg_value, arg_name,
                                was_provided=True
                            )
                            if processed_value is not None:
                                options[field.name] = processed_value
                            field_found = True
                            break

                    if not field_found and arg_value is not None:
                        # Track unknown argument
                        unknown_args.append(arg_name)

        # Validate unknown arguments
        if unknown_args:
            # Check if strict mode is enabled (can be controlled via env var or arg)
            strict_mode = getattr(parsed_args, 'strict_args', False)

            error_messages = []
            for unknown_arg in unknown_args:
                # Suggest similar argument using dest-to-CLI-flag mapping
                suggestion = self._suggest_similar_argument(unknown_arg)

                if suggestion:
                    msg = f"Unknown argument: --{unknown_arg.replace('_', '-')}. Did you mean {suggestion}?"
                else:
                    msg = f"Unknown argument: --{unknown_arg.replace('_', '-')}"

                error_messages.append(msg)

            if strict_mode:
                # Fail on unknown arguments
                full_error = "\n".join(error_messages)
                raise argparse.ArgumentTypeError(
                    f"Invalid arguments:\n{full_error}\n"
                    f"Use 'all2md --help' to see available options."
                )
            else:
                # Warn about unknown arguments via logger
                for msg in error_messages:
                    logger.warning(msg)

        return options

    def _process_argument_value(
            self, field: Any, metadata: Dict[str, Any], arg_value: Any,
            arg_name: str, was_provided: bool = False
    ) -> Any:
        """Process and convert argument values based on field type.

        Simplified version that relies on the was_provided flag to determine
        whether to include a value, eliminating complex default-checking logic.

        Parameters
        ----------
        field : Field
            Dataclass field
        metadata : dict
            Field metadata
        arg_value : Any
            Raw argument value
        arg_name : str
            CLI argument name
        was_provided : bool
            Whether this argument was explicitly provided by the user

        Returns
        -------
        Any
            Processed value or None if should be skipped

        Raises
        ------
        argparse.ArgumentTypeError
            If value type validation fails or choices validation fails

        """
        # If not explicitly provided, skip it
        if not was_provided:
            return None

        # Validate choices if specified
        if 'choices' in metadata and arg_value is not None:
            choices = metadata['choices']
            if arg_value not in choices:
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} must be one of {choices}, got: {arg_value}"
                )

        # Handle list_int type (comma-separated integers)
        if metadata.get('type') == 'list_int' and isinstance(arg_value, str):
            try:
                return [int(x.strip()) for x in arg_value.split(',')]
            except ValueError as e:
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} expects comma-separated integers, "
                    f"got: {arg_value}"
                ) from e

        # Validate integer type if specified in metadata
        if metadata.get('type') is int and arg_value is not None:
            if not isinstance(arg_value, int):
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} expects an integer, "
                    f"got: {arg_value} (type: {type(arg_value).__name__})"
                )

        # Validate float type if specified in metadata
        if metadata.get('type') is float and arg_value is not None:
            if not isinstance(arg_value, (int, float)):
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} expects a number, "
                    f"got: {arg_value} (type: {type(arg_value).__name__})"
                )

        # For explicitly provided arguments, return the value
        # The tracking actions ensure we only get here for user-provided values
        return arg_value


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser using dynamic generation."""
    builder = DynamicCLIBuilder()
    parser = builder.build_parser()

    # Add new CLI options for enhanced features
    parser.add_argument(
        '--rich',
        action=TrackingStoreTrueAction,
        help='Enable rich terminal output with formatting'
    )

    parser.add_argument(
        '--pager',
        action=TrackingStoreTrueAction,
        help='Display output using system pager for long documents (stdout only)'
    )

    parser.add_argument(
        '--progress',
        action=TrackingStoreTrueAction,
        help='Show progress bar for file conversions (automatically enabled for multiple files)'
    )

    parser.add_argument(
        '--output-dir',
        action=TrackingStoreAction,
        type=str,
        help='Directory to save converted files (for multi-file processing)'
    )

    parser.add_argument(
        '--recursive', '-r',
        action=TrackingStoreTrueAction,
        help='Process directories recursively'
    )

    parser.add_argument(
        '--parallel', '-p',
        action=TrackingPositiveIntAction,
        nargs='?',
        const=None,
        default=1,
        help='Process files in parallel (optionally specify number of workers, must be positive)'
    )

    parser.add_argument(
        '--skip-errors',
        action=TrackingStoreTrueAction,
        help='Continue processing remaining files if one fails'
    )

    parser.add_argument(
        '--preserve-structure',
        action=TrackingStoreTrueAction,
        help='Preserve directory structure in output directory'
    )

    parser.add_argument(
        '--zip',
        action=TrackingStoreAction,
        nargs='?',
        const='auto',
        metavar='PATH',
        help='Create zip archive of output (optionally specify custom path, default: output_dir.zip)'
    )

    parser.add_argument(
        '--assets-layout',
        action=TrackingStoreAction,
        choices=['flat', 'by-stem', 'structured'],
        default='flat',
        help='Asset organization: flat (single assets/ dir), by-stem (assets/{doc}/), structured (preserve structure)'
    )

    parser.add_argument(
        '--watch',
        action=TrackingStoreTrueAction,
        help='Watch mode: monitor files/directories and convert on change (requires --output-dir)'
    )

    parser.add_argument(
        '--watch-debounce',
        action=TrackingStoreAction,
        type=float,
        default=1.0,
        metavar='SECONDS',
        help='Debounce delay for watch mode in seconds (default: 1.0)'
    )

    parser.add_argument(
        '--collate',
        action=TrackingStoreTrueAction,
        help='Combine multiple files into a single output (stdout or file)'
    )

    parser.add_argument(
        '--no-summary',
        action=TrackingStoreTrueAction,
        help='Disable summary output after processing multiple files'
    )

    parser.add_argument(
        '--save-config',
        type=str,
        help='Save current CLI arguments to a JSON configuration file'
    )

    parser.add_argument(
        '--dry-run',
        action=TrackingStoreTrueAction,
        help='Show what would be converted without actually processing files'
    )

    parser.add_argument(
        '--detect-only',
        action=TrackingStoreTrueAction,
        help='Show format detection results without conversion (useful for debugging batch inputs)'
    )

    parser.add_argument(
        '--exclude',
        action=TrackingAppendAction,
        metavar='PATTERN',
        help='Exclude files matching this glob pattern (can be specified multiple times)'
    )

    # Security preset flags
    security_group = parser.add_argument_group('Security preset options')
    security_group.add_argument(
        '--strict-html-sanitize',
        action=TrackingStoreTrueAction,
        help='Enable strict HTML sanitization (disables remote fetch, local files, strips dangerous elements)'
    )
    security_group.add_argument(
        '--safe-mode',
        action=TrackingStoreTrueAction,
        help='Balanced security for untrusted input (allows HTTPS remote fetch, strips dangerous elements)'
    )
    security_group.add_argument(
        '--paranoid-mode',
        action=TrackingStoreTrueAction,
        help='Maximum security settings (strict restrictions, reduced size limits)'
    )


    return parser
