"""Pytest configuration and shared fixtures for all2md test suite.

This module provides shared fixtures, test configuration, and utilities
that are used across the entire test suite.
"""

from pathlib import Path
from typing import Generator

import pytest
from utils import cleanup_test_dir, create_test_temp_dir

# Configure Hypothesis for property-based testing
try:
    from hypothesis import Phase, Verbosity, settings

    # Register custom Hypothesis profiles.
    #
    # Do NOT set ``verbosity`` on the "ci" profile. Hypothesis ships its own
    # profile of that exact name and auto-loads it when it detects CI, and
    # ``register_profile`` re-loads a profile that is already the active one.
    # So registering "ci" here lands on the live profile in CI, and every
    # profile registered *after* it -- including "dev", which is what actually
    # runs -- inherits whatever we set. A stray ``verbosity=Verbosity.verbose``
    # therefore made CI, and only CI, pretty-print every generated example;
    # that printer calls ``ast.parse``/``inspect.getsource`` per example and
    # cost ~35s on a complex document, turning a ~40s fuzz run into 68 minutes.
    # Use ``--hypothesis-verbosity=verbose`` for a one-off noisy run instead.
    settings.register_profile("ci", max_examples=100)
    settings.register_profile("dev", max_examples=20)
    settings.register_profile(
        "debug", max_examples=10, verbosity=Verbosity.verbose, phases=[Phase.explicit, Phase.reuse, Phase.generate]
    )

    # Load profile from environment or use default
    import os

    profile = os.getenv("HYPOTHESIS_PROFILE", "dev")
    settings.load_profile(profile)
except ImportError:
    # Hypothesis not installed, skip configuration
    pass


def pytest_report_header() -> list[str]:
    """Print the Hypothesis profile and fuzz mode at the top of every run.

    Both are invisible settings that change what the suite actually measures,
    and both have already gone wrong silently: a profile inherited an unwanted
    verbosity and cost 68 minutes per CI run, and the discovery sweep spent
    months replaying the fixed corpus because its flag did not take. A run that
    is not doing what its workflow name says should say so in its own log.
    """
    import os

    lines = [
        f"all2md fuzz discovery: {'on' if os.environ.get('ALL2MD_FUZZ_DISCOVERY') == '1' else 'off (fixed corpus)'}"
    ]
    try:
        from hypothesis import settings as _settings

        lines.append(
            f"hypothesis profile: {os.getenv('HYPOTHESIS_PROFILE', 'dev')} (verbosity={_settings.default.verbosity!r})"
        )
    except ImportError:
        pass
    return lines


def _setup_test_imports():
    """Setup imports needed for testing while maintaining lazy loading in production."""
    # Make pymupdf available for PDF tests that need to mock it
    try:
        import pymupdf

        import all2md.parsers.pdf

        all2md.parsers.pdf.pymupdf = pymupdf
    except ImportError:
        # If pymupdf isn't available, that's ok - tests that need it will skip
        pass

    # Make Hyperlink available for DOCX tests (already handled in the module)
    # No additional setup needed since we fixed the module-level approach


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests - fast, isolated component tests")
    config.addinivalue_line("markers", "integration: Integration tests - component interaction tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests - full pipeline tests")
    config.addinivalue_line("markers", "slow: Slow tests that may take several seconds")
    config.addinivalue_line("markers", "cli: Tests related to command-line interface")

    # Make lazy imports available for testing
    _setup_test_imports()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files.

    Yields
    ------
    Path
        Temporary directory path that will be cleaned up after test.

    """
    temp_path = create_test_temp_dir()
    try:
        yield temp_path
    finally:
        cleanup_test_dir(temp_path)


@pytest.fixture
def sample_text() -> str:
    """Provide sample text content for testing.

    Returns
    -------
    str
        Standard sample text used across multiple tests.

    """
    return """# Sample Document

This is a **sample document** with _italic text_ and some `inline code`.

## Section 2

Here is a list:
- Item 1
- Item 2
- Item 3

And a numbered list:
1. First item
2. Second item
3. Third item

### Code Block

```python
def hello_world():
    print("Hello, World!")
```

#### Table Example

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Row 1    | Data 1   | Value 1  |
| Row 2    | Data 2   | Value 2  |
"""


@pytest.fixture
def minimal_document_content() -> dict:
    """Provide minimal document content for testing.

    Returns
    -------
    dict
        Dictionary with content for different document elements.

    """
    return {
        "title": "Test Document",
        "heading": "Main Section",
        "paragraph": "This is a test paragraph with some content.",
        "bold_text": "Bold text example",
        "italic_text": "Italic text example",
        "list_items": ["First item", "Second item", "Third item"],
        "table_headers": ["Column 1", "Column 2", "Column 3"],
        "table_rows": [["Row 1 Col 1", "Row 1 Col 2", "Row 1 Col 3"], ["Row 2 Col 1", "Row 2 Col 2", "Row 2 Col 3"]],
    }
