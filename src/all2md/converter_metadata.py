"""Converter metadata definitions for the all2md library.

This module defines dataclasses that describe converter capabilities,
requirements, and registration information for the plugin registry system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Callable, Optional, Union


@dataclass
class ConverterMetadata:
    """Metadata describing a converter's capabilities and requirements.

    This dataclass contains all information needed to register and use
    a converter, including format detection patterns, module locations,
    and dependency requirements.

    Parameters
    ----------
    format_name : str
        Unique identifier for the format (e.g., "pdf", "docx")
    extensions : list[str]
        File extensions supported (e.g., [".pdf"])
    mime_types : list[str]
        MIME types that indicate this format
    magic_bytes : list[tuple[bytes, int]]
        Magic byte patterns and their offset for content detection.
        Each tuple is (pattern, offset) where offset is position in file
    content_detector : Callable[[bytes], bool], optional
        Custom content-based detection function that receives file content bytes
        and returns True if this converter should handle the content
    parser_class : Union[str, type, None], optional
        Parser class specification. Can be:
        - Simple class name (e.g., "DocxParser") - looks in all2md.parsers.{format}
        - Fully qualified name (e.g., "myplugin.parsers.MyParser")
        - Direct class reference (e.g., MyParserClass)
        - None for no parser
    renderer_class : Union[str, type, None], optional
        Renderer class specification. Can be:
        - Simple class name (e.g., "DocxRenderer") - looks in all2md.renderers.{format}
        - Fully qualified name (e.g., "myplugin.renderers.MyRenderer")
        - Direct class reference (e.g., MyRendererClass)
        - None for no renderer
    required_packages : list[tuple[str, str, str]]
        Required packages as (install_name, import_name, version_spec) tuples.
        The install_name is the package name for pip install, import_name is
        the name used in Python import statements, and version_spec is the
        version requirement (can be empty string for no requirement).
        e.g., [("pymupdf", "fitz", ">=1.26.4"), ("Pillow", "PIL", ">=9.0.0")]
    optional_packages : list[tuple[str, str]]
        Optional packages that enhance functionality
    import_error_message : str
        Custom error message for missing dependencies
    parser_options_class : Union[str, type, None]
        Parser options class specification. Can be:
        - Simple class name (e.g., "PdfOptions") - looks in all2md.options
        - Fully qualified name (e.g., "myplugin.options.MyOptions")
        - Direct class reference (e.g., MyOptionsClass)
        - None for no parser options
    renderer_options_class : Union[str, type, None]
        Renderer options class specification. Can be:
        - Simple class name (e.g., "MarkdownOptions") - looks in all2md.options
        - Fully qualified name (e.g., "myplugin.options.MyRendererOptions")
        - Direct class reference (e.g., MyRendererOptionsClass)
        - None for no renderer options
    description : str
        Human-readable description of the converter
    priority : int
        Priority for format detection (higher = checked first)
    """

    format_name: str
    extensions: list[str] = field(default_factory=list)
    mime_types: list[str] = field(default_factory=list)
    magic_bytes: list[tuple[bytes, int]] = field(default_factory=list)
    content_detector: Optional[Callable[[bytes], bool]] = None
    parser_class: Optional[Union[str, type]] = None
    renderer_class: Optional[Union[str, type]] = None
    required_packages: list[tuple[str, str, str]] = field(default_factory=list)
    optional_packages: list[tuple[str, str]] = field(default_factory=list)
    import_error_message: str = ""
    parser_options_class: Optional[Union[str, type]] = None
    renderer_options_class: Optional[Union[str, type]] = None
    description: str = ""
    priority: int = 0

    def get_install_command(self) -> str:
        """Generate pip install command for required packages.

        Returns
        -------
        str
            Pip install command for all required packages
        """
        if not self.required_packages:
            return ""

        packages = []
        for pkg_name, _import_name, version_spec in self.required_packages:
            if version_spec:
                # Handle different version specifier formats
                if version_spec.startswith((">=", "<=", "==", "!=", "~=", ">")):
                    packages.append(f'"{pkg_name}{version_spec}"')
                else:
                    packages.append(f'"{pkg_name}=={version_spec}"')
            else:
                packages.append(pkg_name)

        return f"pip install {' '.join(packages)}"

    def matches_extension(self, filename: str) -> bool:
        """Check if filename matches any supported extension.

        Parameters
        ----------
        filename : str
            Filename to check

        Returns
        -------
        bool
            True if extension matches
        """
        if not filename:
            return False

        import os
        _, ext = os.path.splitext(filename.lower())
        return ext in self.extensions

    def matches_mime_type(self, mime_type: str) -> bool:
        """Check if MIME type matches this converter.

        Parameters
        ----------
        mime_type : str
            MIME type to check

        Returns
        -------
        bool
            True if MIME type matches
        """
        return mime_type in self.mime_types if mime_type else False

    def matches_magic_bytes(self, content: bytes, max_check: int = 512) -> bool:
        """Check if content matches any magic byte patterns.

        Parameters
        ----------
        content : bytes
            File content to check
        max_check : int
            Maximum bytes to check

        Returns
        -------
        bool
            True if any magic byte pattern matches
        """
        if not content or not self.magic_bytes:
            return False

        check_bytes = content[:max_check]

        for pattern, offset in self.magic_bytes:
            if len(check_bytes) >= offset + len(pattern):
                if check_bytes[offset:offset + len(pattern)] == pattern:
                    return True

        return False

    def get_required_packages_for_content(
        self,
        content: Optional[bytes] = None,
        input_data: Optional[Union[str, Path, IO[bytes], bytes]] = None
    ) -> list[tuple[str, str, str]]:
        """Get required packages for specific content, allowing context-aware dependency checking.

        Some parsers may have different dependency requirements based on the actual
        content they're processing. This method allows parsers to specify
        context-specific dependencies.

        Parameters
        ----------
        content : bytes, optional
            File content sample (may be partial) to analyze for dependency requirements
        input_data : various types, optional
            Original input data (path, file object, or bytes) for more accurate detection.
            When provided, implementations can access the full file instead of relying
            on potentially truncated content samples.

        Returns
        -------
        list[tuple[str, str, str]]
            Required packages as (install_name, import_name, version_spec) tuples for this content
        """
        # Default implementation returns all required packages
        # Subclasses or specific parsers can override this logic to use input_data
        return self.required_packages


@dataclass
class ConverterCapabilities:
    """Describes capabilities and features of a converter.

    Parameters
    ----------
    supports_streaming : bool
        Whether converter can process file-like objects
    supports_password : bool
        Whether converter handles password-protected files
    supports_partial : bool
        Whether converter can process specific pages/sections
    supports_attachments : bool
        Whether converter can extract attachments/images
    supports_bidirectional : bool
        Whether converter supports both to/from markdown
    max_file_size : int or None
        Maximum file size in bytes, None for unlimited
    """

    supports_streaming: bool = True
    supports_password: bool = False
    supports_partial: bool = False
    supports_attachments: bool = False
    supports_bidirectional: bool = False
    max_file_size: Optional[int] = None
