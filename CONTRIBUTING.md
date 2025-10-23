# Contributing to all2md

Thank you for your interest in contributing to all2md! This guide will help you get started with development, testing, and submitting contributions.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Quality](#code-quality)
- [Testing](#testing)
- [Documentation](#documentation)
- [Adding New Features](#adding-new-features)
- [Submitting Changes](#submitting-changes)

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Git
- (Recommended) A virtual environment manager

### Setting Up Your Environment

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/yourusername/all2md.git
   cd all2md
   ```

2. **Create and activate a virtual environment:**

   ```bash
   # Using venv
   python -m venv .venv

   # On Windows
   .venv\Scripts\activate

   # On macOS/Linux
   source .venv/bin/activate
   ```

3. **Install development dependencies:**

   ```bash
   # Install all format dependencies and development tools
   pip install -e ".[all]"

   # Install additional development tools
   pip install pytest ruff mypy sphinx
   ```

## Code Quality

We use several tools to maintain code quality:

### Linting with Ruff

Run linting checks:

```bash
# Windows (from virtual environment)
.venv/Scripts/python.exe -m ruff check

# macOS/Linux
python -m ruff check
```

Auto-fix issues where possible:

```bash
.venv/Scripts/python.exe -m ruff check --fix
```

### Code Formatting

Format code with Ruff:

```bash
.venv/Scripts/python.exe -m ruff format
```

### Type Checking

Run type checking with mypy:

```bash
.venv/Scripts/python.exe -m mypy src/
```

### All Quality Checks

Before submitting a PR, run all checks:

```bash
# Linting
.venv/Scripts/python.exe -m ruff check

# Formatting
.venv/Scripts/python.exe -m ruff format --check

# Type checking
.venv/Scripts/python.exe -m mypy src/

# Tests
.venv/Scripts/python.exe -m pytest -m unit
```

## Testing

### Running Tests

We use pytest with test markers for different test categories:

```bash
# Run all tests
.venv/Scripts/python.exe -m pytest tests/

# Run only fast unit tests (recommended during development)
.venv/Scripts/python.exe -m pytest -m unit

# Run integration tests
.venv/Scripts/python.exe -m pytest -m integration

# Run end-to-end tests
.venv/Scripts/python.exe -m pytest -m e2e

# Run format-specific tests
.venv/Scripts/python.exe -m pytest -m pdf
.venv/Scripts/python.exe -m pytest -m docx
.venv/Scripts/python.exe -m pytest -m html

# Run a specific test file
.venv/Scripts/python.exe -m pytest tests/unit/test_pdf2markdown.py

# Run with coverage
.venv/Scripts/python.exe -m pytest --cov=all2md tests/
```

### Test Markers

Available test markers (see `pytest.ini`):

- `unit` - Fast, isolated unit tests
- `integration` - Multi-component integration tests
- `e2e` - End-to-end CLI tests
- `slow` - Slow tests (skipped by default in CI)
- `pdf`, `docx`, `html`, `pptx`, `eml` - Format-specific tests
- `table`, `formatting`, `image` - Feature-specific tests

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Place end-to-end tests in `tests/e2e/`
- Use appropriate markers on test functions
- Follow existing test patterns in the codebase
- Use NumPy-style docstrings for test documentation

## Documentation

### Building Documentation

The project uses Sphinx for documentation:

```bash
cd docs
make html
```

View the built documentation in `docs/build/html/index.html`.

### Documentation Standards

- Use reStructuredText (RST) format
- Follow NumPy-style docstrings for all modules, classes, and functions
- Include code examples in docstrings where appropriate
- Update relevant documentation when adding features
- Keep documentation in sync with code changes

### Key Documentation Files

- `docs/source/` - Sphinx documentation source files
- `README.md` - Project overview and quick start
- `CLAUDE.md` - Development guidance for AI assistants
- `CONTRIBUTING.md` - This file

## Adding New Features

### Adding a New Parser

To add support for a new document format:

1. **Create the parser module:**

   Create `src/all2md/parsers/yourformat.py`:

   ```python
   from all2md.parsers.base import BaseParser
   from all2md.ast.nodes import Document
   from all2md.options.base import BaseParserOptions
   from all2md.converter_metadata import ConverterMetadata

   class YourFormatParser(BaseParser):
       """Parser for YourFormat documents.

       Parameters
       ----------
       options : BaseParserOptions, optional
           Parser options
       """

       def parse(self, input_data) -> Document:
           """Convert YourFormat document to AST.

           Parameters
           ----------
           input_data : str, Path, or IO[bytes]
               Input document

           Returns
           -------
           Document
               AST document node
           """
           # Your parsing logic here
           pass

   # Define converter metadata
   CONVERTER_METADATA = ConverterMetadata(
       format_name="yourformat",
       extensions=[".yf", ".yourformat"],
       mime_types=["application/x-yourformat"],
       parser_class="all2md.parsers.yourformat.YourFormatParser",
       renderer_class="MarkdownRenderer",
       parser_required_packages=[("yourformat-lib", "yourformat", ">=1.0.0")],
       description="YourFormat document parser"
   )
   ```

2. **Create options class (if needed):**

   Create `src/all2md/options/yourformat.py`:

   ```python
   from dataclasses import dataclass
   from all2md.options.base import BaseParserOptions

   @dataclass
   class YourFormatOptions(BaseParserOptions):
       """Options for YourFormat parsing.

       Parameters
       ----------
       custom_option : bool, default=True
           Description of custom option
       """

       custom_option: bool = True
   ```

3. **Register the parser:**

   Add to `src/all2md/converter_registry.py` in the `_register_builtin_converters()` method:

   ```python
   from all2md.parsers.yourformat import CONVERTER_METADATA as yourformat_metadata
   self.register_converter(yourformat_metadata)
   ```

4. **Add tests:**

   Create `tests/unit/test_yourformat_ast.py` and `tests/integration/test_yourformat_integration.py`

5. **Update documentation:**

   Add format documentation to `docs/source/formats.rst`

### Adding a Transform

To add a new AST transform:

1. **Create the transform:**

   In `src/all2md/transforms/builtin.py` or a new module:

   ```python
   from all2md.ast.transforms import NodeTransformer
   from all2md.ast.nodes import SomeNode

   class YourTransform(NodeTransformer):
       """Description of what this transform does.

       Parameters
       ----------
       param : type
           Description
       """

       def __init__(self, param: str):
           self.param = param

       def visit_somenode(self, node: SomeNode) -> SomeNode:
           # Transform logic
           return modified_node
   ```

2. **Register the transform:**

   Add to the transform registry in `src/all2md/transforms/registry.py`

3. **Add tests:**

   Create tests in `tests/unit/test_your_transform.py`

4. **Update documentation:**

   Document in `docs/source/transforms.rst`

### Plugin Development

For third-party plugins, see the detailed guide in `docs/source/plugins.rst`.

## Submitting Changes

### Pull Request Process

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**

   - Follow code style guidelines (Ruff formatting)
   - Add/update tests
   - Add/update documentation
   - Use NumPy-style docstrings

3. **Run quality checks:**

   ```bash
   .venv/Scripts/python.exe -m ruff check
   .venv/Scripts/python.exe -m ruff format
   .venv/Scripts/python.exe -m mypy src/
   .venv/Scripts/python.exe -m pytest -m unit
   ```

4. **Commit your changes:**

   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

   Use clear, descriptive commit messages:
   - `Add: new feature or functionality`
   - `Fix: bug fix`
   - `Update: changes to existing functionality`
   - `Docs: documentation changes`
   - `Test: test additions or changes`

5. **Push to your fork:**

   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request:**

   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your feature branch
   - Fill out the PR template with:
     - Clear description of changes
     - Related issue numbers (if applicable)
     - Test results
     - Documentation updates

### Code Review

- Address reviewer feedback promptly
- Keep discussions constructive and professional
- Update your PR based on review comments
- Ensure CI checks pass before requesting re-review

### Commit Guidelines

- One logical change per commit
- Write clear, concise commit messages
- Reference issue numbers when applicable (`Fixes #123`)
- Keep commits atomic and focused

## Project Architecture

### Key Components

- **Parsers** (`src/all2md/parsers/`) - Convert input formats to AST
- **Renderers** (`src/all2md/renderers/`) - Convert AST to output formats
- **AST** (`src/all2md/ast/`) - Abstract Syntax Tree node definitions
- **Options** (`src/all2md/options/`) - Configuration dataclasses
- **Transforms** (`src/all2md/transforms/`) - AST transformation pipeline
- **Registry** (`src/all2md/converter_registry.py`) - Format detection and routing
- **CLI** (`src/all2md/cli/`) - Command-line interface

### Entry Point System

The converter registry uses Python entry points for plugin discovery:

```toml
[project.entry-points."all2md.converters"]
yourformat = "all2md.parsers.yourformat:CONVERTER_METADATA"
```

### Important Files

- `src/all2md/__init__.py` - Main public API
- `src/all2md/constants.py` - All magic numbers and constants
- `src/all2md/exceptions.py` - Custom exception hierarchy
- `pytest.ini` - Pytest configuration and markers
- `pyproject.toml` - Package configuration

## Getting Help

- Check existing issues on GitHub
- Read the documentation at [docs/source/](docs/source/)
- Ask questions in GitHub Discussions
- Review the architecture guide in `docs/source/architecture.rst`

## Code of Conduct

Be respectful, constructive, and collaborative. We're all here to make all2md better.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
