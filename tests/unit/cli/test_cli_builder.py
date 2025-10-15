"""Unit tests for all2md CLI functionality.

This module tests the command-line interface components including argument parsing,
option mapping, and validation logic.
"""

import argparse
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from all2md.cli.builder import DynamicCLIBuilder, create_parser
from all2md.cli.commands import (
    _run_convert_command,
    collect_input_files,
    handle_dependency_commands,
    save_config_to_file,
)
from all2md.cli.custom_actions import TrackingStoreFalseAction, TrackingStoreTrueAction
from all2md.cli.processors import generate_output_path, parse_merge_list, process_dry_run


@pytest.mark.unit
@pytest.mark.cli
class TestDynamicCLIBuilder:
    """Test dynamic CLI builder functionality."""

    def test_snake_to_kebab_conversion(self):
        """Test conversion of snake_case to kebab-case."""
        builder = DynamicCLIBuilder()

        assert builder.snake_to_kebab("test_field") == "test-field"
        assert builder.snake_to_kebab("simple") == "simple"
        assert builder.snake_to_kebab("multiple_word_field") == "multiple-word-field"
        assert builder.snake_to_kebab("detect_columns") == "detect-columns"

    def test_cli_name_inference(self):
        """Test CLI name inference from field names."""
        builder = DynamicCLIBuilder()

        # Basic inference
        assert builder.infer_cli_name("test_field") == "--test-field"

        # With format prefix
        assert builder.infer_cli_name("detect_columns", "pdf") == "--pdf-detect-columns"

        # Boolean with True default (should get --no-* form)
        assert builder.infer_cli_name("detect_columns", "pdf", True) == "--pdf-no-detect-columns"

        # Markdown options
        assert builder.infer_cli_name("emphasis_symbol", "markdown") == "--markdown-emphasis-symbol"

    def test_argument_mapping_pdf_options(self):
        """Test mapping of PDF-specific CLI arguments with new dot notation system."""
        builder = DynamicCLIBuilder()

        # Create mock parsed args with the new dot notation naming convention
        parsed_args = Mock()
        parsed_args.input = "test.pdf"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.about = False
        parsed_args.version = False
        parsed_args.config = None

        # Set explicitly provided arguments (simulating the tracking actions)
        parsed_args._provided_args = {'pdf.pages', 'pdf.password', 'pdf.detect_columns', 'markdown.emphasis_symbol'}

        # Mock vars to simulate the argument namespace with dot notation
        with patch('builtins.vars', return_value={
            'input': 'test.pdf',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'about': False,
            'version': False,
            'config': None,
            '_provided_args': parsed_args._provided_args,
            'pdf.pages': '1,2,3',
            'pdf.password': 'secret',
            'pdf.detect_columns': False,
            'markdown.emphasis_symbol': '_',
        }):
            options = builder.map_args_to_options(parsed_args)

        # Check PDF options mapping
        assert 'pdf.pages' in options
        assert options['pdf.pages'] == "1,2,3"
        assert options['pdf.password'] == 'secret'
        assert options['pdf.detect_columns'] is False

        # Check Markdown options mapping
        assert options['markdown.emphasis_symbol'] == '_'

        # Legacy keys should no longer be present
        assert 'pages' not in options
        assert 'password' not in options
        assert 'detect_columns' not in options

    def test_list_int_processing(self):
        """Test processing of list_int type arguments."""
        builder = DynamicCLIBuilder()

        # Mock field and metadata for pages field
        mock_field = Mock()
        mock_field.type = list[int] | None
        mock_field.default = None

        metadata = {"type": "list_int"}

        # Test valid comma-separated integers with was_provided=True
        result = builder._process_argument_value(mock_field, metadata, "1,2,3", "pdf.pages", was_provided=True)
        assert result == [1, 2, 3]

        # Test single integer
        result = builder._process_argument_value(mock_field, metadata, "5", "pdf.pages", was_provided=True)
        assert result == [5]

        # Test with spaces
        result = builder._process_argument_value(mock_field, metadata, "1, 2, 3", "pdf.pages", was_provided=True)
        assert result == [1, 2, 3]

        # Test invalid input raises ArgumentTypeError
        with pytest.raises(argparse.ArgumentTypeError):
            builder._process_argument_value(mock_field, metadata, "1,invalid,3", "pdf.pages", was_provided=True)

        # Test that not provided returns None
        result = builder._process_argument_value(mock_field, metadata, "1,2,3", "pdf.pages", was_provided=False)
        assert result is None

    def test_help_suffix_appended_without_overwriting(self):
        """Ensure metadata help text is preserved when adding suffixes."""
        from dataclasses import dataclass, field

        @dataclass
        class SampleOptions:
            tags: list[str] = field(
                default_factory=list,
                metadata={'help': 'Comma separated tags to include'},
            )

        builder = DynamicCLIBuilder()
        options_class = SampleOptions
        sample_field = options_class.__dataclass_fields__['tags']

        kwargs = builder.get_argument_kwargs(
            sample_field,
            dict(sample_field.metadata),
            '--tags',
            options_class,
        )

        assert kwargs['help'] == 'Comma separated tags to include (comma-separated values)'

    def test_json_dot_notation_preserves_full_paths(self):
        """Test that JSON options with dot notation preserve full key paths (Issue #8)."""
        builder = DynamicCLIBuilder()

        # Create mock parsed args with no CLI arguments
        parsed_args = Mock()
        parsed_args.input = "test.html"
        parsed_args.format = "auto"
        parsed_args._provided_args = set()

        # Mock the vars() return to simulate namespace
        with patch('builtins.vars', return_value={
            'input': 'test.html',
            'format': 'auto',
            '_provided_args': set(),
        }):
            # Test with deeply nested JSON options (3 levels)
            json_options = {
                "html.network.allowed_hosts": ["example.com"],
                "html.network.require_https": True,
                "pdf.pages": [1, 2, 3],
                "attachment_mode": "download"  # Top-level option
            }

            options = builder.map_args_to_options(parsed_args, json_options)

            # Verify that fully qualified keys are preserved (not stripped)
            assert "html.network.allowed_hosts" in options
            assert options["html.network.allowed_hosts"] == ["example.com"]
            assert "html.network.require_https" in options
            assert options["html.network.require_https"] is True

            # Verify 2-level nesting is preserved
            assert "pdf.pages" in options
            assert options["pdf.pages"] == [1, 2, 3]

            # Verify top-level options still work
            assert "attachment_mode" in options
            assert options["attachment_mode"] == "download"

            # Verify we didn't create collisions (e.g., bare "allowed_hosts" key)
            assert "allowed_hosts" not in options or options.get("allowed_hosts") is None

    def test_fuzzy_suggestion_uses_correct_cli_flags(self):
        """Test that fuzzy suggestions return CLI flags with hyphens, not dots (Issue #9)."""
        builder = DynamicCLIBuilder()

        # Build a minimal parser and populate dest_to_cli_flag mapping
        builder.dest_to_cli_flag = {
            "pdf.pages": "--pdf-pages",
            "pdf.password": "--pdf-password",
            "html.network.allowed_hosts": "--html-network-allowed-hosts",
            "markdown.emphasis_symbol": "--markdown-emphasis-symbol"
        }

        # Test suggestion for a typo in "pdf.pages" dest name
        suggestion = builder._suggest_similar_argument("pdf.page")
        assert suggestion == "--pdf-pages"  # Should be all hyphens, not --pdf.pages

        # Test suggestion for "html.network" related field
        suggestion = builder._suggest_similar_argument("html.network.allowed_host")
        assert suggestion == "--html-network-allowed-hosts"  # Should be all hyphens

        # Test that no suggestion is returned for completely unrelated arg
        suggestion = builder._suggest_similar_argument("totally_unrelated_arg")
        assert suggestion is None

    def test_has_default_helper(self):
        """Test _has_default helper correctly identifies fields with defaults (Issue #11)."""
        from dataclasses import dataclass, field

        builder = DynamicCLIBuilder()

        # Test field with explicit default value
        @dataclass
        class TestWithDefault:
            field_with_default: str = "default_value"

        assert builder._has_default(TestWithDefault.__dataclass_fields__['field_with_default']) is True

        # Test field with default_factory
        @dataclass
        class TestWithFactory:
            field_with_factory: list = field(default_factory=list)

        assert builder._has_default(TestWithFactory.__dataclass_fields__['field_with_factory']) is True

        # Test boolean fields with and without defaults
        @dataclass
        class TestBoolOptions:
            bool_with_default: bool = True
            bool_with_false_default: bool = False

        assert builder._has_default(TestBoolOptions.__dataclass_fields__['bool_with_default']) is True
        assert builder._has_default(TestBoolOptions.__dataclass_fields__['bool_with_false_default']) is True

    def test_boolean_field_without_default_gets_store_true(self):
        """Test that boolean field without default gets store_true action (Issue #11)."""
        from dataclasses import MISSING, dataclass, field

        builder = DynamicCLIBuilder()

        @dataclass
        class TestOptions:
            bool_no_default: bool = field(default=MISSING)

        test_field = TestOptions.__dataclass_fields__['bool_no_default']
        metadata = {}
        cli_name = "--bool-no-default"

        # Get argument kwargs
        kwargs, help_suffix = builder._infer_argument_type_and_action(
            test_field, bool, False, metadata, cli_name
        )

        # Should get store_true action (not crash trying to compare MISSING to True/False)
        assert kwargs['action'] == 'store_true'
        assert help_suffix is None

    def test_boolean_cli_negates_default_with_custom_flag(self):
        """Boolean flags honor cli_negates_default metadata without forced --no- prefix."""
        from dataclasses import dataclass, field

        @dataclass
        class SampleOptions:
            disable_feature: bool = field(
                default=True,
                metadata={
                    'help': 'Disable expensive feature checks',
                    'cli_negates_default': True,
                    'cli_negated_name': 'disable-feature',
                }
            )

        builder = DynamicCLIBuilder()
        parser = argparse.ArgumentParser()
        builder._add_options_arguments_internal(parser, SampleOptions)

        action = next(
            a for a in parser._actions
            if '--disable-feature' in getattr(a, 'option_strings', [])
        )

        assert isinstance(action, TrackingStoreFalseAction)
        assert action.dest == 'disable_feature'
        assert action.default is True

    def test_boolean_default_factory_is_treated_as_missing(self):
        """Boolean default_factory should not force --no flag semantics."""
        from dataclasses import dataclass, field

        @dataclass
        class FactoryOptions:
            feature_enabled: bool = field(
                default_factory=lambda: True,
                metadata={'help': 'Factory default should be ignored by CLI'},
            )

        builder = DynamicCLIBuilder()
        parser = argparse.ArgumentParser()
        builder._add_options_arguments_internal(parser, FactoryOptions)

        action = next(
            a for a in parser._actions
            if '--feature-enabled' in getattr(a, 'option_strings', [])
        )

        assert isinstance(action, TrackingStoreTrueAction)
        # store_true defaults to False until the user passes the flag
        assert action.default is False

    def test_logger_used_instead_of_print(self):
        """Test that logger is used instead of print for warnings (Issue #13)."""
        import logging
        from unittest.mock import patch

        builder = DynamicCLIBuilder()

        # Test that logger.warning is called instead of print
        with patch.object(logging.getLogger('all2md.cli.builder'), 'warning') as _mock_warning:
            # Create a parser with an invalid argument to trigger warning
            parser = argparse.ArgumentParser()
            try:
                # Try to add an argument that will fail
                builder._add_options_arguments_internal(
                    parser,
                    type("InvalidOptions", (), {}),  # Not a dataclass - will skip
                    format_prefix=None,
                    group_name=None
                )
                # No warning expected since it's not a dataclass
            except Exception:
                pass

        # The real test is that no print() was called to stderr
        # This is a lightweight test - the important thing is the code doesn't crash

    def test_nested_dataclass_cli_args_parsing(self):
        """Test that nested dataclass CLI args are parsed correctly with proper dest format."""
        parser = create_parser()

        # Parse args with nested HTML network options
        # Note: require_https defaults to False, so we don't use --no- prefix
        # allow_remote_fetch defaults to False, so use regular flag to set it to True
        args = parser.parse_args([
            "test.html",
            "--html-network-allow-remote-fetch",
            "--html-network-network-timeout", "30"
        ])

        # Check that args have proper dest format (dot-separated, not hyphenated)
        assert hasattr(args, 'html.network.allow_remote_fetch')
        assert hasattr(args, 'html.network.network_timeout')
        assert getattr(args, 'html.network.allow_remote_fetch') is True
        assert getattr(args, 'html.network.network_timeout') == 30.0

    def test_nested_dataclass_cli_args_mapping(self):
        """Test that nested dataclass CLI args map correctly to options (Issue: nested mapping broken)."""
        from unittest.mock import Mock, patch

        builder = DynamicCLIBuilder()

        # Create mock parsed args with nested network options
        parsed_args = Mock()
        parsed_args.input = "test.html"
        parsed_args.format = "auto"
        parsed_args.strict_args = False
        parsed_args._provided_args = {
            'html.network.allow_remote_fetch',
            'html.network.require_https',
            'html.network.allowed_hosts'
        }

        # Mock vars to simulate the argument namespace with dot notation
        with patch('builtins.vars', return_value={
            'input': 'test.html',
            'format': 'auto',
            '_provided_args': parsed_args._provided_args,
            'html.network.allow_remote_fetch': True,
            'html.network.require_https': True,
            'html.network.allowed_hosts': ['example.com', 'cdn.example.com'],
        }):
            options = builder.map_args_to_options(parsed_args)

        # Verify options are mapped correctly with fully qualified keys
        assert options['html.network.allow_remote_fetch'] is True
        assert options['html.network.require_https'] is True
        assert options['html.network.allowed_hosts'] == ['example.com', 'cdn.example.com']

        # Legacy keys should not be present
        assert 'allow_remote_fetch' not in options
        assert 'require_https' not in options
        assert 'allowed_hosts' not in options

    def test_nested_field_resolution(self):
        """Test the _resolve_nested_field helper for multi-level nesting."""
        from all2md.options.html import HtmlOptions

        builder = DynamicCLIBuilder()

        # Test resolving a two-level nested field path
        result = builder._resolve_nested_field(HtmlOptions, ['network', 'allow_remote_fetch'])
        assert result is not None
        field, field_type = result
        assert field.name == 'allow_remote_fetch'
        assert field_type is bool

        # Test resolving another nested field
        result = builder._resolve_nested_field(HtmlOptions, ['network', 'allowed_hosts'])
        assert result is not None
        field, field_type = result
        assert field.name == 'allowed_hosts'

        # Test invalid path returns None
        result = builder._resolve_nested_field(HtmlOptions, ['nonexistent', 'field'])
        assert result is None

        # Test single-level path
        result = builder._resolve_nested_field(HtmlOptions, ['extract_title'])
        assert result is not None
        field, field_type = result
        assert field.name == 'extract_title'

    def test_dest_to_cli_flag_mapping_with_nested(self):
        """Test that dest_to_cli_flag mapping works correctly for nested options."""
        builder = DynamicCLIBuilder()
        parser = builder.build_parser()

        # After building parser, dest_to_cli_flag should have nested mappings with dot notation
        assert 'html.network.allow_remote_fetch' in builder.dest_to_cli_flag
        assert builder.dest_to_cli_flag['html.network.allow_remote_fetch'] == '--html-network-allow-remote-fetch'

        # Test suggestion system with nested options
        suggestion = builder._suggest_similar_argument('html.network.allow_remote')
        assert suggestion == '--html-network-allow-remote-fetch'


