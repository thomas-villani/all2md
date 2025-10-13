"""Unit tests for new CLI enhancements.

This module tests the enhanced CLI features including:
- Version mismatch detection in DependencyError
- list-formats command
- Enhanced dry-run with format detection
- detect-only mode
- Security preset flags
"""

from unittest.mock import Mock, patch

import pytest

from all2md.cli import create_parser, process_detect_only, process_dry_run
from all2md.cli.commands import handle_list_formats_command
from all2md.cli.processors import apply_security_preset
from all2md.exceptions import DependencyError


@pytest.mark.unit
class TestDependencyErrorEnhancements:
    """Test DependencyError with version mismatch support."""

    def test_dependency_error_with_missing_packages_only(self):
        """Test DependencyError with only missing packages."""
        error = DependencyError(
            converter_name="pdf",
            missing_packages=[("pymupdf", ">=1.24.0"), ("pillow", "")],
            version_mismatches=[]
        )

        assert error.converter_name == "pdf"
        assert len(error.missing_packages) == 2
        assert len(error.version_mismatches) == 0
        assert "requires the following packages" in str(error)
        assert "pymupdf" in str(error)
        assert "pillow" in str(error)

    def test_dependency_error_with_version_mismatches_only(self):
        """Test DependencyError with only version mismatches."""
        error = DependencyError(
            converter_name="pdf",
            missing_packages=[],
            version_mismatches=[
                ("numpy", ">=1.24.0", "1.20.0"),
                ("pandas", ">=2.0.0", "1.5.3")
            ]
        )

        assert error.converter_name == "pdf"
        assert len(error.missing_packages) == 0
        assert len(error.version_mismatches) == 2
        assert "version mismatches" in str(error)
        assert "numpy" in str(error)
        assert "requires >=1.24.0, but 1.20.0 is installed" in str(error)

    def test_dependency_error_with_both_types(self):
        """Test DependencyError with both missing packages and version mismatches."""
        error = DependencyError(
            converter_name="pdf",
            missing_packages=[("pymupdf", ">=1.24.0")],
            version_mismatches=[("numpy", ">=1.24.0", "1.20.0")]
        )

        error_str = str(error)
        assert "requires the following packages" in error_str
        assert "version mismatches" in error_str
        assert "pymupdf" in error_str
        assert "numpy" in error_str

    def test_dependency_error_install_command_generation(self):
        """Test that install command includes all problematic packages."""
        error = DependencyError(
            converter_name="pdf",
            missing_packages=[("pymupdf", ">=1.24.0")],
            version_mismatches=[("numpy", ">=1.24.0", "1.20.0")]
        )

        error_str = str(error)
        assert "pip install --upgrade" in error_str
        assert "pymupdf" in error_str
        assert "numpy" in error_str


@pytest.mark.unit
class TestListFormatsCommand:
    """Test list-formats CLI command."""

    def test_list_formats_help(self):
        """Test that list-formats shows help with -h flag."""
        result = handle_list_formats_command(['--help'])
        assert result == 0

    @patch('all2md.converter_registry.registry')
    @patch('all2md.dependencies.check_version_requirement')
    @patch('all2md.dependencies.get_package_version')
    def test_list_formats_basic(self, mock_get_version, mock_check_version, mock_registry):
        """Test basic list-formats output."""
        # Setup mock registry
        mock_registry.auto_discover = Mock()
        mock_registry.list_formats = Mock(return_value=['pdf', 'docx', 'html'])

        # Mock format info
        mock_metadata = Mock()
        mock_metadata.description = "PDF converter"
        mock_metadata.extensions = ['.pdf']
        mock_metadata.mime_types = ['application/pdf']
        mock_metadata.parser_class = "PdfParser"
        mock_metadata.renderer_class = "MarkdownRenderer"
        mock_metadata.get_converter_display_string = Mock(return_value="Parser: all2md.parsers.pdf.PdfParser | Renderer: all2md.renderers.markdown.MarkdownRenderer")
        mock_metadata.priority = 100
        mock_metadata.required_packages = []

        mock_registry.get_format_info = Mock(return_value=[mock_metadata])

        # Test execution (plain text mode)
        result = handle_list_formats_command([])
        assert result == 0

    @patch('all2md.converter_registry.registry')
    @patch('all2md.dependencies.check_version_requirement')
    @patch('all2md.dependencies.get_package_version')
    def test_list_formats_with_specific_format(self, mock_get_version, mock_check_version, mock_registry):
        """Test list-formats with specific format."""
        mock_registry.auto_discover = Mock()
        mock_registry.list_formats = Mock(return_value=['pdf', 'docx', 'html'])

        mock_metadata = Mock()
        mock_metadata.description = "PDF converter"
        mock_metadata.extensions = ['.pdf']
        mock_metadata.mime_types = ['application/pdf']
        mock_metadata.parser_class = "PdfParser"
        mock_metadata.renderer_class = "MarkdownRenderer"
        mock_metadata.get_converter_display_string = Mock(return_value="Parser: all2md.parsers.pdf.PdfParser | Renderer: all2md.renderers.markdown.MarkdownRenderer")
        mock_metadata.priority = 100
        # required_packages is a list of (install_name, import_name, version_spec) tuples
        mock_metadata.required_packages = [("pymupdf", "fitz", ">=1.24.0")]

        mock_registry.get_format_info = Mock(return_value=[mock_metadata])
        mock_check_version.return_value = (True, "1.24.0")

        result = handle_list_formats_command(['pdf'])
        assert result == 0

    @patch('all2md.converter_registry.registry')
    def test_list_formats_unknown_format(self, mock_registry):
        """Test list-formats with unknown format."""
        mock_registry.auto_discover = Mock()
        mock_registry.list_formats = Mock(return_value=['pdf', 'docx', 'html'])

        result = handle_list_formats_command(['unknown'])
        assert result == 3


