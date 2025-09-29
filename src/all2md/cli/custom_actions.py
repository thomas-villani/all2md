"""Custom argparse actions for improved CLI argument handling.

This module provides custom actions that enhance argparse functionality
for better argument tracking and nested namespace handling.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
from typing import Any, Optional, Sequence, Union


class TrackingStoreAction(argparse.Action):
    """Custom action that tracks whether an argument was explicitly provided.

    This action stores both the value and metadata about whether the argument
    was provided by the user, making it easier to distinguish between default
    values and user-provided values that happen to match the default.
    """

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Optional[Union[int, str]] = None,
        const: Optional[Any] = None,
        default: Optional[Any] = None,
        type: Optional[Any] = None,
        choices: Optional[Sequence[Any]] = None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[Union[str, tuple[str, ...]]] = None
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
            metavar=metavar
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None
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
        if not hasattr(namespace, '_provided_args'):
            namespace._provided_args = set()
        namespace._provided_args.add(self.dest)


class TrackingStoreTrueAction(argparse.Action):
    """Custom store_true action that tracks whether the flag was explicitly provided."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: bool = False,
        required: bool = False,
        help: Optional[str] = None
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
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=True,
            default=default,
            required=required,
            help=help
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None
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
        if not hasattr(namespace, '_provided_args'):
            namespace._provided_args = set()
        namespace._provided_args.add(self.dest)


class TrackingStoreFalseAction(argparse.Action):
    """Custom store_false action that tracks whether the flag was explicitly provided."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        default: bool = True,
        required: bool = False,
        help: Optional[str] = None
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
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=False,
            default=default,
            required=required,
            help=help
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None
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
        if not hasattr(namespace, '_provided_args'):
            namespace._provided_args = set()
        namespace._provided_args.add(self.dest)


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
    parts = dot_string.split('.')
    result = {}
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