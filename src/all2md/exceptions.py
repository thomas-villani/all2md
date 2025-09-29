#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Custom exceptions for the all2md library.

This module defines specialized exception classes for various error conditions
that can occur during document parsing and conversion operations. These
exceptions provide more specific error information than generic built-ins.

Exception Hierarchy
-------------------
- All2MdError (base exception)
  - PasswordProtectedError (PDF password protection)
  - FormatError (unsupported formats)
  - InputError (invalid input types/values)
  - MarkdownConversionError (conversion process failures)
"""

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
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class PasswordProtectedError(All2MdError):
    """Exception raised when a PDF file requires a password for access.

    This exception is raised specifically when attempting to process
    a password-protected PDF document without providing the correct
    password or when the provided password is incorrect.

    Parameters
    ----------
    message : str, optional
        Custom error message. If not provided, uses default message
    filename : str, optional
        Name of the file that requires a password

    Attributes
    ----------
    filename : str or None
        The name of the password-protected file, if provided
    """

    def __init__(self, message: str | None = None, filename: str | None = None):
        if message is None:
            if filename:
                message = f"PDF file '{filename}' is password-protected and requires authentication"
            else:
                message = "PDF file is password-protected and requires a password for access"

        super().__init__(message)
        self.filename = filename


class FormatError(All2MdError):
    """Exception raised when attempting to process an unsupported file format.

    This exception indicates that the requested file format or conversion
    operation is not supported by the current version of all2md or that
    required dependencies are missing.

    Parameters
    ----------
    message : str, optional
        Custom error message
    format_type : str, optional
        The unsupported format type (file extension or MIME type)
    supported_formats : list[str], optional
        List of supported formats for reference

    Attributes
    ----------
    format_type : str or None
        The format that was not supported
    supported_formats : list[str] or None
        Available supported formats
    """

    def __init__(
            self, message: str | None = None, format_type: str | None = None,
            supported_formats: list[str] | None = None,
            original_error: Exception | None = None
    ):
        if message is None:
            if format_type:
                message = f"Unsupported format: '{format_type}'"
                if supported_formats:
                    formats_str = ", ".join(supported_formats[:5])  # Show first 5
                    if len(supported_formats) > 5:
                        formats_str += f" (and {len(supported_formats) - 5} more)"
                    message += f". Supported formats include: {formats_str}"
            else:
                message = "File format is not supported for conversion"

        super().__init__(message, original_error=original_error)
        self.format_type = format_type
        self.supported_formats = supported_formats


class InputError(All2MdError):
    """Exception raised for invalid input parameters or data.

    This exception covers various input validation errors such as:
    - Invalid page ranges for PDF processing
    - Unsupported input types (not path-like, bytes, or file-like)
    - Invalid parameter combinations
    - Malformed input data

    Parameters
    ----------
    message : str
        Description of the input error
    parameter_name : str, optional
        Name of the invalid parameter
    parameter_value : any, optional
        The invalid value that was provided

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
            parameter_value=None,
            original_error: Exception | None = None
    ):
        super().__init__(message, original_error=original_error)
        self.parameter_name = parameter_name
        self.parameter_value = parameter_value


class MarkdownConversionError(All2MdError):
    """Exception raised when document conversion fails.

    This exception is raised when the conversion process encounters
    an error that prevents successful completion, such as:
    - Corrupt or malformed input files
    - Missing required data or metadata
    - Internal processing errors
    - Memory or resource constraints

    Parameters
    ----------
    message : str
        Description of the conversion failure
    conversion_stage : str, optional
        The stage of conversion where the error occurred
    original_error : Exception, optional
        The underlying exception that caused the conversion failure

    Attributes
    ----------
    conversion_stage : str or None
        Where in the conversion process the error occurred
    """

    def __init__(self, message: str, conversion_stage: str | None = None, original_error: Exception | None = None):
        super().__init__(message, original_error)
        self.conversion_stage = conversion_stage


class DependencyError(ImportError, All2MdError):
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
    install_command : str
        Command to install missing dependencies
    """

    def __init__(
            self,
            converter_name: str,
            missing_packages: list[tuple[str, str]],
            install_command: str = "",
            message: str | None = None
    ):
        if message is None:
            pkg_list = ", ".join(
                f"'{name}{spec}'" if spec else f"'{name}'"
                for name, spec in missing_packages
            )
            message = (
                f"{converter_name.upper()} format requires the following packages: {pkg_list}\n"
            )
            if install_command:
                message += f"Install with: {install_command}"
            else:
                # Generate install command if not provided
                packages_str = " ".join(
                    f'"{name}{spec}"' if spec else name
                    for name, spec in missing_packages
                )
                message += f"Install with: pip install {packages_str}"

        super().__init__(message)
        self.converter_name = converter_name
        self.missing_packages = missing_packages
        self.install_command = install_command
