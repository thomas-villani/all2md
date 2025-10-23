# Changelog

All notable changes to the VCS Document Converter example will be documented in this file.

## [1.0.0] - 2025-10-22

### Added
- Initial release of VCS Document Converter
- Convert binary documents (DOCX, PPTX, PDF) to markdown
- Bidirectional conversion (markdown back to binary)
- Pre-commit hook for automatic conversion
- Batch processing for entire repositories
- Metadata preservation in JSON format
- Configuration file support
- Hook installation script
- Comprehensive documentation and examples
- Demo script showcasing all features

### Features
- **Conversion**:
  - DOCX to markdown and back
  - PDF to markdown and back
  - PPTX to markdown (rendering back not yet implemented)
  - Preserves formatting metadata

- **Git Integration**:
  - Pre-commit hook (Bash)
  - Hook installer (Python)
  - Configurable behavior
  - Automatic staging of generated files

- **Batch Processing**:
  - Scan repository for binary documents
  - Convert all documents at once
  - Skip unchanged documents
  - Force reconversion option

- **Documentation**:
  - Comprehensive README with multiple workflows
  - Quick start guide
  - Contributing guidelines
  - Example demo script

### Known Limitations
- PPTX to markdown conversion is one-way only (reconstruction not implemented)
- Comment and CommentInline AST nodes not serialized (requires update to all2md core)
- Complex formatting may not round-trip perfectly
- Large files may be slow to convert

### Future Enhancements
- Git LFS integration
- Semantic line breaks for better diffs
- Conflict resolution helper
- Parallel batch processing
- GUI tool
- CI/CD workflow templates
