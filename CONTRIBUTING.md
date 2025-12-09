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

- Python 3.10 or higher
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
   pip install -e ".[all,dev]"
   ```

## Code Quality

We use several tools to maintain code quality and consistency across the codebase.

### Code Formatting with Black

Black is "the uncompromising Python code formatter" that ensures consistent code style across the project.

**Configuration:**
- Line length: 120 characters (configured in `pyproject.toml`)
- Target: Python 3.10+
- String normalization: enabled

**Running Black manually:**

```bash
# Format all code (Windows)
.venv/Scripts/python.exe -m black src/ tests/

# Check formatting without making changes
.venv/Scripts/python.exe -m black --check src/ tests/

# Format specific file
.venv/Scripts/python.exe -m black src/all2md/api.py

# macOS/Linux
python -m black src/ tests/
```

**Why Black?**
- Zero configuration needed (opinionated by design)
- Deterministic formatting (same code always formats the same way)
- Fast formatting
- Reduces code review time by eliminating style debates

### Linting with Ruff

Ruff is an extremely fast Python linter that replaces multiple tools (Flake8, isort, pyupgrade, etc.).

**Enabled rule sets:**
- `D` - pydocstyle (docstring conventions)
- `E` - pycodestyle errors
- `F` - pyflakes
- `W` - pycodestyle warnings
- `C` - complexity checks (max complexity: 25)
- `B` - flake8-bugbear (common bugs)
- `I` - import sorting

**Running Ruff:**

```bash
# Run linting checks (Windows)
.venv/Scripts/python.exe -m ruff check

# Auto-fix issues where possible
.venv/Scripts/python.exe -m ruff check --fix

# Check specific file
.venv/Scripts/python.exe -m ruff check src/all2md/api.py

# Show all violations (not just first occurrence)
.venv/Scripts/python.exe -m ruff check --output-format=full

# macOS/Linux
python -m ruff check
```

**Ruff can also format code:**

```bash
# Format code (alternative to Black, but we use Black primarily)
.venv/Scripts/python.exe -m ruff format

# Check formatting without changes
.venv/Scripts/python.exe -m ruff format --check
```

### Type Checking with mypy

mypy performs static type checking to catch type-related errors before runtime.

**Configuration:**
- Strict optional checking enabled
- Disallow untyped definitions
- Custom type stubs in `stubs/` directory
- Python 3.10+ compatibility

**Running mypy:**

```bash
# Type check all source code (Windows)
.venv/Scripts/python.exe -m mypy src/

# Check specific module
.venv/Scripts/python.exe -m mypy src/all2md/parsers/

# Show error codes
.venv/Scripts/python.exe -m mypy src/ --show-error-codes

# macOS/Linux
python -m mypy src/
```

**Type hints requirements:**
- All function signatures must have type hints
- Use `from __future__ import annotations` for forward references
- Follow NumPy-style docstrings with type information

### Pre-commit Hooks

Pre-commit hooks automatically run code quality checks before each commit, catching issues early.

**Installation:**

```bash
# Install pre-commit hooks (one-time setup)
# Windows
.venv/Scripts/python.exe -m pip install pre-commit
pre-commit install

# macOS/Linux
pip install pre-commit
pre-commit install
```

**Configured hooks:**

The project uses the following pre-commit hooks (see `.pre-commit-config.yaml`):

1. **Custom Format Sync Hooks** (Local)
   - `format-sync-update`: Auto-updates DocumentFormat Literal in constants.py
   - `format-sync-validate`: Validates DocumentFormat synchronization

2. **Black** (v25.9.0)
   - Automatically formats Python code on commit
   - Configuration: 120 char line length, Python 3.10+

3. **Ruff** (v0.14.2)
   - Lints code and auto-fixes common issues
   - Runs with `--fix` flag to automatically correct problems

4. **Pre-commit-hooks** (v6.0.0) - Basic file checks:
   - `trailing-whitespace`: Removes trailing whitespace
   - `end-of-file-fixer`: Ensures files end with newline
   - `check-yaml`: Validates YAML syntax
   - `check-json`: Validates JSON syntax
   - `check-toml`: Validates TOML syntax
   - `check-added-large-files`: Prevents committing files >1MB
   - `mixed-line-ending`: Ensures consistent line endings

**Using pre-commit:**

```bash
# Hooks run automatically on git commit
git commit -m "Your message"

# Run hooks manually on all files
pre-commit run --all-files

# Run hooks on staged files only
pre-commit run

# Run specific hook
pre-commit run black --all-files
pre-commit run ruff --all-files

# Update hook versions
pre-commit autoupdate

# Temporarily skip hooks (use sparingly!)
git commit --no-verify -m "Emergency fix"
```

**What happens when hooks fail?**
- The commit is aborted
- Auto-fixable issues (formatting, trailing whitespace) are fixed automatically
- Re-stage the fixed files and commit again:
  ```bash
  git add .
  git commit -m "Your message"
  ```

**Benefits of pre-commit hooks:**
- Catches issues before they reach code review
- Ensures consistent code style across all contributors
- Reduces back-and-forth in pull requests
- Automatically fixes many common issues

### All Quality Checks

Before submitting a PR, run all checks manually to ensure everything passes:

```bash
# 1. Format code with Black
.venv/Scripts/python.exe -m black src/ tests/

# 2. Run linting
.venv/Scripts/python.exe -m ruff check

# 3. Check formatting
.venv/Scripts/python.exe -m black --check src/ tests/

# 4. Run type checking
.venv/Scripts/python.exe -m mypy src/

# 5. Run tests
.venv/Scripts/python.exe -m pytest -m unit

# Or run pre-commit on all files
pre-commit run --all-files
```

**Quick command to run everything:**

```bash
# Windows
.venv/Scripts/python.exe -m black src/ tests/ && .venv/Scripts/python.exe -m ruff check && .venv/Scripts/python.exe -m mypy src/ && .venv/Scripts/python.exe -m pytest -m unit

# macOS/Linux
python -m black src/ tests/ && python -m ruff check && python -m mypy src/ && python -m pytest -m unit
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

   - Follow code style guidelines (Black + Ruff)
   - Add/update tests
   - Add/update documentation
   - Use NumPy-style docstrings
   - Install pre-commit hooks (recommended):
     ```bash
     pre-commit install
     ```

3. **Run quality checks:**

   ```bash
   # Format with Black
   .venv/Scripts/python.exe -m black src/ tests/

   # Lint with Ruff
   .venv/Scripts/python.exe -m ruff check

   # Type check
   .venv/Scripts/python.exe -m mypy src/

   # Run tests
   .venv/Scripts/python.exe -m pytest -m unit

   # Or use pre-commit to run all checks
   pre-commit run --all-files
   ```

4. **Commit your changes:**

   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

   **Note:** If you installed pre-commit hooks, they will run automatically on commit and may modify files (formatting, trailing whitespace, etc.). If this happens, simply stage the changes and commit again.

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
