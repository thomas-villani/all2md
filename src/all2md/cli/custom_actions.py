"""Custom argparse actions for improved CLI argument handling.

This module provides custom actions that enhance argparse functionality
for better argument tracking, nested namespace handling, and environment
variable support.
"""

from __future__ import annotations

#  Copyright (c) 2025 Tom Villani, Ph.D.
import argparse
import logging
import os
from typing import Any, Callable, Optional, Sequence, Union


class TrackingStoreAction(argparse.Action):
    """Custom action that tracks whether an argument was explicitly provided.

    This action stores both the value and metadata about whether the argument
    was provided by the user, making it easier to distinguish between default
    values and user-provided values that happen to match the default.

    Also supports environment variable defaults using the pattern ALL2MD_DEST_NAME.
    """

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Optional[Union[int, str]] = None,
        const: Optional[Any] = None,
        default: Optional[Any] = None,
        type: Optional[Callable[[str], Any]] = None,
        choices: Optional[Sequence[Any]] = None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[Union[str, tuple[str, ...]]] = None,
    ) -> None:
        """Initialize the tracking store action.

        Parameters
        ----------
        option_strings : Sequence[str]
            The option strings for this action
        dest : str
            The attribute name to store the value
        nargs : Optional[Union[int, str]]
            Number of arguments to consume
        const : Optional[Any]
            Constant value for special cases
        default : Optional[Any]
            Default value if not provided
        type : Optional[Any]
            Type conversion function
        choices : Optional[Sequence[Any]]
            Valid choices for the argument
        required : bool
            Whether this argument is required
        help : Optional[str]
            Help text for the argument
        metavar : Optional[Union[str, tuple[str, ...]]]
            Display name for the argument value

        """
        # Check environment variable and set as default if present
        env_key = f"ALL2MD_{dest.upper().replace('-', '_').replace('.', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            # Apply type conversion if specified
            try:
                if type is not None:
                    default = type(env_value)
                else:
                    default = env_value
            except (ValueError, TypeError) as e:
                logging.warning(f"Invalid environment variable {env_key}={env_value}: {e}")

        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        """Store the value and mark it as explicitly provided.

        Parameters
        ----------
        parser : argparse.ArgumentParser
            The parser instance
        namespace : argparse.Namespace
            The namespace to store values in
        values : Union[str, Sequence[Any], None]
            The parsed values
        option_string : Optional[str]
            The option string that was used

        """
        # Store the actual value
        setattr(namespace, self.dest, values)

        # Track that this argument was explicitly provided
        if not hasattr(namespace, "_provided_args"):
            namespace._provided_args = set()
        namespace._provided_args.add(self.dest)


class TrackingStoreTrueAction(argparse.Action):
    """Custom store_true action that tracks whether the flag was explicitly provided.

    Also supports environment variable defaults using the pattern ALL2MD_DEST_NAME.
    """

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: bool = False,
        required: bool = False,
        help: Optional[str] = None,
    ) -> None:
        """Initialize the tracking store_true action.

        Parameters
        ----------
        option_strings : Sequence[str]
            The option strings for this action
        dest : str
            The attribute name to store the value
        default : bool
            Default value (should be False for store_true)
        required : bool
            Whether this argument is required
        help : Optional[str]
            Help text for the argument

        """
        # Check environment variable and set as default if present
        env_key = f"ALL2MD_{dest.upper().replace('-', '_').replace('.', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            # Convert env var to boolean
            default = env_value.lower() in ("true", "1", "yes", "on")

        super().__init__(
            option_strings=option_strings, dest=dest, nargs=0, const=True, default=default, required=required, help=help
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        """Store True and mark as explicitly provided.

        Parameters
        ----------
        parser : argparse.ArgumentParser
            The parser instance
        namespace : argparse.Namespace
            The namespace to store values in
        values : Union[str, Sequence[Any], None]
            The parsed values (ignored for store_true)
        option_string : Optional[str]
            The option string that was used

        """
        setattr(namespace, self.dest, True)

        # Track that this argument was explicitly provided
        if not hasattr(namespace, "_provided_args"):
            namespace._provided_args = set()
        namespace._provided_args.add(self.dest)


class TrackingStoreFalseAction(argparse.Action):
    """Custom store_false action that tracks whether the flag was explicitly provided.

    Also supports environment variable defaults using the pattern ALL2MD_DEST_NAME.
    """

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: bool = True,
        required: bool = False,
        help: Optional[str] = None,
    ) -> None:
        """Initialize the tracking store_false action.

        Parameters
        ----------
        option_strings : Sequence[str]
            The option strings for this action
        dest : str
            The attribute name to store the value
        default : bool
            Default value (should be True for store_false)
        required : bool
            Whether this argument is required
        help : Optional[str]
            Help text for the argument

        """
        # Check environment variable and set as default if present
        env_key = f"ALL2MD_{dest.upper().replace('-', '_').replace('.', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            # Convert env var to boolean
            # For store_false action, we keep the same logic as store_true
            default = env_value.lower() in ("true", "1", "yes", "on")

        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=False,
            default=default,
            required=required,
            help=help,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        """Store False and mark as explicitly provided.

        Parameters
        ----------
        parser : argparse.ArgumentParser
            The parser instance
        namespace : argparse.Namespace
            The namespace to store values in
        values : Union[str, Sequence[Any], None]
            The parsed values (ignored for store_false)
        option_string : Optional[str]
            The option string that was used

        """
        setattr(namespace, self.dest, False)

        # Track that this argument was explicitly provided
        if not hasattr(namespace, "_provided_args"):
            namespace._provided_args = set()
        namespace._provided_args.add(self.dest)