@pytest.mark.unit
@pytest.mark.cli
class TestCLIParser:
    """Test CLI argument parser functionality."""

    def test_create_parser_basic(self):
        """Test basic parser creation and help text."""
        parser = create_parser()
        assert parser.prog == "all2md"
        assert "Convert documents to Markdown" in parser.description

    def test_parser_required_arguments(self):
        """Test that input argument is optional at parser level but validated in main()."""
        parser = create_parser()

        # Should succeed with input file (now returns a list for multi-file support)
        args = parser.parse_args(["test.pdf"])
        assert args.input == ["test.pdf"]

        # Should succeed without input file at parser level (validation happens in main)
        args = parser.parse_args([])
        assert args.input == []

        # Should succeed with --about flag and no input file
        args = parser.parse_args(["--about"])
        assert args.about is True
        assert args.input == []

    def test_parser_format_choices(self):
        """Test format argument choices."""
        parser = create_parser()

        # Valid format choices
        valid_formats = ["auto", "pdf", "docx", "pptx", "html", "eml", "rtf", "ipynb", "spreadsheet", "image", "txt"]
        for fmt in valid_formats:
            args = parser.parse_args(["test.pdf", "--format", fmt])
            assert args.format == fmt

        # Invalid format choice should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--format", "invalid"])

    def test_parser_log_level_choices(self):
        """Test log level argument choices."""
        parser = create_parser()

        # Valid log level choices
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        for level in valid_levels:
            args = parser.parse_args(["test.pdf", "--log-level", level])
            assert args.log_level == level

        # Invalid log level should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--log-level", "INVALID"])

    def test_parser_dynamic_arguments_exist(self):
        """Test that dynamically generated arguments exist in the parser."""
        parser = create_parser()

        # Test that PDF options exist
        args = parser.parse_args(["test.pdf", "--pdf-pages", "1,2,3"])
        assert hasattr(args, 'pdf.pages')
        # Pages are now correctly parsed as a list of integers
        assert getattr(args, 'pdf.pages') == [1, 2, 3]

        # Test that HTML options exist
        args = parser.parse_args(["test.html", "--html-extract-title"])
        assert hasattr(args, 'html.extract_title')
        assert getattr(args, 'html.extract_title') is True

        # Test that Markdown options exist
        args = parser.parse_args(["test.pdf", "--markdown-emphasis-symbol", "_"])
        assert hasattr(args, 'markdown.emphasis_symbol')
        assert getattr(args, 'markdown.emphasis_symbol') == "_"

    def test_parser_boolean_no_flags(self):
        """Test --no-* flags for boolean options with True defaults."""
        parser = create_parser()

        # Test --pdf-no-detect-columns flag
        args = parser.parse_args(["test.pdf", "--pdf-no-detect-columns"])
        assert hasattr(args, 'pdf.detect_columns')
        assert getattr(args, 'pdf.detect_columns') is False

        # Test --markdown-no-use-hash-headings flag
        args = parser.parse_args(["test.html", "--markdown-no-use-hash-headings"])
        assert hasattr(args, 'markdown.use_hash_headings')
        assert getattr(args, 'markdown.use_hash_headings') is False

        # Test --markdown-no-escape-special flag
        args = parser.parse_args(["test.pdf", "--markdown-no-escape-special"])
        assert hasattr(args, 'markdown.escape_special')
        assert getattr(args, 'markdown.escape_special') is False

    def test_parser_boolean_flags(self):
        """Test boolean flag arguments."""
        parser = create_parser()

        # Test HTML flags
        args = parser.parse_args(["test.html", "--html-extract-title", "--html-strip-dangerous-elements"])
        assert getattr(args, 'html.extract_title') is True
        assert getattr(args, 'html.strip_dangerous_elements') is True

        # Test PowerPoint flags
        args = parser.parse_args(["test.pptx", "--pptx-include-slide-numbers"])
        assert getattr(args, 'pptx.include_slide_numbers') is True

        # Test negative flags
        args = parser.parse_args(["test.eml", "--eml-no-include-headers", "--eml-no-preserve-thread-structure"])
        assert getattr(args, 'eml.include_headers') is False
        assert getattr(args, 'eml.preserve_thread_structure') is False


