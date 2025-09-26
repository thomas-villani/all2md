"""Custom argparse Action classes for all2md CLI.

This module provides specialized argparse Action classes that handle complex
argument processing without requiring post-creation parser modification.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import logging
import os
from typing import Any, Optional, Sequence, Union


class EnvironmentVariableAction(argparse.Action):
    """Action that applies environment variables as defaults during argument parsing.

    This replaces the need to modify parser._actions after creation by handling
    environment variable integration during the parsing phase.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the action with environment variable support."""
        super().__init__(*args, **kwargs)
        self._env_applied = False

    def __call__(
            self, parser: argparse.ArgumentParser, namespace: argparse.Namespace,
            values: Union[str, Sequence[Any], None], option_string: Optional[str] = None
            ):
        """Apply environment variable if no explicit value provided."""
        # Apply environment variable as default if not already done
        if not self._env_applied:
            self._apply_env_default()
            self._env_applied = True

        # Process the actual argument value
        if self.action == 'store_true':
            setattr(namespace, self.dest, True)
        elif self.action == 'store_false':
            setattr(namespace, self.dest, False)
        elif self.action == 'store':
            setattr(namespace, self.dest, values)
        elif self.action == 'append':
            items = getattr(namespace, self.dest, None) or []
            items.append(values)
            setattr(namespace, self.dest, items)
        else:
            # Fallback to default action
            setattr(namespace, self.dest, values)

    def _apply_env_default(self):
        """Apply environment variable as default if available."""
        env_key = f"ALL2MD_{self.dest.upper().replace('-', '_')}"
        env_value = os.environ.get(env_key)

        if env_value is not None:
            # Handle different argument types
            if self.type is int:
                try:
                    self.default = int(env_value)
                except ValueError:
                    logging.warning(f"Invalid integer value for {env_key}: {env_value}")
            elif self.type is float:
                try:
                    self.default = float(env_value)
                except ValueError:
                    logging.warning(f"Invalid float value for {env_key}: {env_value}")
            elif hasattr(self, 'choices') and self.choices:
                # Handle choice arguments
                if env_value in self.choices:
                    self.default = env_value
                else:
                    logging.warning(f"Invalid choice for {env_key}: {env_value}. Choices: {list(self.choices)}")
            elif self.action == 'store_true':
                # Handle boolean flags
                self.default = env_value.lower() in ('true', '1', 'yes', 'on')
            elif self.action == 'store_false':
                # Handle negative boolean flags
                self.default = env_value.lower() not in ('true', '1', 'yes', 'on')
            else:
                # Handle string arguments
                self.default = env_value


class DynamicVersionAction(argparse._VersionAction):
    """Action that displays version information without requiring post-creation modification.

    This replaces the need to modify parser._actions to update version strings.
    """

    def __init__(self, option_strings, version_callback=None, **kwargs):
        """Initialize with a callback to get version dynamically.

        Parameters
        ----------
        version_callback : callable, optional
            Function that returns the version string when called
        """
        # Store callback and use placeholder version for parent
        self.version_callback = version_callback

        # Set default parameters for _VersionAction
        if 'version' not in kwargs:
            kwargs['version'] = "placeholder"
        if 'dest' not in kwargs:
            kwargs['dest'] = argparse.SUPPRESS
        if 'default' not in kwargs:
            kwargs['default'] = argparse.SUPPRESS

        # Call parent constructor
        super().__init__(option_strings, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """Display version and exit."""
        version = self.version
        if self.version_callback:
            version = self.version_callback()

        parser.exit(message=f"{version}\n")


class TypedChoiceAction(argparse.Action):
    """Action that handles typed choices with better validation and error messages."""

    def __init__(self, *args, choices=None, choice_type=None, **kwargs):
        """Initialize with typed choices.

        Parameters
        ----------
        choices : list
            Valid choices for the argument
        choice_type : type, optional
            Type to convert the choice to
        """
        super().__init__(*args, **kwargs)
        self.choices = choices
        self.choice_type = choice_type

    def __call__(self, parser, namespace, values, option_string=None):
        """Validate and convert the choice value."""
        if self.choices and values not in self.choices:
            raise argparse.ArgumentTypeError(
                f"Invalid choice: '{values}' (choose from {list(self.choices)})"
            )

        # Convert to the specified type if provided
        if self.choice_type:
            try:
                values = self.choice_type(values)
            except (ValueError, TypeError) as e:
                raise argparse.ArgumentTypeError(
                    f"Cannot convert '{values}' to {self.choice_type.__name__}: {e}"
                ) from e

        setattr(namespace, self.dest, values)


class PositiveIntAction(argparse.Action):
    """Action that validates positive integers with better error messages."""

    def __call__(self, parser, namespace, values, option_string=None):
        """Validate and convert to positive integer."""
        # Handle nargs='?' case where values can be None (use const)
        if values is None:
            setattr(namespace, self.dest, self.const)
            return

        try:
            ivalue = int(values)
            if ivalue <= 0:
                parser.error(f"argument {option_string}: {values} is not a positive integer")
            setattr(namespace, self.dest, ivalue)
        except ValueError:
            parser.error(f"argument {option_string}: {values} is not a valid integer")


class CommaSeparatedListAction(argparse.Action):
    """Action that parses comma-separated values into a list."""

    def __init__(self, *args, item_type=str, **kwargs):
        """Initialize with item type for list elements.

        Parameters
        ----------
        item_type : type, default str
            Type to convert each list item to
        """
        super().__init__(*args, **kwargs)
        self.item_type = item_type

    def __call__(self, parser, namespace, values, option_string=None):
        """Parse comma-separated values into a typed list."""
        if isinstance(values, str):
            try:
                items = [self.item_type(item.strip()) for item in values.split(',')]
                setattr(namespace, self.dest, items)
            except (ValueError, TypeError) as e:
                raise argparse.ArgumentTypeError(
                    f"Cannot convert comma-separated values to {self.item_type.__name__}: {e}"
                ) from e
        else:
            setattr(namespace, self.dest, values)


def create_env_aware_action(**action_kwargs):
    """Factory function to create environment-aware action classes.

    Parameters
    ----------
    **action_kwargs
        Action-specific kwargs (like action='store_true', type=str, etc.)

    Returns
    -------
    type
        Custom action class with environment variable support
    """
    action_type = action_kwargs.get('action', 'store')

    # Determine the base action class based on the action type
    if action_type == 'store_true':
        base_class = argparse._StoreTrueAction
    elif action_type == 'store_false':
        base_class = argparse._StoreFalseAction
    elif action_type == 'store':
        base_class = argparse._StoreAction
    elif action_type == 'append':
        base_class = argparse._AppendAction
    else:
        base_class = argparse.Action

    class EnvAwareAction(base_class):
        def __init__(self, *args, **kwargs):
            # Merge provided action_kwargs
            final_kwargs = action_kwargs.copy()
            final_kwargs.update(kwargs)

            # Remove 'action' from kwargs since it's used for class selection
            if 'action' in final_kwargs:
                del final_kwargs['action']

            super().__init__(*args, **final_kwargs)
            # Don't apply env vars in __init__ - dest isn't set yet

        def __call__(self, parser, namespace, values, option_string=None):
            """Apply environment variable default and then call parent action."""
            # Apply environment variable default if this argument wasn't explicitly provided
            if not hasattr(namespace, self.dest) or getattr(namespace, self.dest) == self.default:
                self._apply_env_default()

            # Call parent action
            if callable(super()):
                super().__call__(parser, namespace, values, option_string)
            else:
                # Fallback for actions that don't define __call__
                setattr(namespace, self.dest, values if values is not None else self.default)

        def _apply_env_default(self):
            """Apply environment variable as default if available."""
            env_key = f"ALL2MD_{self.dest.upper().replace('-', '_')}"
            env_value = os.environ.get(env_key)

            if env_value is not None:
                # Handle different action types
                if isinstance(self, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
                    # For boolean actions, convert string to boolean
                    self.default = env_value.lower() in ('true', '1', 'yes', 'on')
                elif self.type:
                    try:
                        self.default = self.type(env_value)
                    except (ValueError, TypeError):
                        logging.warning(f"Cannot convert env var {env_key}={env_value} to {self.type}")
                else:
                    self.default = env_value

    return EnvAwareAction
