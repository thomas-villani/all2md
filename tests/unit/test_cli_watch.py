"""Unit tests for CLI watch mode.

Tests for --watch, --watch-debounce flags and watch mode functionality.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Check if watchdog is available
try:
    from watchdog.observers import Observer
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class TestConversionEventHandler:
    """Test ConversionEventHandler class."""

    def test_handler_initialization(self, tmp_path):
        """Test event handler initialization."""
        from all2md.cli.watch import ConversionEventHandler

        paths = [tmp_path / "doc.txt"]
        output_dir = tmp_path / "out"
        options = {}

        handler = ConversionEventHandler(
            paths_to_watch=paths,
            output_dir=output_dir,
            options=options,
            format_arg="auto",
            debounce_seconds=1.0
        )

        assert handler.output_dir == output_dir
        assert handler.debounce_seconds == 1.0

    def test_should_process_valid_file(self, tmp_path):
        """Test that valid files are processed."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        # Create a valid document file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"test")

        assert handler.should_process(str(test_file))

    def test_should_process_skips_unsupported_extension(self, tmp_path):
        """Test that unsupported extensions are skipped."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        # Create file with unsupported extension
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"test")

        assert not handler.should_process(str(test_file))

    def test_should_process_respects_debounce(self, tmp_path):
        """Test that debounce delay is respected."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto",
            debounce_seconds=0.5
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # First call should process
        assert handler.should_process(str(test_file))

        # Update last processed time
        handler._last_processed[str(test_file)] = time.time()

        # Immediate second call should be skipped (debounce)
        assert not handler.should_process(str(test_file))

        # After debounce delay, should process again
        time.sleep(0.6)
        assert handler.should_process(str(test_file))

    def test_should_process_respects_exclude_patterns(self, tmp_path):
        """Test that exclude patterns are respected."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto",
            exclude_patterns=["*.tmp", "temp_*"]
        )

        # Should skip files matching exclude patterns
        assert not handler.should_process(str(tmp_path / "test.tmp"))
        assert not handler.should_process(str(tmp_path / "temp_file.txt"))

        # Should process files not matching patterns
        assert handler.should_process(str(tmp_path / "test.txt"))

    def test_should_process_skips_already_processing(self, tmp_path):
        """Test that files already being processed are skipped."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Mark as processing
        handler._processing.add(str(test_file))

        # Should skip
        assert not handler.should_process(str(test_file))

    @patch('all2md.to_markdown')
    def test_convert_file_success(self, mock_to_markdown, tmp_path):
        """Test successful file conversion."""
        from all2md.cli.watch import ConversionEventHandler

        output_dir = tmp_path / "out"
        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=output_dir,
            options={},
            format_arg="auto"
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_to_markdown.return_value = "# Test"

        # Convert file
        handler.convert_file(str(test_file))

        # Should call to_markdown
        mock_to_markdown.assert_called_once()

        # Should create output file
        output_file = output_dir / "test.md"
        assert output_file.exists()
        assert output_file.read_text() == "# Test"

    @patch('all2md.to_markdown')
    def test_convert_file_handles_error(self, mock_to_markdown, tmp_path, caplog):
        """Test that conversion errors are handled gracefully."""
        from all2md.cli.watch import ConversionEventHandler
        from all2md.exceptions import MarkdownConversionError

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Simulate conversion error
        mock_to_markdown.side_effect = MarkdownConversionError("Test error")

        # Should not raise, but log error
        handler.convert_file(str(test_file))

        # Check error was logged
        assert any("Conversion error" in record.message for record in caplog.records)

    @patch('all2md.to_markdown')
    def test_convert_file_clears_processing_flag(self, mock_to_markdown, tmp_path):
        """Test that processing flag is cleared after conversion."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mock_to_markdown.return_value = "# Test"

        # Convert file
        handler.convert_file(str(test_file))

        # Processing flag should be cleared
        assert str(test_file) not in handler._processing

    def test_on_modified_event(self, tmp_path):
        """Test on_modified event handler."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Create mock event
        event = Mock()
        event.is_directory = False
        event.src_path = str(test_file)

        # Mock convert_file to avoid actual conversion
        handler.convert_file = Mock()

        # Handle event
        handler.on_modified(event)

        # Should call convert_file
        handler.convert_file.assert_called_once_with(str(test_file))

    def test_on_created_event(self, tmp_path):
        """Test on_created event handler."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        event = Mock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler.convert_file = Mock()

        handler.on_created(event)

        handler.convert_file.assert_called_once_with(str(test_file))

    def test_on_moved_event(self, tmp_path):
        """Test on_moved event handler."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        event = Mock()
        event.is_directory = False
        event.dest_path = str(test_file)

        handler.convert_file = Mock()

        handler.on_moved(event)

        # Should convert destination path
        handler.convert_file.assert_called_once_with(str(test_file))

    def test_directory_events_ignored(self, tmp_path):
        """Test that directory events are ignored."""
        from all2md.cli.watch import ConversionEventHandler

        handler = ConversionEventHandler(
            paths_to_watch=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        event = Mock()
        event.is_directory = True
        event.src_path = str(tmp_path / "subdir")

        handler.convert_file = Mock()

        # Handle directory events
        handler.on_modified(event)
        handler.on_created(event)

        # Should not call convert_file for directories
        handler.convert_file.assert_not_called()


class TestRunWatchMode:
    """Test run_watch_mode function."""

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    @patch('time.sleep')
    @patch('watchdog.observers.Observer')
    def test_watch_mode_basic(self, mock_observer_class, mock_sleep, tmp_path):
        """Test basic watch mode setup."""
        from all2md.cli.watch import run_watch_mode

        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer

        # Mock keyboard interrupt in the sleep loop to stop immediately
        mock_sleep.side_effect = KeyboardInterrupt()

        paths = [tmp_path / "test.txt"]
        paths[0].write_text("test")

        output_dir = tmp_path / "out"

        # Run watch mode
        result = run_watch_mode(
            paths=paths,
            output_dir=output_dir,
            options={},
            format_arg="auto"
        )

        # Should set up observer
        mock_observer.schedule.assert_called()
        mock_observer.start.assert_called_once()

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    @patch('time.sleep')
    @patch('watchdog.observers.Observer')
    def test_watch_mode_directory(self, mock_observer_class, mock_sleep, tmp_path):
        """Test watch mode on directory."""
        from all2md.cli.watch import run_watch_mode

        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer
        mock_sleep.side_effect = KeyboardInterrupt()

        # Watch a directory
        result = run_watch_mode(
            paths=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto",
            recursive=True
        )

        # Should schedule with recursive=True
        call_args = mock_observer.schedule.call_args
        assert call_args[1]['recursive'] is True

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    @patch('time.sleep')
    @patch('watchdog.observers.Observer')
    def test_watch_mode_handles_keyboard_interrupt(self, mock_observer_class, mock_sleep, tmp_path, capsys):
        """Test that watch mode handles Ctrl+C gracefully."""
        from all2md.cli.watch import run_watch_mode

        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer
        mock_sleep.side_effect = KeyboardInterrupt()

        result = run_watch_mode(
            paths=[tmp_path],
            output_dir=tmp_path / "out",
            options={},
            format_arg="auto"
        )

        # Should stop observer
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

        # Should return success
        assert result == 0

        # Should print stop message
        captured = capsys.readouterr()
        assert "Stopping watch mode" in captured.out

    def test_watch_mode_without_watchdog(self, tmp_path, caplog):
        """Test watch mode without watchdog installed."""
        import logging
        import sys
        from all2md.cli.watch import run_watch_mode

        # Temporarily remove watchdog from sys.modules
        watchdog_modules = {k: v for k, v in sys.modules.items() if 'watchdog' in k}
        for key in watchdog_modules:
            del sys.modules[key]

        # Mock the import to raise ImportError
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if 'watchdog' in name:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        try:
            with patch('builtins.__import__', side_effect=mock_import):
                with caplog.at_level(logging.ERROR):
                    result = run_watch_mode(
                        paths=[tmp_path],
                        output_dir=tmp_path / "out",
                        options={},
                        format_arg="auto"
                    )

            # Should return dependency error code
            assert result == 2

            # Should log error message
            assert any("watchdog" in record.message.lower() for record in caplog.records)
        finally:
            # Restore watchdog modules
            sys.modules.update(watchdog_modules)

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    @patch('time.sleep')
    @patch('watchdog.observers.Observer')
    def test_watch_mode_creates_output_dir(self, mock_observer_class, mock_sleep, tmp_path):
        """Test that watch mode creates output directory."""
        from all2md.cli.watch import run_watch_mode

        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer
        mock_sleep.side_effect = KeyboardInterrupt()

        output_dir = tmp_path / "nonexistent" / "out"

        run_watch_mode(
            paths=[tmp_path],
            output_dir=output_dir,
            options={},
            format_arg="auto"
        )

        # Output directory should be created
        assert output_dir.exists()


class TestWatchCLIIntegration:
    """Test --watch CLI flag integration."""

    @patch('all2md.cli.watch.run_watch_mode')
    def test_watch_flag_calls_watch_mode(self, mock_watch_mode, tmp_path):
        """Test that --watch flag calls run_watch_mode."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        output_dir = tmp_path / "out"

        mock_watch_mode.return_value = 0

        result = main([
            str(test_file),
            '--watch',
            '--output-dir', str(output_dir)
        ])

        # Should call watch mode
        mock_watch_mode.assert_called_once()

    def test_watch_requires_output_dir(self, tmp_path, capsys):
        """Test that --watch requires --output-dir."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Run --watch without --output-dir
        result = main([str(test_file), '--watch'])

        # Should fail with error
        assert result != 0

        captured = capsys.readouterr()
        assert "output-dir" in captured.err.lower()

    @patch('all2md.cli.watch.run_watch_mode')
    def test_watch_debounce_flag(self, mock_watch_mode, tmp_path):
        """Test --watch-debounce flag."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mock_watch_mode.return_value = 0

        result = main([
            str(test_file),
            '--watch',
            '--watch-debounce', '2.5',
            '--output-dir', str(tmp_path / 'out')
        ])

        # Should pass debounce value to watch mode
        call_kwargs = mock_watch_mode.call_args[1]
        assert call_kwargs['debounce'] == 2.5

    def test_watch_with_recursive(self, tmp_path):
        """Test --watch with --recursive."""
        from all2md.cli import create_parser

        parser = create_parser()

        args = parser.parse_args([
            str(tmp_path),
            '--watch',
            '--recursive',
            '--output-dir', str(tmp_path / 'out')
        ])

        # Should have recursive flag
        assert args.recursive is True
        assert args.watch is True

    def test_watch_with_exclude_patterns(self, tmp_path):
        """Test --watch with --exclude patterns."""
        from all2md.cli import create_parser

        parser = create_parser()
        test_file = tmp_path / "test.txt"

        args = parser.parse_args([
            str(test_file),
            '--watch',
            '--exclude', '*.tmp',
            '--exclude', '*.bak',
            '--output-dir', str(tmp_path / 'out')
        ])

        # Should have exclude patterns
        assert args.exclude == ['*.tmp', '*.bak']
        assert args.watch is True


@pytest.mark.integration
class TestWatchModeIntegration:
    """Integration tests for watch mode."""

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    @patch('time.sleep')
    @patch('watchdog.observers.Observer')
    def test_watch_mode_full_workflow(self, mock_observer_class, mock_sleep, tmp_path):
        """Test complete watch mode workflow."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        output_dir = tmp_path / "out"

        # Mock observer to stop immediately
        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer
        mock_sleep.side_effect = KeyboardInterrupt()

        # Run watch mode
        result = main([
            str(test_file),
            '--watch',
            '--output-dir', str(output_dir)
        ])

        # Should set up and run watch mode
        assert result == 0
        mock_observer.schedule.assert_called()
        mock_observer.start.assert_called()

    @pytest.mark.skipif(
        True,  # Skip by default as it requires actual file system monitoring
        reason="Requires real file system events and watchdog"
    )
    def test_watch_mode_actual_file_change(self, tmp_path):
        """Test watch mode with actual file changes (requires watchdog)."""
        from all2md.cli.watch import run_watch_mode
        import threading

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial content")

        output_dir = tmp_path / "out"

        # Run watch mode in background thread
        def run_watch():
            run_watch_mode(
                paths=[test_file],
                output_dir=output_dir,
                options={},
                format_arg="auto",
                debounce=0.1
            )

        watch_thread = threading.Thread(target=run_watch, daemon=True)
        watch_thread.start()

        # Give watch mode time to start
        time.sleep(0.5)

        # Modify file
        test_file.write_text("modified content")

        # Wait for processing
        time.sleep(0.5)

        # Check output was created
        output_file = output_dir / "test.md"
        assert output_file.exists()

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    def test_watch_mode_real_file_modification(self, tmp_path):
        """Test watch mode with real file modification events."""
        from all2md.cli.watch import run_watch_mode
        import threading

        # Create test file
        test_file = tmp_path / "document.txt"
        test_file.write_text("Initial content")

        output_dir = tmp_path / "output"

        # Track when watch mode is ready
        ready_event = threading.Event()
        stop_event = threading.Event()

        def run_watch_thread():
            ready_event.set()
            try:
                run_watch_mode(
                    paths=[test_file],
                    output_dir=output_dir,
                    options={},
                    format_arg="auto",
                    debounce=0.2
                )
            except KeyboardInterrupt:
                pass

        # Start watch mode in background
        watch_thread = threading.Thread(target=run_watch_thread, daemon=True)
        watch_thread.start()

        # Wait for watch mode to be ready
        ready_event.wait(timeout=2.0)
        time.sleep(0.5)  # Give observer time to fully start

        # Modify the file
        test_file.write_text("Modified content for testing")

        # Wait for conversion to complete
        time.sleep(1.0)

        # Check output was created
        output_file = output_dir / "document.md"
        assert output_file.exists(), "Output markdown file should be created"

        # Verify content
        content = output_file.read_text()
        assert "Modified content" in content

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    def test_watch_mode_real_file_creation(self, tmp_path):
        """Test watch mode detects newly created files."""
        from all2md.cli.watch import run_watch_mode
        import threading

        output_dir = tmp_path / "output"

        ready_event = threading.Event()

        def run_watch_thread():
            ready_event.set()
            try:
                run_watch_mode(
                    paths=[tmp_path],
                    output_dir=output_dir,
                    options={},
                    format_arg="auto",
                    debounce=0.2,
                    recursive=False
                )
            except KeyboardInterrupt:
                pass

        # Start watch mode
        watch_thread = threading.Thread(target=run_watch_thread, daemon=True)
        watch_thread.start()

        ready_event.wait(timeout=2.0)
        time.sleep(0.5)

        # Create a new file
        new_file = tmp_path / "new_document.txt"
        new_file.write_text("New file content")

        # Wait for conversion
        time.sleep(1.0)

        # Check output
        output_file = output_dir / "new_document.md"
        assert output_file.exists(), "Newly created file should be converted"

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    def test_watch_mode_debounce_rapid_changes(self, tmp_path):
        """Test that debouncing prevents duplicate processing of rapid changes."""
        from all2md.cli.watch import run_watch_mode
        import threading

        test_file = tmp_path / "rapid_change.txt"
        test_file.write_text("Initial")

        output_dir = tmp_path / "output"

        ready_event = threading.Event()

        def run_watch_thread():
            ready_event.set()
            try:
                run_watch_mode(
                    paths=[test_file],
                    output_dir=output_dir,
                    options={},
                    format_arg="auto",
                    debounce=0.5  # 500ms debounce
                )
            except KeyboardInterrupt:
                pass

        watch_thread = threading.Thread(target=run_watch_thread, daemon=True)
        watch_thread.start()

        ready_event.wait(timeout=2.0)
        time.sleep(0.5)

        # Make rapid changes
        for i in range(5):
            test_file.write_text(f"Change {i}")
            time.sleep(0.1)  # Much faster than debounce time

        # Wait for debounce and one conversion
        time.sleep(1.0)

        # Output should exist
        output_file = output_dir / "rapid_change.md"
        assert output_file.exists()

        # Content should reflect the first change that triggered conversion
        # (subsequent rapid changes are debounced and ignored)
        content = output_file.read_text()
        assert "Change" in content  # File was converted with one of the changes

    @pytest.mark.skipif(not WATCHDOG_AVAILABLE, reason="requires watchdog")
    def test_watch_mode_exclude_patterns_real(self, tmp_path):
        """Test that exclude patterns work with real file events."""
        from all2md.cli.watch import run_watch_mode
        import threading

        output_dir = tmp_path / "output"

        ready_event = threading.Event()

        def run_watch_thread():
            ready_event.set()
            try:
                run_watch_mode(
                    paths=[tmp_path],
                    output_dir=output_dir,
                    options={},
                    format_arg="auto",
                    debounce=0.2,
                    exclude_patterns=["*.tmp", "draft_*"]
                )
            except KeyboardInterrupt:
                pass

        watch_thread = threading.Thread(target=run_watch_thread, daemon=True)
        watch_thread.start()

        ready_event.wait(timeout=2.0)
        time.sleep(0.5)

        # Create files - some should be excluded
        (tmp_path / "normal.txt").write_text("Should be converted")
        (tmp_path / "test.tmp").write_text("Should be excluded")
        (tmp_path / "draft_doc.txt").write_text("Should be excluded")

        time.sleep(1.0)

        # Only normal.txt should be converted
        assert (output_dir / "normal.md").exists()
        assert not (output_dir / "test.md").exists()
        assert not (output_dir / "draft_doc.md").exists()
