"""Converter registry for dynamic converter management.

This module implements a registry pattern for converters, enabling:
- Lazy loading of converter modules
- Dynamic converter discovery and registration
- Proper dependency error handling
- Format detection and converter routing
"""

from __future__ import annotations

import importlib
import importlib.metadata
import io
import logging
import mimetypes
from pathlib import Path
from typing import IO, Callable, Dict, List, Optional, Tuple, Union

from .converter_metadata import ConverterMetadata
from .exceptions import DependencyError, FormatError

logger = logging.getLogger(__name__)


def _check_package_installed(package_name: str) -> bool:
    """Check if a package is installed and importable.

    Parameters
    ----------
    package_name : str
        Name of the package to check

    Returns
    -------
    bool
        True if package is installed and importable
    """
    # Mapping from package names to their actual import names
    # Many packages have different install names vs import names
    package_import_map = {
        'python-docx': 'docx',
        'beautifulsoup4': 'bs4',
        'python-pptx': 'pptx',
        'odfpy': 'odf',
        'pillow': 'PIL',
        'pyyaml': 'yaml',
        # Add more mappings as needed
    }

    # Determine the correct import name
    import_names_to_try = []

    # First try the mapped name if it exists
    if package_name.lower() in package_import_map:
        import_names_to_try.append(package_import_map[package_name.lower()])

    # Then try replacing hyphens with underscores
    if '-' in package_name:
        import_names_to_try.append(package_name.replace("-", "_"))

    # Finally try the original package name
    import_names_to_try.append(package_name)

    # Try each possible import name
    for import_name in import_names_to_try:
        try:
            importlib.import_module(import_name)
            return True
        except ImportError:
            continue

    return False


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
                if not _check_package_installed(pkg_name):
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
        elif isinstance(input_data, io.IOBase):
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

        # Check magic bytes first
        for format_name, metadata in sorted_converters:
            if metadata.matches_magic_bytes(content):
                return format_name

        # Check custom content detectors
        for format_name, metadata in sorted_converters:
            if metadata.content_detector and metadata.content_detector(content):
                logger.debug(f"Format detected via content detector: {format_name}")
                return format_name

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

    def check_dependencies(self, format_name: Optional[str] = None, input_data: Optional[Union[str, Path, IO[bytes], bytes]] = None) -> Dict[str, List[str]]:
        """Check which dependencies are missing.

        Parameters
        ----------
        format_name : str, optional
            Check specific format, or all if None
        input_data : various types, optional
            Input data to use for context-aware dependency checking

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

        # Get content for context-aware dependency checking
        content = None
        if input_data:
            if isinstance(input_data, bytes):
                content = input_data
            elif isinstance(input_data, (str, Path)):
                try:
                    with open(input_data, 'rb') as f:
                        content = f.read(1024)  # Read first 1KB for analysis
                except Exception:
                    pass
            elif isinstance(input_data, io.IOBase):
                try:
                    pos = input_data.tell()
                    input_data.seek(0)
                    content = input_data.read(1024)
                    input_data.seek(pos)
                except Exception:
                    pass

        for fmt in formats_to_check:
            if fmt not in self._converters:
                continue

            metadata = self._converters[fmt]
            format_missing = []

            # Use context-aware dependency checking if available
            required_packages = metadata.get_required_packages_for_content(content)

            for pkg_name, _ in required_packages:
                if not _check_package_installed(pkg_name):
                    format_missing.append(pkg_name)

            if format_missing:
                missing[fmt] = format_missing

        return missing

    def auto_discover(self) -> None:
        """Auto-discover and register converters from multiple sources.

        This method:
        1. Scans the converters directory for Python modules with CONVERTER_METADATA
        2. Discovers plugins via entry points from installed packages

        This enables a true plug-and-play system for both internal and external converters.
        """
        if self._initialized:
            return

        # Discover internal converter modules by scanning the converters package
        converter_modules = self._discover_converter_modules()

        for module_name in converter_modules:
            try:
                # Import the module
                module_path = f"all2md.converters.{module_name}"
                module = importlib.import_module(module_path)

                # Look for CONVERTER_METADATA in the module
                if hasattr(module, "CONVERTER_METADATA"):
                    self.register(module.CONVERTER_METADATA)
                    logger.debug(f"Auto-registered internal converter: {module_name}")
            except ImportError as e:
                # Module has unmet dependencies, skip it
                logger.debug(f"Could not load {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error loading {module_name}: {e}")

        # Discover external plugins via entry points
        self._discover_plugins()

        self._initialized = True

    def _discover_converter_modules(self) -> List[str]:
        """Discover converter modules by scanning the converters package directory.

        Returns
        -------
        List[str]
            List of module names found in the converters package
        """
        converter_modules = []

        try:
            # Import the converters package to get its path
            import all2md.converters as converters_package
            converters_path = Path(converters_package.__file__).parent

            # Scan for Python files in the converters directory
            for file_path in converters_path.glob("*.py"):
                module_name = file_path.stem

                # Skip __init__.py and any private modules
                if module_name != "__init__" and not module_name.startswith("_"):
                    converter_modules.append(module_name)

            logger.debug(f"Discovered converter modules: {converter_modules}")

        except Exception as e:
            logger.warning(f"Failed to discover converter modules: {e}")
            # Fallback to empty list - no converters will be registered

        return converter_modules

    def _discover_plugins(self) -> None:
        """Discover and register third-party converter plugins via entry points.

        This method scans for installed packages that define converters
        via the 'all2md.converters' entry point group.
        """
        try:
            # Discover entry points for the all2md.converters group
            entry_points = importlib.metadata.entry_points(group="all2md.converters")

            for entry_point in entry_points:
                try:
                    # Load the converter metadata from the entry point
                    converter_metadata = entry_point.load()

                    # Validate that it's actually a ConverterMetadata instance
                    if isinstance(converter_metadata, ConverterMetadata):
                        # Check if we already have a converter with this format name
                        if converter_metadata.format_name in self._converters:
                            dist_name = entry_point.dist.name if entry_point.dist else "unknown"
                            logger.warning(
                                f"Plugin '{entry_point.name}' from '{dist_name}' "
                                f"conflicts with existing converter for format '{converter_metadata.format_name}'. "
                                f"Skipping plugin."
                            )
                            continue

                        self.register(converter_metadata)
                        dist_name = entry_point.dist.name if entry_point.dist else "unknown"
                        logger.info(
                            f"Registered plugin converter: {converter_metadata.format_name} "
                            f"from package '{dist_name}'"
                        )
                    else:
                        dist_name = entry_point.dist.name if entry_point.dist else "unknown"
                        logger.warning(
                            f"Entry point '{entry_point.name}' from '{dist_name}' "
                            f"did not return a ConverterMetadata instance"
                        )

                except Exception as e:
                    dist_name = entry_point.dist.name if entry_point.dist else "unknown"
                    logger.warning(
                        f"Failed to load plugin '{entry_point.name}' from "
                        f"'{dist_name}': {e}"
                    )

        except Exception as e:
            logger.debug(f"No plugins found or error discovering plugins: {e}")


# Global registry instance
registry = ConverterRegistry()
