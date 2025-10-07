"""Converter registry for dynamic converter management.

This module implements a registry pattern for parsers, enabling:
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
from typing import IO, Dict, List, Optional, Union

from .converter_metadata import ConverterMetadata
from .exceptions import FormatError

logger = logging.getLogger(__name__)


def _check_package_installed(import_name: str) -> bool:
    """Check if a package is installed and importable.

    Parameters
    ----------
    import_name : str
        Name to use in import statement (e.g., 'docx' for python-docx package)

    Returns
    -------
    bool
        True if package is installed and importable

    """
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def _load_class(
    class_spec: Union[str, type, None],
    default_module_path: str,
    class_type_name: str
) -> Optional[type]:
    """Generic class loader for parsers, renderers, and options classes.

    Parameters
    ----------
    class_spec : Union[str, type, None]
        Class specification. Can be:
        - Simple class name (e.g., "PdfOptions") - looks in default_module_path
        - Fully qualified name (e.g., "myplugin.options.MyOptions")
        - Direct class reference
        - None
    default_module_path : str
        Module path to use for simple class names (e.g., "all2md.options")
    class_type_name : str
        Type name for error messages (e.g., "options", "parser", "renderer")

    Returns
    -------
    Optional[type]
        The loaded class or None

    """
    if class_spec is None:
        return None
    elif isinstance(class_spec, type):
        # Direct class reference
        return class_spec
    elif isinstance(class_spec, str):
        # String specification
        # Check if it contains a dot (fully qualified)
        if '.' in class_spec:
            # Parse module and class name
            module_path, class_name = class_spec.rsplit('.', 1)
            try:
                module = importlib.import_module(module_path)
                return getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not load {class_type_name} class '{class_spec}': {e}")
                return None
        else:
            # Simple name - look in default module
            try:
                module = importlib.import_module(default_module_path)
                return getattr(module, class_spec, None)
            except (ImportError, AttributeError) as e:
                logger.warning(
                    f"{class_type_name.capitalize()} class '{class_spec}' "
                    f"not found in {default_module_path}: {e}"
                )
                return None
    else:
        # This shouldn't happen with proper typing, but handle it gracefully
        logger.warning(f"Invalid {class_type_name}_class specification type: {type(class_spec)}")
        return None


def _load_options_class(options_class_spec: Union[str, type, None]) -> Optional[type]:
    """Load options class from various specifications.

    Parameters
    ----------
    options_class_spec : Union[str, type, None]
        Options class specification. Can be:
        - Simple class name (e.g., "PdfOptions") - looks in all2md.options
        - Fully qualified name (e.g., "myplugin.options.MyOptions")
        - Direct class reference
        - None

    Returns
    -------
    Optional[type]
        The loaded options class or None

    """
    return _load_class(options_class_spec, "all2md.options", "options")


def _load_parser_class(parser_class_spec: Union[str, type, None], format_name: str) -> Optional[type]:
    """Load parser class from various specifications.

    Parameters
    ----------
    parser_class_spec : Union[str, type, None]
        Parser class specification. Can be:
        - Simple class name (e.g., "DocxParser") - looks in all2md.parsers.{format}
        - Fully qualified name (e.g., "myplugin.parsers.MyParser")
        - Direct class reference
        - None
    format_name : str
        Format name for default module lookup

    Returns
    -------
    Optional[type]
        The loaded parser class or None

    """
    return _load_class(parser_class_spec, f"all2md.parsers.{format_name}", "parser")


def _load_renderer_class(renderer_class_spec: Union[str, type, None], format_name: str) -> Optional[type]:
    """Load renderer class from various specifications.

    Parameters
    ----------
    renderer_class_spec : Union[str, type, None]
        Renderer class specification. Can be:
        - Simple class name (e.g., "DocxRenderer") - looks in all2md.renderers.{format}
        - Fully qualified name (e.g., "myplugin.renderers.MyRenderer")
        - Direct class reference
        - None
    format_name : str
        Format name for default module lookup

    Returns
    -------
    Optional[type]
        The loaded renderer class or None

    """
    return _load_class(renderer_class_spec, f"all2md.renderers.{format_name}", "renderer")


class ConverterRegistry:
    """Registry for managing document parsers.

    This class provides a central registry for all parsers, handling:
    - Converter registration and discovery
    - Format detection from files/content
    - Lazy loading of converter modules
    - Dependency checking and error handling

    Attributes
    ----------
    _instance : ConverterRegistry or None
        Singleton instance of the registry
    _converters : dict
        Registered parsers by format name
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

        Notes
        -----
        If a converter with the same format_name is already registered, it will
        be overwritten and a warning will be logged.

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

    def get_parser_options_class(self, format_name: str) -> Optional[type]:
        """Get parser options class for a format.

        Parameters
        ----------
        format_name : str
            Format name to get parser options class for

        Returns
        -------
        type or None
            Parser options class or None if format has no parser options

        Raises
        ------
        FormatError
            If format not registered

        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(
                format_type=format_name,
                supported_formats=available
            )

        metadata = self._converters[format_name]
        return _load_options_class(metadata.parser_options_class)

    def get_renderer_options_class(self, format_name: str) -> Optional[type]:
        """Get renderer options class for a format.

        Parameters
        ----------
        format_name : str
            Format name to get renderer options class for

        Returns
        -------
        type or None
            Renderer options class or None if format has no renderer options

        Raises
        ------
        FormatError
            If format not registered

        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(
                format_type=format_name,
                supported_formats=available
            )

        metadata = self._converters[format_name]
        return _load_options_class(metadata.renderer_options_class)

    def get_parser(self, format_name: str) -> type:
        """Get parser class for a format.

        Parameters
        ----------
        format_name : str
            Format name to get parser for

        Returns
        -------
        type
            Parser class (subclass of BaseParser)

        Raises
        ------
        FormatError
            If format not registered or parser not available
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

        # Try to load the parser class
        parser_class = _load_parser_class(metadata.parser_class, format_name)

        if parser_class is None:
            raise FormatError(
                f"No parser available for format '{format_name}'. "
                f"Parser class specification: {metadata.parser_class}"
            )

        return parser_class

    def get_renderer(self, format_name: str) -> type:
        """Get renderer class for a format.

        Parameters
        ----------
        format_name : str
            Format name to get renderer for

        Returns
        -------
        type
            Renderer class (subclass of BaseRenderer)

        Raises
        ------
        FormatError
            If format not registered or renderer not available

        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(
                format_type=format_name,
                supported_formats=available
            )

        metadata = self._converters[format_name]

        # Try to load the renderer class
        renderer_class = _load_renderer_class(metadata.renderer_class, format_name)

        if renderer_class is None:
            raise FormatError(
                f"No renderer available for format '{format_name}'. "
                f"Renderer class specification: {metadata.renderer_class}"
            )

        return renderer_class

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

    def check_dependencies(
        self,
        format_name: Optional[str] = None,
        input_data: Optional[Union[str, Path, IO[bytes], bytes]] = None,
        operation: str = "both"
    ) -> Dict[str, List[str]]:
        """Check which dependencies are missing.

        Parameters
        ----------
        format_name : str, optional
            Check specific format, or all if None
        input_data : various types, optional
            Input data to use for context-aware dependency checking
        operation : str, default="both"
            Operation type to check dependencies for: "parse", "render", or "both"

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
            # Pass both content sample, original input_data, and operation type for accurate detection
            required_packages = metadata.get_required_packages_for_content(content, input_data, operation)

            for pkg_name, import_name, _ in required_packages:
                if not _check_package_installed(import_name):
                    format_missing.append(pkg_name)

            if format_missing:
                missing[fmt] = format_missing

        return missing

    def auto_discover(self) -> None:
        """Auto-discover and register parsers from multiple sources.

        This method:
        1. Scans the parsers directory for Python modules with CONVERTER_METADATA
        2. Discovers plugins via entry points from installed packages

        This enables a true plug-and-play system for both internal and external parsers.
        """
        if self._initialized:
            return

        # Discover internal converter modules by scanning the parsers package
        converter_modules = self._discover_converter_modules()

        for module_name in converter_modules:
            try:
                # Import the module
                module_path = f"all2md.parsers.{module_name}"
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
        """Discover converter modules by scanning the parsers package directory.

        Returns
        -------
        List[str]
            List of module names found in the parsers package

        """
        converter_modules = []

        try:
            # Import the parsers package to get its path
            import all2md.parsers as converters_package
            converters_path = Path(converters_package.__file__).parent

            # Scan for Python files in the parsers directory
            for file_path in converters_path.glob("*.py"):
                module_name = file_path.stem

                # Skip __init__.py and any private modules
                if module_name != "__init__" and not module_name.startswith("_"):
                    converter_modules.append(module_name)

            logger.debug(f"Discovered converter modules: {converter_modules}")

        except Exception as e:
            logger.warning(f"Failed to discover converter modules: {e}")
            # Fallback to empty list - no parsers will be registered

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
