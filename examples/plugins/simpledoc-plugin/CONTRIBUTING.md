# Contributing to SimpleDoc Plugin

Thank you for your interest in contributing! This plugin serves as an educational example for the all2md library.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/thomas-villani/all2md.git
   cd all2md/examples/simpledoc-plugin
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install in development mode:
   ```bash
   pip install -e .
   pip install pytest
   ```

## Running Tests

Run all tests:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=all2md_simpledoc tests/
```

## Code Style

This plugin follows the same style as the main all2md project:
- Use NumPy style docstrings
- Follow PEP 8 conventions
- Type hints for all function signatures

## Making Changes

1. Create a new branch for your changes
2. Make your changes with appropriate tests
3. Ensure all tests pass
4. Submit a pull request

## Plugin Architecture

This plugin demonstrates:
- **Parser**: Converting SimpleDoc text to AST (parser.py)
- **Renderer**: Converting AST to SimpleDoc text (renderer.py)
- **Options**: Configuration classes for parser and renderer (options.py)
- **Registration**: Entry points and metadata (__init__.py)
- **Testing**: Comprehensive test coverage (tests/)

## Questions?

Open an issue on GitHub or refer to the [all2md plugin documentation](https://github.com/thomas-villani/all2md).
