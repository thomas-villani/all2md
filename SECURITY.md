# Security Policy

## Reporting a Vulnerability

We take the security of all2md seriously. If you believe you've found a security vulnerability in all2md, please report it to us as described below.

### Reporting Process

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to:
- **Email**: thomas.villani@njii.com
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
- **Asset Size Limits**: Configurable caps on embedded and fetched assets
  (`max_asset_size_bytes`) to prevent resource exhaustion

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

- **HTML Sanitization**: Optional stripping of dangerous elements and attributes
  (`strip_dangerous_elements`), using bleach when the `sanitizer` extra is installed
- **JavaScript Removal**: Strips JavaScript from HTML documents
- **Attribute Sanitization**: Removes dangerous HTML attributes
- **Sandboxed Rendering**: HTML rendering uses security-conscious defaults

### 5. Dependency Security

- **Minimal Core Dependencies**: Core library has three runtime dependencies
  (tomli-w, pyyaml, platformdirs), plus tomli and typing_extensions as
  backports on Python 3.10
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
from all2md.utils.security import resolve_file_url_to_path, validate_local_file_access

# Decide explicitly whether a user-supplied file:// URL may be read
if not validate_local_file_access(
    user_provided_url,
    allow_local_files=True,
    local_file_allowlist=["/srv/uploads"],
):
    raise PermissionError(user_provided_url)

markdown = to_markdown(resolve_file_url_to_path(user_provided_url))
```

When you write attachments out, validate the destination the same way:

```python
from all2md.utils.security import validate_safe_output_directory

# Raises SecurityError on ../ traversal or a sensitive system directory
output_dir = validate_safe_output_directory("./attachments")
```

### 2. Disable Remote Fetching in Production

```python
from all2md import to_markdown, HtmlOptions
from all2md.options.common import NetworkFetchOptions

# Remote fetching is already off by default; this states it explicitly
network_opts = NetworkFetchOptions(
    allow_remote_fetch=False,  # Disable all remote fetching
)
html_opts = HtmlOptions(network=network_opts)
markdown = to_markdown('document.html', parser_options=html_opts)
```

### 3. Enable HTML Sanitization

```python
from all2md import to_markdown, HtmlOptions

# Enable HTML sanitization for untrusted HTML content
opts = HtmlOptions(
    strip_dangerous_elements=True,  # Remove script, style, event handlers
    strip_comments=True,            # Drop comments (on by default)
)
markdown = to_markdown('untrusted.html', parser_options=opts)
```

Add `strip_framework_attributes=True` when the converted output will be
re-rendered in a browser running Alpine/Vue/Angular/HTMX. See
[HTML sanitization](docs/source/security.rst) for the full element and
attribute lists.

### 4. Cap Asset Sizes

all2md does not impose a limit on the size of the document you hand it — check
that yourself before calling `to_markdown`. What it does cap is the size of any
asset it extracts or fetches out of that document:

```python
from all2md import to_markdown, HtmlOptions

# Refuse to pull in any single asset larger than 10 MB (default: 50 MB)
opts = HtmlOptions(max_asset_size_bytes=10 * 1024 * 1024)
markdown = to_markdown('document.html', parser_options=opts)
```

### 5. Validate Archive Contents

Zip-bomb and path-traversal checks run automatically on every ZIP-backed
format (`.zip`, `.docx`, `.pptx`, `.xlsx`, `.epub`). To tighten the thresholds,
or to screen an archive before handing it over, call the validator directly:

```python
from all2md import to_markdown
from all2md.options.archive import ArchiveOptions
from all2md.utils.security import validate_zip_archive

# Raises ZipFileSecurityError if the archive looks like a bomb
validate_zip_archive(
    'archive.zip',
    max_compression_ratio=50.0,          # default 100.0
    max_uncompressed_size=500 * 1024 * 1024,  # default 1 GB
    max_entries=1000,                    # default 10000
)

# Limit how far nested archives are followed
opts = ArchiveOptions(max_depth=2)
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
- Use `strip_dangerous_elements=True` for untrusted content
- External resources (images, CSS) are not fetched by default

### 4. Archive Formats

- Nested archives can cause resource exhaustion
- ZIP bombs are detected; use `validate_zip_archive` to tighten the limits
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
- Email thomas.villani@njii.com with "[all2md Security]" in the subject

For general issues and feature requests:
- [GitHub Issues](https://github.com/thomas-villani/all2md/issues)

Thank you for helping keep all2md and its users safe!
