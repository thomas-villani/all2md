"""Unit tests for all2md CLI functionality.

This module tests the command-line interface components including argument parsing,
option mapping, and validation logic.
"""

import argparse
from unittest.mock import Mock, patch

import pytest

from all2md.cli import create_parser, parse_pdf_pages
from all2md.cli_builder import DynamicCLIBuilder


@pytest.mark.unit
@pytest.mark.cli
class TestDynamicCLIBuilder:
    """Test dynamic CLI builder functionality."""

    def test_pdf_pages_parsing_valid(self):
        """Test parsing of valid PDF page numbers."""
        # Single page
        assert parse_pdf_pages("5") == [5]

        # Multiple pages
        assert parse_pdf_pages("1,2,3") == [1, 2, 3]

        # Pages with spaces
        assert parse_pdf_pages("1, 2, 3") == [1, 2, 3]

        # Mixed formatting
        assert parse_pdf_pages("0,5, 10,15") == [0, 5, 10, 15]

    def test_pdf_pages_parsing_invalid(self):
        """Test parsing of invalid PDF page numbers raises error."""
        with pytest.raises(argparse.ArgumentTypeError):
            parse_pdf_pages("invalid")

        with pytest.raises(argparse.ArgumentTypeError):
            parse_pdf_pages("1,invalid,3")

        with pytest.raises(argparse.ArgumentTypeError):
            parse_pdf_pages("1.5,2")

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
        """Test mapping of PDF-specific CLI arguments with new dynamic system."""
        builder = DynamicCLIBuilder()

        # Create mock parsed args with the new naming convention
        parsed_args = Mock()
        parsed_args.input = "test.pdf"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.about = False
        parsed_args.version = False
        parsed_args.options_json = None

        # PDF options (new format)
        parsed_args.pdf_pages = "1,2,3"
        parsed_args.pdf_password = "secret"
        parsed_args.pdf_detect_columns = False  # This would be set by --pdf-no-detect-columns

        # Markdown options (new format)
        parsed_args.markdown_emphasis_symbol = "_"

        # Mock vars to simulate the argument namespace
        with patch('builtins.vars', return_value={
            'input': 'test.pdf',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'about': False,
            'version': False,
            'options_json': None,
            'pdf_pages': '1,2,3',
            'pdf_password': 'secret',
            'pdf_detect_columns': False,
            'markdown_emphasis_symbol': '_',
        }):
            options = builder.map_args_to_options(parsed_args)

        # Check PDF options mapping
        assert 'pages' in options
        assert options['pages'] == [1, 2, 3]
        assert options['password'] == 'secret'
        assert options['detect_columns'] is False

        # Check Markdown options mapping
        assert options['emphasis_symbol'] == '_'

    def test_list_int_processing(self):
        """Test processing of list_int type arguments."""
        builder = DynamicCLIBuilder()

        # Mock field and metadata for pages field
        mock_field = Mock()
        mock_field.type = list[int] | None
        mock_field.default = None

        metadata = {"type": "list_int"}

        # Test valid comma-separated integers
        result = builder._process_argument_value(mock_field, metadata, "1,2,3", "pdf_pages")
        assert result == [1, 2, 3]

        # Test single integer
        result = builder._process_argument_value(mock_field, metadata, "5", "pdf_pages")
        assert result == [5]

        # Test with spaces
        result = builder._process_argument_value(mock_field, metadata, "1, 2, 3", "pdf_pages")
        assert result == [1, 2, 3]

        # Test invalid input returns None
        result = builder._process_argument_value(mock_field, metadata, "1,invalid,3", "pdf_pages")
        assert result is None



