#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Dynamic CLI argument builder for all2md.

This module provides a system for automatically generating CLI arguments
from dataclass options using field metadata.
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import types
from dataclasses import MISSING, fields, is_dataclass
from typing import Annotated, Any, Dict, Optional, Type, Union, get_args, get_origin, get_type_hints

from all2md.cli.custom_actions import (
    DynamicVersionAction,
    TieredHelpAction,
    TrackingAppendAction,
    TrackingPositiveIntAction,
    TrackingStoreAction,
    TrackingStoreFalseAction,
    TrackingStoreTrueAction,
)
from all2md.cli.presets import get_preset_names
from all2md.converter_registry import registry
from all2md.exceptions import (
    DependencyError,
    FileError,
    FormatError,
    ParsingError,
    PasswordProtectedError,
    RenderingError,
    SecurityError,
    ValidationError,
)
from all2md.options import AttachmentOptionsMixin
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.markdown import MarkdownRendererOptions
from all2md.utils.input_sources import RemoteInputOptions

# Note: transform_registry is imported lazily in functions that need it
# to avoid loading the entire transforms system during CLI module initialization

# Module logger for consistent warning/error reporting
logger = logging.getLogger(__name__)

# Well-known metadata keys used across option definitions. Centralizing the
# string constants here keeps option modules and the CLI builder aligned.
CLI_METADATA_NEGATES_DEFAULT = "cli_negates_default"
CLI_METADATA_FLATTEN = "cli_flatten"
CLI_METADATA_NEGATED_NAME = "cli_negated_name"


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
        self._options_class_cache: Optional[Dict[str, Type[Any]]] = None

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

        The key insight is to let get_type_hints() handle the namespace resolution
        automatically. When we specify globalns explicitly, we must ensure ALL
        types referenced in the class (including inherited fields) are available
        in that namespace. Since options classes inherit from BaseParserOptions
        which references types like AttachmentMode, those types must be available.

        The solution is to let get_type_hints() use its default behavior, which
        properly resolves types across module boundaries and inheritance hierarchies.

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
            # Use get_type_hints without explicit globalns/localns
            # This allows proper resolution across module boundaries and inheritance
            type_hints = get_type_hints(options_class, include_extras=True)
            if field.name in type_hints:
                return type_hints[field.name]
        except (NameError, AttributeError, TypeError):
            # Fallback if type hints can't be resolved
            pass

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

    def _get_options_classes(self) -> Dict[str, Type[Any]]:
        """Return mapping of option namespaces to their dataclass classes."""
        if self._options_class_cache is not None:
            return self._options_class_cache

        options_classes: Dict[str, Type[Any]] = {}

        options_classes["base"] = BaseParserOptions
        options_classes["renderer_base"] = BaseRendererOptions
        options_classes["markdown"] = MarkdownRendererOptions
        options_classes["remote_input"] = RemoteInputOptions

        registry.auto_discover()

        for format_name in registry.list_formats():
            if format_name == "markdown":
                continue

            try:
                options_class = registry.get_parser_options_class(format_name)
            except Exception:
                options_class = None

            if options_class and is_dataclass(options_class):
                options_classes.setdefault(format_name, options_class)

            try:
                renderer_class = registry.get_renderer_options_class(format_name)
            except Exception:
                renderer_class = None

            if renderer_class and is_dataclass(renderer_class):
                options_classes.setdefault(f"renderer_{format_name}", renderer_class)

        self._options_class_cache = options_classes
        return self._options_class_cache

    def get_options_class_map(self) -> Dict[str, Type[Any]]:
        """Expose cached options classes for external introspection."""
        return dict(self._get_options_classes())

    def _handle_boolean_type(self, field: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Handle boolean field type inference.

        Parameters
        ----------
        field : Field
            Dataclass field
        metadata : dict
            Field metadata

        Returns
        -------
        dict
            Argparse kwargs for boolean fields

        """
        kwargs: Dict[str, Any] = {}
        default_value: Any = MISSING

        if self._has_default(field):
            candidate_default = self._get_default(field)
            if isinstance(candidate_default, bool):
                default_value = candidate_default
            elif callable(candidate_default):
                logger.debug(
                    "Boolean field %s uses default_factory; treating as no default for CLI",
                    field.name,
                )
            else:
                default_value = candidate_default

        negate_via_metadata = bool(metadata.get(CLI_METADATA_NEGATES_DEFAULT, False))

        if negate_via_metadata and default_value not in (True, False, MISSING):
            logger.debug(
                "Boolean field %s sets cli_negates_default but default is %r; CLI will still use store_false",
                field.name,
                default_value,
            )

        if negate_via_metadata or default_value is True:
            kwargs["action"] = "store_false"
        elif default_value is False:
            kwargs["action"] = "store_true"
        elif default_value is MISSING:
            kwargs["action"] = "store_true"
        else:
            # For Optional[bool] defaulting to None, accept explicit true/false strings
            kwargs["type"] = lambda x: x.lower() in ("true", "1", "yes")

        return kwargs

    @staticmethod
    def _handle_union_type(resolved_type: Type) -> tuple[Dict[str, Any], str | None]:
        """Handle Union type inference (e.g., int | list[int]).

        Parameters
        ----------
        resolved_type : Type
            Resolved Union type

        Returns
        -------
        tuple[dict, str | None]
            Argparse kwargs and help suffix

        """
        kwargs: Dict[str, Any] = {}
        help_suffix: str | None = None

        args = get_args(resolved_type)
        non_none_args = [arg for arg in args if arg is not type(None)]

        # Check if this is Union[scalar, list[scalar]]
        if len(non_none_args) == 2:
            scalar_type = None
            list_type = None

            for arg in non_none_args:
                if get_origin(arg) is list:
                    list_args = get_args(arg)
                    if list_args:
                        list_type = list_args[0]
                elif arg in (int, float, str):
                    scalar_type = arg

            # Create flexible parser for matching scalar and list types
            if scalar_type and list_type and scalar_type == list_type and scalar_type is int:

                def parse_int_or_list(value: str) -> int | list[int]:
                    if "," in value:
                        try:
                            return [int(x.strip()) for x in value.split(",")]
                        except ValueError as e:
                            raise argparse.ArgumentTypeError(
                                f"Expected integer or comma-separated integers, got: {value}"
                            ) from e
                    else:
                        try:
                            return int(value)
                        except ValueError as e:
                            raise argparse.ArgumentTypeError(
                                f"Expected integer or comma-separated integers, got: {value}"
                            ) from e

                kwargs["type"] = parse_int_or_list
                help_suffix = "(single value or comma-separated)"

        return kwargs, help_suffix

    @staticmethod
    def _handle_list_type(resolved_type: Type) -> tuple[Dict[str, Any], str | None]:
        """Handle list type inference.

        Parameters
        ----------
        resolved_type : Type
            Resolved list type

        Returns
        -------
        tuple[dict, str | None]
            Argparse kwargs and help suffix

        """
        kwargs: Dict[str, Any] = {}
        args = get_args(resolved_type)

        if args:
            item_type = args[0]
            if item_type is int:

                def parse_int_list(value: str) -> list[int]:
                    try:
                        return [int(x.strip()) for x in value.split(",")]
                    except ValueError as e:
                        raise argparse.ArgumentTypeError(f"Expected comma-separated integers, got: {value}") from e

                kwargs["type"] = parse_int_list
                return kwargs, "(comma-separated integers)"
            elif item_type is float:

                def parse_float_list(value: str) -> list[float]:
                    try:
                        return [float(x.strip()) for x in value.split(",")]
                    except ValueError as e:
                        raise argparse.ArgumentTypeError(f"Expected comma-separated floats, got: {value}") from e

                kwargs["type"] = parse_float_list
                return kwargs, "(comma-separated floats)"
            else:

                def parse_str_list(value: str) -> list[str]:
                    return [x.strip() for x in value.split(",") if x.strip()]

                kwargs["type"] = parse_str_list
                return kwargs, "(comma-separated values)"
        else:
            # Fallback for untyped lists
            def parse_str_list_fallback(value: str) -> list[str]:
                return [x.strip() for x in value.split(",") if x.strip()]

            kwargs["type"] = parse_str_list_fallback
            return kwargs, "(comma-separated values)"

    @staticmethod
    def _handle_int_list() -> tuple[Dict[str, Any], str]:
        def parse_int_list(value: str) -> list[int]:
            try:
                return [int(x.strip()) for x in value.split(",")]
            except ValueError as e:
                raise argparse.ArgumentTypeError(f"Expected comma-separated integers, got: {value}") from e

        return {"type": parse_int_list}, "(comma-separated integers)"

    @staticmethod
    def _handle_dict_type() -> tuple[Dict[str, Any], str]:
        """Handle dict type inference.

        Returns
        -------
        tuple[dict, str]
            Argparse kwargs and help suffix

        """

        def parse_json_dict(value: str) -> dict:
            try:
                result = json.loads(value)
                if not isinstance(result, dict):
                    raise ValueError("Expected JSON object")
                return result
            except (json.JSONDecodeError, ValueError) as e:
                raise argparse.ArgumentTypeError(f"Expected JSON object, got: {value}. Error: {e}") from e

        return {"type": parse_json_dict}, "(JSON format)"

    def _infer_argument_type_and_action(
        self, field: Any, resolved_type: Type, is_optional: bool, metadata: Dict[str, Any], cli_name: str
    ) -> tuple[Dict[str, Any], str | None]:
        """Infer argparse type/action metadata from resolved field type.

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
        tuple[dict, str | None]
            Argparse kwargs (type/action/choices only) and optional help suffix

        """
        # Handle boolean fields
        if resolved_type is bool:
            return self._handle_boolean_type(field, metadata), None

        # Handle choices from metadata
        if "choices" in metadata:
            return {"choices": metadata["choices"]}, None

        # Handle Union types
        if get_origin(resolved_type) in (Union, types.UnionType):
            return self._handle_union_type(resolved_type)

        # Handle list types
        if get_origin(resolved_type) is list:
            return self._handle_list_type(resolved_type)

        # Handle dict types
        if get_origin(resolved_type) is dict:
            return self._handle_dict_type()

        # Handle legacy metadata types
        if metadata.get("type") == "list_int":
            return self._handle_int_list()

        # Handle basic types
        if resolved_type in (int, float):
            return {"type": resolved_type}, None

        # str is default, don't specify
        return {}, None

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
        return name.replace("_", "-")

    def infer_cli_name(
        self, field_name: str, format_prefix: Optional[str] = None, is_boolean_with_true_default: bool = False
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
            if not kebab_name.startswith("no-"):
                kebab_name = f"no-{kebab_name}"

        # Add format prefix if provided (after no- prefix if applicable)
        if format_prefix:
            if is_boolean_with_true_default:
                # Format: --format-no-field-name
                # At this point, kebab_name always starts with 'no-' due to lines 304-306
                base_name = kebab_name[3:]  # Remove 'no-' prefix
                kebab_name = f"{format_prefix}-no-{base_name}"
            else:
                # Format: --format-field-name
                kebab_name = f"{format_prefix}-{kebab_name}"

        return f"--{kebab_name}"

    def get_argument_kwargs(
        self, field: Any, metadata: Dict[str, Any], cli_name: str, options_class: Type
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
        kwargs["help"] = metadata.get("help", f"Configure {field.name}")

        # Resolve field type using robust type resolution
        resolved_type = self._resolve_field_type(field, options_class)
        underlying_type, is_optional = self._handle_optional_type(resolved_type)

        # Get type-based kwargs
        type_kwargs, help_suffix = self._infer_argument_type_and_action(
            field, underlying_type, is_optional, metadata, cli_name
        )
        kwargs.update(type_kwargs)

        if help_suffix:
            kwargs["help"] = f"{kwargs['help']} {help_suffix}"

        # Handle metadata-specified types that override type inference
        if metadata.get("type") in (int, float):
            kwargs["type"] = metadata["type"]

        # Honor metadata-specified action (e.g., append) if present
        # This allows fields to explicitly request append behavior
        if "action" in metadata and not kwargs.get("action"):
            kwargs["action"] = metadata["action"]

        # Set default if field has one (checking for MISSING)
        if self._has_default(field) and not kwargs.get("action"):
            default_val = self._get_default(field)
            # Only set if not MISSING and not a factory
            if default_val is not MISSING and not callable(default_val):
                kwargs["default"] = default_val

        return kwargs

    def _should_process_field(
        self, field: Any, base_field_names: set[str], exclude_base_fields: bool
    ) -> tuple[bool, Dict[str, Any]]:
        """Determine if a field should be processed and return its metadata.

        Parameters
        ----------
        field : Field
            Dataclass field to check
        base_field_names : set of str
            Names of base fields to exclude
        exclude_base_fields : bool
            Whether to skip base fields

        Returns
        -------
        tuple[bool, dict]
            (should_process, metadata) where should_process is True if field should be added

        """
        # Skip BaseOptions fields if exclude_base_fields is True
        if exclude_base_fields and field.name in base_field_names:
            return False, {}

        metadata: Dict[str, Any] = dict(field.metadata) if field.metadata else {}

        # Skip if explicitly excluded from CLI
        if bool(metadata.get("exclude_from_cli", False)):
            return False, metadata

        # Skip markdown_options field - handled separately
        if field.name == "markdown_options":
            return False, metadata

        return True, metadata

    def _handle_flattened_field(
        self,
        group: Union[argparse.ArgumentParser, argparse._ArgumentGroup],
        field: Any,
        options_class: Type,
        format_prefix: Optional[str],
        dest_prefix: Optional[str],
        exclude_base_fields: bool,
    ) -> bool:
        """Handle flattened nested dataclass fields.

        Parameters
        ----------
        group : ArgumentParser or _ArgumentGroup
            Target argument group
        field : Field
            Field to check for flattening
        options_class : Type
            Parent options class
        format_prefix : str or None
            CLI prefix for flags
        dest_prefix : str or None
            Dest prefix for destinations
        exclude_base_fields : bool
            Whether to exclude base fields in nested dataclass

        Returns
        -------
        bool
            True if field was flattened (caller should continue to next field)

        """
        field_type = self._resolve_field_type(field, options_class)
        field_type, _ = self._handle_optional_type(field_type)

        if is_dataclass(field_type):
            # Handle nested dataclass by flattening its fields
            # Decouple CLI prefix (hyphenated) from dest prefix (dot-separated)
            kebab_name = self.snake_to_kebab(field.name)
            # CLI prefix uses hyphens for --html-network-* style flags
            nested_cli_prefix = f"{format_prefix}-{kebab_name}" if format_prefix else kebab_name
            # Dest prefix uses dots for html.network.* style destinations
            nested_dest_prefix = f"{dest_prefix}.{field.name}" if dest_prefix else field.name
            self._add_options_arguments_internal(
                group,
                field_type,
                format_prefix=nested_cli_prefix,
                group_name=None,
                exclude_base_fields=exclude_base_fields,
                dest_prefix=nested_dest_prefix,
            )
            return True
        else:
            logger.debug(
                "Field %s requested cli_flatten but resolved type %s is not a dataclass",
                field.name,
                field_type,
            )
            return True

    def _determine_cli_name_and_negation(
        self,
        field: Any,
        metadata: Dict[str, Any],
        options_class: Type,
        format_prefix: Optional[str],
    ) -> tuple[str, bool]:
        """Determine CLI name and whether negation is needed for boolean fields.

        Parameters
        ----------
        field : Field
            Dataclass field
        metadata : dict
            Field metadata
        options_class : Type
            Options class
        format_prefix : str or None
            Format prefix for CLI name

        Returns
        -------
        tuple[str, bool]
            (cli_name, use_negated_flag)

        """
        # Determine if this is a boolean with True default for --no-* handling
        resolved_field_type = self._resolve_field_type(field, options_class)
        underlying_field_type, _ = self._handle_optional_type(resolved_field_type)

        bool_default_value: Any = MISSING
        if underlying_field_type is bool and self._has_default(field):
            candidate_default = self._get_default(field)
            if isinstance(candidate_default, bool):
                bool_default_value = candidate_default
            elif callable(candidate_default):
                bool_default_value = MISSING

        negate_via_metadata = (
            bool(metadata.get(CLI_METADATA_NEGATES_DEFAULT, False)) if underlying_field_type is bool else False
        )
        use_negated_flag = bool_default_value is True or negate_via_metadata

        # Get CLI name (explicit or inferred)
        if "cli_name" in metadata:
            cli_meta_name = metadata["cli_name"]
            cli_name = f"--{format_prefix}-{cli_meta_name}" if format_prefix else f"--{cli_meta_name}"
        elif use_negated_flag and CLI_METADATA_NEGATED_NAME in metadata:
            negated_name_hint = metadata[CLI_METADATA_NEGATED_NAME]
            kebab_hint = self.snake_to_kebab(str(negated_name_hint))
            cli_name = f"--{format_prefix}-{kebab_hint}" if format_prefix else f"--{kebab_hint}"
        else:
            cli_name = self.infer_cli_name(field.name, format_prefix, use_negated_flag)

        return cli_name, use_negated_flag

    def _add_argument_with_tracking(
        self,
        group: Union[argparse.ArgumentParser, argparse._ArgumentGroup],
        cli_name: str,
        field: Any,
        kwargs: Dict[str, Any],
        dest_prefix: Optional[str],
    ) -> None:
        """Add argument with appropriate tracking action and dest.

        Parameters
        ----------
        group : ArgumentParser or _ArgumentGroup
            Target argument group
        cli_name : str
            CLI flag name
        field : Field
            Dataclass field
        kwargs : dict
            Argument kwargs to modify
        dest_prefix : str or None
            Prefix for dest name

        """
        # Set dest using dot notation and tracking actions
        if "action" in kwargs:
            if kwargs["action"] == "store_true":
                kwargs["action"] = TrackingStoreTrueAction
                kwargs["dest"] = f"{dest_prefix}.{field.name}" if dest_prefix else field.name
            elif kwargs["action"] == "store_false":
                kwargs["action"] = TrackingStoreFalseAction
                kwargs["dest"] = f"{dest_prefix}.{field.name}" if dest_prefix else field.name
            elif kwargs["action"] == "append":
                kwargs["action"] = TrackingAppendAction
                kwargs["dest"] = f"{dest_prefix}.{field.name}" if dest_prefix else field.name
        else:
            # For non-boolean arguments, use TrackingStoreAction
            kwargs["action"] = TrackingStoreAction
            kwargs["dest"] = f"{dest_prefix}.{field.name}" if dest_prefix else field.name

        # Add the argument
        try:
            group.add_argument(cli_name, **kwargs)
            # Track mapping from dest name to actual CLI flag for better suggestions
            if "dest" in kwargs:
                self.dest_to_cli_flag[kwargs["dest"]] = cli_name
        except Exception as e:
            logger.warning(f"Could not add argument {cli_name}: {e}")

    def _add_options_arguments_internal(
        self,
        parser: Union[argparse.ArgumentParser, argparse._ArgumentGroup],
        options_class: Type,
        format_prefix: Optional[str] = None,
        group_name: Optional[str] = None,
        exclude_base_fields: bool = False,
        dest_prefix: Optional[str] = None,
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
            Prefix for CLI argument names (e.g., 'pdf' for --pdf-pages).
            For nested dataclasses, uses hyphenated format (e.g., 'html-network')
        group_name : str, optional
            Name for argument group
        exclude_base_fields : bool, default=False
            If True, skip fields that are defined in BaseParserOptions
        dest_prefix : str, optional
            Prefix for argparse dest names using dot notation (e.g., 'html.network').
            If None, uses format_prefix. This allows CLI flags to use hyphens
            while dests use dots for proper option mapping.

        """
        if not is_dataclass(options_class):
            return

        # Initialize dest_prefix to format_prefix if not provided
        if dest_prefix is None:
            dest_prefix = format_prefix

        # Get BaseOptions fields to exclude if requested
        base_field_names = set()
        if exclude_base_fields:
            base_field_names = {f.name for f in fields(BaseParserOptions)}

        # Create argument group if requested
        group: Union[argparse.ArgumentParser, argparse._ArgumentGroup]
        if group_name:
            group = parser.add_argument_group(group_name)
        else:
            group = parser

        for field in fields(options_class):
            # Check if field should be processed
            should_process, metadata = self._should_process_field(field, base_field_names, exclude_base_fields)
            if not should_process:
                continue

            # Handle flattened nested dataclasses
            if bool(metadata.get(CLI_METADATA_FLATTEN, False)):
                if self._handle_flattened_field(
                    group, field, options_class, format_prefix, dest_prefix, exclude_base_fields
                ):
                    continue

            # Determine CLI name and whether to use negation
            cli_name, _ = self._determine_cli_name_and_negation(field, metadata, options_class, format_prefix)

            # Build argument kwargs
            kwargs = self.get_argument_kwargs(field, metadata, cli_name, options_class)

            # Add argument with tracking action
            self._add_argument_with_tracking(group, cli_name, field, kwargs, dest_prefix)

    def add_options_class_arguments(
        self,
        parser: argparse.ArgumentParser,
        options_class: Type,
        format_prefix: Optional[str] = None,
        group_name: Optional[str] = None,
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
        self,
        parser: argparse.ArgumentParser,
        options_class: Type,
        format_prefix: Optional[str] = None,
        group_name: Optional[str] = None,
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
        self._add_options_arguments_internal(parser, options_class, format_prefix, group_name, exclude_base_fields=True)

    def add_renderer_options(
        self,
        parser: argparse.ArgumentParser,
        options_class: Type,
        format_name: str,
    ) -> None:
        """Add renderer options for a given format with dedicated prefixes."""
        cli_prefix = f"{format_name}-renderer"
        dest_prefix = f"renderer_{format_name}"
        group_name = f"{format_name.upper()} renderer options"

        self._add_options_arguments_internal(
            parser,
            options_class,
            format_prefix=cli_prefix,
            group_name=group_name,
            exclude_base_fields=False,
            dest_prefix=dest_prefix,
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
        # Lazy import to avoid loading transforms module at CLI startup
        from all2md.transforms.registry import transform_registry

        # Add --transform flag (repeatable, ordered) with tracking
        parser.add_argument(
            "--transform",
            "-t",
            action=TrackingAppendAction,
            dest="transforms",
            metavar="NAME",
            help="Apply transform to AST before rendering (repeatable, order matters). "
            'Use "all2md list-transforms" to see available transforms.',
        )

        # Create transform options group if we have transforms
        transform_names = transform_registry.list_transforms()
        if not transform_names:
            return

        transform_group = parser.add_argument_group("Transform options")

        # For each transform, add parameter arguments based on ParameterSpec
        for transform_name in transform_names:
            try:
                metadata = transform_registry.get_metadata(transform_name)

                for param_name, param_spec in metadata.parameters.items():
                    if not param_spec.should_expose():
                        continue

                    cli_flag = param_spec.get_cli_flag(param_name)

                    # Get argparse kwargs from ParameterSpec (centralized logic)
                    # This includes action, type, default, help, choices, dest, etc.
                    kwargs = param_spec.get_argparse_kwargs(param_name, transform_name)

                    # Add the argument to the transform options group
                    transform_group.add_argument(cli_flag, **kwargs)
                    dest_name = kwargs.get("dest")
                    if dest_name:
                        self.dest_to_cli_flag[dest_name] = cli_flag

            except Exception as e:
                # Skip problematic transforms
                logger.warning(f"Could not add CLI args for transform {transform_name}: {e}")

    def add_global_attachment_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add global attachment handling arguments that apply to all formats.

        These arguments are extracted from AttachmentOptionsMixin and apply to
        all formats unless overridden by format-specific arguments.

        Parameters
        ----------
        parser : ArgumentParser
            Parser to add arguments to

        """
        # Create argument group for global attachment options
        attachment_group = parser.add_argument_group(
            "Global attachment options",
            "Apply to every parser that supports attachments (PDF, DOCX, HTML, etc.). "
            "Text-only formats ignore these flags, and format-specific overrides still take precedence.",
        )

        # Iterate over AttachmentOptionsMixin fields
        for field in fields(AttachmentOptionsMixin):
            # Build CLI flag name (no prefix for global)
            cli_name = f"--{self.snake_to_kebab(field.name)}"

            # Get metadata
            field_metadata = dict(field.metadata) if field.metadata else {}

            # Build argument kwargs using existing builder logic
            kwargs = self.get_argument_kwargs(field, field_metadata, cli_name, AttachmentOptionsMixin)

            # Set dest (no dot notation - just field name for global)
            # and use tracking actions
            if "action" in kwargs:
                if kwargs["action"] == "store_true":
                    kwargs["action"] = TrackingStoreTrueAction
                    kwargs["dest"] = field.name
                elif kwargs["action"] == "store_false":
                    kwargs["action"] = TrackingStoreFalseAction
                    kwargs["dest"] = field.name
                elif kwargs["action"] == "append":
                    kwargs["action"] = TrackingAppendAction
                    kwargs["dest"] = field.name
            else:
                # For non-boolean arguments, use TrackingStoreAction
                kwargs["action"] = TrackingStoreAction
                kwargs["dest"] = field.name

            # Add the argument
            try:
                attachment_group.add_argument(cli_name, **kwargs)
                # Track mapping from dest name to actual CLI flag
                self.dest_to_cli_flag[field.name] = cli_name
            except Exception as e:
                logger.warning(f"Could not add global attachment argument {cli_name}: {e}")

    def build_parser(self) -> argparse.ArgumentParser:
        """Build the complete argument parser with dynamic arguments.

        Returns
        -------
        ArgumentParser
            Configured parser

        """
        parser = argparse.ArgumentParser(
            prog="all2md",
            usage="all2md [-h] [-o OUTPUT] [--config CONFIG] [--format FORMAT] [--output-format FORMAT] "
            "[OPTIONS] input [input ...]",
            description="Convert documents to Markdown (and other formats)",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=False,
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

  # Reading from stdin (use '-' for stdin in any command)
  cat document.pdf | all2md -
  curl -s https://example.com/doc.pdf | all2md - --out output.md
  echo "<h1>Test</h1>" | all2md view -
  cat report.pdf | all2md grep "search term" -
  echo "<p>Version 1</p>" | all2md diff - version2.html

  # Extract a section by name or index
  all2md document.pdf --extract "Materials and Methods"
  all2md document.pdf --extract "#:3"

  # Image handling
  all2md document.html --attachment-mode save --attachment-output-dir ./images
  all2md book.epub --attachment-mode base64

  # Using options from config file
  all2md document.pdf --config config.toml
  all2md document.docx --config config.json --out custom.md

  # Viewing a document in a browser
  all2md view document.pdf
  all2md view document.pdf --toc --dark --theme sidebar

  # Compare documents
  all2md diff document-v1.docx document-v2.docx
  all2md diff document-v1.docx document-v2.docx --format html --output difference.html --granularity sentence

  # Search documents
  # grep-style
  all2md grep "search string" documents/*.pdf
  all2md grep "search str.*g" documents/*.pdf --regex --recursive --context 3 -n --rich

  # BM25 keyword search
  all2md search "keywords to search" documents/*.pdf --keyword
  all2md search "keywords to search" documents/*.pdf --keyword --persist --index-dir index/ --rich

  # Vector search
  all2md search "vector search query" documents/ --vector
  all2md search "vector search query" documents/ --vector --chunk-size 150 --vector-model all-mpnet-base-v2

  # Hybrid keyword/vector search
  all2md search "vector search query" documents/ --hybrid --hybrid-keyword-weight 50
        """,
        )

        parser.add_argument(
            "-h",
            "--help",
            action=TieredHelpAction,
            help="Show CLI help. Omit SECTION for a quick overview, or provide full/pdf/etc. "
            "(e.g., --help full, --help pdf).",
        )

        # Core arguments (keep these manual)
        parser.add_argument("input", nargs="*", help="Input file(s) or directory(ies) to convert (use '-' for stdin)")
        parser.add_argument("--out", "-o", help="Output file path (default: print to stdout)")

        # Section extraction option
        parser.add_argument(
            "--extract",
            type=str,
            metavar="SPEC",
            help="Extract specific section(s) from document. "
            "Supports: name pattern ('Introduction', 'Chapter*'), "
            "single index ('#:1'), range ('#:1-3'), "
            "multiple ('#:1,3,5'), or open-ended ('#:3-'). "
            "Sections are 1-indexed. Pattern matching is case-insensitive with wildcard support.",
        )

        # Outline extraction option
        parser.add_argument(
            "--outline",
            action="store_true",
            help="Output document outline (table of contents) instead of full content. "
            "Shows all headings in markdown list format. Cannot be used with --extract.",
        )

        parser.add_argument(
            "--outline-max-level",
            type=int,
            metavar="LEVEL",
            default=6,
            help="Maximum heading level to include in outline (1-6, default: 6). "
            "Only applies when --outline is used.",
        )

        # Document splitting options
        parser.add_argument(
            "--split-by",
            type=str,
            metavar="STRATEGY",
            help="Split document into multiple output files. Strategies: "
            "h1/h2/h3/h4/h5/h6 (by heading level), "
            "length=N (by word count), "
            "break (at horizontal rules/thematic breaks), "
            "delimiter=TEXT (split at custom text markers like '\\n***\\n'), "
            "page (by PDF pages), chapter (by EPUB chapters), "
            "parts=N (into N equal parts), "
            "auto (automatic detection). "
            "Requires --out or --output-dir for output location. "
            "Cannot be used with --collate or --extract.",
        )

        parser.add_argument(
            "--split-by-naming",
            type=str,
            choices=["numeric", "title"],
            default="numeric",
            help="File naming strategy for splits: 'numeric' (001, 002, ...) or "
            "'title' (include heading text in filename). Default: numeric",
        )

        parser.add_argument(
            "--split-by-digits",
            type=int,
            default=3,
            metavar="N",
            help="Number of digits for split numbering (default: 3, produces 001, 002, etc.)",
        )

        # Format override option
        # Use registry.list_formats() directly for most up-to-date format list
        # Including "auto" as the first choice for format detection
        format_choices = ["auto"] + sorted(registry.list_formats())

        parser.add_argument(
            "--format",
            "--input-type",
            dest="format",
            choices=format_choices,
            default="auto",
            help="Force specific input format instead of auto-detection (default: auto)",
        )

        parser.add_argument(
            "--output-format",
            "--to",
            choices=format_choices,
            default="markdown",
            help="Target format for conversion (default: markdown)",
        )

        # Configuration file
        parser.add_argument(
            "--config",
            help="Path to configuration file (JSON or TOML format). "
            "If not specified, searches for .all2md.toml or .all2md.json in current directory, "
            "then in home directory.",
        )

        parser.add_argument(
            "--no-config",
            action="store_true",
            dest="no_config",
            help="Disable loading of configuration files. Ignores auto-discovered configs, "
            "ALL2MD_CONFIG environment variable, and any --config flag.",
        )

        # Preset configurations
        parser.add_argument(
            "--preset",
            choices=get_preset_names(),
            help="Apply a preset configuration. Presets provide pre-configured settings for common use cases. "
            "CLI arguments override preset values. "
            "Available: fast (speed-optimized), quality (maximum fidelity), minimal (text-only), "
            "complete (full preservation), archival (self-contained with base64), "
            "documentation (optimized for technical docs).",
        )

        # Logging and verbosity options
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output with detailed logging (equivalent to --log-level DEBUG)",
        )
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="WARNING",
            help="Set logging level for debugging (default: WARNING). Overrides --verbose if both are specified.",
        )
        parser.add_argument(
            "--log-file",
            type=str,
            metavar="PATH",
            help="Write log messages to specified file in addition to console output",
        )
        parser.add_argument(
            "--trace",
            action="store_true",
            help="Enable trace mode with very verbose logging and per-stage timing information",
        )

        # Argument validation options
        parser.add_argument(
            "--strict-args",
            action="store_true",
            dest="strict_args",
            help="Fail on unknown command-line arguments instead of warning (helps catch typos)",
        )

        def get_version() -> str:
            """Get the version of all2md package."""
            try:
                from importlib.metadata import version

                return version("all2md")
            except Exception:
                return "unknown"

        parser.add_argument(
            "--version", "-V", action=DynamicVersionAction, version_callback=lambda: f"all2md {get_version()}"
        )
        parser.add_argument(
            "--about", "-A", action="store_true", help="Show detailed information about all2md and exit"
        )

        # Add BaseOptions as universal options (no prefix)
        from all2md.options.base import BaseParserOptions
        from all2md.utils.input_sources import RemoteInputOptions

        self.add_options_class_arguments(
            parser, BaseParserOptions, format_prefix=None, group_name="Universal parser options"
        )

        # Add MarkdownRendererOptions as common options
        self.add_options_class_arguments(
            parser, MarkdownRendererOptions, format_prefix="markdown", group_name="Common Markdown formatting options"
        )

        # Add remote input options (top-level, apply to all formats)
        self._add_options_arguments_internal(
            parser,
            RemoteInputOptions,
            format_prefix="remote-input",
            group_name="Remote input options",
            exclude_base_fields=False,
            dest_prefix="remote_input",
        )

        # Auto-discover parsers and add their options
        registry.auto_discover()

        for format_name in registry.list_formats():
            try:
                # Skip markdown format - we already added MarkdownRendererOptions explicitly above
                # to avoid duplicate --markdown-flavor and other overlapping arguments
                if format_name == "markdown":
                    continue

                options_class = registry.get_parser_options_class(format_name)
                if options_class and is_dataclass(options_class):
                    # Create group name
                    group_name = f"{format_name.upper()} options"

                    # Add format-specific options (excluding BaseOptions fields)
                    self.add_format_specific_options(
                        parser, options_class, format_prefix=format_name, group_name=group_name
                    )

                renderer_options_class = registry.get_renderer_options_class(format_name)
                if renderer_options_class and is_dataclass(renderer_options_class):
                    self.add_renderer_options(parser, renderer_options_class, format_name=format_name)
            except Exception as e:
                logger.warning(f"Could not process converter {format_name}: {e}")

        # Add transform arguments (after format-specific options)
        self.add_transform_arguments(parser)

        self.parser = parser
        return parser

    def _resolve_nested_field(self, options_class: Type, field_path: list[str]) -> tuple[Any, Type] | None:
        """Resolve a nested field path in a dataclass hierarchy.

        Parameters
        ----------
        options_class : Type
            Starting dataclass to search from
        field_path : list[str]
            List of field names to traverse (e.g., ['network', 'allowed_hosts'])

        Returns
        -------
        tuple[Any, Type] or None
            Tuple of (field, field_type) if found, None if path is invalid

        Examples
        --------
        >>> # For HtmlOptions with nested NetworkFetchOptions:
        >>> field, field_type = builder._resolve_nested_field(
        ...     HtmlOptions, ['network', 'allowed_hosts']
        ... )
        >>> # Returns: (allowed_hosts_field, list[str])

        """
        if not field_path:
            return None

        current_class = options_class

        # Walk the path, resolving each level
        for i, field_name in enumerate(field_path):
            field_found = None

            # Search for field in current class
            for field in fields(current_class):
                if field.name == field_name:
                    field_found = field
                    break

            if not field_found:
                return None

            # If this is the last component, return the field
            if i == len(field_path) - 1:
                # Resolve the final field type
                resolved_type = self._resolve_field_type(field_found, current_class)
                underlying_type, _ = self._handle_optional_type(resolved_type)
                return field_found, underlying_type

            # Otherwise, resolve the intermediate type and continue walking
            field_type = self._resolve_field_type(field_found, current_class)
            underlying_type, _ = self._handle_optional_type(field_type)

            # Verify it's a dataclass before continuing
            if not is_dataclass(underlying_type):
                return None

            current_class = underlying_type

        return None

    def resolve_option_field(self, dest: str) -> tuple[Any, Dict[str, Any]] | None:
        """Return the dataclass field and metadata for a CLI destination."""
        options_classes = self._get_options_classes()

        if "." in dest:
            prefix, remainder = dest.split(".", 1)
            options_class = options_classes.get(prefix)
            if not options_class:
                return None

            if "." in remainder:
                field_path = remainder.split(".")
                result = self._resolve_nested_field(options_class, field_path)
                if result:
                    field, _ = result
                    metadata = dict(field.metadata) if field.metadata else {}
                    return field, metadata
                return None

            for field in fields(options_class):
                if field.name == remainder:
                    metadata = dict(field.metadata) if field.metadata else {}
                    return field, metadata
            return None

        base_class = options_classes.get("base")
        if not base_class:
            return None

        for field in fields(base_class):
            if field.name == dest:
                metadata = dict(field.metadata) if field.metadata else {}
                return field, metadata

        return None

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
        arg_clean = unknown_arg.replace(".", "_").replace("-", "_")

        # Build list of known dest names for matching
        known_dests = list(self.dest_to_cli_flag.keys())
        known_clean = [dest.replace(".", "_").replace("-", "_") for dest in known_dests]

        # Find close matches (similarity threshold 0.6)
        matches = difflib.get_close_matches(arg_clean, known_clean, n=1, cutoff=0.6)

        if matches:
            # Find the original dest name that matches
            matched_index = known_clean.index(matches[0])
            matched_dest = known_dests[matched_index]
            # Return the actual CLI flag from the mapping
            return self.dest_to_cli_flag[matched_dest]

        return None

    def _flatten_config_options(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Flatten nested configuration dictionaries into dot-key form."""
        flattened: Dict[str, Any] = {}

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                flattened.update(self._flatten_config_options(value, full_key))
            else:
                flattened[full_key] = value

        return flattened

    def _process_dot_notation_arg(
        self,
        arg_name: str,
        arg_value: Any,
        options_classes: dict[str, Type],
        options: dict[str, Any],
        unknown_args: list[str],
    ) -> None:
        """Process dot notation arguments (e.g., pdf.pages or html.network.allowed_hosts).

        Parameters
        ----------
        arg_name : str
            Argument name with dot notation
        arg_value : Any
            Argument value
        options_classes : dict[str, Type]
            Map of format names to options classes
        options : dict[str, Any]
            Options dictionary to update
        unknown_args : list[str]
            List to append unknown arguments to

        """
        parts = arg_name.split(".", 1)
        format_prefix = parts[0]
        remainder = parts[1]

        # Validate field exists in the corresponding options class
        if format_prefix not in options_classes:
            return

        options_class = options_classes[format_prefix]

        # Check if this is multi-level nesting (e.g., "network.allowed_hosts")
        if "." in remainder:
            # Split remainder into path components
            field_path = remainder.split(".")

            # Use helper to resolve nested field
            result = self._resolve_nested_field(options_class, field_path)

            if result:
                field, field_type = result
                processed_value = self._process_argument_value(
                    field,
                    dict(field.metadata) if field.metadata else {},
                    arg_value,
                    arg_name,
                    was_provided=True,
                )
                if processed_value is not None:
                    options[arg_name] = processed_value
            elif arg_value is not None:
                # Track unknown argument
                unknown_args.append(arg_name)
        else:
            # Single-level nesting (e.g., "pdf.pages")
            field_name = remainder
            field_found = False

            for field in fields(options_class):
                if field.name == field_name:
                    processed_value = self._process_argument_value(
                        field,
                        dict(field.metadata) if field.metadata else {},
                        arg_value,
                        arg_name,
                        was_provided=True,
                    )
                    if processed_value is not None:
                        options[arg_name] = processed_value
                    field_found = True
                    break

            if not field_found and arg_value is not None:
                # Track unknown argument
                unknown_args.append(arg_name)

    def _process_base_options_arg(
        self,
        arg_name: str,
        arg_value: Any,
        options_classes: dict[str, Type],
        options: dict[str, Any],
        unknown_args: list[str],
    ) -> None:
        """Process non-dot notation arguments (BaseOptions fields).

        Parameters
        ----------
        arg_name : str
            Argument name without dot notation
        arg_value : Any
            Argument value
        options_classes : dict[str, Type]
            Map of format names to options classes
        options : dict[str, Any]
            Options dictionary to update
        unknown_args : list[str]
            List to append unknown arguments to

        """
        if "base" not in options_classes:
            return

        base_options = options_classes["base"]
        field_found = False

        for field in fields(base_options):
            if field.name == arg_name:
                processed_value = self._process_argument_value(
                    field,
                    dict(field.metadata) if field.metadata else {},
                    arg_value,
                    arg_name,
                    was_provided=True,
                )
                if processed_value is not None:
                    options[field.name] = processed_value
                field_found = True
                break

        if not field_found and arg_value is not None:
            # Track unknown argument
            unknown_args.append(arg_name)

    def _propagate_global_attachment_fields(
        self,
        provided_args: set[str],
        args_dict: dict[str, Any],
        options_classes: dict[str, Type],
        options: dict[str, Any],
    ) -> None:
        """Propagate global attachment flags to all format-specific options.

        Parameters
        ----------
        provided_args : set[str]
            Set of explicitly provided arguments
        args_dict : dict[str, Any]
            Dictionary of all arguments
        options_classes : dict[str, Type]
            Map of format names to options classes
        options : dict[str, Any]
            Options dictionary to update

        """
        from dataclasses import fields as get_fields

        from all2md.options.common import AttachmentOptionsMixin

        attachment_field_names = {field.name for field in get_fields(AttachmentOptionsMixin)}

        for field_name in attachment_field_names:
            # Check if global flag was provided
            if field_name not in provided_args or field_name not in args_dict:
                continue

            global_value = args_dict[field_name]

            # Apply to each format that supports attachments
            for format_name, options_class in options_classes.items():
                if format_name in ["base", "renderer_base", "markdown", "remote_input"]:
                    continue

                # Check if this options class has this attachment field
                has_field = any(field.name == field_name for field in get_fields(options_class))
                if not has_field:
                    continue

                # Build format-specific key
                format_field_key = f"{format_name}.{field_name}"

                # Only apply global if format-specific wasn't explicitly provided
                if format_field_key not in provided_args:
                    options[format_field_key] = global_value

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
        # Start with JSON options if provided, flattening nested structures to dot-notation keys
        options: Dict[str, Any] = {}
        if json_options:
            flattened = self._flatten_config_options(json_options)
            options.update(flattened)

        # Get the set of explicitly provided arguments first
        provided_args: set[str] = getattr(parsed_args, "_provided_args", set())

        # Create a copy of the args dict to avoid "dictionary changed size during iteration" errors
        args_dict = dict(vars(parsed_args))

        # Collect all options classes for field validation
        options_classes = dict(self._get_options_classes())

        # Track unknown arguments for validation
        unknown_args: list[str] = []

        # Build set of global attachment field names
        from dataclasses import fields as get_fields

        from all2md.options.common import AttachmentOptionsMixin

        global_attachment_fields = {field.name for field in get_fields(AttachmentOptionsMixin)}

        # Define CLI-only arguments that should not be mapped to converter options
        # These are arguments handled directly by the CLI layer
        cli_only_args = {
            # Core arguments from builder.build_parser
            "input",
            "out",
            "format",
            "output_format",
            "config",
            "no_config",
            "preset",
            "verbose",
            "log_level",
            "log_file",
            "trace",
            "strict_args",
            "about",
            "_provided_args",
            # Note: 'version' uses argparse.SUPPRESS and doesn't appear in namespace
            # Multi-file processing arguments from cli.create_parser
            "rich",
            "pager",
            "progress",
            "output_dir",
            "output_extension",
            "recursive",
            "parallel",
            "skip_errors",
            "preserve_structure",
            "zip",
            "assets_layout",
            "watch",
            "watch_debounce",
            "collate",
            "no_summary",
            "save_config",
            "dry_run",
            "detect_only",
            "exclude",
            # Rich output customization arguments
            "rich_code_theme",
            "rich_inline_code_theme",
            "rich_no_word_wrap",
            "rich_hyperlinks",
            "rich_justify",
            "force_rich",
            # Security presets from cli.create_parser
            "strict_html_sanitize",
            "safe_mode",
            "paranoid_mode",
            # Transform arguments
            "transforms",
            # Merge-from-list arguments
            "merge_from_list",
            "generate_toc",
            "toc_title",
            "toc_depth",
            "toc_position",
            "list_separator",
            "no_section_titles",
            # Batch-from-list arguments
            "batch_from_list",
            # Section extraction and outline arguments
            "extract",
            "outline",
            "outline_max_level",
        } | global_attachment_fields  # Union with global attachment fields

        # Process each argument
        for arg_name, arg_value in args_dict.items():
            # Skip CLI-only arguments
            if arg_name in cli_only_args:
                continue

            # Only process arguments that were explicitly provided
            if arg_name not in provided_args:
                continue

            # Handle dot notation arguments (e.g., "pdf.pages" or "html.network.allowed_hosts")
            if "." in arg_name:
                self._process_dot_notation_arg(arg_name, arg_value, options_classes, options, unknown_args)
            else:
                # Handle non-dot notation arguments (BaseOptions fields)
                self._process_base_options_arg(arg_name, arg_value, options_classes, options, unknown_args)

        # Handle global attachment flags - propagate to all formats
        self._propagate_global_attachment_fields(provided_args, args_dict, options_classes, options)

        # Validate unknown arguments
        if unknown_args:
            # Check if strict mode is enabled (can be controlled via env var or arg)
            strict_mode = getattr(parsed_args, "strict_args", False)

            help_hint = "See 'all2md help full' or 'all2md help <format>'."

            error_messages = []
            for unknown_arg in unknown_args:
                # Suggest similar argument using dest-to-CLI-flag mapping
                suggestion = self._suggest_similar_argument(unknown_arg)

                if suggestion:
                    msg = (
                        f"Unknown argument: --{unknown_arg.replace('_', '-')}. "
                        f"Did you mean {suggestion}? {help_hint}"
                    )
                else:
                    msg = f"Unknown argument: --{unknown_arg.replace('_', '-')}. " f"{help_hint}"

                error_messages.append(msg)

            if strict_mode:
                # Fail on unknown arguments
                full_error = "\n".join(error_messages)
                raise argparse.ArgumentTypeError(
                    f"Invalid arguments:\n{full_error}\n"
                    "See 'all2md help full' or 'all2md help <format>' for complete option lists."
                )
            else:
                # Warn about unknown arguments via logger
                for msg in error_messages:
                    logger.warning(msg)

        return options

    def _process_argument_value(
        self, field: Any, metadata: Dict[str, Any], arg_value: Any, arg_name: str, was_provided: bool = False
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
        if "choices" in metadata and arg_value is not None:
            choices = metadata["choices"]
            if arg_value not in choices:
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} must be one of {choices}, got: {arg_value}"
                )

        # Handle list_int type (comma-separated integers)
        if metadata.get("type") == "list_int" and isinstance(arg_value, str):
            try:
                return [int(x.strip()) for x in arg_value.split(",")]
            except ValueError as e:
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} expects comma-separated integers, " f"got: {arg_value}"
                ) from e

        # Validate integer type if specified in metadata
        if metadata.get("type") is int and arg_value is not None:
            if not isinstance(arg_value, int):
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} expects an integer, "
                    f"got: {arg_value} (type: {type(arg_value).__name__})"
                )

        # Validate float type if specified in metadata
        if metadata.get("type") is float and arg_value is not None:
            if not isinstance(arg_value, (int, float)):
                raise argparse.ArgumentTypeError(
                    f"Argument --{arg_name.replace('_', '-')} expects a number, "
                    f"got: {arg_value} (type: {type(arg_value).__name__})"
                )

        # For explicitly provided arguments, return the value
        # The tracking actions ensure we only get here for user-provided values
        return arg_value


def validate_pygments_theme(theme_name: str) -> str:
    """Validate that a Pygments theme name is valid.

    Parameters
    ----------
    theme_name : str
        Theme name to validate

    Returns
    -------
    str
        The validated theme name

    Raises
    ------
    argparse.ArgumentTypeError
        If theme name is not valid

    """
    try:
        from pygments.styles import get_all_styles
    except ImportError:
        # Hardcoded for fallback
        def get_all_styles() -> list[str]:
            """Return list of available Pygments styles as fallback."""
            return [
                "abap",
                "algol",
                "algol_nu",
                "arduino",
                "autumn",
                "bw",
                "borland",
                "coffee",
                "colorful",
                "default",
                "dracula",
                "emacs",
                "friendly_grayscale",
                "friendly",
                "fruity",
                "github-dark",
                "gruvbox-dark",
                "gruvbox-light",
                "igor",
                "inkpot",
                "lightbulb",
                "lilypond",
                "lovelace",
                "manni",
                "material",
                "monokai",
                "murphy",
                "native",
                "nord-darker",
                "nord",
                "one-dark",
                "paraiso-dark",
                "paraiso-light",
                "pastie",
                "perldoc",
                "rainbow_dash",
                "rrt",
                "sas",
                "solarized-dark",
                "solarized-light",
                "staroffice",
                "stata-dark",
                "stata-light",
                "tango",
                "trac",
                "vim",
                "vs",
                "xcode",
                "zenburn",
            ]

    available_themes = list(get_all_styles())
    if theme_name not in available_themes:
        # Show top 10 suggestions
        suggestions = sorted(difflib.get_close_matches(theme_name, available_themes))
        raise argparse.ArgumentTypeError(
            f"Invalid Pygments theme '{theme_name}'. "
            f"Did you mean: {', '.join(suggestions)}... "
            f"See https://pygments.org/styles/ for full list."
        )
    return theme_name


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser using dynamic generation."""
    builder = DynamicCLIBuilder()
    parser = builder.build_parser()

    # Add global attachment arguments that apply to all formats
    builder.add_global_attachment_arguments(parser)

    # Multi-file processing options
    parser.add_argument("--recursive", "-r", action=TrackingStoreTrueAction, help="Process directories recursively")

    parser.add_argument(
        "--parallel",
        "-p",
        action=TrackingPositiveIntAction,
        nargs="?",
        const=None,
        default=1,
        help="Process files in parallel (optionally specify number of workers, must be positive)",
    )

    parser.add_argument(
        "--output-dir",
        action=TrackingStoreAction,
        type=str,
        help="Directory to save converted files (for multi-file processing)",
    )

    parser.add_argument(
        "--output-extension",
        action=TrackingStoreAction,
        type=str,
        metavar="EXT",
        help="Custom output file extension (e.g., .htm). Overrides default extension from --output-format. "
        "Primarily useful with --watch or --output-dir for batch conversions.",
    )

    parser.add_argument(
        "--preserve-structure", action=TrackingStoreTrueAction, help="Preserve directory structure in output directory"
    )

    parser.add_argument(
        "--skip-errors", action=TrackingStoreTrueAction, help="Continue processing remaining files if one fails"
    )

    parser.add_argument(
        "--exclude",
        action=TrackingAppendAction,
        metavar="PATTERN",
        help="Exclude files matching this glob pattern (can be specified multiple times)",
    )

    # File merging and collation options
    parser.add_argument(
        "--collate", action=TrackingStoreTrueAction, help="Combine multiple files into a single output (stdout or file)"
    )

    parser.add_argument(
        "--merge-from-list",
        action=TrackingStoreAction,
        type=str,
        metavar="PATH",
        help="Merge files from a list file (TSV format: path[<tab>section_title])",
    )

    parser.add_argument(
        "--batch-from-list",
        action=TrackingStoreAction,
        type=str,
        metavar="PATH",
        help="Process files from a list file (one path per line, # for comments). "
        'Use "-" to read from stdin. Paths are processed individually unlike --merge-from-list.',
    )

    parser.add_argument(
        "--list-separator",
        action=TrackingStoreAction,
        type=str,
        default="\t",
        metavar="SEP",
        help="Separator character for list file (default: tab)",
    )

    parser.add_argument(
        "--generate-toc", action=TrackingStoreTrueAction, help="Generate table of contents when using --merge-from-list"
    )

    parser.add_argument(
        "--toc-title",
        action=TrackingStoreAction,
        type=str,
        default="Table of Contents",
        metavar="TITLE",
        help='Title for the table of contents (default: "Table of Contents")',
    )

    parser.add_argument(
        "--toc-depth",
        action=TrackingStoreAction,
        type=int,
        default=3,
        metavar="DEPTH",
        help="Maximum heading level to include in TOC (1-6, default: 3)",
    )

    parser.add_argument(
        "--toc-position",
        action=TrackingStoreAction,
        type=str,
        choices=["top", "bottom"],
        default="top",
        help="Position of the table of contents (default: top)",
    )

    parser.add_argument(
        "--no-section-titles",
        action=TrackingStoreTrueAction,
        help="Disable section title headers when merging from list",
    )

    # Configuration save option
    parser.add_argument("--save-config", type=str, help="Save current CLI arguments to a JSON configuration file")

    # Output display options
    parser.add_argument(
        "--rich",
        action=TrackingStoreTrueAction,
        help="Enable rich terminal output with formatting (automatically disabled when output is piped)",
    )

    parser.add_argument(
        "--pager",
        action=TrackingStoreTrueAction,
        help="Display output using system pager for long documents (stdout only)",
    )

    parser.add_argument(
        "--progress",
        action=TrackingStoreTrueAction,
        help="Show progress bar for file conversions (automatically enabled for multiple files)",
    )

    parser.add_argument(
        "--no-summary", action=TrackingStoreTrueAction, help="Disable summary output after processing multiple files"
    )

    # Create Rich output options group
    rich_group = parser.add_argument_group(
        "Rich output customization",
        "Customize rich terminal output with syntax highlighting and formatting. "
        "Requires: `pip install all2md[rich]`",
    )
    rich_group.add_argument(
        "--rich-code-theme",
        action=TrackingStoreAction,
        type=validate_pygments_theme,
        metavar="THEME",
        default="monokai",
        help="Pygments theme for code blocks. Popular themes: monokai (default), dracula, "
        "github-dark, vim, material, one-dark, nord, solarized-dark, solarized-light. "
        "Full list: https://pygments.org/styles/",
    )
    rich_group.add_argument(
        "--rich-inline-code-theme",
        action=TrackingStoreAction,
        type=validate_pygments_theme,
        metavar="THEME",
        help="Pygments theme for inline code. If not specified, uses same theme as code blocks. "
        "See --rich-code-theme for available themes.",
    )
    rich_group.add_argument(
        "--rich-no-word-wrap",
        action=TrackingStoreTrueAction,
        help="Disable word wrapping in rich output (defaults to wrapping long lines)",
    )
    rich_group.add_argument(
        "--no-rich-hyperlinks",
        action=TrackingStoreFalseAction,
        dest="rich_hyperlinks",
        default=True,
        help="Disable clickable hyperlink rendering in terminal output",
    )
    rich_group.add_argument(
        "--rich-justify",
        action=TrackingStoreAction,
        type=str,
        choices=["left", "center", "right", "full"],
        default="left",
        help="Text justification for markdown rendering. Options: left (default), center, right, full",
    )
    rich_group.add_argument(
        "--force-rich",
        action=TrackingStoreTrueAction,
        help="Force rich output even when stdout is piped or redirected. By default, rich formatting "
        "is automatically disabled when output is piped to preserve clean parseable content.",
    )

    # Output packaging options
    parser.add_argument(
        "--zip",
        action=TrackingStoreAction,
        nargs="?",
        const="auto",
        metavar="PATH",
        help="Create zip archive of output (optionally specify custom path, default: output_dir.zip)",
    )

    parser.add_argument(
        "--assets-layout",
        action=TrackingStoreAction,
        choices=["flat", "by-stem", "structured"],
        default="flat",
        help="Asset organization: flat (single assets/ dir), by-stem (assets/{doc}/), structured (preserve structure)",
    )

    # Watch mode options
    parser.add_argument(
        "--watch",
        action=TrackingStoreTrueAction,
        help="Watch mode: monitor files/directories and convert on change (requires --output-dir)",
    )

    parser.add_argument(
        "--watch-debounce",
        action=TrackingStoreAction,
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="Debounce delay for watch mode in seconds (default: 1.0)",
    )

    # Security preset flags
    security_group = parser.add_argument_group("Security preset options")
    security_group.add_argument(
        "--strict-html-sanitize",
        action=TrackingStoreTrueAction,
        help="Enable strict HTML sanitization (disables remote fetch, local files, strips dangerous elements)",
    )
    security_group.add_argument(
        "--safe-mode",
        action=TrackingStoreTrueAction,
        help="Balanced security for untrusted input (allows HTTPS remote fetch, strips dangerous elements)",
    )
    security_group.add_argument(
        "--paranoid-mode",
        action=TrackingStoreTrueAction,
        help="Maximum security settings (strict restrictions, reduced size limits)",
    )

    # Debugging and validation options
    parser.add_argument(
        "--dry-run",
        action=TrackingStoreTrueAction,
        help="Show what would be converted without actually processing files",
    )

    parser.add_argument(
        "--detect-only",
        action=TrackingStoreTrueAction,
        help="Show format detection results without conversion (useful for debugging batch inputs)",
    )

    return parser


EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_DEPENDENCY_ERROR = 2
EXIT_VALIDATION_ERROR = 3
EXIT_FILE_ERROR = 4
EXIT_FORMAT_ERROR = 5
EXIT_PARSING_ERROR = 6
EXIT_RENDERING_ERROR = 7
EXIT_SECURITY_ERROR = 8
EXIT_PASSWORD_ERROR = 9
EXIT_INPUT_ERROR = 10


def get_exit_code_for_exception(exception: Exception) -> int:
    """Map an exception to an appropriate CLI exit code.

    Parameters
    ----------
    exception : Exception
        The exception to map to an exit code

    Returns
    -------
    int
        The appropriate exit code for the exception type

    """
    # Check for password-protected files (most specific)
    if isinstance(exception, PasswordProtectedError):
        return EXIT_PASSWORD_ERROR

    # Check for security violations
    if isinstance(exception, SecurityError):
        return EXIT_SECURITY_ERROR

    # Check for dependency-related errors
    if isinstance(exception, (DependencyError, ImportError)):
        return EXIT_DEPENDENCY_ERROR

    # Check for validation errors
    if isinstance(exception, ValidationError):
        return EXIT_VALIDATION_ERROR

    # Check for file I/O errors
    if isinstance(exception, FileError):
        return EXIT_FILE_ERROR

    # Check for format errors
    if isinstance(exception, FormatError):
        return EXIT_FORMAT_ERROR

    # Check for parsing errors
    if isinstance(exception, ParsingError):
        return EXIT_PARSING_ERROR

    # Check for rendering errors
    if isinstance(exception, RenderingError):
        return EXIT_RENDERING_ERROR

    # All other errors (unexpected errors)
    return EXIT_ERROR
