"""Custom argparse Action classes for all2md CLI.

This module provides specialized argparse Action classes that handle complex
argument processing without requiring post-creation parser modification.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import logging
import os


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



class PositiveIntAction(argparse.Action):
    """Action that validates positive integers with environment variable support."""

    def __call__(self, parser, namespace, values, option_string=None):
        """Validate and convert to positive integer."""
        # Handle nargs='?' case where values can be None (use const)
        if values is None:
            setattr(namespace, self.dest, self.const)
            return

        # Check environment variable first
        if not hasattr(namespace, '_env_checked'):
            namespace._env_checked = set()

        if self.dest not in namespace._env_checked:
            namespace._env_checked.add(self.dest)
            env_key = f"ALL2MD_{self.dest.upper().replace('-', '_')}"
            env_value = os.environ.get(env_key)

            if env_value is not None and not hasattr(namespace, self.dest):
                try:
                    ivalue = int(env_value)
                    if ivalue <= 0:
                        parser.error(f"Environment variable {env_key}: {env_value} is not a positive integer")
                    setattr(namespace, self.dest, ivalue)
                    return
                except ValueError:
                    parser.error(f"Environment variable {env_key}: {env_value} is not a valid integer")

        # Normal validation
        try:
            ivalue = int(values)
            if ivalue <= 0:
                parser.error(f"argument {option_string}: {values} is not a positive integer")
            setattr(namespace, self.dest, ivalue)
        except ValueError:
            parser.error(f"argument {option_string}: {values} is not a valid integer")


class EnvironmentAwareAction(argparse.Action):
    """Base action that supports environment variable defaults.

    This action checks for environment variables with the pattern ALL2MD_DEST_NAME
    and uses them as defaults when the argument is not explicitly provided.
    """

    def __init__(self, *args, **kwargs):
        # Check environment variable and set as default if present
        dest = kwargs.get('dest')
        if dest is None and args:
            # Extract dest from option strings like '--output-dir' -> 'output_dir'
            for option in args:
                if option.startswith('--'):
                    dest = option[2:].replace('-', '_')
                    break
                elif option.startswith('-'):
                    dest = option[1:]
                    break

        if dest:
            env_key = f"ALL2MD_{dest.upper().replace('-', '_')}"
            env_value = os.environ.get(env_key)
            if env_value is not None:
                # Apply type conversion and validation, override any existing default
                try:
                    converted_value = self._convert_env_value(env_value, dest)
                    kwargs['default'] = converted_value
                except (ValueError, TypeError) as e:
                    # Log warning but don't fail initialization
                    logging.warning(f"Invalid environment variable {env_key}={env_value}: {e}")

        super().__init__(*args, **kwargs)

    def _convert_env_value(self, env_value: str, dest: str):
        """Convert environment variable string to appropriate type."""
        # Handle type conversion
        if hasattr(self, 'type') and self.type is not None:
            return self.type(env_value)

        return env_value

    def __call__(self, parser, namespace, values, option_string=None):
        """Standard action processing."""
        setattr(namespace, self.dest, values)


class EnvironmentAwareBooleanAction(argparse._StoreTrueAction):
    """Boolean action that supports environment variable defaults."""

    def __init__(self, *args, **kwargs):
        # Check environment variable and set as default if present
        dest = kwargs.get('dest')
        if dest is None and args:
            # Extract dest from option strings like '--rich' -> 'rich'
            for option in args:
                if option.startswith('--'):
                    dest = option[2:].replace('-', '_')
                    break
                elif option.startswith('-'):
                    dest = option[1:]
                    break

        if dest:
            env_key = f"ALL2MD_{dest.upper().replace('-', '_')}"
            env_value = os.environ.get(env_key)
            if env_value is not None:
                # Convert env var to boolean and override any existing default
                bool_value = env_value.lower() in ('true', '1', 'yes', 'on')
                kwargs['default'] = bool_value

        super().__init__(*args, **kwargs)


class EnvironmentAwareBooleanFalseAction(argparse._StoreFalseAction):
    """Boolean false action (--no-*) that supports environment variable defaults."""

    def __init__(self, *args, **kwargs):
        # Check environment variable and set as default if present
        dest = kwargs.get('dest')
        if dest is None and args:
            # Extract dest from option strings like '--no-rich' -> 'rich'
            for option in args:
                if option.startswith('--no-'):
                    dest = option[5:].replace('-', '_')
                    break
                elif option.startswith('--'):
                    dest = option[2:].replace('-', '_')
                    break
                elif option.startswith('-'):
                    dest = option[1:]
                    break

        if dest:
            env_key = f"ALL2MD_{dest.upper().replace('-', '_')}"
            env_value = os.environ.get(env_key)
            if env_value is not None:
                # Convert env var to boolean and override any existing default
                # For store_false action, we invert the logic
                bool_value = env_value.lower() in ('true', '1', 'yes', 'on')
                kwargs['default'] = bool_value

        super().__init__(*args, **kwargs)


class EnvironmentAwareAppendAction(argparse._AppendAction):
    """Append action that supports environment variable defaults."""

    def __init__(self, *args, **kwargs):
        # Check environment variable and set as default if present
        dest = kwargs.get('dest')
        if dest is None and args:
            # Extract dest from option strings like '--exclude' -> 'exclude'
            for option in args:
                if option.startswith('--'):
                    dest = option[2:].replace('-', '_')
                    break
                elif option.startswith('-'):
                    dest = option[1:]
                    break

        if dest:
            env_key = f"ALL2MD_{dest.upper().replace('-', '_')}"
            env_value = os.environ.get(env_key)
            if env_value is not None:
                # Split on commas for append actions, override any existing default
                items = [item.strip() for item in env_value.split(',')]
                kwargs['default'] = items

        super().__init__(*args, **kwargs)


def create_env_aware_argument(parser, *args, **kwargs):
    """Helper function to add arguments with automatic environment variable support.

    This function automatically selects the appropriate environment-aware action
    based on the argument configuration.
    """
    action = kwargs.get('action', 'store')

    if action == 'store_true':
        kwargs['action'] = EnvironmentAwareBooleanAction
    elif action == 'store_false':
        kwargs['action'] = EnvironmentAwareBooleanFalseAction
    elif action == 'append':
        kwargs['action'] = EnvironmentAwareAppendAction
    elif action in ('store', None):
        kwargs['action'] = EnvironmentAwareAction
    # For other actions like DynamicVersionAction, PositiveIntAction, leave as-is

    return parser.add_argument(*args, **kwargs)


