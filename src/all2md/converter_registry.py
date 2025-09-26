"""Converter registry for dynamic converter management.

This module implements a registry pattern for converters, enabling:
- Lazy loading of converter modules
- Dynamic converter discovery and registration
- Proper dependency error handling
- Format detection and converter routing
"""

from __future__ import annotations

import importlib
import logging
import mimetypes
from pathlib import Path
from typing import IO, Callable, Dict, List, Optional, Tuple, Union

from .converter_metadata import ConverterMetadata
from .exceptions import DependencyError, FormatError

logger = logging.getLogger(__name__)


class ConverterRegistry:
    """Registry for managing document converters.

    This class provides a central registry for all converters, handling:
    - Converter registration and discovery
    - Format detection from files/content
    - Lazy loading of converter modules
    - Dependency checking and error handling

    Attributes
    ----------
    _instance : ConverterRegistry or None
        Singleton instance of the registry
    _converters : dict
        Registered converters by format name
    _initialized : bool
        Whether auto-discovery has been run
    """

    _instance: Optional[ConverterRegistry] = None
    _converters: Dict[str, ConverterMetadata] = {}
    _initialized: bool = False

    def __new__(cls) -> ConverterRegistry:
        """Create or return singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._converters = {}
            cls._instance._initialized = False
        return cls._instance

    def register(self, metadata: ConverterMetadata) -> None:
        """Register a converter with its metadata.

        Parameters
        ----------
        metadata : ConverterMetadata
            Converter metadata to register

        Raises
        ------
        ValueError
            If converter with same format_name already registered
        """
        if metadata.format_name in self._converters:
            logger.warning(
                f"Converter '{metadata.format_name}' already registered, overwriting"
            )

        self._converters[metadata.format_name] = metadata
        logger.debug(f"Registered converter: {metadata.format_name}")

    def unregister(self, format_name: str) -> bool:
        """Unregister a converter.

        Parameters
        ----------
        format_name : str
            Format name to unregister

        Returns
        -------
        bool
            True if unregistered, False if not found
        """
        if format_name in self._converters:
            del self._converters[format_name]
            logger.debug(f"Unregistered converter: {format_name}")
            return True
        return False

    def get_converter(
        self,
        format_name: str
    ) -> Tuple[Callable, Optional[type]]:
        """Get converter function and options class for a format.

        Parameters
        ----------
        format_name : str
            Format name to get converter for

        Returns
        -------
        tuple
            (converter_function, options_class)

        Raises
        ------
        FormatError
            If format not registered
        DependencyError
            If required dependencies not installed
        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(
                format_type=format_name,
                supported_formats=available
            )

        metadata = self._converters[format_name]

        # Try to import the converter module
        try:
            module = importlib.import_module(metadata.converter_module)
            converter_func = getattr(module, metadata.converter_function)

            # Try to get options class if specified
            options_class = None
            if metadata.options_class:
                # Import from options module
                from . import options
                options_class = getattr(options, metadata.options_class, None)

            return converter_func, options_class

        except ImportError as e:
            # Check which specific package failed
            missing_packages = []

            for pkg_name, version_spec in metadata.required_packages:
                try:
                    __import__(pkg_name.replace("-", "_"))
                except ImportError:
                    missing_packages.append((pkg_name, version_spec))

            if missing_packages:
                raise DependencyError(
                    converter_name=metadata.format_name,
                    missing_packages=missing_packages,
                    install_command=metadata.get_install_command()
                ) from e
            else:
                # Re-raise if it's not a dependency issue
                raise

        except AttributeError as e:
            raise FormatError(
                f"Converter function '{metadata.converter_function}' "
                f"not found in module '{metadata.converter_module}'"
            ) from e

    def detect_format(
        self,
        input_data: Union[str, Path, IO[bytes], bytes],
        hint: Optional[str] = None
    ) -> str:
        """Detect format from input data.

        Uses multiple strategies:
        1. Explicit hint if provided
        2. Filename extension matching
        3. MIME type detection
        4. Magic bytes content analysis
        5. Default fallback

        Parameters
        ----------
        input_data : various types
            Input data to detect format from
        hint : str, optional
            Format hint to prefer

        Returns
        -------
        str
            Detected format name
        """
        # If hint provided and valid, use it
        if hint and hint in self._converters:
            return hint

        # Try filename-based detection
        if isinstance(input_data, (str, Path)):
            filename = str(input_data)
            format_name = self._detect_by_filename(filename)
            if format_name:
                logger.debug(f"Format detected from filename: {format_name}")
                return format_name

        # For file-like objects, try to get filename
        elif hasattr(input_data, 'name'):
            filename = getattr(input_data, 'name', None)
            if filename and filename != 'unknown':
                format_name = self._detect_by_filename(filename)
                if format_name:
                    logger.debug(f"Format detected from file object name: {format_name}")
                    return format_name

        # Try content-based detection
        content = None
        if isinstance(input_data, bytes):
            content = input_data
        elif isinstance(input_data, (str, Path)):
            # Read first 1KB for detection
            try:
                with open(input_data, 'rb') as f:
                    content = f.read(1024)
            except Exception:
                pass
        elif isinstance(input_data, IO):
            # Save position and read sample
            try:
                pos = input_data.tell()
                input_data.seek(0)
                content = input_data.read(1024)
                input_data.seek(pos)
            except Exception:
                pass

        if content:
            format_name = self._detect_by_content(content)
            if format_name:
                logger.debug(f"Format detected from content: {format_name}")
                return format_name

        # Default fallback
        logger.debug("No format detected, defaulting to txt")
        return "txt"

    def _detect_by_filename(self, filename: str) -> Optional[str]:
        """Detect format from filename.

        Parameters
        ----------
        filename : str
            Filename to analyze

        Returns
        -------
        str or None
            Format name if detected
        """
        # Sort by priority for extension matching
        sorted_converters = sorted(
            self._converters.items(),
            key=lambda x: x[1].priority,
            reverse=True
        )

        # Check extensions
        for format_name, metadata in sorted_converters:
            if metadata.matches_extension(filename):
                return format_name

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            for format_name, metadata in sorted_converters:
                if metadata.matches_mime_type(mime_type):
                    return format_name

        return None

    def _detect_by_content(self, content: bytes) -> Optional[str]:
        """Detect format from file content.

        Parameters
        ----------
        content : bytes
            File content to analyze

        Returns
        -------
        str or None
            Format name if detected
        """
        # Sort by priority for content matching
        sorted_converters = sorted(
            self._converters.items(),
            key=lambda x: x[1].priority,
            reverse=True
        )

        for format_name, metadata in sorted_converters:
            if metadata.matches_magic_bytes(content):
                return format_name

        # Fallback to CSV/TSV detection for special handling
        try:
            content_str = content.decode('utf-8', errors='ignore')
            non_empty_lines = [line.strip() for line in content_str.split('\n') if line.strip()]

            if len(non_empty_lines) >= 2:  # Need at least 2 lines (header + data)
                comma_count = sum(line.count(',') for line in non_empty_lines)
                tab_count = sum(line.count('\t') for line in non_empty_lines)

                # More relaxed CSV detection
                if comma_count >= len(non_empty_lines):  # At least one comma per line
                    logger.debug(f"CSV pattern detected: {comma_count} commas in {len(non_empty_lines)} lines")
                    return "csv"
                elif tab_count >= len(non_empty_lines):  # At least one tab per line
                    logger.debug(f"TSV pattern detected: {tab_count} tabs in {len(non_empty_lines)} lines")
                    return "tsv"
        except UnicodeDecodeError:
            pass

        return None

    def list_formats(self) -> List[str]:
        """List all registered format names.

        Returns
        -------
        list[str]
            Sorted list of format names
        """
        return sorted(self._converters.keys())

    def get_format_info(self, format_name: str) -> Optional[ConverterMetadata]:
        """Get metadata for a specific format.

        Parameters
        ----------
        format_name : str
            Format to get info for

        Returns
        -------
        ConverterMetadata or None
            Metadata if format registered
        """
        return self._converters.get(format_name)

    def check_dependencies(self, format_name: Optional[str] = None) -> Dict[str, List[str]]:
        """Check which dependencies are missing.

        Parameters
        ----------
        format_name : str, optional
            Check specific format, or all if None

        Returns
        -------
        dict
            Format names mapped to list of missing packages
        """
        missing = {}

        formats_to_check = (
            [format_name] if format_name
            else self._converters.keys()
        )

        for fmt in formats_to_check:
            if fmt not in self._converters:
                continue

            metadata = self._converters[fmt]
            format_missing = []

            for pkg_name, _ in metadata.required_packages:
                try:
                    # Try importing the package
                    importlib.import_module(pkg_name.replace("-", "_"))
                except ImportError:
                    format_missing.append(pkg_name)

            if format_missing:
                missing[fmt] = format_missing

        return missing

    def auto_discover(self) -> None:
        """Auto-discover and register converters from the converters package.

        This method is called automatically on first use but can be
        called manually to refresh the registry.
        """
        if self._initialized:
            return

        # Import all converter modules to trigger their registration
        converter_modules = [
            "pdf2markdown",
            "docx2markdown",
            "pptx2markdown",
            "html2markdown",
            "eml2markdown",
            "ipynb2markdown",
            "epub2markdown",
            "mhtml2markdown",
            "odf2markdown",
            "rtf2markdown",
        ]

        for module_name in converter_modules:
            try:
                # This will trigger the module's registration code
                module_path = f"all2md.converters.{module_name}"
                module = importlib.import_module(module_path)

                # Look for CONVERTER_METADATA in the module
                if hasattr(module, "CONVERTER_METADATA"):
                    self.register(module.CONVERTER_METADATA)
            except ImportError as e:
                # Module has unmet dependencies, skip it
                logger.debug(f"Could not load {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error loading {module_name}: {e}")

        self._initialized = True


# Global registry instance
registry = ConverterRegistry()
