# Contributing to all2md-watermark

Thank you for your interest in contributing to all2md-watermark!

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/thomas-villani/all2md.git
   cd all2md/examples/watermark-plugin
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

## Making Changes

1. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Add tests for your changes in `tests/`

4. Run the test suite:
   ```bash
   pytest
   ```

5. Run type checking:
   ```bash
   mypy src/
   ```

6. Run linting:
   ```bash
   ruff check src/
   ruff format src/
   ```

## Submitting Changes

1. Commit your changes:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

2. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

3. Open a Pull Request on GitHub

## Code Style

- Follow PEP 8 style guidelines
- Use NumPy-style docstrings
- Keep line length to 120 characters
- Add type hints to all functions

## Testing

- Write tests for all new functionality
- Ensure all tests pass before submitting PR
- Aim for high test coverage

## Documentation

- Update README.md if adding new features
- Add docstrings to all public functions and classes
- Update examples if the API changes

## Questions?

Feel free to open an issue for any questions or concerns!
