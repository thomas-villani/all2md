"""Dynamic CLI argument builder for all2md.

This module provides a system for automatically generating CLI arguments
from dataclass options using field metadata.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional, Type, Union, get_args, get_type_hints

from all2md.constants import DocumentFormat
from all2md.converter_registry import registry
from all2md.options import MarkdownOptions


class DynamicCLIBuilder:
    """Builds CLI arguments dynamically from options dataclasses.

    This class introspects converter options dataclasses and their metadata
    to automatically generate argparse arguments, eliminating the need for
    hard-coded CLI argument definitions.
    """

    def __init__(self) -> None:
        """Initialize the CLI builder."""
        self.parser: Optional[argparse.ArgumentParser] = None

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

        Parameters
        ----------
        field_type : Type
            Type annotation to analyze

        Returns
        -------
        tuple[Type, bool]
            Tuple of (underlying_type, is_optional)
        """
        # Handle Union types (including Optional which is Union[T, None])
        if hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
            args = field_type.__args__
            if len(args) == 2 and type(None) in args:
                # This is Optional[SomeType] (Union[SomeType, None])
                underlying_type = args[0] if args[1] is type(None) else args[1]
                return underlying_type, True
            else:
                # Non-Optional Union - return as-is
                return field_type, False

        # Handle other generic types with __origin__ (like list[int])
        if hasattr(field_type, '__origin__'):
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
        kwargs = {}

        # Handle boolean fields
        if resolved_type is bool:
            default_value = field.default
            if default_value is True and '-no-' in cli_name:
                # For --no-* flags (True defaults), use store_false
                kwargs['action'] = 'store_false'
            elif default_value is False:
                # For regular boolean flags (False defaults), use store_true
                kwargs['action'] = 'store_true'
            else:
                # For other boolean fields, use type conversion
                kwargs['type'] = lambda x: x.lower() in ('true', '1', 'yes')

        # Handle choices from metadata
        elif 'choices' in metadata:
            kwargs['choices'] = metadata['choices']

        # Handle list types
        elif hasattr(resolved_type, '__origin__') and resolved_type.__origin__ is list:
            # Get the list item type if available
            if hasattr(resolved_type, '__args__') and resolved_type.__args__:
                item_type = resolved_type.__args__[0]
                if item_type is int:
                    kwargs['help'] = kwargs.get('help', '') + ' (comma-separated integers)'
                    # Will be handled by custom action or type function
                else:
                    kwargs['help'] = kwargs.get('help', '') + ' (comma-separated)'
            else:
                kwargs['help'] = kwargs.get('help', '') + ' (comma-separated)'

        # Handle special metadata types
        elif metadata.get('type') == 'list_int':
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

        # Set default if field has one and it's not None
        if field.default is not None and not kwargs.get('action'):
            kwargs['default'] = field.default

        return kwargs

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
        if not is_dataclass(options_class):
            return

        # Create argument group if requested
        if group_name:
            group = parser.add_argument_group(group_name)
        else:
            group = parser

        for field in fields(options_class):
            metadata = field.metadata or {}

            # Skip excluded fields
            if metadata.get('exclude_from_cli', False):
                continue

            # Skip markdown_options field - handled separately
            if field.name == 'markdown_options':
                continue

            # Determine if this is a boolean with True default for --no-* handling
            field_type_is_bool = field.type is bool or field.type == 'bool'
            is_bool_true_default = field_type_is_bool and field.default is True

            # Get CLI name (explicit or inferred)
            if 'cli_name' in metadata:
                if metadata['cli_name'].startswith('no-'):
                    cli_name = f"--{format_prefix}-{metadata['cli_name']}" if format_prefix else f"--{metadata['cli_name']}"
                else:
                    cli_name = f"--{format_prefix}-{metadata['cli_name']}" if format_prefix else f"--{metadata['cli_name']}"
            else:
                cli_name = self.infer_cli_name(field.name, format_prefix, is_bool_true_default)

            # Build argument kwargs
            kwargs = self.get_argument_kwargs(field, metadata, cli_name, options_class)

            # Set dest for boolean flags that need special handling
            if 'action' in kwargs and kwargs['action'] in ['store_true', 'store_false']:
                if format_prefix and format_prefix != 'markdown':
                    kwargs['dest'] = f"{format_prefix}_{field.name}"
                elif format_prefix == 'markdown':
                    kwargs['dest'] = f"markdown_{field.name}"
                else:
                    kwargs['dest'] = field.name

            # Add the argument
            try:
                group.add_argument(cli_name, **kwargs)
            except Exception as e:
                print(f"Warning: Could not add argument {cli_name}: {e}")

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
        if not is_dataclass(options_class):
            return

        # Get BaseOptions fields to exclude
        from all2md.options import BaseOptions
        base_field_names = {f.name for f in fields(BaseOptions)}

        # Create argument group if requested
        if group_name:
            group = parser.add_argument_group(group_name)
        else:
            group = parser

        for field in fields(options_class):
            # Skip BaseOptions fields - they're handled as universal options
            if field.name in base_field_names:
                continue

            metadata = field.metadata or {}

            # Skip excluded fields
            if metadata.get('exclude_from_cli', False):
                continue

            # Skip markdown_options field - handled separately
            if field.name == 'markdown_options':
                continue

            # Determine if this is a boolean with True default for --no-* handling
            field_type_is_bool = field.type is bool or field.type == 'bool'
            is_bool_true_default = field_type_is_bool and field.default is True

            # Get CLI name (explicit or inferred)
            if 'cli_name' in metadata:
                if metadata['cli_name'].startswith('no-'):
                    cli_name = f"--{format_prefix}-{metadata['cli_name']}" if format_prefix else f"--{metadata['cli_name']}"
                else:
                    cli_name = f"--{format_prefix}-{metadata['cli_name']}" if format_prefix else f"--{metadata['cli_name']}"
            else:
                cli_name = self.infer_cli_name(field.name, format_prefix, is_bool_true_default)

            # Build argument kwargs
            kwargs = self.get_argument_kwargs(field, metadata, cli_name, options_class)

            # Set dest for boolean flags that need special handling
            if 'action' in kwargs and kwargs['action'] in ['store_true', 'store_false']:
                if format_prefix and format_prefix != 'markdown':
                    kwargs['dest'] = f"{format_prefix}_{field.name}"
                elif format_prefix == 'markdown':
                    kwargs['dest'] = f"markdown_{field.name}"
                else:
                    kwargs['dest'] = field.name

            # Add the argument
            try:
                group.add_argument(cli_name, **kwargs)
            except Exception as e:
                print(f"Warning: Could not add argument {cli_name}: {e}")

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
            "--format",
            choices=list(get_args(DocumentFormat)),
            default="auto",
            help="Force specific file format instead of auto-detection (default: auto)"
        )

        # Options JSON file
        parser.add_argument("--options-json", help="Path to JSON file containing conversion options")

        # Logging level option
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="WARNING",
            help="Set logging level for debugging (default: WARNING)"
        )

        # Version and about options
        from all2md.cli.actions import DynamicVersionAction

        def get_version() -> str:
            """Get the version of all2md package."""
            try:
                from importlib.metadata import version
                return version("all2md")
            except Exception:
                return "unknown"

        parser.add_argument("--version", "-v", action=DynamicVersionAction,
                            version_callback=lambda: f"all2md {get_version()}")
        parser.add_argument("--about", "-A", action="store_true",
                            help="Show detailed information about all2md and exit")

        # Add BaseOptions as universal options (no prefix)
        from all2md.options import BaseOptions
        self.add_options_class_arguments(
            parser,
            BaseOptions,
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

        # Auto-discover converters and add their options
        registry.auto_discover()

        for format_name in registry.list_formats():
            try:
                _, options_class = registry.get_converter(format_name)
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
                print(f"Warning: Could not process converter {format_name}: {e}")

        self.parser = parser
        return parser

    def map_args_to_options(self, parsed_args: argparse.Namespace, json_options: dict | None = None) -> dict:
        """Map CLI arguments to options using dataclass introspection.

        This replaces the old hard-coded _map_cli_args_to_options function
        with a generic system that works with any dataclass.

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
        # Start with JSON options if provided
        options = json_options.copy() if json_options else {}
        args_dict = vars(parsed_args)

        # Auto-discover converters to get their options classes
        registry.auto_discover()

        # Collect all options classes
        options_classes = {}

        # Add BaseOptions (universal options with no prefix)
        from all2md.options import BaseOptions
        options_classes['base'] = BaseOptions

        # Add MarkdownOptions (handled specially with markdown prefix)
        options_classes['markdown'] = MarkdownOptions

        # Add converter-specific options
        for format_name in registry.list_formats():
            try:
                _, options_class = registry.get_converter(format_name)
                if options_class and is_dataclass(options_class):
                    options_classes[format_name] = options_class
            except Exception:
                continue

        # Process each argument
        for arg_name, arg_value in args_dict.items():
            # Skip None values and special arguments
            if arg_value is None or arg_name in ['input', 'out', 'format', 'log_level', 'options_json', 'about',
                                                 'version']:
                continue

            # Handle different argument patterns
            mapped = False

            # Check BaseOptions (no prefix)
            if not mapped and 'base' in options_classes:
                base_options = options_classes['base']
                for field in fields(base_options):
                    if field.name == arg_name:
                        processed_value = self._process_argument_value(field, field.metadata or {}, arg_value, arg_name)
                        if processed_value is not None:
                            options[field.name] = processed_value
                        mapped = True
                        break

            # Check MarkdownOptions (markdown_ prefix)
            if not mapped and arg_name.startswith('markdown_'):
                field_name = arg_name[9:]  # Remove 'markdown_' prefix
                if 'markdown' in options_classes:
                    markdown_options = options_classes['markdown']
                    for field in fields(markdown_options):
                        if field.name == field_name:
                            processed_value = self._process_argument_value(field, field.metadata or {}, arg_value,
                                                                           arg_name)
                            if processed_value is not None:
                                options[field.name] = processed_value
                            mapped = True
                            break

            # Check format-specific options (format_ prefix)
            if not mapped and '_' in arg_name:
                parts = arg_name.split('_', 1)
                if len(parts) == 2:
                    format_prefix, field_name = parts
                    if format_prefix in options_classes:
                        format_options = options_classes[format_prefix]
                        for field in fields(format_options):
                            if field.name == field_name:
                                processed_value = self._process_argument_value(field, field.metadata or {}, arg_value,
                                                                               arg_name)
                                if processed_value is not None:
                                    options[field.name] = processed_value
                                mapped = True
                                break

            # Handle unmapped arguments as direct field names
            if not mapped and arg_value:
                options[arg_name] = arg_value

        return options

    def _process_argument_value(self, field: Any, metadata: Dict[str, Any], arg_value: Any, arg_name: str) -> Any:
        """Process and convert argument values based on field type.

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

        Returns
        -------
        Any
            Processed value or None if should be skipped
        """
        # Handle list_int type (comma-separated integers)
        if metadata.get('type') == 'list_int' and isinstance(arg_value, str):
            try:
                return [int(x.strip()) for x in arg_value.split(',')]
            except ValueError:
                return None

        # Handle boolean fields with defaults (handle string type annotations)
        field_type_is_bool = field.type is bool or field.type == 'bool'
        if field_type_is_bool:
            default_value = field.default

            # For --no-* flags with True defaults, arg_value is False when flag is used
            # This handles both explicit cli_name metadata and inferred --no-* names
            if default_value is True and arg_value is False:
                # Either has explicit no- prefix in metadata, or is a True-default being set to False
                if ('cli_name' in metadata and metadata['cli_name'].startswith('no-')) or \
                   ('cli_name' not in metadata):
                    return False

            # For regular boolean flags with False defaults, arg_value is True when flag is used
            elif default_value is False and arg_value is True:
                return True

            # Skip setting if boolean value matches default and wasn't explicitly set
            elif arg_value == default_value:
                return None

        # Handle choices - only include non-default values
        if 'choices' in metadata and arg_value != field.default:
            return arg_value

        # Handle numeric types
        if metadata.get('type') in (int, float) and arg_value != field.default:
            return arg_value

        # Handle string types - only include non-default values
        if isinstance(arg_value, str) and arg_value != field.default:
            return arg_value

        return None
