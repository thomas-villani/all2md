#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/encoding.py
"""Character encoding detection and handling utilities.

This module provides utilities for detecting and handling character encodings
in text-based files, with support for chardet-based detection and fallback
strategies for maximum compatibility.
"""

from __future__ import annotations

import logging
from typing import IO

logger = logging.getLogger(__name__)


def detect_encoding(
    data: bytes,
    sample_size: int = 8192,
    confidence_threshold: float = 0.7,
) -> str | None:
    """Detect character encoding of binary data using chardet.

    Parameters
    ----------
    data : bytes
        Binary data to analyze
    sample_size : int, default 8192
        Number of bytes to sample for detection (uses first N bytes)
    confidence_threshold : float, default 0.7
        Minimum confidence level (0.0-1.0) required to trust detection

    Returns
    -------
    str | None
        Detected encoding name (e.g., 'utf-8', 'latin-1'), or None if:
        - chardet is not available
        - detection fails
        - confidence is below threshold

    Examples
    --------
    >>> data = b"Hello, world!"
    >>> encoding = detect_encoding(data)
    >>> if encoding:
    ...     text = data.decode(encoding)

    """
    try:
        import chardet
    except ImportError:
        logger.debug("chardet not available for encoding detection")
        return None

    try:
        # Sample the data if it's larger than sample_size
        sample = data[:sample_size] if len(data) > sample_size else data

        # Detect encoding
        result = chardet.detect(sample)

        if not result or not result.get("encoding"):
            logger.debug("chardet: No encoding detected")
            return None

        encoding = result["encoding"]
        confidence = result.get("confidence", 0.0)

        logger.debug(f"chardet detected encoding: {encoding} (confidence: {confidence:.2f})")

        # Return encoding only if confidence is above threshold
        if confidence >= confidence_threshold:
            return encoding
        else:
            logger.debug(f"chardet confidence {confidence:.2f} below threshold {confidence_threshold}")
            return None

    except Exception as e:
        logger.debug(f"chardet detection failed: {e}")
        return None


def read_text_with_encoding_detection(
    data: bytes,
    fallback_encodings: list[str] | None = None,
    use_chardet: bool = True,
    chardet_sample_size: int = 8192,
    chardet_confidence_threshold: float = 0.7,
) -> str:
    """Read binary data as text with automatic encoding detection.

    Attempts to decode binary data using multiple strategies:
    1. chardet-based detection (if enabled and available)
    2. Fallback encodings in order
    3. Final fallback with error replacement

    Parameters
    ----------
    data : bytes
        Binary data to decode
    fallback_encodings : list[str] | None, default None
        List of encodings to try in order. If None, uses:
        ['utf-8', 'utf-8-sig', 'latin-1']
    use_chardet : bool, default True
        Whether to attempt chardet-based detection first
    chardet_sample_size : int, default 8192
        Number of bytes to sample for chardet detection
    chardet_confidence_threshold : float, default 0.7
        Minimum confidence for chardet detection

    Returns
    -------
    str
        Decoded text content

    Raises
    ------
    ValueError
        If data cannot be decoded with any encoding (should be rare
        since latin-1 accepts any byte sequence)

    Examples
    --------
    >>> data = b"Hello, world!"
    >>> text = read_text_with_encoding_detection(data)
    >>> print(text)
    Hello, world!

    >>> # Custom fallback encodings
    >>> text = read_text_with_encoding_detection(
    ...     data,
    ...     fallback_encodings=['cp1252', 'utf-8', 'latin-1']
    ... )

    """
    if fallback_encodings is None:
        fallback_encodings = ["utf-8", "utf-8-sig", "latin-1"]

    # Try chardet detection first if enabled
    if use_chardet:
        detected_encoding = detect_encoding(
            data,
            sample_size=chardet_sample_size,
            confidence_threshold=chardet_confidence_threshold,
        )
        if detected_encoding:
            # Try the detected encoding first
            try:
                text = data.decode(detected_encoding)
                logger.debug(f"Successfully decoded with chardet-detected encoding: {detected_encoding}")
                return text
            except (UnicodeDecodeError, LookupError) as e:
                logger.debug(f"Failed to decode with chardet-detected encoding {detected_encoding}: {e}")
                # Continue to fallback encodings

    # Try each fallback encoding in order
    for encoding in fallback_encodings:
        try:
            text = data.decode(encoding)
            logger.debug(f"Successfully decoded with encoding: {encoding}")
            return text
        except UnicodeDecodeError as e:
            logger.debug(f"Failed to decode with {encoding}: {e}")
            continue
        except LookupError as e:
            logger.debug(f"Unknown encoding {encoding}: {e}")
            continue

    # Final fallback: utf-8 with error replacement (should not be reached if latin-1 is in fallbacks)
    logger.warning("All encoding attempts failed, using utf-8 with error replacement")
    return data.decode("utf-8", errors="replace")