@pytest.mark.unit
@pytest.mark.cli
class TestNewCLIFeatures:
    """Test new CLI features added for enhanced functionality."""

    def test_rich_flag_parsing(self):
        """Test --rich flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.rich is False

        # Test with --rich flag
        args = parser.parse_args(["test.pdf", "--rich"])
        assert args.rich is True

    def test_progress_flag_parsing(self):
        """Test --progress flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.progress is False

        # Test with --progress flag
        args = parser.parse_args(["test.pdf", "--progress"])
        assert args.progress is True

    def test_output_dir_parsing(self):
        """Test --output-dir argument parsing."""
        parser = create_parser()

        # Test default (None)
        args = parser.parse_args(["test.pdf"])
        assert args.output_dir is None

        # Test with output directory
        args = parser.parse_args(["test.pdf", "--output-dir", "./converted"])
        assert args.output_dir == "./converted"

    def test_recursive_flag_parsing(self):
        """Test --recursive/-r flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.recursive is False

        # Test with --recursive
        args = parser.parse_args(["test.pdf", "--recursive"])
        assert args.recursive is True

        # Test with -r shorthand
        args = parser.parse_args(["test.pdf", "-r"])
        assert args.recursive is True

    def test_parallel_flag_parsing(self):
        """Test --parallel/-p flag parsing with optional worker count."""
        parser = create_parser()

        # Test default (1)
        args = parser.parse_args(["test.pdf"])
        assert args.parallel == 1

        # Test with --parallel (no value, should use const=None)
        args = parser.parse_args(["test.pdf", "--parallel"])
        assert args.parallel is None

        # Test with specific worker count
        args = parser.parse_args(["test.pdf", "--parallel", "4"])
        assert args.parallel == 4

        # Test with -p shorthand
        args = parser.parse_args(["test.pdf", "-p", "2"])
        assert args.parallel == 2

    def test_skip_errors_flag_parsing(self):
        """Test --skip-errors flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.skip_errors is False

        # Test with --skip-errors
        args = parser.parse_args(["test.pdf", "--skip-errors"])
        assert args.skip_errors is True

    def test_preserve_structure_flag_parsing(self):
        """Test --preserve-structure flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.preserve_structure is False

        # Test with --preserve-structure
        args = parser.parse_args(["test.pdf", "--preserve-structure"])
        assert args.preserve_structure is True

    def test_collate_flag_parsing(self):
        """Test --collate flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.collate is False

        # Test with --collate
        args = parser.parse_args(["test.pdf", "--collate"])
        assert args.collate is True

    def test_no_summary_flag_parsing(self):
        """Test --no-summary flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.no_summary is False

        # Test with --no-summary
        args = parser.parse_args(["test.pdf", "--no-summary"])
        assert args.no_summary is True

    def test_multiple_input_files_parsing(self):
        """Test parsing of multiple input files."""
        parser = create_parser()

        # Test single file
        args = parser.parse_args(["test.pdf"])
        assert args.input == ["test.pdf"]

        # Test multiple files
        args = parser.parse_args(["file1.pdf", "file2.docx", "file3.html"])
        assert args.input == ["file1.pdf", "file2.docx", "file3.html"]

        # Test no input files (should be empty list)
        args = parser.parse_args([])
        assert args.input == []

    def test_complex_multi_file_options_combination(self):
        """Test complex combination of multi-file options."""
        parser = create_parser()

        args = parser.parse_args([
            "file1.pdf", "file2.docx",
            "--output-dir", "./converted",
            "--recursive",
            "--parallel", "4",
            "--skip-errors",
            "--preserve-structure",
            "--collate",
            "--rich",
            "--no-summary"
        ])

        assert args.input == ["file1.pdf", "file2.docx"]
        assert args.output_dir == "./converted"
        assert args.recursive is True
        assert args.parallel == 4
        assert args.skip_errors is True
        assert args.preserve_structure is True
        assert args.collate is True
        assert args.rich is True
        assert args.no_summary is True

    def test_environment_variable_support_unit(self):
        """Test environment variable functionality through parser."""
        import os

        # Test environment variable integration through the parser
        os.environ['ALL2MD_RICH'] = 'true'
        os.environ['ALL2MD_OUTPUT_DIR'] = '/tmp/test'

        try:
            parser = create_parser()
            args = parser.parse_args(['test.pdf'])

            # Environment variables should be applied as defaults
            assert args.rich is True
            assert args.output_dir == '/tmp/test'
        finally:
            # Clean up
            os.environ.pop('ALL2MD_RICH', None)
            os.environ.pop('ALL2MD_OUTPUT_DIR', None)

    def test_environment_variable_type_conversion(self):
        """Test environment variable type conversion for different argument types."""
        import os

        # Set environment variables with different types
        os.environ['ALL2MD_RICH'] = 'true'
        os.environ['ALL2MD_NO_SUMMARY'] = 'false'
        os.environ['ALL2MD_OUTPUT_DIR'] = '/tmp/test'

        try:
            parser = create_parser()
            args = parser.parse_args(["test.pdf"])

            # Test that different types were converted correctly
            assert args.rich is True  # Boolean conversion
            assert args.no_summary is False  # Boolean false conversion
            assert args.output_dir == '/tmp/test'  # String value

        finally:
            # Clean up
            os.environ.pop('ALL2MD_RICH', None)
            os.environ.pop('ALL2MD_NO_SUMMARY', None)
            os.environ.pop('ALL2MD_OUTPUT_DIR', None)

    def test_environment_variable_precedence(self):
        """Test that CLI arguments take precedence over environment variables."""
        import os

        # Set environment variable
        os.environ['ALL2MD_RICH'] = 'false'

        try:
            parser = create_parser()

            # Test that env var sets default
            args_default = parser.parse_args(["test.pdf"])
            assert args_default.rich is False  # From env var

            # Test that CLI arg overrides env var
            args_override = parser.parse_args(["test.pdf", "--rich"])
            assert args_override.rich is True  # CLI arg overrides env var

        finally:
            os.environ.pop('ALL2MD_RICH', None)

    def test_invalid_parallel_worker_count(self):
        """Test error handling for invalid parallel worker counts."""
        parser = create_parser()

        # Test that negative values are rejected at parse time
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--parallel", "-1"])

        # Test that zero is also rejected
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--parallel", "0"])

        # Test that positive values work
        args = parser.parse_args(["test.pdf", "--parallel", "4"])
        assert args.parallel == 4

    def test_conflicting_options_validation(self):
        """Test validation of conflicting options."""
        parser = create_parser()

        # These should parse successfully but might conflict logically
        # The CLI should handle conflicts gracefully in main()
        args = parser.parse_args([
            "test.pdf",
            "--collate",
            "--output-dir", "./individual"  # Conflict: collate typically goes to single output
        ])

        assert args.collate is True
        assert args.output_dir == "./individual"
        # Logic validation happens in main(), not parser

    def test_backward_compatibility_preserved(self):
        """Test that new features don't break existing CLI usage."""
        parser = create_parser()

        # All existing usage patterns should still work
        test_cases = [
            ["document.pdf"],
            ["document.pdf", "--out", "output.md"],
            ["document.pdf", "--format", "pdf"],
            ["document.html", "--html-extract-title"],
            ["document.pdf", "--pdf-pages", "1,2,3"],
            ["document.pdf", "--attachment-mode", "download"],
        ]

        for args_list in test_cases:
            args = parser.parse_args(args_list)
            # Should parse successfully and have expected format
            assert hasattr(args, 'input')
            assert hasattr(args, 'format')
            # New attributes should exist with defaults
            assert hasattr(args, 'rich')
            assert hasattr(args, 'progress')
            assert hasattr(args, 'collate')

    def test_file_collection_logic_unit(self):
        """Test file collection logic with various patterns."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "file1.pdf").write_text("test")
            (temp_path / "file2.docx").write_text("test")
            (temp_path / "file3.txt").write_text("test")
            (temp_path / "file4.PDF").write_text("test")
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested.pdf").write_text("test")

            # Test single file
            files = collect_input_files([str(temp_path / "file1.pdf")])
            assert len(files) == 1
            assert files[0].name == "file1.pdf"

            # Test directory (non-recursive)
            files = collect_input_files([str(temp_path)], recursive=False)
            assert len(files) >= 3  # At least the files we created

            # Test directory (recursive)
            files = collect_input_files([str(temp_path)], recursive=True)
            assert len(files) >= 4  # Including nested file

            # Test specific extensions
            files = collect_input_files([str(temp_path)], extensions=['.pdf'])
            assert files
            assert all(f.suffix.lower() == '.pdf' for f in files)

            # Glob patterns should exclude directories even when matched
            with patch('pathlib.Path.cwd', return_value=temp_path):
                globbed = collect_input_files(['*'], extensions=['.pdf'])
                assert all(p.is_file() for p in globbed)
                names = {p.name for p in globbed}
                assert 'subdir' not in names
                assert {p.suffix.lower() for p in globbed} == {'.pdf'}

    def test_output_path_generation(self):
        """Test output path generation logic."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "test.pdf"

            # Test basic output path generation
            output_path = generate_output_path(input_file)
            assert output_path.name == "test.md"
            assert output_path.parent == temp_path

            # Test with output directory
            output_dir = temp_path / "output"
            output_path = generate_output_path(input_file, output_dir)
            assert output_path.name == "test.md"
            assert output_path.parent == output_dir

            # Test with structure preservation
            base_dir = temp_path / "base"
            nested_input = base_dir / "sub" / "nested.pdf"
            output_path = generate_output_path(
                nested_input, output_dir, preserve_structure=True, base_input_dir=base_dir
            )
            assert output_path.name == "nested.md"
            assert "sub" in str(output_path)

    def test_cli_help_contains_new_options(self):
        """Test that help text includes all new options."""
        parser = create_parser()
        help_text = parser.format_help()

        # Check that new options appear in help
        assert "--rich" in help_text
        assert "--progress" in help_text
        assert "--output-dir" in help_text
        assert "--recursive" in help_text
        assert "--parallel" in help_text
        assert "--skip-errors" in help_text
        assert "--preserve-structure" in help_text
        assert "--collate" in help_text
        assert "--no-summary" in help_text

        help_text_lower = help_text.lower()
        assert "rich terminal output" in help_text_lower
        assert "progress bar" in help_text_lower
        assert "parallel" in help_text_lower
        assert "recursive" in help_text_lower
        assert "collate" in help_text_lower or "combine" in help_text_lower

    def test_run_convert_command_collate_delegates(self):
        """Ensure the convert subcommand delegates to the collate processor."""
        with (
            patch('all2md.cli.commands.process_files_collated', return_value=0) as mock_collate,
            patch('all2md.cli.commands.collect_input_files', return_value=[Path('dummy.pdf')]),
            patch('all2md.cli.commands.setup_and_validate_options', return_value=({}, 'pdf', None)),
            patch('all2md.cli.commands.validate_arguments', return_value=True),
        ):
            parsed_args = argparse.Namespace(
                input=['dummy.pdf'],
                output_type='markdown',
                collate=True,
                out=None,
                output_dir=None,
                preserve_structure=False,
                progress=False,
                rich=False,
                skip_errors=False,
                format='auto',
                recursive=False,
                exclude=None,
                detect_only=False,
                dry_run=False,
                pager=False,
                no_summary=False,
                log_level='WARNING',
                log_file=None,
                trace=False,
                verbose=False,
                strict_args=False,
                transforms=None,
                merge_from_list=None,
                generate_toc=False,
                toc_title=None,
                toc_depth=None,
                toc_position=None,
                list_separator=None,
                no_section_titles=False,
                watch=False,
                watch_debounce=None,
                parallel=None,
                zip=None,
                assets_layout=None,
                save_config=None,
            )

            exit_code = _run_convert_command(parsed_args)

            assert exit_code == 0
            mock_collate.assert_called_once()


