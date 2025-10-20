#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for progress callback support in document source retrievers."""

from unittest.mock import Mock, patch

import pytest

from all2md.progress import ProgressEvent
from all2md.utils.input_sources import (
    DocumentSourceRequest,
    HttpRetriever,
    RemoteInputOptions,
)


class TestHttpRetrieverProgress:
    """Tests for HttpRetriever progress event emission."""

    def test_http_retriever_emits_started_event(self):
        """Test that HttpRetriever emits 'started' event before fetch."""
        url = "https://example.com/document.pdf"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        callback_mock = Mock()

        request = DocumentSourceRequest(
            raw_input=url, remote_options=remote_options, progress_callback=callback_mock
        )

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"test content"

            retriever.load(request)

        # Verify started event was emitted
        calls = callback_mock.call_args_list
        assert len(calls) >= 2  # At least started and item_done

        # Check first call is 'started' event
        started_event = calls[0][0][0]
        assert isinstance(started_event, ProgressEvent)
        assert started_event.event_type == "started"
        assert started_event.metadata.get("item_type") == "download"
        assert started_event.metadata.get("url") == url
        assert "Downloading" in started_event.message

    def test_http_retriever_emits_completed_event(self):
        """Test that HttpRetriever emits 'item_done' event on success."""
        url = "https://example.com/document.pdf"
        test_content = b"test content bytes"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        callback_mock = Mock()

        request = DocumentSourceRequest(
            raw_input=url, remote_options=remote_options, progress_callback=callback_mock
        )

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = test_content

            retriever.load(request)

        # Verify completed event was emitted
        calls = callback_mock.call_args_list
        assert len(calls) >= 2

        # Check second call is 'item_done' event
        completed_event = calls[1][0][0]
        assert isinstance(completed_event, ProgressEvent)
        assert completed_event.event_type == "item_done"
        assert completed_event.metadata.get("item_type") == "download"
        assert completed_event.metadata.get("url") == url
        assert completed_event.metadata.get("bytes") == len(test_content)
        assert completed_event.current == 1
        assert completed_event.total == 1

    def test_http_retriever_emits_error_event_on_security_error(self):
        """Test that HttpRetriever emits 'error' event on NetworkSecurityError."""
        from all2md.exceptions import NetworkSecurityError

        url = "https://example.com/document.pdf"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        callback_mock = Mock()

        request = DocumentSourceRequest(
            raw_input=url, remote_options=remote_options, progress_callback=callback_mock
        )

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.side_effect = NetworkSecurityError("Blocked by security policy")

            with pytest.raises(NetworkSecurityError):
                retriever.load(request)

        # Verify error event was emitted
        calls = callback_mock.call_args_list
        assert len(calls) >= 2  # started + error

        # Check that error event was emitted
        error_event = calls[-1][0][0]
        assert isinstance(error_event, ProgressEvent)
        assert error_event.event_type == "error"
        assert error_event.metadata.get("stage") == "download"
        assert error_event.metadata.get("url") == url
        assert "failed" in error_event.message.lower()

    def test_http_retriever_emits_error_event_on_general_exception(self):
        """Test that HttpRetriever emits 'error' event on general Exception."""
        url = "https://example.com/document.pdf"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        callback_mock = Mock()

        request = DocumentSourceRequest(
            raw_input=url, remote_options=remote_options, progress_callback=callback_mock
        )

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.side_effect = ValueError("Network error")

            # Should raise NetworkSecurityError wrapping the original error
            from all2md.exceptions import NetworkSecurityError

            with pytest.raises(NetworkSecurityError):
                retriever.load(request)

        # Verify error event was emitted
        calls = callback_mock.call_args_list
        error_events = [call[0][0] for call in calls if call[0][0].event_type == "error"]
        assert len(error_events) >= 1

        error_event = error_events[0]
        assert error_event.metadata.get("stage") == "download"
        assert error_event.metadata.get("url") == url
        assert "error" in error_event.metadata.get("error", "").lower()

    def test_http_retriever_no_events_when_callback_none(self):
        """Test that HttpRetriever works without callback (backward compatibility)."""
        url = "https://example.com/document.pdf"
        remote_options = RemoteInputOptions(allow_remote_input=True)

        # No progress_callback provided
        request = DocumentSourceRequest(raw_input=url, remote_options=remote_options, progress_callback=None)

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"test content"

            source = retriever.load(request)

        # Should complete successfully without error
        assert source is not None
        assert source.display_name

    def test_http_retriever_handles_callback_exceptions(self):
        """Test that HttpRetriever handles exceptions in callback gracefully."""
        url = "https://example.com/document.pdf"
        remote_options = RemoteInputOptions(allow_remote_input=True)

        def failing_callback(event: ProgressEvent) -> None:
            raise ValueError("Callback error")

        request = DocumentSourceRequest(
            raw_input=url, remote_options=remote_options, progress_callback=failing_callback
        )

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"test content"

            # Should complete successfully despite callback errors
            source = retriever.load(request)

        assert source is not None

    def test_http_retriever_event_sequence(self):
        """Test that HttpRetriever emits events in correct sequence."""
        url = "https://example.com/document.pdf"
        remote_options = RemoteInputOptions(allow_remote_input=True)
        events_log = []

        def logging_callback(event: ProgressEvent) -> None:
            events_log.append(event.event_type)

        request = DocumentSourceRequest(
            raw_input=url, remote_options=remote_options, progress_callback=logging_callback
        )

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = b"test content"

            retriever.load(request)

        # Verify event sequence: started -> item_done
        assert events_log == ["started", "item_done"]

    def test_http_retriever_event_metadata_complete(self):
        """Test that HttpRetriever includes all expected metadata in events."""
        url = "https://example.com/document.pdf"
        test_content = b"x" * 1024  # 1 KB
        remote_options = RemoteInputOptions(allow_remote_input=True)
        events_log = []

        def logging_callback(event: ProgressEvent) -> None:
            events_log.append(event)

        request = DocumentSourceRequest(
            raw_input=url, remote_options=remote_options, progress_callback=logging_callback
        )

        retriever = HttpRetriever()

        with patch("all2md.utils.input_sources.fetch_content_securely") as fetch_mock:
            fetch_mock.return_value = test_content

            retriever.load(request)

        assert len(events_log) == 2

        # Check started event metadata
        started = events_log[0]
        assert started.metadata["item_type"] == "download"
        assert started.metadata["url"] == url

        # Check completed event metadata
        completed = events_log[1]
        assert completed.metadata["item_type"] == "download"
        assert completed.metadata["url"] == url
        assert completed.metadata["bytes"] == 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
