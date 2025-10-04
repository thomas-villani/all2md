#!/usr/bin/env python3
"""Demo of progress callback functionality.

This example demonstrates how to use progress callbacks to track conversion
progress, which is useful for UI updates in applications that embed all2md.
"""

from all2md import to_markdown, ProgressEvent


def simple_progress_handler(event: ProgressEvent):
    """Simple progress handler that prints events."""
    print(f"[{event.event_type.upper()}] {event.message}")
    if event.total > 0:
        percentage = (event.current / event.total) * 100
        print(f"  Progress: {event.current}/{event.total} ({percentage:.1f}%)")
    if event.metadata:
        print(f"  Metadata: {event.metadata}")
    print()


def detailed_progress_handler(event: ProgressEvent):
    """Detailed progress handler with event-specific handling."""
    if event.event_type == "started":
        print(f"Starting conversion: {event.message}")
        print("-" * 50)
    elif event.event_type == "page_done":
        percentage = (event.current / event.total) * 100 if event.total > 0 else 0
        print(f"  Page {event.current}/{event.total} done ({percentage:.1f}%)")
    elif event.event_type == "table_detected":
        table_count = event.metadata.get('table_count', 0)
        page = event.metadata.get('page', '?')
        print(f"  Found {table_count} table(s) on page {page}")
    elif event.event_type == "finished":
        print("-" * 50)
        print(f"Conversion complete: {event.message}")
    elif event.event_type == "error":
        error = event.metadata.get('error', 'Unknown error')
        print(f"  ERROR: {error}")
    print()


def main():
    """Run the demo."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python progress_callback_demo.py <file_path>")
        print()
        print("Example:")
        print("  python progress_callback_demo.py document.pdf")
        sys.exit(1)

    file_path = sys.argv[1]

    print("=" * 70)
    print("Progress Callback Demo - Simple Handler")
    print("=" * 70)
    print()

    # Convert with simple progress handler
    markdown = to_markdown(file_path, progress=simple_progress_handler)

    print()
    print("=" * 70)
    print("Progress Callback Demo - Detailed Handler")
    print("=" * 70)
    print()

    # Convert with detailed progress handler
    markdown = to_markdown(file_path, progress=detailed_progress_handler)

    print()
    print("=" * 70)
    print(f"Conversion successful! Generated {len(markdown)} characters of markdown.")
    print("=" * 70)


if __name__ == "__main__":
    main()