def get_charset_from_content_type(content_type: str) -> str | None:
    """Extract charset parameter from Content-Type header.

    Parameters
    ----------
    content_type : str
        Content-Type header value (e.g., 'text/html; charset=utf-8')

    Returns
    -------
    str | None
        Charset value if present, None otherwise

    Examples
    --------
    >>> get_charset_from_content_type('text/html; charset=utf-8')
    'utf-8'
    >>> get_charset_from_content_type('text/html')
    None

    """
    if not content_type:
        return None

    # Split by semicolon and look for charset parameter
    parts = content_type.split(";")
    for part in parts[1:]:  # Skip the media type part
        part = part.strip()
        # Handle both "charset=value" and "charset = value"
        if "=" in part:
            key, value = part.split("=", 1)
            if key.strip().lower() == "charset":
                charset = value.strip()
                # Remove quotes if present
                if charset.startswith('"') and charset.endswith('"'):
                    charset = charset[1:-1]
                if charset.startswith("'") and charset.endswith("'"):
                    charset = charset[1:-1]
                return charset.strip()

    return None


def normalize_stream_to_text(
    stream: IO[bytes] | IO[str],
    fallback_encodings: list[str] | None = None,
    use_chardet: bool = True,
    chardet_sample_size: int = 8192,
    chardet_confidence_threshold: float = 0.7,
) -> str:
    """Read content from a file-like object and normalize to text.

    This helper handles both binary-mode streams (IO[bytes]) and text-mode
    streams (IO[str]):
    - Binary streams: decodes using automatic encoding detection
    - Text streams: returns content as-is

    This is useful for parsers that need to accept both binary and text mode
    file-like objects without crashing on type mismatches.

    Parameters
    ----------
    stream : IO[bytes] or IO[str]
        File-like object to read from. Can be either binary mode (e.g.,
        io.BytesIO, open(file, 'rb')) or text mode (e.g., io.StringIO,
        open(file, 'r'))
    fallback_encodings : list[str] or None, optional
        List of encodings to try if chardet detection fails. If None,
        uses ['utf-8', 'utf-8-sig', 'latin-1']
    use_chardet : bool, default True
        Whether to use chardet for automatic encoding detection on
        binary streams
    chardet_sample_size : int, default 8192
        Number of bytes to sample for chardet detection
    chardet_confidence_threshold : float, default 0.7
        Minimum confidence level for chardet detection

    Returns
    -------
    str
        Decoded text content from the stream

    Raises
    ------
    TypeError
        If stream.read() returns something other than bytes or str

    Examples
    --------
    >>> from io import BytesIO, StringIO
    >>> # Binary stream
    >>> binary_stream = BytesIO(b"Hello, world!")
    >>> text = normalize_stream_to_text(binary_stream)
    >>> print(text)
    Hello, world!

    >>> # Text stream
    >>> text_stream = StringIO("Hello, world!")
    >>> text = normalize_stream_to_text(text_stream)
    >>> print(text)
    Hello, world!

    """
    content = stream.read()

    if isinstance(content, bytes):
        # Binary stream - decode with encoding detection
        return read_text_with_encoding_detection(
            content,
            fallback_encodings=fallback_encodings,
            use_chardet=use_chardet,
            chardet_sample_size=chardet_sample_size,
            chardet_confidence_threshold=chardet_confidence_threshold,
        )
    elif isinstance(content, str):
        # Text stream - return as-is
        return content
    else:
        # Unexpected type
        raise TypeError(f"Stream read() returned unexpected type {type(content).__name__}. " f"Expected bytes or str.")


def normalize_stream_to_bytes(
    stream: IO[bytes] | IO[str],
    encoding: str = "utf-8",
) -> bytes:
    """Read content from a file-like object and normalize to bytes.

    This helper handles both binary-mode streams (IO[bytes]) and text-mode
    streams (IO[str]):
    - Binary streams: returns content as-is
    - Text streams: encodes using specified encoding

    This is useful for parsers that need to work with binary data (e.g., for
    format detection, ZIP signatures, JSON decoding) but may receive either
    binary or text mode streams.

    Parameters
    ----------
    stream : IO[bytes] or IO[str]
        File-like object to read from. Can be either binary mode (e.g.,
        io.BytesIO, open(file, 'rb')) or text mode (e.g., io.StringIO,
        open(file, 'r'))
    encoding : str, default "utf-8"
        Encoding to use when converting text streams to bytes

    Returns
    -------
    bytes
        Content as bytes

    Raises
    ------
    TypeError
        If stream.read() returns something other than bytes or str

    Examples
    --------
    >>> from io import BytesIO, StringIO
    >>> # Binary stream
    >>> binary_stream = BytesIO(b"Hello, world!")
    >>> data = normalize_stream_to_bytes(binary_stream)
    >>> print(data)
    b'Hello, world!'

    >>> # Text stream
    >>> text_stream = StringIO("Hello, world!")
    >>> data = normalize_stream_to_bytes(text_stream)
    >>> print(data)
    b'Hello, world!'

    """
    content = stream.read()

    if isinstance(content, bytes):
        # Binary stream - return as-is
        return content
    elif isinstance(content, str):
        # Text stream - encode with specified encoding
        return content.encode(encoding)
    else:
        # Unexpected type
        raise TypeError(f"Stream read() returned unexpected type {type(content).__name__}. " f"Expected bytes or str.")
