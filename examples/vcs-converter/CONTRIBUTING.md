# Contributing to VCS Converter

Thank you for your interest in improving the VCS Document Converter!

## Development Setup

1. Install all2md in development mode:
```bash
pip install -e ../../  # Assumes you're in examples/vcs-converter
```

2. Install development dependencies:
```bash
pip install pytest mypy ruff black
```

## Making Changes

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all functions
- Use NumPy-style docstrings
- Format with `ruff format`
- Lint with `ruff check`
- Type check with `mypy`

### Testing Your Changes

1. Run the demo script:
```bash
python demo.py
```

2. Test manual conversion:
```bash
# Create a test document
python demo.py  # Creates samples

# Test single file conversion
python vcs_converter.py to-md /path/to/test.docx

# Test batch conversion
python vcs_converter.py batch --root /path/to/test-repo

# Test reverse conversion
python vcs_converter.py to-binary .vcs-docs/test.vcs.md
```

3. Test the pre-commit hook:
```bash
# In a test git repository
python install_hook.py

# Make a change to a binary doc
# Try committing
git add test.docx
git commit -m "Test commit"

# Verify markdown was generated
ls .vcs-docs/
```

## Ideas for Improvements

### High Priority

1. **Git LFS Integration**
   - Automatically configure LFS for binary files
   - Track only markdown in git, binaries in LFS

2. **Better Diff Output**
   - Semantic line breaks (one sentence per line)
   - Normalize whitespace
   - Better table formatting

3. **Conflict Resolution Helper**
   - Tool to help resolve markdown merge conflicts
   - Automatic binary regeneration after merge

4. **Performance Improvements**
   - Parallel processing for batch conversion
   - Caching of unchanged documents
   - Incremental conversion

### Medium Priority

5. **Additional Format Support**
   - ODT (OpenDocument Text)
   - Pages (Apple)
   - Google Docs (via export)

6. **Enhanced Metadata**
   - Track document statistics (word count, etc.)
   - Store style information
   - Preserve comments and tracked changes

7. **CI/CD Integration**
   - GitHub Actions workflow template
   - GitLab CI template
   - Pre-commit.com hook

8. **GUI Tool**
   - Simple GUI for non-technical users
   - Drag-and-drop conversion
   - Visual diff viewer

### Low Priority

9. **Advanced Features**
   - Support for document templates
   - Bulk operations on repositories
   - Integration with document management systems

10. **Documentation**
    - Video tutorial
    - More workflow examples
    - Troubleshooting guide expansion

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Questions?

Open an issue in the main all2md repository with the tag `example:vcs-converter`.
