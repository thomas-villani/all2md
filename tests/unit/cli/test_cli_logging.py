"""Unit tests for CLI logging features.

Tests for --log-file, --trace flags and logging configuration.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest


class TestLoggingConfiguration:
    """Test logging configuration functions."""

    def test_configure_logging_basic(self):
        """Test basic logging configuration."""
        from all2md.cli import _configure_logging

        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            _configure_logging(logging.INFO)

            mock_logger.setLevel.assert_called_once_with(logging.INFO)
            # Check handlers were added
            assert mock_logger.addHandler.called

    def test_configure_logging_with_file(self, tmp_path):
        """Test logging configuration with file output."""
        from all2md.cli import _configure_logging

        log_file = tmp_path / "test.log"

        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            _configure_logging(logging.DEBUG, log_file=str(log_file))

            # Should add both console and file handlers
            assert mock_logger.addHandler.call_count == 2

    def test_configure_logging_trace_mode(self):
        """Test trace mode uses detailed format."""
        from all2md.cli import _configure_logging

        with patch('logging.getLogger') as mock_get_logger, \
             patch('logging.Formatter') as mock_formatter:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            _configure_logging(logging.DEBUG, trace_mode=True)

            # Check that formatter was called with timestamp format
            formatter_calls = mock_formatter.call_args_list
            assert len(formatter_calls) > 0
            format_str = formatter_calls[0][0][0]
            assert 'asctime' in format_str
            assert 'levelname' in format_str
            assert 'name' in format_str

    def test_configure_logging_normal_mode(self):
        """Test normal mode uses simple format."""
        from all2md.cli import _configure_logging

        with patch('logging.getLogger') as mock_get_logger, \
             patch('logging.Formatter') as mock_formatter:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            _configure_logging(logging.INFO, trace_mode=False)

            # Check that formatter was called with simple format
            formatter_calls = mock_formatter.call_args_list
            assert len(formatter_calls) > 0
            format_str = formatter_calls[0][0][0]
            assert 'levelname' in format_str
            assert 'message' in format_str
            # Should NOT have asctime in normal mode
            assert 'asctime' not in format_str

    def test_configure_logging_invalid_file_path(self, capsys):
        """Test logging configuration with invalid file path."""
        from all2md.cli import _configure_logging

        # Try to write to a directory that doesn't exist and can't be created
        invalid_path = "/invalid/path/that/does/not/exist/test.log"

        # Should not raise, but should print warning
        _configure_logging(logging.INFO, log_file=invalid_path)

        captured = capsys.readouterr()
        assert "Warning:" in captured.err or "Could not create log file" in captured.err


class TestLogFileCLIFlag:
    """Test --log-file CLI flag."""

    @patch('all2md.cli._configure_logging')
    @patch('all2md.cli.processors.process_multi_file')
    def test_log_file_flag_calls_configure(self, mock_process, mock_config, tmp_path):
        """Test that --log-file flag calls _configure_logging."""
        from all2md.cli import main

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        log_file = tmp_path / "test.log"

        # Mock successful processing
        mock_process.return_value = 0

        # Run with --log-file
        main([str(test_file), '--log-file', str(log_file), '--output-dir', str(tmp_path / 'out')])

        # Should call configure_logging with log_file
        assert mock_config.called
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs['log_file'] == str(log_file)

    @patch('all2md.cli._configure_logging')
    @patch('all2md.cli.processors.process_multi_file')
    def test_trace_flag_sets_debug_level(self, mock_process, mock_config, tmp_path):
        """Test that --trace flag sets DEBUG log level."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_process.return_value = 0

        # Run with --trace
        main([str(test_file), '--trace', '--output-dir', str(tmp_path / 'out')])

        # Should call configure_logging with DEBUG and trace_mode=True
        assert mock_config.called
        call_args = mock_config.call_args
        assert call_args[0][0] == logging.DEBUG  # First positional arg is log_level
        assert call_args[1]['trace_mode'] is True

    @patch('all2md.cli._configure_logging')
    @patch('all2md.cli.processors.process_multi_file')
    def test_log_level_precedence(self, mock_process, mock_config, tmp_path):
        """Test log level precedence: --trace > --verbose > --log-level."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_process.return_value = 0

        # Test --trace takes precedence
        main([str(test_file), '--trace', '--log-level', 'ERROR', '--output-dir', str(tmp_path / 'out')])
        assert mock_config.call_args[0][0] == logging.DEBUG

        # Test --verbose with default log-level
        main([str(test_file), '--verbose', '--output-dir', str(tmp_path / 'out')])
        assert mock_config.call_args[0][0] == logging.DEBUG

        # Test explicit --log-level
        main([str(test_file), '--log-level', 'ERROR', '--output-dir', str(tmp_path / 'out')])
        assert mock_config.call_args[0][0] == logging.ERROR


class TestEnhancedAbout:
    """Test enhanced --about command."""

    def test_about_shows_system_info(self, capsys):
        """Test --about shows system information."""
        from all2md.cli import main

        main(['--about'])

        captured = capsys.readouterr()
        output = captured.out

        # Should show system info
        assert "System Information:" in output
        assert "Python:" in output
        assert "Platform:" in output
        assert "Architecture:" in output

    def test_about_shows_dependencies(self, capsys):
        """Test --about shows dependency information."""
        from all2md.cli import main

        main(['--about'])

        captured = capsys.readouterr()
        output = captured.out

        # Should show dependency info
        assert "Installed Dependencies" in output
        # Should show at least some package status (✓ or ✗)
        assert "✓" in output or "✗" in output

    def test_about_shows_format_availability(self, capsys):
        """Test --about shows available formats."""
        from all2md.cli import main

        main(['--about'])

        captured = capsys.readouterr()
        output = captured.out

        # Should show format availability
        assert "Available Formats" in output
        assert "ready" in output.lower()

    def test_about_exit_code(self):
        """Test --about returns exit code 0."""
        from all2md.cli import main

        result = main(['--about'])
        assert result == 0

@pytest.mark.timing
@pytest.mark.skipif(os.getenv("CI") == "true", reason="Timing tests are flaky in CI")
class TestTimingInstrumentation:
    """Test timing instrumentation in conversion pipeline."""

    def test_trace_mode_logs_timing(self, tmp_path, caplog):
        """Test that trace mode logs timing information."""
        from all2md import to_markdown

        # Create a simple markdown file (txt format takes special path without timing)
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\ntest content")

        # Enable DEBUG logging to capture timing logs
        with caplog.at_level(logging.DEBUG):
            to_markdown(test_file, source_format="markdown")

            # Check that timing logs were created
            timing_logs = [record for record in caplog.records if 'completed in' in record.message]
            # Should have at least parsing and rendering timing
            assert len(timing_logs) >= 2

    def test_normal_mode_no_timing(self, tmp_path, caplog):
        """Test that normal mode doesn't log timing."""
        from all2md import to_markdown

        # Create a simple markdown file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\ntest content")

        # Use WARNING level (normal mode)
        with caplog.at_level(logging.WARNING):
            to_markdown(test_file, source_format="markdown")

            # Should not have timing logs at WARNING level
            timing_logs = [record for record in caplog.records if 'completed in' in record.message]
            assert len(timing_logs) == 0


@pytest.mark.integration
@pytest.mark.slow
class TestLogFileIntegration:
    """Integration tests for log file functionality."""

    def test_log_file_creation(self, tmp_path):
        """Test that log file is actually created."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        log_file = tmp_path / "conversion.log"
        output_dir = tmp_path / "out"

        # Run conversion with log file
        main([
            str(test_file),
            '--log-file', str(log_file),
            '--output-dir', str(output_dir),
            '--verbose'
        ])

        # Log file should be created
        assert log_file.exists()

        # Log file should contain some content
        log_content = log_file.read_text()
        assert len(log_content) > 0

    def test_trace_mode_format_in_log_file(self, tmp_path):
        """Test that trace mode produces properly formatted logs."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        log_file = tmp_path / "conversion.log"
        output_dir = tmp_path / "out"

        # Run with --trace
        main([
            str(test_file),
            '--trace',
            '--log-file', str(log_file),
            '--output-dir', str(output_dir)
        ])

        # Check log format
        log_content = log_file.read_text()

        # Trace format should include timestamps
        # Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [module] message
        import re
        timestamp_pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]'
        assert re.search(timestamp_pattern, log_content), "Log should contain timestamps in trace mode"
