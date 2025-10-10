# Exit Codes Documentation

The `all2md` CLI now provides meaningful exit codes to allow scripts and automation to properly handle different types of failures.

## Exit Codes

| Code | Constant | Description | Examples |
|------|----------|-------------|----------|
| 0 | `EXIT_SUCCESS` | Successful conversion | File converted successfully |
| 1 | `EXIT_ERROR` | General/unexpected errors | Unexpected exceptions, system errors |
| 2 | `EXIT_DEPENDENCY_ERROR` | Missing dependency | Required library not installed, converter unavailable |
| 3 | `EXIT_VALIDATION_ERROR` | Validation errors | Invalid arguments, bad parameter values, page range errors |
| 4 | `EXIT_FILE_ERROR` | File access errors | File not found, permission denied, file locked, malformed files |
| 5 | `EXIT_FORMAT_ERROR` | Format detection errors | Unknown format, unsupported file type |
| 6 | `EXIT_PARSING_ERROR` | Document parsing errors | Failed to parse input document, corrupted file structure |
| 7 | `EXIT_RENDERING_ERROR` | Output generation errors | Failed to generate output, write errors |
| 8 | `EXIT_SECURITY_ERROR` | Security violations | SSRF detected, zip bombs, path traversal attempts |
| 9 | `EXIT_PASSWORD_ERROR` | Password-protected files | Document requires password, decryption failed |

## Usage Examples

### Shell Scripts

```bash
#!/bin/bash

# Convert a file and handle errors
all2md document.pdf -o output.md

case $? in
    0)
        echo "Success!"
        ;;
    1)
        echo "Unexpected error occurred"
        exit 1
        ;;
    2)
        echo "Missing dependencies - install with: pip install all2md[full]"
        exit 2
        ;;
    3)
        echo "Validation error - check command-line arguments"
        exit 3
        ;;
    4)
        echo "File error - check file path and permissions"
        exit 4
        ;;
    5)
        echo "Format error - unsupported or unknown file format"
        exit 5
        ;;
    6)
        echo "Parsing error - file may be corrupted"
        exit 6
        ;;
    7)
        echo "Rendering error - failed to generate output"
        exit 7
        ;;
    8)
        echo "Security error - operation blocked by security policy"
        exit 8
        ;;
    9)
        echo "Password required - file is password-protected"
        exit 9
        ;;
esac
```

### Batch Processing

```bash
#!/bin/bash

# Process multiple files and track failures by type
SUCCESS=0
GENERAL_ERRORS=0
DEPENDENCY_ERRORS=0
VALIDATION_ERRORS=0
FILE_ERRORS=0
FORMAT_ERRORS=0
PARSING_ERRORS=0
RENDERING_ERRORS=0
SECURITY_ERRORS=0
PASSWORD_ERRORS=0

for file in *.pdf; do
    all2md "$file" -o "${file%.pdf}.md"

    case $? in
        0) ((SUCCESS++)) ;;
        1) ((GENERAL_ERRORS++)) ;;
        2) ((DEPENDENCY_ERRORS++)) ;;
        3) ((VALIDATION_ERRORS++)) ;;
        4) ((FILE_ERRORS++)) ;;
        5) ((FORMAT_ERRORS++)) ;;
        6) ((PARSING_ERRORS++)) ;;
        7) ((RENDERING_ERRORS++)) ;;
        8) ((SECURITY_ERRORS++)) ;;
        9) ((PASSWORD_ERRORS++)) ;;
    esac
done

echo "Summary:"
echo "  Successful: $SUCCESS"
echo "  General errors: $GENERAL_ERRORS"
echo "  Dependency errors: $DEPENDENCY_ERRORS"
echo "  Validation errors: $VALIDATION_ERRORS"
echo "  File errors: $FILE_ERRORS"
echo "  Format errors: $FORMAT_ERRORS"
echo "  Parsing errors: $PARSING_ERRORS"
echo "  Rendering errors: $RENDERING_ERRORS"
echo "  Security errors: $SECURITY_ERRORS"
echo "  Password errors: $PASSWORD_ERRORS"
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Convert documentation
  run: all2md docs/*.md -o output/
  id: convert
  continue-on-error: true

- name: Handle conversion failure
  if: failure()
  run: |
    if [ ${{ steps.convert.outcome }} -eq 2 ]; then
      echo "Missing dependencies - installing..."
      pip install all2md[full]
      all2md docs/*.md -o output/
    elif [ ${{ steps.convert.outcome }} -eq 3 ]; then
      echo "Input error - check file paths"
      exit 1
    else
      echo "Conversion failed"
      exit 1
    fi
```