@pytest.mark.unit
class TestDetectOnlyMode:
    """Test detect-only mode functionality."""

    def test_detect_only_flag_in_parser(self):
        """Test that --detect-only flag is available in parser."""
        parser = create_parser()
        args = parser.parse_args(['--detect-only', 'test.pdf'])

        assert hasattr(args, 'detect_only')
        assert args.detect_only is True

    @patch('all2md.converter_registry.registry')
    @patch('all2md.dependencies.check_version_requirement')
    @patch('all2md.dependencies.check_package_installed')
    def test_detect_only_basic(self, mock_check_installed, mock_check_version, mock_registry):
        """Test basic detect-only functionality."""
        from pathlib import Path

        # Setup mocks
        mock_registry.auto_discover = Mock()
        mock_registry.detect_format = Mock(return_value='pdf')

        mock_metadata = Mock()
        mock_metadata.extensions = ['.pdf']
        mock_metadata.mime_types = ['application/pdf']
        mock_metadata.required_packages = []

        mock_registry.get_format_info = Mock(return_value=[mock_metadata])
        mock_registry.list_formats = Mock(return_value=['pdf'])

        # Create mock args
        args = Mock()
        args.rich = False

        # Create a temporary test file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            test_file = Path(f.name)

        try:
            result = process_detect_only([test_file], args, 'auto')
            assert result == 0
        finally:
            test_file.unlink()


@pytest.mark.unit
class TestSecurityPresets:
    """Test security preset functionality."""

    def test_strict_html_sanitize_preset(self):
        """Test --strict-html-sanitize preset applies correct options."""
        args = Mock()
        args.strict_html_sanitize = True
        args.safe_mode = False
        args.paranoid_mode = False

        options = {}
        result = apply_security_preset(args, options)

        # Check format-qualified keys (new format)
        assert result['html.strip_dangerous_elements'] is True
        assert result['html.network.allow_remote_fetch'] is False
        assert result['html.local_files.allow_local_files'] is False
        assert result['html.local_files.allow_cwd_files'] is False

    def test_safe_mode_preset(self):
        """Test --safe-mode preset applies correct options."""
        args = Mock()
        args.strict_html_sanitize = False
        args.safe_mode = True
        args.paranoid_mode = False

        options = {}
        result = apply_security_preset(args, options)

        # Check format-qualified keys (new format)
        assert result['html.strip_dangerous_elements'] is True
        assert result['html.network.allow_remote_fetch'] is True
        assert result['html.network.require_https'] is True
        assert result['html.local_files.allow_local_files'] is False
        assert result['html.local_files.allow_cwd_files'] is False

    def test_paranoid_mode_preset(self):
        """Test --paranoid-mode preset applies correct options."""
        args = Mock()
        args.strict_html_sanitize = False
        args.safe_mode = False
        args.paranoid_mode = True

        options = {}
        result = apply_security_preset(args, options)

        # Check format-qualified keys (new format)
        assert result['html.strip_dangerous_elements'] is True
        assert result['html.network.allow_remote_fetch'] is True
        assert result['html.network.require_https'] is True
        assert result['html.network.allowed_hosts'] == []
        assert result['html.local_files.allow_local_files'] is False
        assert result['html.local_files.allow_cwd_files'] is False
        assert result['html.max_asset_size_bytes'] == 5 * 1024 * 1024
        assert result['max_asset_size_bytes'] == 5 * 1024 * 1024

    def test_no_preset_applied(self):
        """Test that no preset leaves options unchanged."""
        args = Mock()
        args.strict_html_sanitize = False
        args.safe_mode = False
        args.paranoid_mode = False

        options = {'existing_option': 'value'}
        result = apply_security_preset(args, options)

        assert result == {'existing_option': 'value'}
        # Verify no security preset keys were added (format-qualified keys)
        assert 'html.strip_dangerous_elements' not in result
        assert 'html.network.allow_remote_fetch' not in result

    def test_preset_flags_in_parser(self):
        """Test that security preset flags are available in parser."""
        parser = create_parser()

        # Test strict-html-sanitize
        args = parser.parse_args(['--strict-html-sanitize', 'test.html'])
        assert args.strict_html_sanitize is True

        # Test safe-mode
        args = parser.parse_args(['--safe-mode', 'test.html'])
        assert args.safe_mode is True

        # Test paranoid-mode
        args = parser.parse_args(['--paranoid-mode', 'test.html'])
        assert args.paranoid_mode is True