class TrackingAppendAction(argparse.Action):
    """Custom append action that tracks explicitly provided arguments.

    Also supports environment variable defaults using the pattern ALL2MD_DEST_NAME.
    Environment values are split on commas.
    """

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Optional[Union[int, str]] = None,
        const: Optional[Any] = None,
        default: Optional[list] = None,
        type: Optional[Callable[[str], Any]] = None,
        choices: Optional[Sequence[Any]] = None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[Union[str, tuple[str, ...]]] = None,
    ) -> None:
        """Initialize the tracking append action.

        Parameters
        ----------
        option_strings : Sequence[str]
            The option strings for this action
        dest : str
            The attribute name to store the value
        nargs : Optional[Union[int, str]]
            Number of arguments to consume
        const : Optional[Any]
            Constant value for special cases
        default : Optional[list]
            Default value if not provided
        type : Optional[Any]
            Type conversion function
        choices : Optional[Sequence[Any]]
            Valid choices for the argument
        required : bool
            Whether this argument is required
        help : Optional[str]
            Help text for the argument
        metavar : Optional[Union[str, tuple[str, ...]]]
            Display name for the argument value

        """
        # Check environment variable and set as default if present
        env_key = f"ALL2MD_{dest.upper().replace('-', '_').replace('.', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            # Split on commas for append actions
            default = [item.strip() for item in env_value.split(",")]
            # Apply type conversion if specified (matching CLI behavior)
            if type is not None:
                try:
                    default = [type(item) for item in default]
                except (ValueError, TypeError) as e:
                    logging.warning(f"Invalid type conversion for {env_key}={env_value}: {e}")
                    default = None  # Fall back to no default if conversion fails

        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        """Append the value and mark as explicitly provided.

        Handles both single values and lists (from nargs) correctly.
        For nargs='+', extends the list instead of appending a nested list.

        Parameters
        ----------
        parser : argparse.ArgumentParser
            The parser instance
        namespace : argparse.Namespace
            The namespace to store values in
        values : Union[str, Sequence[Any], None]
            The parsed values
        option_string : Optional[str]
            The option string that was used

        """
        # Get existing list or create new one
        items = getattr(namespace, self.dest, None)
        if items is None:
            items = []
        else:
            items = items.copy() if isinstance(items, list) else []

        # Handle nargs lists vs single values
        if isinstance(values, (list, tuple)):
            # For nargs='+' or nargs=N, extend the list instead of appending
            # Apply type converter to each element if provided
            if self.type is not None:
                try:
                    converted_values = [self.type(v) for v in values]  # type: ignore[operator]
                    items.extend(converted_values)
                except (ValueError, TypeError) as e:
                    parser.error(f"argument {option_string}: invalid value(s): {e}")
            else:
                items.extend(values)
        else:
            # Single value - append normally
            # Apply type converter if provided
            converted_value: Union[str, Sequence[Any], None] = values
            if self.type is not None and values is not None:
                try:
                    converted_value = self.type(values)  # type: ignore[arg-type, assignment, operator]
                except (ValueError, TypeError) as e:
                    parser.error(f"argument {option_string}: invalid value: {e}")
            items.append(converted_value)

        setattr(namespace, self.dest, items)

        # Track that this argument was explicitly provided
        if not hasattr(namespace, "_provided_args"):
            namespace._provided_args = set()
        namespace._provided_args.add(self.dest)


