#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Custom exceptions for the all2md library.

This module defines specialized exception classes for various error conditions
that can occur during document parsing and conversion operations. These
exceptions provide more specific error information than generic built-ins.

Exception Hierarchy
-------------------
- All2MdError (base exception)

  - ValidationError (parameter/option validation)
    - InvalidOptionsError (wrong options class for parser)
    - PageRangeError (page range parsing errors)

  - FileError (file access and I/O)
    - FileNotFoundError (file doesn't exist)
    - FileAccessError (permissions, locked files)
    - MalformedFileError (corrupted/invalid file structure)

  - FormatError (unsupported/unknown formats)

  - ParsingError (input document parsing failures)
    - PasswordProtectedError (password-protected files)

  - RenderingError (output generation failures)
    - OutputWriteError (file write failures)

  - TransformError (AST transformation failures)

  - SecurityError (security violations)
    - NetworkSecurityError (SSRF, network violations)
    - ZipFileSecurityError (zip bombs, path traversal)

  - DependencyError (missing/incompatible packages)

"""

from typing import Any


class All2MdError(Exception):
    """Base exception class for all all2md-specific errors.

    This serves as the root exception class for all custom exceptions
    raised by the all2md library. Catching this will catch all
    library-specific errors.

    Parameters
    ----------
    message : str
        Human-readable description of the error
    original_error : Exception, optional
        The original exception that caused this error, if applicable

    Attributes
    ----------
    message : str
        The error message
    original_error : Exception or None
        The wrapped original exception, if any

    """

    def __init__(self, message: str, original_error: Exception | None = None):
        """Initialize the error with a message and optional original exception."""
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class ValidationError(All2MdError):
    """Exception raised for invalid input parameters or options.

    This exception covers validation errors such as:
    - Invalid parameter values
    - Invalid parameter combinations
    - Invalid option specifications

    Parameters
    ----------
    message : str
        Description of the validation error
    parameter_name : str, optional
        Name of the invalid parameter
    parameter_value : any, optional
        The invalid value that was provided
    original_error : Exception, optional
        The original exception that caused this error

    Attributes
    ----------
    parameter_name : str or None
        The name of the problematic parameter
    parameter_value : any
        The value that caused the error

    """

    def __init__(
        self,
        message: str,
        parameter_name: str | None = None,
        parameter_value: Any = None,
        original_error: Exception | None = None,
    ):
        """Initialize the validation error with parameter details."""
        super().__init__(message, original_error=original_error)
        self.parameter_name = parameter_name
        self.parameter_value = parameter_value


class InvalidOptionsError(ValidationError):
    """Exception raised when incorrect options class is provided to a parser.

    This exception is raised when a parser receives an options object of the
    wrong type. For example, passing PdfOptions to a plaintext parser.

    Parameters
    ----------
    converter_name : str
        Name of the parser that received invalid options
    expected_type : type
        The expected options class type
    received_type : type
        The actual options class type that was received
    message : str, optional
        Custom error message. If not provided, generates a helpful message
    original_error : Exception, optional
        The original exception that caused this error

    Attributes
    ----------
    converter_name : str
        Name of the parser
    expected_type : type
        Expected options class
    received_type : type
        Received options class

    """

    def __init__(
        self,
        converter_name: str,
        expected_type: type,
        received_type: type,
        message: str | None = None,
        original_error: Exception | None = None,
    ):
        """Initialize the invalid options error."""
        if message is None:
            message = (
                f"{converter_name} expected options of type '{expected_type.__name__}' "
                f"but received '{received_type.__name__}'. "
                f"Please provide the correct options type for the parser."
            )
        super().__init__(
            message, parameter_name="options", parameter_value=received_type, original_error=original_error
        )
        self.converter_name = converter_name
        self.expected_type = expected_type
        self.received_type = received_type


class PageRangeError(ValidationError):
    """Exception raised for invalid page range specifications.

    Parameters
    ----------
    message : str
        Description of the page range error
    parameter_value : any, optional
        The invalid page range value
    original_error : Exception, optional
        The original exception that caused this error

    """

    def __init__(self, message: str, parameter_value: Any = None, original_error: Exception | None = None):
        """Initialize the page range error."""
        super().__init__(
            message, parameter_name="pages", parameter_value=parameter_value, original_error=original_error
        )


class FileError(All2MdError):
    """Base exception for file access and I/O errors.

    This exception covers file-related errors such as:
    - File not found
    - Permission denied
    - File locked or in use
    - Invalid file structure

    Parameters
    ----------
    message : str
        Description of the file error
    file_path : str, optional
        Path to the problematic file
    original_error : Exception, optional
        The original exception that caused this error

    Attributes
    ----------
    file_path : str or None
        Path to the file that caused the error

    """

    def __init__(self, message: str, file_path: str | None = None, original_error: Exception | None = None):
        """Initialize the file error with path and message."""
        super().__init__(message, original_error=original_error)
        self.file_path = file_path


class FileNotFoundError(FileError):
    """Exception raised when a file cannot be found.

    Parameters
    ----------
    file_path : str
        Path to the file that was not found
    message : str, optional
        Custom error message. If not provided, uses default message
    original_error : Exception, optional
        The original exception that caused this error

    """

    def __init__(self, file_path: str, message: str | None = None, original_error: Exception | None = None):
        """Initialize the file not found error."""
        if message is None:
            message = f"File not found: {file_path}"
        super().__init__(message, file_path=file_path, original_error=original_error)


class FileAccessError(FileError):
    """Exception raised when a file cannot be accessed.

    This includes permission errors, locked files, etc.

    Parameters
    ----------
    file_path : str
        Path to the file that cannot be accessed
    message : str, optional
        Custom error message. If not provided, uses default message
    original_error : Exception, optional
        The original exception that caused this error

    """

    def __init__(self, file_path: str, message: str | None = None, original_error: Exception | None = None):
        """Initialize the file access error."""
        if message is None:
            message = f"Cannot access file: {file_path}"
        super().__init__(message, file_path=file_path, original_error=original_error)


class MalformedFileError(FileError):
    """Exception raised when a file has invalid or corrupted structure.

    Parameters
    ----------
    file_path : str, optional
        Path to the malformed file
    message : str, optional
        Description of what is malformed
    original_error : Exception, optional
        The original exception that caused this error

    """

    def __init__(self, message: str, file_path: str | None = None, original_error: Exception | None = None):
        """Initialize the malformed file error."""
        super().__init__(message, file_path=file_path, original_error=original_error)


class FormatError(All2MdError):
    """Exception raised when attempting to process an unsupported file format.

    This exception indicates that the requested file format or conversion
    operation is not supported by the current version of all2md.

    Parameters
    ----------
    message : str, optional
        Custom error message
    format_type : str, optional
        The unsupported format type (file extension or MIME type)
    supported_formats : list[str], optional
        List of supported formats for reference
    original_error : Exception, optional
        The original exception that caused this error

    Attributes
    ----------
    format_type : str or None
        The format that was not supported
    supported_formats : list[str] or None
        Available supported formats

    """

    def __init__(
        self,
        message: str | None = None,
        format_type: str | None = None,
        supported_formats: list[str] | None = None,
        original_error: Exception | None = None,
    ):
        """Initialize the format error."""
        if message is None:
            if format_type:
                message = f"Unsupported format: '{format_type}'"
                if supported_formats:
                    formats_str = ", ".join(supported_formats[:5])
                    if len(supported_formats) > 5:
                        formats_str += f" (and {len(supported_formats) - 5} more)"
                    message += f". Supported formats include: {formats_str}"
            else:
                message = "File format is not supported for conversion"

        super().__init__(message, original_error=original_error)
        self.format_type = format_type
        self.supported_formats = supported_formats


class ParsingError(All2MdError):
    """Exception raised when document parsing fails.

    This exception is raised when the parsing process encounters
    an error that prevents successful completion, such as:
    - Malformed document structure
    - Unsupported document features
    - Password-protected files

    Parameters
    ----------
    message : str
        Description of the parsing failure
    parsing_stage : str, optional
        The stage of parsing where the error occurred
    original_error : Exception, optional
        The underlying exception that caused the parsing failure

    Attributes
    ----------
    parsing_stage : str or None
        Where in the parsing process the error occurred

    """

    def __init__(self, message: str, parsing_stage: str | None = None, original_error: Exception | None = None):
        """Initialize the parsing error."""
        super().__init__(message, original_error)
        self.parsing_stage = parsing_stage


class PasswordProtectedError(ParsingError):
    """Exception raised when a file requires a password for access.

    This exception is raised specifically when attempting to process
    a password-protected document without providing the correct
    password or when the provided password is incorrect.

    Parameters
    ----------
    message : str, optional
        Custom error message. If not provided, uses default message
    filename : str, optional
        Name of the file that requires a password
    original_error : Exception, optional
        The original exception that caused this error

    Attributes
    ----------
    filename : str or None
        The name of the password-protected file, if provided

    """

    def __init__(
        self, message: str | None = None, filename: str | None = None, original_error: Exception | None = None
    ):
        """Initialize the password protected error."""
        if message is None:
            if filename:
                message = f"File '{filename}' is password-protected and requires authentication"
            else:
                message = "File is password-protected and requires a password for access"

        super().__init__(message, parsing_stage="authentication", original_error=original_error)
        self.filename = filename


class RenderingError(All2MdError):
    """Exception raised when output rendering fails.

    This exception is raised when the rendering process encounters
    an error that prevents successful completion, such as:
    - Missing required data or metadata
    - Internal processing errors
    - Unsupported AST nodes

    Parameters
    ----------
    message : str
        Description of the rendering failure
    rendering_stage : str, optional
        The stage of rendering where the error occurred
    original_error : Exception, optional
        The underlying exception that caused the rendering failure

    Attributes
    ----------
    rendering_stage : str or None
        Where in the rendering process the error occurred

    """

    def __init__(self, message: str, rendering_stage: str | None = None, original_error: Exception | None = None):
        """Initialize the rendering error."""
        super().__init__(message, original_error)
        self.rendering_stage = rendering_stage


class OutputWriteError(RenderingError):
    """Exception raised when writing output file fails.

    Parameters
    ----------
    file_path : str
        Path to the output file that failed to write
    message : str, optional
        Custom error message. If not provided, uses default message
    original_error : Exception, optional
        The original exception that caused this error

    Attributes
    ----------
    file_path : str
        Path to the file that failed to write

    """

    def __init__(self, file_path: str, message: str | None = None, original_error: Exception | None = None):
        """Initialize the output write error."""
        if message is None:
            message = f"Failed to write output file: {file_path}"
        super().__init__(message, rendering_stage="file_write", original_error=original_error)
        self.file_path = file_path


class TransformError(All2MdError):
    """Exception raised when AST transformation fails.

    This exception is raised when a transform operation encounters
    an error during AST processing.

    Parameters
    ----------
    message : str
        Description of the transform failure
    transform_name : str, optional
        Name of the transform that failed
    original_error : Exception, optional
        The underlying exception that caused the transform failure

    Attributes
    ----------
    transform_name : str or None
        Name of the transform that failed

    """

    def __init__(self, message: str, transform_name: str | None = None, original_error: Exception | None = None):
        """Initialize the transform error."""
        super().__init__(message, original_error)
        self.transform_name = transform_name


class SecurityError(All2MdError):
    """Base exception for security violations.

    This exception covers security-related errors such as:
    - SSRF (Server-Side Request Forgery) attempts
    - Path traversal attempts
    - Zip bomb attacks
    - Other security violations

    Parameters
    ----------
    message : str
        Description of the security violation
    original_error : Exception, optional
        The original exception that caused this error

    """


class NetworkSecurityError(SecurityError):
    """Exception raised when a network security violation is detected.

    This includes SSRF attempts, blocked hosts, invalid URLs, etc.

    Parameters
    ----------
    message : str
        Description of the network security violation
    original_error : Exception, optional
        The original exception that caused this error

    """


class ZipFileSecurityError(SecurityError):
    """Exception raised when a zip file security violation is detected.

    This includes zip bombs, path traversal attempts, excessive compression, etc.

    Parameters
    ----------
    message : str
        Description of the zip file security violation
    original_error : Exception, optional
        The original exception that caused this error

    """


class ArchiveSecurityError(SecurityError):
    """Exception raised when an archive file security violation is detected.

    This includes archive bombs, path traversal attempts, excessive compression, etc.
    Applies to TAR, 7Z, and RAR archives.

    Parameters
    ----------
    message : str
        Description of the archive security violation
    original_error : Exception, optional
        The original exception that caused this error

    """


class DependencyError(All2MdError):
    """Exception raised when required dependencies are not available.

    This exception is raised when attempting to use a converter that
    requires external packages that are not installed or don't meet
    version requirements.

    Parameters
    ----------
    converter_name : str
        Name of the converter requiring dependencies
    missing_packages : list[tuple[str, str]]
        List of (package_name, version_spec) tuples for missing packages
    version_mismatches : list[tuple[str, str, str]], optional
        List of (package_name, required_version, installed_version) tuples
        for packages with version mismatches
    install_command : str, optional
        Suggested pip install command to resolve the issue
    message : str, optional
        Custom error message. If not provided, generates a helpful message

    Attributes
    ----------
    converter_name : str
        The converter that has missing dependencies
    missing_packages : list[tuple[str, str]]
        Packages that need to be installed
    version_mismatches : list[tuple[str, str, str]]
        Packages with version mismatches
    install_command : str
        Command to install missing dependencies

    """

    def __init__(
        self,
        converter_name: str,
        missing_packages: list[tuple[str, str]],
        version_mismatches: list[tuple[str, str, str]] | None = None,
        install_command: str = "",
        message: str | None = None,
        original_import_error: ImportError | None = None,
    ):
        """Initialize the dependency error with package details."""
        version_mismatches = version_mismatches or []
        self.original_import_error = original_import_error
        if message is None:
            message_parts = []

            # Add missing packages section
            if missing_packages:
                pkg_list = ", ".join(f"'{name}{spec}'" if spec else f"'{name}'" for name, spec in missing_packages)
                message_parts.append(f"{converter_name.upper()} format requires the following packages: {pkg_list}")

            # Add version mismatch section
            if version_mismatches:
                mismatch_details = []
                for name, required, installed in version_mismatches:
                    mismatch_details.append(f"'{name}' (requires {required}, but {installed} is installed)")
                mismatch_str = ", ".join(mismatch_details)
                message_parts.append(f"{converter_name.upper()} format has version mismatches: {mismatch_str}")

            message = "\n".join(message_parts)

            # Add install command
            if install_command:
                message += f"\nInstall with: {install_command}"
            else:
                # Generate install command for all problematic packages
                all_packages = missing_packages + [(name, req) for name, req, _ in version_mismatches]
                if all_packages:
                    packages_str = " ".join(f'"{name}{spec}"' if spec else name for name, spec in all_packages)
                    message += f"\nInstall with: pip install --upgrade {packages_str}"

        super().__init__(message)
        self.converter_name = converter_name
        self.missing_packages = missing_packages
        self.version_mismatches = version_mismatches
        self.install_command = install_command
