"""Test custom argparse actions for the CLI."""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import os
from unittest.mock import patch

import pytest

from all2md.cli.custom_actions import (
    DynamicVersionAction,
    TrackingAppendAction,
    TrackingPositiveIntAction,
    TrackingStoreAction,
    TrackingStoreFalseAction,
    TrackingStoreTrueAction,
    merge_nested_dicts,
    parse_dot_notation,
)


@pytest.mark.unit
@pytest.mark.cli
class TestDotNotationHelpers:
    """Test dot notation helper functions."""

    def test_parse_dot_notation_single_level(self):
        """Test parsing single-level dot notation."""
        result = parse_dot_notation("field", "value")
        assert result == {"field": "value"}

    def test_parse_dot_notation_two_levels(self):
        """Test parsing two-level dot notation."""
        result = parse_dot_notation("pdf.pages", [1, 2, 3])
        assert result == {"pdf": {"pages": [1, 2, 3]}}

    def test_parse_dot_notation_three_levels(self):
        """Test parsing three-level dot notation."""
        result = parse_dot_notation("format.pdf.password", "secret")
        assert result == {"format": {"pdf": {"password": "secret"}}}

    def test_merge_nested_dicts_simple(self):
        """Test merging simple nested dictionaries."""
        base = {"a": 1, "b": 2}
        update = {"c": 3}
        result = merge_nested_dicts(base, update)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_merge_nested_dicts_nested(self):
        """Test merging nested dictionaries."""
        base = {"pdf": {"pages": [1, 2]}}
        update = {"pdf": {"password": "secret"}}
        result = merge_nested_dicts(base, update)
        assert result == {"pdf": {"pages": [1, 2], "password": "secret"}}

    def test_merge_nested_dicts_override(self):
        """Test that merge overrides values."""
        base = {"pdf": {"pages": [1, 2]}}
        update = {"pdf": {"pages": [3, 4]}}
        result = merge_nested_dicts(base, update)
        assert result == {"pdf": {"pages": [3, 4]}}

    def test_merge_nested_dicts_deep_nesting(self):
        """Test merging deeply nested dictionaries."""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        update = {"a": {"b": {"c": 3, "e": 4}}}
        result = merge_nested_dicts(base, update)
        assert result == {"a": {"b": {"c": 3, "d": 2, "e": 4}}}


