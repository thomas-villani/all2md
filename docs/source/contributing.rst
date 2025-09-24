Contributing Guide
==================

Thank you for your interest in contributing to mdparse! This guide will help you get started with development and ensure your contributions align with the project's standards.

Getting Started
---------------

Development Environment Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Fork and Clone the Repository**

   .. code-block:: bash

      git clone https://github.com/yourusername/mdparse.git
      cd mdparse

2. **Create a Virtual Environment**

   .. code-block:: bash

      python -m venv .venv
      source .venv/bin/activate  # On Windows: .venv\Scripts\activate

3. **Install Development Dependencies**

   .. code-block:: bash

      pip install -e .[dev]

   This installs mdparse in editable mode with all development tools.

4. **Verify Installation**

   .. code-block:: bash

      python -c "import mdparse; print('Installation successful!')"

Code Quality Standards
----------------------

Linting and Formatting
~~~~~~~~~~~~~~~~~~~~~~~

We use **Ruff** for both linting and formatting:

.. code-block:: bash

   # Check linting issues
   ruff check src/

   # Auto-fix linting issues
   ruff check --fix src/

   # Format code
   ruff format src/

   # Using virtual environment (Windows)
   .venv\Scripts\python.exe -m ruff check src/
   .venv\Scripts\python.exe -m ruff format src/

Type Checking
~~~~~~~~~~~~~

We use **MyPy** for type checking:

.. code-block:: bash

   # Run type checking
   mypy src/

   # Using virtual environment (Windows)
   .venv\Scripts\python.exe -m mypy src/

**Note:** Currently there are 100+ MyPy errors that need fixing. This is a great area for contribution!

Documentation Standards
~~~~~~~~~~~~~~~~~~~~~~~

All code must include proper documentation:

- **Module-level docstrings** in NumPy format
- **Function/class docstrings** in NumPy format
- **Type annotations** for all function parameters and returns
- **Inline comments** for complex logic

Example of proper documentation:

.. code-block:: python

   def convert_document(file_path: str, output_format: str = "markdown") -> str:
       """Convert a document to the specified format.

       Parameters
       ----------
       file_path : str
           Path to the input document file.
       output_format : str, default "markdown"
           Target format for conversion.

       Returns
       -------
       str
           Converted document content in the specified format.

       Raises
       ------
       FileNotFoundError
           If the input file does not exist.
       ValueError
           If the output format is not supported.
       """

Testing
-------

Test Framework
~~~~~~~~~~~~~~

**Note:** Test suite is not yet implemented. Setting up comprehensive testing is a high-priority contribution area.

Planned test structure:

.. code-block:: text

   tests/
   ├── unit/
   │   ├── test_pdf2markdown.py
   │   ├── test_docx2markdown.py
   │   ├── test_html2markdown.py
   │   └── ...
   ├── integration/
   │   ├── test_parse_file.py
   │   └── test_batch_processing.py
   ├── fixtures/
   │   ├── sample.pdf
   │   ├── sample.docx
   │   └── ...
   └── conftest.py

Running Tests (Future)
~~~~~~~~~~~~~~~~~~~~~~

Once tests are implemented:

.. code-block:: bash

   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=src/mdparse

   # Run specific test file
   pytest tests/unit/test_pdf2markdown.py

Contributing Areas
------------------

High Priority Areas
~~~~~~~~~~~~~~~~~~~

1. **Testing Framework Implementation**
   - Set up pytest configuration
   - Create test fixtures
   - Write unit tests for each module
   - Add integration tests
   - Set up CI/CD pipeline

2. **MyPy Type Error Resolution**
   - Fix 100+ existing type errors
   - Add missing type annotations
   - Improve type safety throughout codebase

3. **Performance Optimization**
   - Memory usage optimization for large files
   - Processing speed improvements
   - Async processing capabilities

4. **Additional Format Support**
   - RTF (Rich Text Format) support
   - ODT (OpenDocument Text) support
   - EPUB e-book format support
   - Additional image formats (TIFF, BMP, WebP)

Medium Priority Areas
~~~~~~~~~~~~~~~~~~~~~

1. **Feature Enhancements**
   - OCR integration for scanned PDFs
   - Advanced table detection algorithms
   - Improved email thread reconstruction
   - Custom styling options for output

2. **Documentation Improvements**
   - More usage examples
   - Video tutorials
   - Performance benchmarks
   - Migration guides

3. **Developer Tools**
   - CLI tool for batch conversion
   - Web interface for online conversion
   - REST API for service integration
   - Docker containerization

Code Contribution Process
-------------------------

1. **Choose an Issue**
   - Check the GitHub Issues page
   - Look for issues labeled "good first issue" or "help wanted"
   - Comment on the issue to indicate you're working on it

2. **Create a Feature Branch**

   .. code-block:: bash

      git checkout -b feature/your-feature-name
      # or
      git checkout -b fix/issue-description

3. **Make Your Changes**
   - Follow the coding standards
   - Add appropriate documentation
   - Include type annotations
   - Write tests (when framework is available)

4. **Test Your Changes**

   .. code-block:: bash

      # Run linting
      ruff check src/
      ruff format src/

      # Run type checking
      mypy src/

      # Test manually with various file types
      python -c "
      from mdparse import parse_file
      # Test your changes here
      "