@pytest.mark.unit
class TestEnhancedDryRun:
    """Test enhanced dry-run with format detection."""

    def test_dry_run_flag_still_works(self):
        """Test that existing --dry-run flag still works."""
        parser = create_parser()
        args = parser.parse_args(['--dry-run', 'test.pdf'])

        assert hasattr(args, 'dry_run')
        assert args.dry_run is True

    @patch('all2md.converter_registry.registry')
    @patch('all2md.dependencies.check_version_requirement')
    @patch('all2md.dependencies.check_package_installed')
    def test_dry_run_shows_format_detection(self, mock_check_installed, mock_check_version, mock_registry):
        """Test that enhanced dry-run shows format detection info."""
        from pathlib import Path

        # Setup mocks
        mock_registry.auto_discover = Mock()
        mock_registry.detect_format = Mock(return_value='pdf')
        mock_registry.list_formats = Mock(return_value=['pdf'])

        mock_metadata = Mock()
        mock_metadata.extensions = ['.pdf']
        mock_metadata.required_packages = []
        mock_metadata.get_required_packages_for_content = Mock(return_value=[])

        mock_registry.get_format_info = Mock(return_value=[mock_metadata])

        args = Mock()
        args.rich = False
        args.collate = False
        args.out = None
        args.output_dir = None
        args.preserve_structure = False
        args.format = 'auto'
        args.recursive = False
        args.parallel = 1
        args.exclude = None
        # Add _provided_args to avoid TypeError when checking 'in' operator
        args._provided_args = set()

        # Create a temporary test file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            test_file = Path(f.name)

        try:
            result = process_dry_run([test_file], args, 'auto')
            assert result == 0
        finally:
            test_file.unlink()


@pytest.mark.unit
class TestCLIIntegration:
    """Test integration of all new features."""

    def test_all_new_flags_in_help(self):
        """Test that all new flags appear in help output."""
        parser = create_parser()
        help_text = parser.format_help()

        # Check for new flags
        assert '--detect-only' in help_text
        assert '--strict-html-sanitize' in help_text
        assert '--safe-mode' in help_text
        assert '--paranoid-mode' in help_text

    def test_security_and_detect_together(self):
        """Test that security presets work with detect-only mode."""
        parser = create_parser()
        args = parser.parse_args(['--detect-only', '--safe-mode', 'test.html'])

        assert args.detect_only is True
        assert args.safe_mode is True

    def test_security_and_dry_run_together(self):
        """Test that security presets work with dry-run mode."""
        parser = create_parser()
        args = parser.parse_args(['--dry-run', '--paranoid-mode', 'test.html'])

        assert args.dry_run is True
        assert args.paranoid_mode is True


