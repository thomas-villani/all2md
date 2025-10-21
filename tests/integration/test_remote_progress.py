#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for remote progress tracking in CLI."""

from unittest.mock import Mock, patch

import pytest

from all2md import to_ast
from all2md.progress import ProgressEvent
from all2md.utils.input_sources import RemoteInputOptions


@pytest.mark.integration
class TestRemoteProgressTracking:
    """Integration tests for progress tracking with remote inputs."""

    def test_to_markdown_remote_url_emits_progress(self):
        """Test that to_markdown emits progress events for remote URLs."""
        from all2md import convert

        url = "https://example.com/document.md"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        events_log = []

        def logging_callback(event: ProgressEvent) -> None:
            events_log.append((event.event_type, event.metadata.get("item_type")))

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"# Test Document\n\nContent here."

            result = convert(
                url,
                source_format="markdown",
                target_format="markdown",
                remote_input_options=remote_options,
                progress_callback=logging_callback,
            )

        # Verify result
        assert "# Test Document" in result

        # Verify progress events were emitted
        assert len(events_log) >= 2
        # Check that download events were emitted
        download_events = [e for e in events_log if e[1] == "download"]
        assert len(download_events) >= 2
        # Should have started and item_done
        assert ("started", "download") in download_events
        assert ("item_done", "download") in download_events

    def test_to_ast_remote_url_emits_progress(self):
        """Test that to_ast emits progress events for remote URLs."""
        url = "https://example.com/document.md"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        events_log = []

        def logging_callback(event: ProgressEvent) -> None:
            events_log.append(event)

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"# Heading\n\nParagraph."

            doc = to_ast(
                url, source_format="markdown", remote_input_options=remote_options, progress_callback=logging_callback
            )

        # Verify result
        assert doc is not None
        assert len(doc.children) > 0

        # Verify progress events were emitted for download
        download_started = [
            e for e in events_log if e.event_type == "started" and e.metadata.get("item_type") == "download"
        ]
        download_done = [
            e for e in events_log if e.event_type == "item_done" and e.metadata.get("item_type") == "download"
        ]

        assert len(download_started) == 1
        assert len(download_done) == 1

        # Check event details
        started = download_started[0]
        assert started.metadata["url"] == url
        assert "Downloading" in started.message

        done = download_done[0]
        assert done.metadata["url"] == url
        assert done.metadata["bytes"] > 0

    def test_remote_progress_with_https_requirement(self):
        """Test progress events work with HTTPS requirement."""
        from all2md import convert

        url = "https://secure.example.com/doc.md"
        remote_options = RemoteInputOptions(allow_remote_input=True, require_https=True)
        callback_mock = Mock()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"# Secure Doc"

            convert(
                url,
                source_format="markdown",
                target_format="markdown",
                remote_input_options=remote_options,
                progress_callback=callback_mock,
            )

        # Verify callback was called
        assert callback_mock.call_count >= 2

    def test_remote_progress_callback_receives_byte_count(self):
        """Test that progress callback receives correct byte count."""
        from all2md import convert

        url = "https://example.com/large-doc.md"
        test_content = b"# Large Document\n" + (b"x" * 10000)  # ~10KB
        remote_options = RemoteInputOptions(allow_remote_input=True)
        byte_counts = []

        def byte_counting_callback(event: ProgressEvent) -> None:
            if event.event_type == "item_done" and event.metadata.get("item_type") == "download":
                byte_counts.append(event.metadata.get("bytes", 0))

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = test_content

            convert(
                url,
                source_format="markdown",
                target_format="markdown",
                remote_input_options=remote_options,
                progress_callback=byte_counting_callback,
            )

        # Verify byte count was reported
        assert len(byte_counts) == 1
        assert byte_counts[0] == len(test_content)

    def test_remote_progress_with_network_error(self):
        """Test that error events are emitted on network failures."""
        from all2md import convert
        from all2md.exceptions import NetworkSecurityError

        url = "https://example.com/failing-doc.md"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        error_events = []

        def error_logging_callback(event: ProgressEvent) -> None:
            if event.event_type == "error":
                error_events.append(event)

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.side_effect = NetworkSecurityError("Connection refused")

            with pytest.raises(NetworkSecurityError):
                convert(
                    url,
                    source_format="markdown",
                    target_format="markdown",
                    remote_input_options=remote_options,
                    progress_callback=error_logging_callback,
                )

        # Verify error event was emitted
        assert len(error_events) >= 1
        error = error_events[0]
        assert error.metadata.get("stage") == "download"
        assert error.metadata.get("url") == url

    def test_multiple_remote_fetches_emit_separate_events(self):
        """Test that multiple remote fetches emit separate progress events."""
        # This would be used when collating multiple remote documents
        urls = [
            "https://example.com/doc1.md",
            "https://example.com/doc2.md",
        ]
        remote_options = RemoteInputOptions(allow_remote_input=True)
        all_events = []

        def collecting_callback(event: ProgressEvent) -> None:
            if event.metadata.get("item_type") == "download":
                all_events.append((event.event_type, event.metadata.get("url")))

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"# Document\n\nContent."

            for url in urls:
                to_ast(
                    url,
                    source_format="markdown",
                    remote_input_options=remote_options,
                    progress_callback=collecting_callback,
                )

        # Should have events for both URLs
        unique_urls = {url for _, url in all_events}
        assert len(unique_urls) == 2
        assert all(url in unique_urls for url in urls)

        # Each URL should have started and completed events
        for url in urls:
            url_events = [event_type for event_type, event_url in all_events if event_url == url]
            assert "started" in url_events
            assert "item_done" in url_events


@pytest.mark.integration
class TestCLIProgressContextCallback:
    """Integration tests for CLI progress context callback wrapper."""

    def test_progress_context_callback_logs_download_events(self):
        """Test that progress context callback handles download events."""
        import sys
        from io import StringIO

        from all2md.cli.progress import ProgressContext, create_progress_context_callback

        # Capture stderr output
        captured_output = StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_output

        try:
            with ProgressContext(use_rich=False, use_progress=True, total=1, description="Testing") as progress:
                callback = create_progress_context_callback(progress)

                # Simulate download events
                callback(
                    ProgressEvent(
                        event_type="started",
                        message="Downloading https://example.com/doc.md",
                        metadata={"item_type": "download", "url": "https://example.com/doc.md"},
                    )
                )

                callback(
                    ProgressEvent(
                        event_type="item_done",
                        message="Downloaded https://example.com/doc.md",
                        current=1,
                        total=1,
                        metadata={"item_type": "download", "bytes": 1024, "url": "https://example.com/doc.md"},
                    )
                )

            output = captured_output.getvalue()
            # Should log download messages
            assert "Downloading" in output or "Downloaded" in output

        finally:
            sys.stderr = old_stderr

    def test_progress_context_callback_handles_errors(self):
        """Test that progress context callback handles error events."""
        import sys
        from io import StringIO

        from all2md.cli.progress import ProgressContext, create_progress_context_callback

        captured_output = StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_output

        try:
            with ProgressContext(use_rich=False, use_progress=True, total=1, description="Testing") as progress:
                callback = create_progress_context_callback(progress)

                # Simulate error event
                callback(
                    ProgressEvent(
                        event_type="error",
                        message="Download failed: https://example.com/doc.md",
                        metadata={
                            "stage": "download",
                            "url": "https://example.com/doc.md",
                            "error": "Connection timeout",
                        },
                    )
                )

            output = captured_output.getvalue()
            # Should log error message
            assert "failed" in output.lower() or "error" in output.lower()

        finally:
            sys.stderr = old_stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