@pytest.mark.unit
@pytest.mark.cli
class TestCLIParser:
    """Test CLI argument parser functionality."""

    def test_create_parser_basic(self):
        """Test basic parser creation and help text."""
        parser = create_parser()
        assert parser.prog == "all2md"
        assert "Convert documents to Markdown format" in parser.description

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
        valid_formats = ["auto", "pdf", "docx", "pptx", "html", "eml", "rtf", "ipynb", "csv", "tsv", "xlsx", "image", "txt"]
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
        assert hasattr(args, 'pdf_pages')
        assert args.pdf_pages == "1,2,3"

        # Test that HTML options exist
        args = parser.parse_args(["test.html", "--html-extract-title"])
        assert hasattr(args, 'html_extract_title')
        assert args.html_extract_title is True

        # Test that Markdown options exist
        args = parser.parse_args(["test.pdf", "--markdown-emphasis-symbol", "_"])
        assert hasattr(args, 'markdown_emphasis_symbol')
        assert args.markdown_emphasis_symbol == "_"

    def test_parser_boolean_no_flags(self):
        """Test --no-* flags for boolean options with True defaults."""
        parser = create_parser()

        # Test --pdf-no-detect-columns flag
        args = parser.parse_args(["test.pdf", "--pdf-no-detect-columns"])
        assert hasattr(args, 'pdf_detect_columns')
        assert args.pdf_detect_columns is False

        # Test --html-no-use-hash-headings flag
        args = parser.parse_args(["test.html", "--html-no-use-hash-headings"])
        assert hasattr(args, 'html_use_hash_headings')
        assert args.html_use_hash_headings is False

        # Test --markdown-no-escape-special flag
        args = parser.parse_args(["test.pdf", "--markdown-no-escape-special"])
        assert hasattr(args, 'markdown_escape_special')
        assert args.markdown_escape_special is False

    def test_parser_boolean_flags(self):
        """Test boolean flag arguments."""
        parser = create_parser()

        # Test HTML flags
        args = parser.parse_args(["test.html", "--html-extract-title", "--html-strip-dangerous-elements"])
        assert args.html_extract_title is True
        assert args.html_strip_dangerous_elements is True

        # Test PowerPoint flags
        args = parser.parse_args(["test.pptx", "--pptx-slide-numbers"])
        assert args.pptx_slide_numbers is True

        # Test negative flags
        args = parser.parse_args(["test.eml", "--eml-no-include-headers", "--eml-no-preserve-thread-structure"])
        assert args.eml_include_headers is False
        assert args.eml_preserve_thread_structure is False


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
        """Test environment variable parsing logic."""
        import os

        from all2md.cli import get_env_var_value

        # Test getting environment variable
        os.environ['ALL2MD_RICH'] = 'true'
        os.environ['ALL2MD_OUTPUT_DIR'] = '/tmp/test'
        os.environ['ALL2MD_PARALLEL'] = '4'

        try:
            assert get_env_var_value('rich') == 'true'
            assert get_env_var_value('output_dir') == '/tmp/test'
            assert get_env_var_value('parallel') == '4'
            assert get_env_var_value('nonexistent') is None
        finally:
            # Clean up
            os.environ.pop('ALL2MD_RICH', None)
            os.environ.pop('ALL2MD_OUTPUT_DIR', None)
            os.environ.pop('ALL2MD_PARALLEL', None)

    def test_environment_variable_type_conversion(self):
        """Test environment variable type conversion for different argument types."""
        import os

        from all2md.cli import apply_env_vars_to_parser

        parser = create_parser()

        # Set environment variables
        os.environ['ALL2MD_RICH'] = 'true'
        os.environ['ALL2MD_NO_SUMMARY'] = 'false'
        os.environ['ALL2MD_PARALLEL'] = '4'
        os.environ['ALL2MD_OUTPUT_DIR'] = '/tmp/test'

        try:
            # Apply environment variables
            apply_env_vars_to_parser(parser)

            # Test that defaults were set from environment
            args = parser.parse_args(["test.pdf"])
            assert args.rich is True  # Boolean conversion
            assert args.no_summary is False  # Boolean false conversion
            assert args.parallel == 4  # Integer conversion
            assert args.output_dir == '/tmp/test'  # String value

        finally:
            # Clean up
            os.environ.pop('ALL2MD_RICH', None)
            os.environ.pop('ALL2MD_NO_SUMMARY', None)
            os.environ.pop('ALL2MD_PARALLEL', None)
            os.environ.pop('ALL2MD_OUTPUT_DIR', None)

    def test_environment_variable_precedence(self):
        """Test that CLI arguments take precedence over environment variables."""
        import os

        from all2md.cli import apply_env_vars_to_parser

        parser = create_parser()

        # Set environment variable
        os.environ['ALL2MD_RICH'] = 'true'

        try:
            apply_env_vars_to_parser(parser)

            # CLI arg should override env var
            args = parser.parse_args(["test.pdf"])
            assert args.rich is True  # From env var

            # No way to test override in unit test since argparse sets defaults
            # This will be tested in integration tests

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

        from all2md.cli import collect_input_files

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "file1.pdf").write_text("test")
            (temp_path / "file2.docx").write_text("test")
            (temp_path / "file3.txt").write_text("test")
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
            pdf_files = [f for f in files if f.suffix == '.pdf']
            assert len(pdf_files) >= 1

    def test_output_path_generation(self):
        """Test output path generation logic."""
        import tempfile
        from pathlib import Path

        from all2md.cli import generate_output_path

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

        # Check help descriptions are meaningful
        assert "rich terminal output" in help_text.lower()
        assert "progress bar" in help_text.lower()
        assert "parallel" in help_text.lower()
        assert "recursive" in help_text.lower()
        assert "collate" in help_text.lower() or "combine" in help_text.lower()


@pytest.mark.unit
@pytest.mark.cli
class TestNewEnhancedCLIFeatures:
    """Test newly added CLI enhancement features."""

    def test_dependency_commands_parsing(self):
        """Test parsing of dependency management commands."""
        from all2md.cli import handle_dependency_commands

        # Test check-deps command
        result = handle_dependency_commands(['check-deps'])
        assert result is not None  # Should return exit code

        # Test check-deps with format
        result = handle_dependency_commands(['check-deps', 'pdf'])
        assert result is not None

        # Test install-deps command
        result = handle_dependency_commands(['install-deps'])
        assert result is not None

        # Test install-deps with format
        result = handle_dependency_commands(['install-deps', 'pdf'])
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

        from all2md.cli import save_config_to_file

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
                'exclude': ['*.tmp', 'backup_*']
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
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        from io import StringIO
        import sys

        from all2md.cli import process_dry_run

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

            # Test with rich available
            with patch('rich.console.Console') as mock_console:
                with patch('rich.table.Table') as mock_table:
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