@pytest.mark.unit
@pytest.mark.cli
class TestTrackingActions:
    """Test custom tracking argparse actions."""

    def test_tracking_store_action(self):
        """Test TrackingStoreAction tracks provided arguments."""
        parser = argparse.ArgumentParser()
        action = TrackingStoreAction(option_strings=["--test"], dest="test_field")

        namespace = argparse.Namespace()
        action(parser, namespace, "test_value", "--test")

        assert namespace.test_field == "test_value"
        assert hasattr(namespace, "_provided_args")
        assert "test_field" in namespace._provided_args

    def test_tracking_store_action_with_type(self):
        """Test TrackingStoreAction with type conversion."""
        parser = argparse.ArgumentParser()
        action = TrackingStoreAction(option_strings=["--number"], dest="number_field", type=int)

        namespace = argparse.Namespace()
        # The type conversion happens before the action is called
        action(parser, namespace, 42, "--number")

        assert namespace.number_field == 42
        assert "number_field" in namespace._provided_args

    def test_tracking_store_true_action(self):
        """Test TrackingStoreTrueAction."""
        parser = argparse.ArgumentParser()
        action = TrackingStoreTrueAction(option_strings=["--enable"], dest="enable_feature")

        namespace = argparse.Namespace()
        action(parser, namespace, None, "--enable")

        assert namespace.enable_feature is True
        assert hasattr(namespace, "_provided_args")
        assert "enable_feature" in namespace._provided_args

    def test_tracking_store_false_action(self):
        """Test TrackingStoreFalseAction."""
        parser = argparse.ArgumentParser()
        action = TrackingStoreFalseAction(option_strings=["--no-feature"], dest="feature_enabled", default=True)

        namespace = argparse.Namespace()
        action(parser, namespace, None, "--no-feature")

        assert namespace.feature_enabled is False
        assert hasattr(namespace, "_provided_args")
        assert "feature_enabled" in namespace._provided_args

    def test_tracking_actions_multiple_args(self):
        """Test that multiple arguments are tracked correctly."""
        parser = argparse.ArgumentParser()

        action1 = TrackingStoreAction(option_strings=["--arg1"], dest="arg1")
        action2 = TrackingStoreAction(option_strings=["--arg2"], dest="arg2")

        namespace = argparse.Namespace()

        action1(parser, namespace, "value1", "--arg1")
        action2(parser, namespace, "value2", "--arg2")

        assert namespace.arg1 == "value1"
        assert namespace.arg2 == "value2"
        assert "arg1" in namespace._provided_args
        assert "arg2" in namespace._provided_args
        assert len(namespace._provided_args) == 2

    def test_tracking_action_preserves_existing_provided_args(self):
        """Test that tracking actions preserve existing _provided_args."""
        parser = argparse.ArgumentParser()
        action = TrackingStoreAction(option_strings=["--new"], dest="new_arg")

        namespace = argparse.Namespace()
        # Pre-existing provided args
        namespace._provided_args = {"existing_arg"}

        action(parser, namespace, "new_value", "--new")

        assert namespace.new_arg == "new_value"
        assert "existing_arg" in namespace._provided_args
        assert "new_arg" in namespace._provided_args
        assert len(namespace._provided_args) == 2

    def test_tracking_append_action_single_values(self):
        """Test TrackingAppendAction with single values (no nargs)."""
        parser = argparse.ArgumentParser()
        action = TrackingAppendAction(option_strings=["--exclude"], dest="exclude")

        namespace = argparse.Namespace()

        # Add first value
        action(parser, namespace, "*.tmp", "--exclude")
        assert namespace.exclude == ["*.tmp"]
        assert "exclude" in namespace._provided_args

        # Add second value
        action(parser, namespace, "*.bak", "--exclude")
        assert namespace.exclude == ["*.tmp", "*.bak"]

    def test_tracking_append_action_with_nargs_list(self):
        """Test TrackingAppendAction with nargs='+' produces flat list (Issue #10)."""
        parser = argparse.ArgumentParser()
        action = TrackingAppendAction(option_strings=["--files"], dest="files", nargs="+")

        namespace = argparse.Namespace()

        # Simulate nargs='+' behavior: argparse passes values as a list
        values_list = ["file1.txt", "file2.txt", "file3.txt"]
        action(parser, namespace, values_list, "--files")

        # Should extend, not append the list (flat list, not nested)
        assert namespace.files == ["file1.txt", "file2.txt", "file3.txt"]
        assert "files" in namespace._provided_args

        # Add another batch (simulating --files a.txt b.txt --files c.txt d.txt)
        more_values = ["file4.txt", "file5.txt"]
        action(parser, namespace, more_values, "--files")

        # Should extend the existing list
        assert namespace.files == ["file1.txt", "file2.txt", "file3.txt", "file4.txt", "file5.txt"]

    def test_tracking_append_action_with_type_converter(self):
        """Test TrackingAppendAction applies type converter to each element."""
        parser = argparse.ArgumentParser()
        action = TrackingAppendAction(option_strings=["--numbers"], dest="numbers", nargs="+", type=int)

        namespace = argparse.Namespace()

        # Simulate nargs='+' with string values that need conversion
        values_list = ["1", "2", "3"]
        action(parser, namespace, values_list, "--numbers")

        # Type converter should be applied to each element
        assert namespace.numbers == [1, 2, 3]
        assert all(isinstance(n, int) for n in namespace.numbers)

    def test_tracking_append_action_mixed_single_and_nargs(self):
        """Test TrackingAppendAction handles mix of single values and nargs lists."""
        parser = argparse.ArgumentParser()
        action = TrackingAppendAction(option_strings=["--items"], dest="items")

        namespace = argparse.Namespace()

        # Single value
        action(parser, namespace, "single", "--items")
        assert namespace.items == ["single"]

        # List from nargs (in real usage, this would be from different invocation with nargs)
        action(parser, namespace, ["multi1", "multi2"], "--items")
        assert namespace.items == ["single", "multi1", "multi2"]

        # Another single value
        action(parser, namespace, "another", "--items")
        assert namespace.items == ["single", "multi1", "multi2", "another"]


@pytest.mark.unit
@pytest.mark.cli
class TestIntegrationWithArgparse:
    """Test integration of custom actions with argparse."""

    def test_parser_with_tracking_actions(self):
        """Test that a parser can use tracking actions."""
        parser = argparse.ArgumentParser()

        parser.add_argument("--text", action=TrackingStoreAction, dest="text_field")
        parser.add_argument("--enable", action=TrackingStoreTrueAction, dest="enable_flag")
        parser.add_argument("--no-feature", action=TrackingStoreFalseAction, dest="feature_flag", default=True)

        # Parse with some arguments
        args = parser.parse_args(["--text", "hello", "--enable"])

        assert args.text_field == "hello"
        assert args.enable_flag is True
        assert args.feature_flag is True  # Default, not provided

        assert hasattr(args, "_provided_args")
        assert "text_field" in args._provided_args
        assert "enable_flag" in args._provided_args
        assert "feature_flag" not in args._provided_args  # Not provided

    def test_dot_notation_dest_with_tracking(self):
        """Test that dot notation destinations work with tracking actions."""
        parser = argparse.ArgumentParser()

        parser.add_argument("--pdf-pages", action=TrackingStoreAction, dest="pdf.pages")
        parser.add_argument("--markdown-emphasis", action=TrackingStoreAction, dest="markdown.emphasis")

        args = parser.parse_args(["--pdf-pages", "1,2,3", "--markdown-emphasis", "_"])

        # Check that dot notation is preserved in namespace
        assert hasattr(args, "pdf.pages")
        assert getattr(args, "pdf.pages") == "1,2,3"
        assert hasattr(args, "markdown.emphasis")
        assert getattr(args, "markdown.emphasis") == "_"

        # Check tracking
        assert "pdf.pages" in args._provided_args
        assert "markdown.emphasis" in args._provided_args


