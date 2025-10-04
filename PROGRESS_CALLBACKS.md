# Progress Callbacks Implementation

## Overview

Progress callbacks have been added to all API functions (`to_markdown`, `to_ast`, `convert`, `from_markdown`) to enable UI updates for embedders during document conversion.

## Usage

### Basic Example

```python
from all2md import to_markdown, ProgressEvent

def my_progress_handler(event: ProgressEvent):
    print(f"{event.event_type}: {event.message}")
    if event.total > 0:
        percentage = (event.current / event.total) * 100
        print(f"Progress: {percentage:.1f}%")

markdown = to_markdown("document.pdf", progress=my_progress_handler)
```

### Event Types

- **started**: Conversion has begun
- **page_done**: A page/section has been processed (PDF, PPTX)
- **table_detected**: Table structure detected (PDF)
- **finished**: Conversion completed successfully
- **error**: An error occurred

### Event Structure

```python
@dataclass
class ProgressEvent:
    event_type: Literal["started", "page_done", "table_detected", "finished", "error"]
    message: str
    current: int = 0  # Current progress position
    total: int = 0    # Total items to process
    metadata: dict[str, Any] = field(default_factory=dict)  # Event-specific data
```

## Implementation Details

### Modified Files

#### Core Infrastructure
- `src/all2md/progress.py` - Progress event system (NEW)
- `src/all2md/parsers/base.py` - BaseParser with progress callback support
- `src/all2md/__init__.py` - API functions with progress parameter

#### Parsers with Progress Events

**Full progress tracking:**
- `src/all2md/parsers/pdf.py` - Emits started, page_done, table_detected, finished, error
- `src/all2md/parsers/docx.py` - Emits started, finished
- `src/all2md/parsers/pptx.py` - Emits started, finished (with slide count)

**Basic progress tracking:**
- `src/all2md/parsers/html.py` - Emits started, finished
- `src/all2md/parsers/epub.py` - Emits started, finished

**Updated constructors to support progress_callback:**
- `src/all2md/parsers/csv.py`
- `src/all2md/parsers/xlsx.py`
- `src/all2md/parsers/ods_spreadsheet.py`
- `src/all2md/parsers/sourcecode.py`
- `src/all2md/parsers/markdown.py`

### API Changes

All main API functions now accept an optional `progress` parameter:

```python
def to_markdown(
    input,
    *,
    parser_options=None,
    renderer_options=None,
    format="auto",
    flavor=None,
    transforms=None,
    progress: Optional[ProgressCallback] = None,  # NEW
    **kwargs
) -> str:
    ...

def to_ast(
    input,
    *,
    parser_options=None,
    format="auto",
    progress: Optional[ProgressCallback] = None,  # NEW
    **kwargs
):
    ...

def convert(
    source,
    output=None,
    *,
    parser_options=None,
    renderer_options=None,
    source_format="auto",
    target_format="auto",
    transforms=None,
    hooks=None,
    renderer=None,
    flavor=None,
    progress: Optional[ProgressCallback] = None,  # NEW
    **kwargs
):
    ...

def from_markdown(
    markdown,
    target_format,
    output=None,
    *,
    parser_options=None,
    renderer_options=None,
    transforms=None,
    hooks=None,
    progress: Optional[ProgressCallback] = None,  # NEW
    **kwargs
):
    ...
```

## Examples

### Detailed Progress Handler

```python
def detailed_handler(event: ProgressEvent):
    if event.event_type == "started":
        print(f"Starting: {event.message}")
    elif event.event_type == "page_done":
        print(f"  Page {event.current}/{event.total} complete")
    elif event.event_type == "table_detected":
        table_count = event.metadata.get('table_count', 0)
        page = event.metadata.get('page', '?')
        print(f"  Found {table_count} tables on page {page}")
    elif event.event_type == "finished":
        print(f"Complete: {event.message}")
    elif event.event_type == "error":
        error = event.metadata.get('error', 'Unknown')
        print(f"  ERROR: {error}")

markdown = to_markdown("document.pdf", progress=detailed_handler)
```

### GUI Integration Example

```python
from all2md import to_markdown, ProgressEvent
import tkinter as tk
from tkinter import ttk

class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.progress = ttk.Progressbar(root, length=300, mode='determinate')
        self.progress.pack()
        self.status = tk.Label(root, text="Ready")
        self.status.pack()

    def progress_callback(self, event: ProgressEvent):
        if event.total > 0:
            value = (event.current / event.total) * 100
            self.progress['value'] = value
        self.status['text'] = event.message
        self.root.update_idletasks()

    def convert(self, filepath):
        markdown = to_markdown(filepath, progress=self.progress_callback)
        return markdown
```

## Testing

Tests are located in `tests/unit/test_progress_callbacks.py`:

- Event creation and metadata
- Progress callback with various file types
- Exception handling in callbacks
- Integration with to_ast() and to_markdown()

Run tests:
```bash
pytest tests/unit/test_progress_callbacks.py -v
```

## Demo

A complete demo is available:
```bash
python examples/progress_callback_demo.py document.pdf
```

## Error Handling

Progress callbacks are designed to be fail-safe:
- If a callback raises an exception, it's caught and logged
- Conversion continues normally even if the callback fails
- This prevents UI code from breaking the conversion process

## Future Enhancements

Potential future improvements:
- Add progress events to transform pipeline
- Add progress events to renderers
- Page-level progress for more formats (EPUB chapters, DOCX sections)
- Cancellation support (allow callbacks to signal conversion should stop)