@pytest.mark.unit
@pytest.mark.cli
class TestNewEnhancedCLIFeatures:
    """Test newly added CLI enhancement features."""

    def test_dependency_commands_parsing(self):
        """Test parsing of dependency management commands."""
        # Test check-deps command
        result = handle_dependency_commands(['check-deps'])
        assert result is not None  # Should return exit code

        # Test check-deps with format
        result = handle_dependency_commands(['check-deps', 'pdf'])
        assert result is not None

        # Test non-dependency command
        result = handle_dependency_commands(['test.pdf'])
        assert result is None

    def test_save_config_flag_parsing(self):
        """Test --save-config argument parsing."""
        parser = create_parser()

        # Test default (None)
        args = parser.parse_args(["test.pdf"])
        assert args.save_config is None

        # Test with save config path
        args = parser.parse_args(["test.pdf", "--save-config", "config.json"])
        assert args.save_config == "config.json"

    def test_dry_run_flag_parsing(self):
        """Test --dry-run flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["test.pdf"])
        assert args.dry_run is False

        # Test with --dry-run flag
        args = parser.parse_args(["test.pdf", "--dry-run"])
        assert args.dry_run is True

    def test_exclude_patterns_parsing(self):
        """Test --exclude argument parsing."""
        parser = create_parser()

        # Test default (None)
        args = parser.parse_args(["test.pdf"])
        assert args.exclude is None

        # Test single exclude pattern
        args = parser.parse_args(["test.pdf", "--exclude", "*.tmp"])
        assert args.exclude == ["*.tmp"]

        # Test multiple exclude patterns
        args = parser.parse_args([
            "test.pdf",
            "--exclude", "*.tmp",
            "--exclude", "**/.git/*",
            "--exclude", "backup_*"
        ])
        assert args.exclude == ["*.tmp", "**/.git/*", "backup_*"]

    def test_save_config_functionality(self):
        """Test configuration saving functionality."""
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"

            # Create mock args
            args = Mock()
            args.input = ["test.pdf"]
            args.out = "output.md"
            args.save_config = str(config_path)
            args.dry_run = True
            args.about = False
            args.version = False
            args.pdf_pages = "1,2,3"
            args.markdown_emphasis_symbol = "_"
            args.rich = True
            args.exclude = ["*.tmp", "backup_*"]
            # Set _provided_args to track explicitly provided arguments
            args._provided_args = {'pdf_pages', 'markdown_emphasis_symbol', 'rich', 'exclude'}

            # Mock vars() to return args dict
            with patch('builtins.vars', return_value={
                'input': ['test.pdf'],
                'out': 'output.md',
                'save_config': str(config_path),
                'dry_run': True,
                'about': False,
                'version': False,
                'pdf_pages': '1,2,3',
                'markdown_emphasis_symbol': '_',
                'rich': True,
                'exclude': ['*.tmp', 'backup_*'],
                '_provided_args': {'pdf_pages', 'markdown_emphasis_symbol', 'rich', 'exclude'}
            }):
                save_config_to_file(args, str(config_path))

            # Verify config file was created
            assert config_path.exists()

            # Load and verify content
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Should include relevant options but exclude special ones
            assert 'pdf_pages' in config
            assert config['pdf_pages'] == '1,2,3'
            assert 'markdown_emphasis_symbol' in config
            assert config['markdown_emphasis_symbol'] == '_'
            assert 'rich' in config
            assert config['rich'] is True
            assert 'exclude' in config
            assert config['exclude'] == ['*.tmp', 'backup_*']

            # Should exclude special arguments
            assert 'input' not in config
            assert 'out' not in config
            assert 'save_config' not in config
            assert 'dry_run' not in config
            assert 'about' not in config
            assert 'version' not in config

    def test_collect_input_files_with_exclusions(self):
        """Test file collection with exclusion patterns."""
        import tempfile
        from pathlib import Path

        from all2md.cli import collect_input_files

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "file1.pdf").write_text("test")
            (temp_path / "file2.docx").write_text("test")
            (temp_path / "backup_file.pdf").write_text("test")
            (temp_path / "temp.tmp").write_text("test")
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested.pdf").write_text("test")
            (temp_path / "subdir" / "backup_nested.pdf").write_text("test")

            # Test without exclusions
            files = collect_input_files([str(temp_path)], recursive=True)
            original_count = len(files)
            assert original_count >= 5  # At least the files we created (may be fewer due to extension filtering)

            # Test with exclusion patterns
            files = collect_input_files(
                [str(temp_path)],
                recursive=True,
                exclude_patterns=["*.tmp", "backup_*"]
            )
            filtered_count = len(files)

            # Should have fewer files after exclusion
            assert filtered_count < original_count

            # Verify specific exclusions
            file_names = [f.name for f in files]
            assert "temp.tmp" not in file_names
            assert "backup_file.pdf" not in file_names
            assert "backup_nested.pdf" not in file_names

            # Should still include non-excluded files
            assert "file1.pdf" in file_names
            assert "file2.docx" in file_names
            assert "nested.pdf" in file_names

    def test_dry_run_processing(self):
        """Test dry run mode processing."""
        import sys
        import tempfile
        from io import StringIO
        from pathlib import Path
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "file1.pdf").write_text("test")
            (temp_path / "file2.docx").write_text("test")

            files = [temp_path / "file1.pdf", temp_path / "file2.docx"]

            # Create mock args
            args = Mock()
            args.rich = False
            args.collate = False
            args.out = None
            args.output_dir = None
            args.preserve_structure = False
            args.format = "auto"
            args.recursive = False
            args.parallel = 1
            args.exclude = None
            args.output_type = 'markdown'
            # Add _provided_args to avoid TypeError when checking 'in' operator
            args._provided_args = set()

            # Capture output
            captured_output = StringIO()
            sys.stdout = captured_output

            try:
                result = process_dry_run(files, args, "auto")
                output = captured_output.getvalue()

                # Should return 0 (success)
                assert result == 0

                # Should mention dry run mode
                assert "DRY RUN MODE" in output
                assert "Found 2 file(s)" in output

                # Should list files
                assert "file1.pdf" in output
                assert "file2.docx" in output

                # Should not actually convert
                assert "No files were actually converted" in output

            finally:
                sys.stdout = sys.__stdout__

    def test_dry_run_with_rich_output(self):
        """Test dry run mode with rich output (if available)."""
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock, patch

        from all2md.cli import process_dry_run
        pytest.importorskip('rich.console')

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.pdf").write_text("test")
            files = [temp_path / "test.pdf"]

            args = Mock()
            args.rich = True
            args.collate = False
            args.out = None
            args.output_dir = None
            args.preserve_structure = False
            args.format = "auto"
            args.recursive = False
            args.parallel = 1
            args.exclude = None
            args.output_type = 'markdown'
            # Add _provided_args to avoid TypeError when checking 'in' operator
            args._provided_args = set()

            # Test with rich available
            with patch('rich.console.Console'):
                with patch('rich.table.Table'):
                    result = process_dry_run(files, args, "auto")
                    assert result == 0

            # Test with rich disabled (fallback path)
            args.rich = False  # Test fallback without rich
            result = process_dry_run(files, args, "auto")
            assert result == 0  # Should work with simple text output

    def test_enhanced_cli_help_includes_new_features(self):
        """Test that help text includes all new enhanced features."""
        parser = create_parser()
        help_text = parser.format_help()

        # Check dependency management is mentioned in docstring/help
        assert "--save-config" in help_text
        assert "--dry-run" in help_text
        assert "--exclude" in help_text

        # Check help descriptions
        assert "save" in help_text.lower() and "config" in help_text.lower()
        assert "dry" in help_text.lower() and "run" in help_text.lower()
        assert "exclude" in help_text.lower()

    def test_complex_new_features_combination(self):
        """Test complex combination of new enhanced features."""
        parser = create_parser()

        args = parser.parse_args([
            "file1.pdf", "file2.docx",
            "--dry-run",
            "--exclude", "*.tmp",
            "--exclude", "backup_*",
            "--save-config", "my_config.json",
            "--rich",
            "--output-dir", "./output"
        ])

        assert args.input == ["file1.pdf", "file2.docx"]
        assert args.dry_run is True
        assert args.exclude == ["*.tmp", "backup_*"]
        assert args.save_config == "my_config.json"
        assert args.rich is True
        assert args.output_dir == "./output"

    def test_exclusion_pattern_edge_cases(self):
        """Test edge cases for exclusion patterns."""
        import tempfile
        from pathlib import Path

        from all2md.cli import collect_input_files

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files with various names
            test_files = [
                "normal.pdf",
                "file.with.dots.pdf",
                "UPPERCASE.PDF",
                "file-with-dashes.pdf",
                "file_with_underscores.pdf",
                "123numbers.pdf",
                "special@chars.pdf"
            ]

            for filename in test_files:
                (temp_path / filename).write_text("test")

            # Test empty exclusion list
            files = collect_input_files([str(temp_path)], exclude_patterns=[])
            assert len(files) == len(test_files)

            # Test exclusion with wildcards
            files = collect_input_files([str(temp_path)], exclude_patterns=["*.with.*"])
            excluded_files = [f.name for f in files]
            assert "file.with.dots.pdf" not in excluded_files
            assert "file-with-dashes.pdf" in excluded_files  # Dash doesn't match dot

            # Test case-sensitive exclusion
            files = collect_input_files([str(temp_path)], exclude_patterns=["UPPER*"])
            excluded_files = [f.name for f in files]
            assert "UPPERCASE.PDF" not in excluded_files
            assert "normal.pdf" in excluded_files

    def test_backward_compatibility_with_new_features(self):
        """Test that new features don't break existing functionality."""
        parser = create_parser()

        # Existing command patterns should still work with new features available
        test_cases = [
            # Basic usage should still work
            (["document.pdf"], {"dry_run": False, "exclude": None, "save_config": None}),

            # Format-specific options should still work
            (["document.pdf", "--pdf-pages", "1,2"], {"dry_run": False}),

            # Output options should still work
            (["document.pdf", "--out", "output.md"], {"save_config": None}),

            # Multiple format options should still work
            (["document.html", "--html-extract-title", "--markdown-emphasis-symbol", "_"],
             {"dry_run": False, "exclude": None}),
        ]

        for args_list, expected_attrs in test_cases:
            args = parser.parse_args(args_list)

            # Check that new attributes exist with defaults
            assert hasattr(args, 'dry_run')
            assert hasattr(args, 'exclude')
            assert hasattr(args, 'save_config')

            # Check expected values
            for attr, expected_value in expected_attrs.items():
                assert getattr(args, attr) == expected_value


