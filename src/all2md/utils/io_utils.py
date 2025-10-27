#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/io_utils.py
"""I/O utilities for handling output destinations.

This module provides centralized utilities for writing content to various
output destinations (files, file-like objects, or returning as file-like objects).

"""

from __future__ import annotations

import io
from io import BytesIO, StringIO
from pathlib import Path
from typing import IO, Union, cast


def write_content(
    content: Union[str, bytes], output: Union[str, Path, IO[bytes], IO[str], None]
) -> Union[StringIO, BytesIO, None]:
    """Write content to output destination or return as file-like object.

    This function provides a centralized way to handle output destinations,
    supporting file paths, file-like objects, or returning content as a
    file-like object when no destination is provided.

    Parameters
    ----------
    content : str or bytes
        Content to write. Can be text (str) or binary (bytes) data.
    output : str, Path, IO[bytes], IO[str], or None
        Output destination. Can be:
        - None: Returns content as StringIO (for str) or BytesIO (for bytes)
        - str or Path: Writes content to file at that path
        - IO[bytes]: Writes content to binary file-like object
        - IO[str]: Writes content to text file-like object

    Returns
    -------
    StringIO, BytesIO, or None
        - If output is None: Returns StringIO (for str content) or BytesIO (for bytes content)
        - Otherwise: Returns None after writing to the destination

    Raises
    ------
    TypeError
        If output type is not supported or content type doesn't match file mode

    Examples
    --------
    Return as file-like object:
        >>> content = "Hello, world!"
        >>> result = write_content(content, None)
        >>> isinstance(result, StringIO)
        True
        >>> result.read()
        'Hello, world!'

    Write to file path:
        >>> write_content("test content", "output.txt")
        >>> Path("output.txt").read_text()
        'test content'

    Write to file-like object:
        >>> from io import BytesIO
        >>> buffer = BytesIO()
        >>> write_content(b"binary data", buffer)
        >>> buffer.getvalue()
        b'binary data'

    """
    # If output is None, return as file-like object
    if output is None:
        if isinstance(content, str):
            return StringIO(content)
        elif isinstance(content, bytes):
            buffer = BytesIO(content)
            buffer.seek(0)  # Position at start for reading
            return buffer
        else:
            raise TypeError(f"Content must be str or bytes, got {type(content)}")

    # If output is a path (str or Path), write to file
    if isinstance(output, (str, Path)):
        output_path = Path(output)
        if isinstance(content, str):
            output_path.write_text(content, encoding="utf-8")
        elif isinstance(content, bytes):
            output_path.write_bytes(content)
        else:
            raise TypeError(f"Content must be str or bytes, got {type(content)}")
        return None

    # If output is a file-like object, write to it
    if hasattr(output, "write"):
        # Detect if binary or text mode using multiple strategies
        # Strategy 1: Check concrete types first (most reliable)
        if isinstance(output, BytesIO):
            is_binary_mode = True
        elif isinstance(output, StringIO):
            is_binary_mode = False
        # Strategy 2: Check io module base classes (robust for standard streams)
        elif isinstance(output, io.TextIOBase):
            is_binary_mode = False
        elif isinstance(output, (io.BufferedIOBase, io.RawIOBase)):
            is_binary_mode = True
        # Strategy 3: Check mode attribute (fallback for file objects)
        elif hasattr(output, "mode"):
            mode = getattr(output, "mode", "")
            is_binary_mode = isinstance(mode, str) and "b" in mode
        else:
            # Default to text mode if we can't determine (safest for str content)
            is_binary_mode = False

        if is_binary_mode:
            # Binary mode - write bytes
            binary_output = cast(IO[bytes], output)
            if isinstance(content, str):
                binary_output.write(content.encode("utf-8"))
            elif isinstance(content, bytes):
                binary_output.write(content)
            else:
                raise TypeError(f"Content must be str or bytes, got {type(content)}")
        else:
            # Text mode - write str
            text_output = cast(IO[str], output)
            if isinstance(content, bytes):
                text_output.write(content.decode("utf-8"))
            elif isinstance(content, str):
                text_output.write(content)
            else:
                raise TypeError(f"Content must be str or bytes, got {type(content)}")
        return None

    # Unsupported output type
    raise TypeError(f"Unsupported output type: {type(output)}")


__all__ = ["write_content"]