## Exception Mapping

The CLI maps exceptions to exit codes as follows:

- **`PasswordProtectedError`** → Exit code 9 (highest priority check)
  - Document requires password
  - Decryption failed

- **`SecurityError`** (includes `NetworkSecurityError`, `ZipFileSecurityError`) → Exit code 8
  - SSRF attempts blocked
  - Zip bomb detected
  - Path traversal attempts

- **`RenderingError`** (includes `OutputWriteError`) → Exit code 7
  - Failed to generate output
  - Write permission errors

- **`ParsingError`** → Exit code 6
  - Failed to parse input document
  - Corrupted file structure

- **`FormatError`** → Exit code 5
  - Unknown file format
  - Unsupported file type

- **`FileError`** (includes `FileNotFoundError`, `FileAccessError`, `MalformedFileError`) → Exit code 4
  - File not found
  - Permission denied
  - File locked or inaccessible
  - Corrupted or malformed file

- **`ValidationError`** (includes `PageRangeError`) → Exit code 3
  - Invalid command-line arguments
  - Bad parameter values
  - Page range parsing errors

- **`DependencyError`** and **`ImportError`** → Exit code 2
  - Missing required libraries
  - Unavailable converters

- **`TransformError`** → Exit code 1
  - AST transformation failures

- **Generic/unexpected exceptions** → Exit code 1
  - Unexpected errors
  - System errors

## Multi-File Processing

When processing multiple files:

- The CLI returns the **highest exit code** encountered
- With `--skip-errors`, processing continues but still returns the highest error code
- Example: If 5 files succeed (0), 2 have conversion errors (1), and 1 has an input error (3), the final exit code is 3

## Implementation Details

### Constants

Defined in `src/all2md/constants.py`:

```python
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_DEPENDENCY_ERROR = 2
EXIT_VALIDATION_ERROR = 3
EXIT_FILE_ERROR = 4
EXIT_FORMAT_ERROR = 5
EXIT_PARSING_ERROR = 6
EXIT_RENDERING_ERROR = 7
EXIT_SECURITY_ERROR = 8
EXIT_PASSWORD_ERROR = 9

def get_exit_code_for_exception(exception: Exception) -> int:
    """Map an exception to an appropriate CLI exit code.

    Checks exception types in order of specificity, returning the
    most appropriate exit code for the given exception.
    """
    # Maps exception types to exit codes (see constants.py for implementation)
```

## Testing

Comprehensive tests for exit codes are in `tests/e2e/test_exit_codes.py`:

```bash
# Run exit code tests
pytest tests/e2e/test_exit_codes.py -v
```

Tests cover:
- Successful conversions (exit code 0)
- All exception types and their corresponding exit codes (1-9)
- Multi-file processing with mixed results
- Exception mapping correctness
- Edge cases and unexpected exceptions

## Exception Hierarchy

All `all2md` exceptions inherit from `All2MdError` base class:

```
All2MdError (base)
├── ValidationError
│   └── PageRangeError
├── FileError
│   ├── FileNotFoundError
│   ├── FileAccessError
│   └── MalformedFileError
├── FormatError
├── ParsingError
│   └── PasswordProtectedError
├── RenderingError
│   └── OutputWriteError
├── TransformError
├── SecurityError
│   ├── NetworkSecurityError
│   └── ZipFileSecurityError
└── DependencyError
```

## Notes

- Exit codes provide granular error categorization for automation and scripting
- The CLI returns the **highest exit code** when processing multiple files
- Scripts checking for `$? -ne 0` (any error) will continue to work correctly
- Exit code 0 still means success; non-zero codes indicate failure
- Password-protected files (exit code 9) are checked first as they are the most specific error type