@pytest.mark.unit
@pytest.mark.cli
class TestEnvironmentVariableSupport:
    """Test environment variable support in tracking actions."""

    def test_tracking_store_action_with_env_var(self):
        """Test TrackingStoreAction reads from environment variables."""
        with patch.dict(os.environ, {"ALL2MD_OUTPUT_DIR": "/tmp/output"}):
            parser = argparse.ArgumentParser()
            TrackingStoreAction(option_strings=["--output-dir"], dest="output_dir")
            parser.add_argument("--output-dir", action=TrackingStoreAction, dest="output_dir")

            # Parse without providing the argument
            args = parser.parse_args([])

            # Should use env var as default
            assert args.output_dir == "/tmp/output"

    def test_tracking_store_true_action_with_env_var(self):
        """Test TrackingStoreTrueAction reads from environment variables."""
        with patch.dict(os.environ, {"ALL2MD_RICH": "true"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--rich", action=TrackingStoreTrueAction, dest="rich")

            args = parser.parse_args([])

            # Should use env var as default
            assert args.rich is True

    def test_tracking_store_true_action_env_var_false(self):
        """Test TrackingStoreTrueAction handles false env var values."""
        with patch.dict(os.environ, {"ALL2MD_RICH": "false"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--rich", action=TrackingStoreTrueAction, dest="rich")

            args = parser.parse_args([])

            # Should use env var as default (false)
            assert args.rich is False

    def test_tracking_store_false_action_with_env_var(self):
        """Test TrackingStoreFalseAction reads from environment variables."""
        with patch.dict(os.environ, {"ALL2MD_FEATURE": "true"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--no-feature", action=TrackingStoreFalseAction, dest="feature", default=True)

            args = parser.parse_args([])

            # Should use env var as default
            assert args.feature is True

    def test_tracking_append_action_with_env_var(self):
        """Test TrackingAppendAction reads from environment variables."""
        with patch.dict(os.environ, {"ALL2MD_EXCLUDE": "*.tmp,*.bak"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--exclude", action=TrackingAppendAction, dest="exclude")

            args = parser.parse_args([])

            # Should use env var as default (split on commas)
            assert args.exclude == ["*.tmp", "*.bak"]

    def test_tracking_positive_int_action_with_env_var(self):
        """Test TrackingPositiveIntAction reads from environment variables."""
        with patch.dict(os.environ, {"ALL2MD_PARALLEL": "4"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--parallel", action=TrackingPositiveIntAction, dest="parallel")

            args = parser.parse_args([])

            # Should use env var as default
            assert args.parallel == 4

    def test_tracking_positive_int_action_invalid_env_var(self):
        """Test TrackingPositiveIntAction handles invalid env var values."""
        with patch.dict(os.environ, {"ALL2MD_PARALLEL": "invalid"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--parallel", action=TrackingPositiveIntAction, dest="parallel", default=1)

            args = parser.parse_args([])

            # Should fall back to default
            assert args.parallel == 1

    def test_tracking_positive_int_action_negative_env_var(self):
        """Test TrackingPositiveIntAction handles negative env var values."""
        with patch.dict(os.environ, {"ALL2MD_PARALLEL": "-1"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--parallel", action=TrackingPositiveIntAction, dest="parallel", default=1)

            args = parser.parse_args([])

            # Should fall back to default
            assert args.parallel == 1

    def test_env_var_with_dots_in_dest(self):
        """Test that dest names with dots are properly converted for env vars."""
        with patch.dict(os.environ, {"ALL2MD_PDF_PAGES": "1,2,3"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--pdf-pages", action=TrackingStoreAction, dest="pdf.pages")

            args = parser.parse_args([])

            # Should use env var with dots converted to underscores
            assert getattr(args, "pdf.pages") == "1,2,3"

    def test_cli_arg_overrides_env_var(self):
        """Test that explicit CLI arguments override environment variables."""
        with patch.dict(os.environ, {"ALL2MD_OUTPUT_DIR": "/tmp/default"}):
            parser = argparse.ArgumentParser()
            parser.add_argument("--output-dir", action=TrackingStoreAction, dest="output_dir")

            args = parser.parse_args(["--output-dir", "/tmp/override"])

            # CLI arg should override env var
            assert args.output_dir == "/tmp/override"
            # Should be marked as provided
            assert "output_dir" in args._provided_args

    def test_dynamic_version_action(self):
        """Test DynamicVersionAction."""
        parser = argparse.ArgumentParser()

        def get_version():
            return "1.0.0"

        parser.add_argument("--version", action=DynamicVersionAction, version_callback=get_version)

        # Test that it exits with version message
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])

        assert exc_info.value.code == 0