@pytest.mark.unit
class TestSecurityPresetOptionsMapping:
    """Test that security preset options correctly map to nested dataclasses."""

    def test_safe_mode_creates_html_options_with_nested_fields(self):
        """Test that safe-mode flat keys create proper HtmlOptions with nested dataclasses."""
        from all2md import _create_parser_options_from_kwargs
        from all2md.options import HtmlOptions

        # Simulate what apply_security_preset does
        kwargs = {
            'strip_dangerous_elements': True,
            'allow_remote_fetch': True,
            'require_https': True,
            'allow_local_files': False,
            'allow_cwd_files': False,
        }

        options = _create_parser_options_from_kwargs('html', **kwargs)

        # Verify options instance is created
        assert options is not None
        assert isinstance(options, HtmlOptions)

        # Verify top-level field
        assert options.strip_dangerous_elements is True

        # Verify nested NetworkFetchOptions fields
        assert options.network is not None
        assert options.network.allow_remote_fetch is True
        assert options.network.require_https is True

        # Verify nested LocalFileAccessOptions fields
        assert options.local_files is not None
        assert options.local_files.allow_local_files is False
        assert options.local_files.allow_cwd_files is False

    def test_paranoid_mode_creates_html_options_with_all_fields(self):
        """Test that paranoid-mode creates HtmlOptions with all security settings."""
        from all2md import _create_parser_options_from_kwargs
        from all2md.options import HtmlOptions

        kwargs = {
            'strip_dangerous_elements': True,
            'allow_remote_fetch': True,
            'require_https': True,
            'allowed_hosts': [],
            'allow_local_files': False,
            'allow_cwd_files': False,
            'max_asset_size_bytes': 5 * 1024 * 1024,
        }

        options = _create_parser_options_from_kwargs('html', **kwargs)

        assert options is not None
        assert isinstance(options, HtmlOptions)
        assert options.strip_dangerous_elements is True
        assert options.network.allow_remote_fetch is True
        assert options.network.require_https is True
        assert options.network.allowed_hosts == []
        assert options.max_asset_size_bytes == 5 * 1024 * 1024
        assert options.local_files.allow_local_files is False
        assert options.local_files.allow_cwd_files is False

    def test_strict_html_sanitize_creates_html_options(self):
        """Test that strict-html-sanitize creates proper HtmlOptions."""
        from all2md import _create_parser_options_from_kwargs
        from all2md.options import HtmlOptions

        kwargs = {
            'strip_dangerous_elements': True,
            'allow_remote_fetch': False,
            'allow_local_files': False,
            'allow_cwd_files': False,
        }

        options = _create_parser_options_from_kwargs('html', **kwargs)

        assert options is not None
        assert isinstance(options, HtmlOptions)
        assert options.strip_dangerous_elements is True
        assert options.network.allow_remote_fetch is False
        assert options.local_files.allow_local_files is False
        assert options.local_files.allow_cwd_files is False

    def test_eml_options_with_html_network_nested_field(self):
        """Test that EmlOptions correctly handles html_network nested field."""
        from all2md import _create_parser_options_from_kwargs
        from all2md.options import EmlOptions

        kwargs = {
            'allow_remote_fetch': True,
            'require_https': True,
            'convert_html_to_markdown': True,
        }

        options = _create_parser_options_from_kwargs('eml', **kwargs)

        assert options is not None
        assert isinstance(options, EmlOptions)
        assert options.convert_html_to_markdown is True
        assert options.html_network is not None
        assert options.html_network.allow_remote_fetch is True
        assert options.html_network.require_https is True

    def test_mhtml_options_with_local_files_nested_field(self):
        """Test that MhtmlOptions correctly handles local_files nested field."""
        from all2md import _create_parser_options_from_kwargs
        from all2md.options import MhtmlOptions

        kwargs = {
            'allow_local_files': False,
            'allow_cwd_files': False,
        }

        options = _create_parser_options_from_kwargs('mhtml', **kwargs)

        assert options is not None
        assert isinstance(options, MhtmlOptions)
        assert options.local_files is not None
        assert options.local_files.allow_local_files is False
        assert options.local_files.allow_cwd_files is False

    def test_mixed_flat_and_top_level_kwargs(self):
        """Test that mixed flat nested and top-level kwargs work together."""
        from all2md import _create_parser_options_from_kwargs
        from all2md.options import HtmlOptions

        kwargs = {
            'extract_title': True,  # Top-level field
            'allow_remote_fetch': True,  # Nested in network
            'convert_nbsp': True,  # Top-level field
            'require_https': True,  # Nested in network
        }

        options = _create_parser_options_from_kwargs('html', **kwargs)

        assert options is not None
        assert isinstance(options, HtmlOptions)
        # Top-level fields
        assert options.extract_title is True
        assert options.convert_nbsp is True
        # Nested fields
        assert options.network.allow_remote_fetch is True
        assert options.network.require_https is True

    def test_security_preset_end_to_end_integration(self):
        """Test complete flow: preset -> options -> to_markdown."""
        import tempfile
        from pathlib import Path

        from all2md import to_markdown

        # Create a simple HTML file
        html_content = '<html><body><h1>Test</h1><script>alert("xss")</script></body></html>'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_file = Path(f.name)

        try:
            # Test with security preset kwargs (simulating what CLI does)
            markdown = to_markdown(
                temp_file,
                format='html',
                strip_dangerous_elements=True,
                allow_remote_fetch=True,
                require_https=True,
                allow_local_files=False,
                allow_cwd_files=False
            )

            # Verify conversion happened
            assert markdown is not None
            assert 'Test' in markdown
            # Script tag should be stripped by strip_dangerous_elements
            assert 'alert' not in markdown
        finally:
            temp_file.unlink()

    @pytest.mark.skip(reason="_merge_options was removed in options refactoring - use clone() method instead")
    def test_merge_options_with_flat_nested_kwargs(self):
        """Test that _merge_options correctly handles flat nested kwargs."""
        # This test is obsolete - _merge_options was removed
        # Options are now immutable dataclasses that use clone() method
        pass
