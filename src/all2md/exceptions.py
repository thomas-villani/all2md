"""Custom exceptions for the all2md library.

This module defines specialized exception classes for various error conditions
that can occur during document parsing and conversion operations. These
exceptions provide more specific error information than generic built-ins.

Exception Hierarchy
-------------------
- MdparseError (base exception)
  - MdparsePasswordError (PDF password protection)
  - MdparseFormatError (unsupported formats)
  - MdparseInputError (invalid input types/values)
  - MdparseConversionError (conversion process failures)
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


class MdparseError(Exception):
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


class MdparsePasswordError(MdparseError):
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


class MdparseFormatError(MdparseError):
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
        self, message: str | None = None, format_type: str | None = None, supported_formats: list[str] | None = None,
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


class MdparseInputError(MdparseError):
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

    def __init__(self,
                 message: str,
                 parameter_name: str | None = None,
                 parameter_value=None,
                 original_error: Exception | None = None
                 ):
        super().__init__(message, original_error=original_error)
        self.parameter_name = parameter_name
        self.parameter_value = parameter_value


class MdparseConversionError(MdparseError):
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
