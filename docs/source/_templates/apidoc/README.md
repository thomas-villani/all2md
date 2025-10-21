# Sphinx-apidoc Custom Templates

This directory contains custom Jinja2 templates used by `sphinx-apidoc` when generating API documentation.

## Templates

- **package.rst.jinja**: Template for package-level RST files (packages with submodules)
  - Automatically adds `:imported-members: False` to prevent duplicate documentation of re-exported classes

- **module.rst.jinja**: Template for individual module RST files

## Usage

When running sphinx-apidoc, specify this template directory:

```bash
sphinx-apidoc -o docs/source/api src/all2md --templatedir=docs/source/_templates/apidoc
```

Or use the `-t` short option:

```bash
sphinx-apidoc -o docs/source/api src/all2md -t docs/source/_templates/apidoc
```

## Customizations Made

The `package.rst.jinja` template adds `:imported-members: False` to the automodule directive for package files. This prevents Sphinx from documenting classes/functions that are imported into `__init__.py` files, which eliminates duplicate object description warnings.

**Note**: These templates are designed for Sphinx 8.x which uses Jinja2 template format (`.rst.jinja` extension). Older versions of Sphinx used `.rst_t` extension.

For example, `MCPConfig` is defined in `all2md.mcp.config` but imported into `all2md.mcp.__init__.py`. Without `:imported-members: False`, it would be documented twice, causing warnings.

## Automatic Integration

If you use a documentation build script or Makefile, add the `-t` flag to your sphinx-apidoc command to automatically use these templates every time you regenerate the API docs.

## Filename Conflict Resolution

The project includes a post-processing script (`docs/fix_rst_filenames.py`) that runs after `sphinx-apidoc` to fix a naming conflict:

- Python modules named `rst.py` (reStructuredText parsers/renderers) generate files like `all2md.options.rst.rst`
- The double `.rst.rst` extension causes Sphinx warnings about missing toctree references
- The script automatically renames these to `.restructuredtext.rst` and updates all toctree references

This is integrated into `make.bat apidoc` and runs automatically.
