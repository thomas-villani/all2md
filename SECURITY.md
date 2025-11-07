# Security Policy

## Reporting a Vulnerability

We take the security of all2md seriously. If you believe you've found a security vulnerability in all2md, please report it to us as described below.

### Reporting Process

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to:
- **Email**: thomas.villani@gmail.com
- **Subject**: [all2md Security] Brief description of the issue

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

### What to Include

Please include the following information in your report:

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Our Commitment

- We will acknowledge receipt of your vulnerability report within 48 hours
- We will provide a more detailed response within 5 business days indicating the next steps in handling your report
- We will keep you informed of the progress towards a fix and full announcement
- We may ask for additional information or guidance

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Security Features

all2md implements several security measures to protect against common vulnerabilities:

### 1. Input Validation

- **File Format Validation**: Multi-stage format detection (extension, MIME type, magic bytes)
- **Path Traversal Protection**: Validates file paths to prevent directory traversal attacks
- **File Size Limits**: Configurable limits to prevent resource exhaustion

### 2. Network Security

- **SSRF Protection**: Server-Side Request Forgery protection when fetching remote resources
- **URL Validation**: Strict URL validation and sanitization
- **Network Access Control**: Remote fetching disabled by default, must be explicitly enabled
- **Allowlist/Blocklist Support**: Fine-grained control over allowed domains and protocols

### 3. Archive Security

- **ZIP Bomb Protection**: Detects and prevents decompression bombs
- **Path Traversal Prevention**: Validates extracted file paths from archives
- **Size Ratio Validation**: Checks compression ratios to detect suspicious archives
- **Nested Archive Limits**: Prevents resource exhaustion from deeply nested archives

### 4. HTML/Document Security

- **HTML Sanitization**: Optional HTML content sanitization using bleach
- **JavaScript Removal**: Strips JavaScript from HTML documents
- **Attribute Sanitization**: Removes dangerous HTML attributes
- **Sandboxed Rendering**: HTML rendering uses security-conscious defaults

### 5. Dependency Security

- **Minimal Core Dependencies**: Core library has only 2 dependencies (tomli-w, pyyaml)
- **Optional Dependencies**: Install only what you need, reducing attack surface
- **Regular Updates**: Dependencies are regularly updated via Dependabot
- **Security Scanning**: Automated dependency vulnerability scanning

### 6. File System Security

- **Temporary File Handling**: Secure temporary file creation and cleanup
- **Permission Validation**: Checks file permissions before operations
- **Symlink Detection**: Optionally prevents following symbolic links
- **No Arbitrary Code Execution**: Does not execute code from parsed documents

## Security Best Practices for Users

When using all2md, follow these best practices:

### 1. Input Validation

```python
from all2md import to_markdown
from all2md.utils.security import validate_file_path

# Always validate file paths before processing
file_path = validate_file_path(user_provided_path)
markdown = to_markdown(file_path)
```

### 2. Disable Remote Fetching in Production

```python
from all2md import to_markdown, HtmlOptions
from all2md.options.common import NetworkFetchOptions

# Disable remote fetching for untrusted input
network_opts = NetworkFetchOptions(
    enabled=False,  # Disable all remote fetching
)
html_opts = HtmlOptions(network_fetch=network_opts)
markdown = to_markdown('document.html', parser_options=html_opts)
```

### 3. Enable HTML Sanitization

```python
from all2md import to_markdown, HtmlOptions

# Enable HTML sanitization for untrusted HTML content
opts = HtmlOptions(sanitize_html=True)
markdown = to_markdown('untrusted.html', parser_options=opts)
```

### 4. Set File Size Limits

```python
from all2md import to_markdown
from all2md.options.base import BaseParserOptions

# Set reasonable file size limits
opts = BaseParserOptions(max_file_size=10 * 1024 * 1024)  # 10 MB
markdown = to_markdown('document.pdf', parser_options=opts)
```

### 5. Validate Archive Contents

```python
from all2md import to_markdown
from all2md.options.archive import ArchiveOptions

# Enable security checks for archives
opts = ArchiveOptions(
    check_zip_bomb=True,
    max_archive_size=100 * 1024 * 1024,  # 100 MB
    max_extracted_size=500 * 1024 * 1024,  # 500 MB
)
markdown = to_markdown('archive.zip', parser_options=opts)
```

## Known Security Considerations

### 1. PDF Processing

- PDF parsing uses PyMuPDF which has native components
- Consider isolating PDF processing in containers or VMs for high-security environments
- Enable OCR only when necessary as it increases attack surface

### 2. Microsoft Office Documents

- DOCX, PPTX, XLSX are XML-based ZIP archives
- May contain embedded macros (not executed by all2md)
- External references in documents are not fetched by default

### 3. HTML Documents

- HTML can contain embedded scripts and external resources
- Use `sanitize_html=True` for untrusted content
- External resources (images, CSS) are not fetched by default

### 4. Archive Formats

- Nested archives can cause resource exhaustion
- ZIP bombs are detected but configure appropriate limits
- Always validate extracted file paths

### 5. MCP Server

- MCP server includes file access controls and allowlists
- Network fetching can be disabled entirely
- Run with minimal privileges in production
- See [MCP Security Documentation](docs/source/mcp.rst) for details

## Security Updates

Security updates will be released as soon as possible after a vulnerability is confirmed:

1. Critical vulnerabilities: Patch within 24-48 hours
2. High severity: Patch within 1 week
3. Medium severity: Patch in next minor release
4. Low severity: Patch in next release

Security advisories will be published:
- GitHub Security Advisories
- Release notes in CHANGELOG.md
- Package metadata on PyPI

## Security Research

We encourage security researchers to review all2md. If you're conducting security research:

1. Test against the latest version
2. Use isolated test environments
3. Do not test on production systems without permission
4. Report findings responsibly as described above

## Additional Resources

- [Threat Model Documentation](docs/source/threat_model.rst)
- [Security Best Practices](docs/source/security.rst)
- [MCP Security Guide](docs/source/mcp.rst)
- [GitHub Security Advisories](https://github.com/thomas-villani/all2md/security/advisories)

## Contact

For security-related questions that are not vulnerabilities:
- Open a [GitHub Discussion](https://github.com/thomas-villani/all2md/discussions) with the "Security" label
- Email thomas.villani@gmail.com with "[all2md Security]" in the subject

For general issues and feature requests:
- [GitHub Issues](https://github.com/thomas-villani/all2md/issues)

Thank you for helping keep all2md and its users safe!