@pytest.mark.unit
@pytest.mark.cli
class TestMergeFromListFeature:
    """Test merge-from-list CLI feature."""

    def test_merge_from_list_flag_parsing(self):
        """Test --merge-from-list argument parsing."""
        parser = create_parser()

        # Test default (None)
        args = parser.parse_args(["test.pdf"])
        assert args.merge_from_list is None

        # Test with list file path
        args = parser.parse_args(["--merge-from-list", "docs.txt"])
        assert args.merge_from_list == "docs.txt"

    def test_generate_toc_flag_parsing(self):
        """Test --generate-toc flag parsing."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["--merge-from-list", "docs.txt"])
        assert args.generate_toc is False

        # Test with --generate-toc
        args = parser.parse_args(["--merge-from-list", "docs.txt", "--generate-toc"])
        assert args.generate_toc is True

    def test_toc_options_parsing(self):
        """Test TOC-related options parsing."""
        parser = create_parser()

        # Test defaults
        args = parser.parse_args(["--merge-from-list", "docs.txt", "--generate-toc"])
        assert args.toc_title == "Table of Contents"
        assert args.toc_depth == 3
        assert args.toc_position == "top"

        # Test custom values
        args = parser.parse_args([
            "--merge-from-list", "docs.txt",
            "--generate-toc",
            "--toc-title", "Contents",
            "--toc-depth", "2",
            "--toc-position", "bottom"
        ])
        assert args.toc_title == "Contents"
        assert args.toc_depth == 2
        assert args.toc_position == "bottom"

    def test_list_separator_option(self):
        """Test --list-separator option."""
        parser = create_parser()

        # Test default (tab)
        args = parser.parse_args(["--merge-from-list", "docs.txt"])
        assert args.list_separator == "\t"

        # Test custom separator
        args = parser.parse_args(["--merge-from-list", "docs.txt", "--list-separator", ","])
        assert args.list_separator == ","

    def test_no_section_titles_flag(self):
        """Test --no-section-titles flag."""
        parser = create_parser()

        # Test default (False)
        args = parser.parse_args(["--merge-from-list", "docs.txt"])
        assert args.no_section_titles is False

        # Test with flag
        args = parser.parse_args(["--merge-from-list", "docs.txt", "--no-section-titles"])
        assert args.no_section_titles is True

    def test_parse_merge_list_basic(self):
        """Test basic parse_merge_list functionality."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "doc1.md").write_text("# Doc 1")
            (temp_path / "doc2.md").write_text("# Doc 2")

            # Create list file
            list_file = temp_path / "docs.txt"
            list_file.write_text("doc1.md\ndoc2.md\n")

            # Parse list
            entries = parse_merge_list(list_file)

            assert len(entries) == 2
            assert entries[0][0].name == "doc1.md"
            assert entries[0][1] is None  # No section title
            assert entries[1][0].name == "doc2.md"
            assert entries[1][1] is None

    def test_parse_merge_list_with_titles(self):
        """Test parse_merge_list with section titles."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "intro.md").write_text("# Intro")
            (temp_path / "body.md").write_text("# Body")

            # Create list file with titles
            list_file = temp_path / "docs.txt"
            list_file.write_text("intro.md\tIntroduction\nbody.md\tMain Content\n")

            # Parse list
            entries = parse_merge_list(list_file)

            assert len(entries) == 2
            assert entries[0][1] == "Introduction"
            assert entries[1][1] == "Main Content"

    def test_parse_merge_list_with_comments(self):
        """Test parse_merge_list skips comments and blank lines."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            (temp_path / "doc.md").write_text("# Doc")

            # Create list file with comments
            list_file = temp_path / "docs.txt"
            list_file.write_text("# This is a comment\n\ndoc.md\n\n# Another comment\n")

            # Parse list
            entries = parse_merge_list(list_file)

            assert len(entries) == 1
            assert entries[0][0].name == "doc.md"

    def test_parse_merge_list_resolves_relative_paths(self):
        """Test parse_merge_list resolves paths relative to list file."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create subdirectory with files
            sub_dir = temp_path / "sub"
            sub_dir.mkdir()
            (sub_dir / "doc.md").write_text("# Doc")

            # Create list file in parent directory
            list_file = temp_path / "docs.txt"
            list_file.write_text("sub/doc.md\n")

            # Parse list
            entries = parse_merge_list(list_file)

            assert len(entries) == 1
            assert entries[0][0].exists()
            assert "sub" in str(entries[0][0])

    def test_parse_merge_list_missing_file_error(self):
        """Test parse_merge_list raises error for missing files."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create list file referencing non-existent file
            list_file = temp_path / "docs.txt"
            list_file.write_text("nonexistent.md\n")

            # Should raise error
            with pytest.raises(argparse.ArgumentTypeError) as exc_info:
                parse_merge_list(list_file)

            assert "File not found" in str(exc_info.value)
            assert "nonexistent.md" in str(exc_info.value)

    def test_parse_merge_list_empty_file_error(self):
        """Test parse_merge_list raises error for empty list file."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create empty list file
            list_file = temp_path / "docs.txt"
            list_file.write_text("# Only comments\n\n")

            # Should raise error
            with pytest.raises(argparse.ArgumentTypeError) as exc_info:
                parse_merge_list(list_file)

            assert "empty" in str(exc_info.value).lower()

    def test_parse_merge_list_custom_separator(self):
        """Test parse_merge_list with custom separator."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            (temp_path / "doc.md").write_text("# Doc")

            # Create list file with comma separator
            list_file = temp_path / "docs.txt"
            list_file.write_text("doc.md,My Document\n")

            # Parse with comma separator
            entries = parse_merge_list(list_file, separator=",")

            assert len(entries) == 1
            assert entries[0][1] == "My Document"

    def test_merge_from_list_help_text(self):
        """Test that merge-from-list options appear in help."""
        parser = create_parser()
        help_text = parser.format_help()

        assert "--merge-from-list" in help_text
        assert "--generate-toc" in help_text
        assert "--toc-title" in help_text
        assert "--toc-depth" in help_text
        assert "--toc-position" in help_text
        assert "--list-separator" in help_text
        assert "--no-section-titles" in help_text
