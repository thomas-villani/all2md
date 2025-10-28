"""Converter metadata definitions for the all2md library.

This module defines dataclasses that describe converter capabilities,
requirements, and registration information for the plugin registry system.
"""

from __future__ import annotations

import os
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
    parser_required_packages : list[tuple[str, str, str]]
        Required packages for the parser as (install_name, import_name, version_spec) tuples.
        The install_name is the package name for pip install, import_name is
        the name used in Python import statements, and version_spec is the
        version requirement (can be empty string for no requirement).
        e.g., [("pymupdf", "fitz", ">=1.26.4"), ("Pillow", "PIL", ">=9.0.0")]
    renderer_required_packages : list[tuple[str, str, str]]
        Required packages for the renderer as (install_name, import_name, version_spec) tuples.
        Same format as parser_required_packages. Empty list if no renderer or no special
        dependencies needed for rendering.
    required_packages : list[tuple[str, str, str]]
        Combined list of all required packages (parser + renderer). This field is
        computed automatically and provided for backward compatibility.
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
        - Simple class name (e.g., "MarkdownRendererOptions") - looks in all2md.options
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
    parser_required_packages: list[tuple[str, str, str]] = field(default_factory=list)
    renderer_required_packages: list[tuple[str, str, str]] = field(default_factory=list)
    renders_as_string: bool = False
    optional_packages: list[tuple[str, str]] = field(default_factory=list)
    import_error_message: str = ""
    parser_options_class: Optional[Union[str, type]] = None
    renderer_options_class: Optional[Union[str, type]] = None
    description: str = ""
    priority: int = 0

    @property
    def required_packages(self) -> list[tuple[str, str, str]]:
        """Get combined list of all required packages for backward compatibility.

        Returns
        -------
        list[tuple[str, str, str]]
            Combined parser and renderer packages

        """
        return self.parser_required_packages + self.renderer_required_packages

    def get_install_command(self, as_args: bool = False) -> str | list[str]:
        """Generate pip install command for required packages.

        Parameters
        ----------
        as_args : bool, default False
            Returns a list of str for subprocess if True

        Returns
        -------
        str | list[str]
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

        if as_args:
            return ["pip", "install", *packages]
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
                if check_bytes[offset : offset + len(pattern)] == pattern:
                    return True

        return False

    def get_required_packages_for_content(
        self,
        content: Optional[bytes] = None,
        input_data: Optional[Union[str, Path, IO[bytes], bytes]] = None,
        operation: str = "parse",
    ) -> list[tuple[str, str, str]]:
        """Get required packages for specific content, allowing context-aware dependency checking.

        Some parsers or renderers may have different dependency requirements based on the actual
        content they're processing. This method allows parsers/renderers to specify
        context-specific dependencies.

        Parameters
        ----------
        content : bytes, optional
            File content sample (may be partial) to analyze for dependency requirements
        input_data : various types, optional
            Original input data (path, file object, or bytes) for more accurate detection.
            When provided, implementations can access the full file instead of relying
            on potentially truncated content samples.
        operation : str, default="parse"
            The operation type: "parse", "render", or "both"

        Returns
        -------
        list[tuple[str, str, str]]
            Required packages as (install_name, import_name, version_spec) tuples for this content

        """
        # Default implementation returns packages based on operation type
        # Subclasses can override this logic to use content/input_data for context-aware detection
        if operation == "parse":
            return self.parser_required_packages
        elif operation == "render":
            return self.renderer_required_packages
        elif operation == "both":
            return self.required_packages  # Uses the @property which combines both
        else:
            return self.required_packages

    def get_parser_display_name(self) -> str:
        """Get friendly display name for the parser class.

        Returns
        -------
        str
            Display name for parser class

        """
        if self.parser_class is None:
            return "N/A"

        # If it's a type (class reference), extract module and name
        if isinstance(self.parser_class, type):
            module = self.parser_class.__module__
            name = self.parser_class.__qualname__
            return f"{module}.{name}"

        # If it's a string
        if isinstance(self.parser_class, str):
            # If fully qualified (has dot), use as-is
            if "." in self.parser_class:
                return self.parser_class
            # If simple class name, construct full path
            return f"all2md.parsers.{self.format_name}.{self.parser_class}"

        # Fallback for any other type
        return str(self.parser_class)  # type: ignore[unreachable]

    def get_renderer_display_name(self) -> str:
        """Get friendly display name for the renderer class.

        Returns
        -------
        str
            Display name for renderer class

        """
        if self.renderer_class is None:
            return "N/A"

        # If it's a type (class reference), extract module and name
        if isinstance(self.renderer_class, type):
            module = self.renderer_class.__module__
            name = self.renderer_class.__qualname__
            return f"{module}.{name}"

        # If it's a string
        if isinstance(self.renderer_class, str):
            # If fully qualified (has dot), use as-is
            if "." in self.renderer_class:
                return self.renderer_class
            # If simple class name, construct full path
            return f"all2md.renderers.{self.format_name}.{self.renderer_class}"

        # Fallback for any other type
        return str(self.renderer_class)  # type: ignore[unreachable]

    def get_converter_display_string(self) -> str:
        """Get combined display string showing both parser and renderer.

        Returns
        -------
        str
            Combined display string in format "Parser: X | Renderer: Y"

        """
        parser_name = self.get_parser_display_name()
        renderer_name = self.get_renderer_display_name()
        return f"Parser: {parser_name} | Renderer: {renderer_name}"
