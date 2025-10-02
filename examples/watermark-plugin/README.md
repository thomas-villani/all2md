# all2md-watermark

A watermark transform plugin for [all2md](https://github.com/thomas.villani/all2md) that adds watermark metadata to all images in a document.

## Installation

```bash
pip install all2md-watermark
```

## Usage

### From Python

```python
from all2md import to_markdown
from all2md_watermark import WatermarkTransform

# Use default watermark ("CONFIDENTIAL")
transform = WatermarkTransform()
markdown = to_markdown('document.pdf', transforms=[transform])

# Custom watermark text
transform = WatermarkTransform(text="DRAFT")
markdown = to_markdown('document.pdf', transforms=[transform])
```

### From Command Line

```bash
# Default watermark
all2md document.pdf --transform watermark

# Custom watermark text
all2md document.pdf --transform watermark --watermark-text "DRAFT"
```

### Using Transform Names

After installation, the transform is automatically discovered via entry points:

```python
from all2md import to_markdown

# Use by name (requires plugin installation)
markdown = to_markdown('document.pdf', transforms=['watermark'])
```

## How It Works

The watermark transform adds a `watermark` field to the metadata of each `Image` node in the document's AST. This metadata can be used by downstream processing tools to:

- Add visible watermarks to images
- Track document confidentiality
- Mark draft or final versions
- Add custom labels to images

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/all2md-watermark.git
cd all2md-watermark

# Install in development mode
pip install -e .

# Install with all2md development dependencies
pip install -e ".[dev]"
```

### Testing

```bash
# Run tests
pytest

# Run type checking
mypy src/

# Run linting
ruff check src/
```

## Plugin Architecture

This plugin demonstrates the all2md transform plugin architecture:

1. **Transform Class** (`WatermarkTransform`): Inherits from `NodeTransformer` and implements the visitor pattern
2. **Transform Metadata** (`METADATA`): Describes the transform with parameters, CLI flags, and other metadata
3. **Entry Point**: Registered in `pyproject.toml` under `[project.entry-points."all2md.transforms"]`

### File Structure

```
all2md-watermark/
├── pyproject.toml          # Package configuration with entry point
├── README.md               # This file
└── src/
    └── all2md_watermark/
        ├── __init__.py     # Exports METADATA for discovery
        └── transforms.py   # WatermarkTransform implementation
```

## Creating Your Own Plugin

Use this plugin as a template for creating your own all2md transforms:

1. Copy this directory structure
2. Rename `all2md_watermark` to your plugin name
3. Update `pyproject.toml` with your package details
4. Implement your transform in `transforms.py`
5. Update `METADATA` in `__init__.py`
6. Update the entry point in `pyproject.toml`

See the [all2md Transforms Guide](https://all2md.readthedocs.io/en/latest/transforms.html) for more details.

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

- Issues: https://github.com/yourusername/all2md-watermark/issues
- all2md Documentation: https://all2md.readthedocs.io/
- all2md Transforms Guide: https://all2md.readthedocs.io/en/latest/transforms.html
