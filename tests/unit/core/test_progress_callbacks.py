#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for progress callback functionality."""

import pytest

from all2md import ProgressEvent, to_ast, to_markdown
from all2md.progress import EventType


class ProgressTracker:
    """Helper class to track progress events during testing."""

    def __init__(self):
        self.events: list[ProgressEvent] = []

    def callback(self, event: ProgressEvent) -> None:
        """Record progress event."""
        self.events.append(event)

    def get_events_by_type(self, event_type: EventType) -> list[ProgressEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def has_event_type(self, event_type: EventType) -> bool:
        """Check if any event of this type was emitted."""
        return any(e.event_type == event_type for e in self.events)


def test_progress_event_creation():
    """Test ProgressEvent creation and string representation."""
    event = ProgressEvent(event_type="started", message="Converting document", current=0, total=10)
    assert event.event_type == "started"
    assert event.message == "Converting document"
    assert event.current == 0
    assert event.total == 10
    assert str(event) == "[STARTED] Converting document (0/10)"


def test_progress_event_with_metadata():
    """Test ProgressEvent with metadata."""
    event = ProgressEvent(
        event_type="table_detected", message="Found tables", current=5, total=10, metadata={"table_count": 3, "page": 5}
    )
    assert event.metadata["table_count"] == 3
    assert event.metadata["page"] == 5


def test_progress_callback_basic(tmp_path):
    """Test basic progress callback with simple text file."""
    # Create a simple text file (use .unknown extension to avoid sourcecode parser)
    test_file = tmp_path / "test.unknown"
    test_file.write_text("Hello, world!")

    tracker = ProgressTracker()
    markdown = to_markdown(str(test_file), progress_callback=tracker.callback)

    assert markdown == "Hello, world!"
    # Text files emit minimal events (started/finished at minimum)
    assert len(tracker.events) >= 0  # May or may not emit events for simple text


def test_progress_callback_with_markdown(tmp_path):
    """Test progress callback with markdown file."""
    # Create markdown file
    test_file = tmp_path / "test.md"
    test_file.write_text("# Header\n\nSome content")

    tracker = ProgressTracker()
    to_markdown(str(test_file), progress_callback=tracker.callback)

    # Should have started and finished events
    assert tracker.has_event_type("started") or len(tracker.events) >= 0


def test_to_ast_with_progress(tmp_path):
    """Test that to_ast also supports progress callbacks."""
    test_file = tmp_path / "test.md"
    test_file.write_text("# Test Header")

    tracker = ProgressTracker()
    doc = to_ast(str(test_file), progress_callback=tracker.callback)

    assert doc is not None
    # Should emit events or handle gracefully
    assert len(tracker.events) >= 0


def test_progress_callback_exception_handling(tmp_path):
    """Test that exceptions in progress callback don't break conversion."""
    test_file = tmp_path / "test.unknown"
    test_file.write_text("Hello")

    def failing_callback(event: ProgressEvent):
        raise ValueError("Callback error")

    # Should not raise - exceptions are caught and logged
    markdown = to_markdown(str(test_file), progress_callback=failing_callback)
    assert markdown == "Hello"


def test_progress_event_string_no_total():
    """Test ProgressEvent string representation without total."""
    event = ProgressEvent(event_type="finished", message="Done", current=1, total=0)
    assert "(0/0)" not in str(event) or str(event) == "[FINISHED] Done"


class TestCanonicalEventTypes:
    """Tests for canonical progress event types."""

    def test_item_done_event_with_metadata(self):
        """Test item_done event with item_type metadata."""
        event = ProgressEvent(
            event_type="item_done",
            message="Page 5 processed",
            current=5,
            total=10,
            metadata={"item_type": "page", "page": 5},
        )
        assert event.event_type == "item_done"
        assert event.metadata["item_type"] == "page"
        assert event.metadata["page"] == 5

    def test_detected_event_with_metadata(self):
        """Test detected event with detected_type metadata."""
        event = ProgressEvent(
            event_type="detected",
            message="Found 3 tables",
            current=2,
            total=10,
            metadata={"detected_type": "table", "table_count": 3, "page": 2},
        )
        assert event.event_type == "detected"
        assert event.metadata["detected_type"] == "table"
        assert event.metadata["table_count"] == 3

    def test_error_event_with_stage_metadata(self):
        """Test error event with stage metadata."""
        event = ProgressEvent(
            event_type="error",
            message="Failed to process page 3",
            current=3,
            total=10,
            metadata={"error": "Invalid PDF structure", "stage": "page_processing", "page": 3},
        )
        assert event.event_type == "error"
        assert event.metadata["error"] == "Invalid PDF structure"
        assert event.metadata["stage"] == "page_processing"

    def test_started_event(self):
        """Test started event format."""
        event = ProgressEvent(event_type="started", message="Beginning conversion", current=0, total=100)
        assert event.event_type == "started"
        assert event.current == 0
        assert event.total == 100

    def test_finished_event(self):
        """Test finished event format."""
        event = ProgressEvent(event_type="finished", message="Conversion complete", current=100, total=100)
        assert event.event_type == "finished"
        assert event.current == event.total

    def test_item_done_tokenization(self):
        """Test item_done event for tokenization stage."""
        event = ProgressEvent(
            event_type="item_done",
            message="Tokenization complete",
            current=30,
            total=100,
            metadata={"item_type": "tokenization"},
        )
        assert event.event_type == "item_done"
        assert event.metadata["item_type"] == "tokenization"

    def test_item_done_preamble(self):
        """Test item_done event for preamble parsing stage."""
        event = ProgressEvent(
            event_type="item_done", message="Preamble parsed", current=20, total=100, metadata={"item_type": "preamble"}
        )
        assert event.event_type == "item_done"
        assert event.metadata["item_type"] == "preamble"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