5. **Commit Your Changes**

   Use conventional commit messages:

   .. code-block:: bash

      git add .
      git commit -m "feat: add support for RTF files"
      # or
      git commit -m "fix: resolve memory leak in PDF processing"
      # or
      git commit -m "docs: improve API documentation"

6. **Submit a Pull Request**
   - Push your branch to your fork
   - Create a pull request against the main branch
   - Fill out the pull request template
   - Request review from maintainers

Code Style Guidelines
---------------------

General Principles
~~~~~~~~~~~~~~~~~~

- **Readability**: Code should be self-documenting
- **Consistency**: Follow existing patterns in the codebase
- **Simplicity**: Prefer simple, clear solutions
- **Performance**: Consider memory and CPU usage
- **Robustness**: Handle errors gracefully

Specific Guidelines
~~~~~~~~~~~~~~~~~~~

**Function Naming:**

.. code-block:: python

   # Good
   def convert_pdf_to_markdown(file_path: str) -> str:

   # Avoid
   def pdf2md(fp: str) -> str:

**Variable Naming:**

.. code-block:: python

   # Good
   markdown_content = parse_file(file_obj, filename)

   # Avoid
   md = parse_file(f, fn)

**Error Handling:**

.. code-block:: python

   # Good
   try:
       result = risky_operation()
   except SpecificException as e:
       logger.error(f"Operation failed: {e}")
       raise

   # Avoid
   try:
       result = risky_operation()
   except:
       pass

**Import Organization:**

.. code-block:: python

   # Standard library imports
   import os
   import re
   from typing import Any, Optional

   # Third-party imports
   import fitz
   import pandas as pd

   # Local imports
   from .utils import helper_function

Adding New Format Support
-------------------------

To add support for a new file format:

1. **Create a New Module**

   .. code-block:: python

      # src/mdparse/newformat2markdown.py
      """New format to Markdown conversion module.

      This module provides functionality to convert [FORMAT] files
      to Markdown while preserving formatting and structure.
      """

      def newformat_to_markdown(file_obj, **options) -> str:
          """Convert a [FORMAT] file to Markdown.

          Parameters
          ----------
          file_obj : Any
              File object or path to the [FORMAT] file.
          **options
              Additional conversion options.

          Returns
          -------
          str
              Markdown representation of the document.
          """
          # Implementation here
          pass

2. **Update Main Parser**

   Add format detection in ``src/mdparse/__init__.py``:

   .. code-block:: python

      # Add to DOCUMENT_EXTENSIONS or appropriate list
      DOCUMENT_EXTENSIONS = [
          ".pdf",
          ".csv",
          ".xlsx",
          ".docx",
          ".pptx",
          ".eml",
          ".newformat",  # Add your extension
      ]

      # Add conversion logic in parse_file function
      elif file_mimetype == "application/new-format":
          from .newformat2markdown import newformat_to_markdown
          content = newformat_to_markdown(file)

3. **Add Dependencies**

   Update ``pyproject.toml`` if new dependencies are needed:

   .. code-block:: toml

      dependencies = [
          # ... existing dependencies
          "new-library>=1.0.0",
      ]

4. **Write Tests**

   .. code-block:: python

      # tests/unit/test_newformat2markdown.py
      import pytest
      from mdparse.newformat2markdown import newformat_to_markdown

      def test_basic_conversion():
          # Test implementation

5. **Update Documentation**

   - Add format to supported formats list
   - Update README.md
   - Add usage examples
   - Update docs/source/formats.rst

Reporting Issues
----------------

Bug Reports
~~~~~~~~~~~

When reporting bugs, please include:

- **Python version** and operating system
- **mdparse version**
- **Complete error message** with traceback
- **Minimal reproduction case**
- **Expected vs actual behavior**
- **Sample files** (if possible and not sensitive)

Feature Requests
~~~~~~~~~~~~~~~~

For feature requests, please include:

- **Use case description**
- **Expected behavior**
- **Suggested implementation approach** (optional)
- **Alternative solutions considered**

Security Issues
~~~~~~~~~~~~~~~

For security-related issues:

- **Do not** open a public issue
- Email security concerns to: [security email]
- Include detailed description and reproduction steps
- Allow time for assessment before disclosure

Code Review Process
-------------------

All contributions go through code review:

1. **Automated Checks**
   - Linting (Ruff)
   - Type checking (MyPy)
   - Tests (when available)

2. **Human Review**
   - Code quality assessment
   - Architecture compatibility
   - Documentation completeness
   - Performance considerations

3. **Feedback and Iteration**
   - Address reviewer feedback
   - Make necessary changes
   - Re-request review

4. **Approval and Merge**
   - Maintainer approval required
   - Squash and merge preferred
   - Update changelog

Recognition
-----------

Contributors are recognized in:

- **CONTRIBUTORS.md** file
- **Release notes** for significant contributions
- **GitHub contributors** page
- **Documentation** credits

Communication Channels
----------------------

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Pull Requests**: Code contributions and reviews

Getting Help
------------

If you need help with development:

1. Check existing documentation
2. Search GitHub issues
3. Start a GitHub discussion
4. Ask specific questions in pull requests

Thank you for contributing to mdparse! Your efforts help make document conversion more accessible and reliable for everyone.