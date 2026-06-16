# all2md-watermark

A watermark transform plugin for [all2md](https://github.com/thomas.villani/all2md) that embeds a visual watermark into images when their bytes are available (base64 or downloaded attachments). For other images it still records watermark metadata for downstream tools.

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
# Default watermark (embed watermark into inline image data)
all2md document.pdf --attachment-mode base64 --transform watermark

# Custom watermark text while embedding into downloaded attachments
all2md document.pdf --attachment-mode download --transform watermark --watermark-text "DRAFT"
```

### Using Transform Names

After installation, the transform is automatically discovered via entry points:

```python
from all2md import to_markdown

# Use by name (requires plugin installation)
markdown = to_markdown('document.pdf', transforms=['watermark'])
```

## How It Works

The transform looks for the new `Image.metadata["source_data"]` flag exposed by all2md parsers:

- `base64`: the image bytes are embedded in the AST as a data URI
- `downloaded`: the bytes were written to disk and the image URL points to the local file

When either flag is present the plugin decodes the image with [Pillow](https://python-pillow.org), renders the watermark text as a semi-transparent overlay, and re-encodes the bytes (either back into the data URI or rewriting the downloaded file). For other images it still sets the `watermark` metadata field so downstream logic can decide how to handle them.

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/thomas-villani/all2md.git
cd all2md/examples/watermark-plugin

# Install in development mode
pip install -e .

# Install with all2md development dependencies (includes Pillow for watermarking)
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

- Issues: https://github.com/thomas-villani/all2md/issues
- all2md Documentation: https://all2md.readthedocs.io/
- all2md Transforms Guide: https://all2md.readthedocs.io/en/latest/transforms.html