class TrackingPositiveIntAction(argparse.Action):
    """Action that validates positive integers with tracking and environment variable support."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Optional[Union[int, str]] = None,
        const: Optional[Any] = None,
        default: Optional[int] = None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[Union[str, tuple[str, ...]]] = None,
    ) -> None:
        """Initialize the tracking positive int action.

        Parameters
        ----------
        option_strings : Sequence[str]
            The option strings for this action
        dest : str
            The attribute name to store the value
        nargs : Optional[Union[int, str]]
            Number of arguments to consume
        const : Optional[Any]
            Constant value for special cases
        default : Optional[int]
            Default value if not provided
        required : bool
            Whether this argument is required
        help : Optional[str]
            Help text for the argument
        metavar : Optional[Union[str, tuple[str, ...]]]
            Display name for the argument value

        """
        # Check environment variable and set as default if present
        env_key = f"ALL2MD_{dest.upper().replace('-', '_').replace('.', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            try:
                ivalue = int(env_value)
                if ivalue <= 0:
                    logging.warning(f"Environment variable {env_key}: {env_value} is not a positive integer")
                else:
                    default = ivalue
            except ValueError:
                logging.warning(f"Environment variable {env_key}: {env_value} is not a valid integer")

        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            required=required,
            help=help,
            metavar=metavar,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        """Validate and convert to positive integer.

        Parameters
        ----------
        parser : argparse.ArgumentParser
            The parser instance
        namespace : argparse.Namespace
            The namespace to store values in
        values : Union[str, Sequence[Any], None]
            The parsed values
        option_string : Optional[str]
            The option string that was used

        """
        # Handle nargs='?' case where values can be None (use const)
        if values is None:
            setattr(namespace, self.dest, self.const)
            if not hasattr(namespace, "_provided_args"):
                namespace._provided_args = set()
            namespace._provided_args.add(self.dest)
            return

        # Validate and convert to positive integer
        try:
            ivalue = int(str(values))
            if ivalue <= 0:
                parser.error(f"argument {option_string}: {values} is not a positive integer")
            setattr(namespace, self.dest, ivalue)

            # Track that this argument was explicitly provided
            if not hasattr(namespace, "_provided_args"):
                namespace._provided_args = set()
            namespace._provided_args.add(self.dest)
        except ValueError:
            parser.error(f"argument {option_string}: {values} is not a valid integer")


class DynamicVersionAction(argparse._VersionAction):
    """Action that displays version information without requiring post-creation modification.

    This replaces the need to modify parser._actions to update version strings.
    """

    def __init__(
        self, option_strings: Sequence[str], version_callback: Optional[Callable[[], str]] = None, **kwargs: Any
    ) -> None:
        """Initialize with a callback to get version dynamically.

        Parameters
        ----------
        option_strings : Sequence[str]
            Option strings for this action
        version_callback : callable, optional
            Function that returns the version string when called
        **kwargs : Any
            Additional keyword arguments passed to parent action

        """
        # Store callback and use placeholder version for parent
        self.version_callback = version_callback

        # Set default parameters for _VersionAction
        if "version" not in kwargs:
            kwargs["version"] = "placeholder"
        if "dest" not in kwargs:
            kwargs["dest"] = argparse.SUPPRESS
        if "default" not in kwargs:
            kwargs["default"] = argparse.SUPPRESS

        # Call parent constructor
        super().__init__(option_strings, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        """Display version and exit."""
        version = self.version
        if self.version_callback:
            version = self.version_callback()

        parser.exit(message=f"{version}\n")


def parse_dot_notation(dot_string: str, value: Any) -> dict:
    """Parse a dot notation string into a nested dictionary.

    Parameters
    ----------
    dot_string : str
        Dot notation string (e.g., "pdf.pages")
    value : Any
        The value to store at the nested location

    Returns
    -------
    dict
        Nested dictionary with the value at the specified path

    Examples
    --------
    >>> parse_dot_notation("pdf.pages", [1, 2, 3])
    {'pdf': {'pages': [1, 2, 3]}}
    >>> parse_dot_notation("markdown.emphasis_symbol", "_")
    {'markdown': {'emphasis_symbol': '_'}}

    """
    parts = dot_string.split(".")
    result: dict[str, Any] = {}
    current = result

    for part in parts[:-1]:
        current[part] = {}
        current = current[part]

    current[parts[-1]] = value
    return result


def merge_nested_dicts(base: dict, update: dict) -> dict:
    """Recursively merge nested dictionaries.

    Parameters
    ----------
    base : dict
        Base dictionary to merge into
    update : dict
        Dictionary with updates to apply

    Returns
    -------
    dict
        Merged dictionary with updates applied

    Examples
    --------
    >>> base = {'pdf': {'pages': [1, 2]}}
    >>> update = {'pdf': {'password': 'secret'}}
    >>> merge_nested_dicts(base, update)
    {'pdf': {'pages': [1, 2], 'password': 'secret'}}

    """
    result: dict = base.copy()

    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_nested_dicts(result[key], value)
        else:
            result[key] = value

    return result


class TieredHelpAction(argparse.Action):
    """Custom help action that integrates the enhanced help formatter."""

    def __init__(self, option_strings: list[str], dest: str = argparse.SUPPRESS, **kwargs: Any) -> None:
        """Initialize the tiered help action.

        Parameters
        ----------
        option_strings : list
            Option strings for this action
        dest : str, optional
            Destination attribute, defaults to SUPPRESS
        **kwargs : dict
            Additional argparse action keyword arguments

        """
        kwargs.setdefault("nargs", "?")
        kwargs.setdefault("default", argparse.SUPPRESS)
        kwargs.setdefault("metavar", "SECTION")
        super().__init__(option_strings, dest, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Optional[str] = None,
    ) -> None:
        """Execute the help action.

        Parameters
        ----------
        parser : ArgumentParser
            The argument parser
        namespace : Namespace
            The namespace object
        values : Any
            The help section selector
        option_string : str, optional
            The option string used, if any

        """
        from all2md.cli.help_formatter import display_help

        selector = values or "quick"
        display_help(selector)
        parser.exit()
