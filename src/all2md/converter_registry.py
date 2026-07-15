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
from typing import IO, Dict, List, NoReturn, Optional, Tuple, Union

from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, FormatError

logger = logging.getLogger(__name__)


def _sanitize_for_log(value: str) -> str:
    """Sanitize a string for safe logging to prevent log injection.

    Replaces newlines and carriage returns with escape sequences to prevent
    attackers from injecting fake log entries.

    Parameters
    ----------
    value : str
        The string to sanitize

    Returns
    -------
    str
        Sanitized string safe for logging

    """
    return value.replace("\n", "\\n").replace("\r", "\\r")


def check_package_installed(import_name: str) -> bool:
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
        # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def _load_class(class_spec: Union[str, type, None], default_module_path: str, class_type_name: str) -> Optional[type]:
    """Load parsers, renderers, and options classes from various specifications.

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
        if "." in class_spec:
            # Parse module and class name
            module_path, class_name = class_spec.rsplit(".", 1)
            try:
                # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
                module = importlib.import_module(module_path)
                return getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not load {class_type_name} class '{class_spec}': {e}")
                return None
        else:
            # Simple name - look in default module
            try:
                # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
                module = importlib.import_module(default_module_path)
                return getattr(module, class_spec, None)
            except (ImportError, AttributeError) as e:
                logger.warning(
                    f"{class_type_name.capitalize()} class '{_sanitize_for_log(class_spec)}' "
                    f"not found in {default_module_path}: {_sanitize_for_log(str(e))}"
                )
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
    """Registry for managing document parsers and renderers.

    This class provides a central registry for all parsers and renderers, handling:
    - Converter registration and discovery
    - Priority-based parser/renderer selection
    - Format detection from files/content
    - Lazy loading of converter modules
    - Dependency checking and error handling

    The registry supports multiple parsers and renderers for the same format,
    with priority-based selection. Higher priority converters are tried first,
    allowing plugins to override built-in converters or provide fallback options.

    Attributes
    ----------
    _instance : ConverterRegistry or None
        Singleton instance of the registry
    _converters : dict
        Registered converters by format name, with each format mapping to a
        priority-sorted list of ConverterMetadata objects
    _initialized : bool
        Whether auto-discovery has been run

    """

    _instance: Optional[ConverterRegistry] = None
    _converters: Dict[str, List[ConverterMetadata]] = {}
    _initialized: bool = False
    _sorted_converters_cache: Optional[List[Tuple[str, ConverterMetadata]]] = None

    def __new__(cls) -> ConverterRegistry:
        """Create or return singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._converters = {}
            cls._instance._initialized = False
            cls._instance._sorted_converters_cache = None
        return cls._instance

    def _sorted_converter_list(self) -> List[Tuple[str, ConverterMetadata]]:
        """Return all converters flattened and sorted by priority (highest first).

        ``detect_format`` is on the conversion hot path and previously rebuilt and
        re-sorted this list on every call. The registry only changes via
        ``register``/``unregister``, so we memoize the sorted list and invalidate it
        there. Returns the shared cached list; callers must treat it as read-only.
        """
        if self._sorted_converters_cache is None:
            all_converters = [
                (format_name, metadata)
                for format_name, metadata_list in self._converters.items()
                for metadata in metadata_list
            ]
            self._sorted_converters_cache = sorted(all_converters, key=lambda x: x[1].priority, reverse=True)
        return self._sorted_converters_cache

    def register(self, metadata: ConverterMetadata) -> None:
        """Register a converter with its metadata.

        Parameters
        ----------
        metadata : ConverterMetadata
            Converter metadata to register

        Notes
        -----
        Multiple converters can be registered for the same format_name with
        different priorities. When retrieving a parser or renderer, the highest
        priority converter with available dependencies is used.

        Converters are automatically sorted by priority (highest first) when
        registered. If no priority is specified, it defaults to 0.

        """
        if metadata.format_name not in self._converters:
            self._converters[metadata.format_name] = []
            logger.debug(f"Registered converter: {metadata.format_name} (priority={metadata.priority})")
        else:
            logger.debug(f"Adding additional converter for '{metadata.format_name}' (priority={metadata.priority})")

        # Add to list and sort by priority (highest first)
        self._converters[metadata.format_name].append(metadata)
        self._converters[metadata.format_name].sort(key=lambda m: m.priority, reverse=True)
        self._sorted_converters_cache = None

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
            self._sorted_converters_cache = None
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

        Notes
        -----
        Returns the parser options class from the highest priority converter
        that has a parser_options_class specified.

        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(format_type=format_name, supported_formats=available)

        # Get from highest priority converter that has parser options
        for metadata in self._converters[format_name]:
            if metadata.parser_options_class is not None:
                options_class = _load_options_class(metadata.parser_options_class)
                if options_class is not None:
                    return options_class

        return None

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

        Notes
        -----
        Returns the renderer options class from the highest priority converter
        that has a renderer_options_class specified.

        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(format_type=format_name, supported_formats=available)

        # Get from highest priority converter that has renderer options
        for metadata in self._converters[format_name]:
            if metadata.renderer_options_class is not None:
                options_class = _load_options_class(metadata.renderer_options_class)
                if options_class is not None:
                    return options_class

        return None

    def get_parser(self, format_name: str) -> type:
        """Get parser class for a format with priority-based selection.

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
            If format not registered or no parser available
        DependencyError
            If required dependencies not installed

        Notes
        -----
        When multiple converters are registered for the same format, this method
        tries them in priority order (highest first). It returns the first parser
        that can be successfully loaded. This allows for graceful fallback if
        high-priority converters have missing dependencies.

        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(format_type=format_name, supported_formats=available)

        # Try each converter in priority order (already sorted)
        for metadata in self._converters[format_name]:
            if metadata.parser_class is None:
                continue

            # Try to load the parser class
            parser_class = _load_parser_class(metadata.parser_class, format_name)

            if parser_class is not None:
                logger.debug(
                    f"Selected parser for '{format_name}': {metadata.get_parser_display_name()} "
                    f"(priority={metadata.priority})"
                )
                return parser_class

        # No parser could be loaded — surface a dependency error if that's why.
        self._raise_converter_unavailable(format_name, "parser", "parse")

    def get_renderer(self, format_name: str) -> type:
        """Get renderer class for a format with priority-based selection.

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
            If format not registered or no renderer available

        Notes
        -----
        When multiple converters are registered for the same format, this method
        tries them in priority order (highest first). It returns the first renderer
        that can be successfully loaded. This allows for graceful fallback if
        high-priority converters have missing dependencies.

        """
        if format_name not in self._converters:
            available = list(self._converters.keys())
            raise FormatError(format_type=format_name, supported_formats=available)

        # Try each converter in priority order (already sorted)
        for metadata in self._converters[format_name]:
            if metadata.renderer_class is None:
                continue

            # Try to load the renderer class
            renderer_class = _load_renderer_class(metadata.renderer_class, format_name)

            if renderer_class is not None:
                logger.debug(
                    f"Selected renderer for '{_sanitize_for_log(format_name)}': "
                    f"{metadata.get_renderer_display_name()} (priority={metadata.priority})"
                )
                return renderer_class

        # No renderer could be loaded — surface a dependency error if that's why.
        self._raise_converter_unavailable(format_name, "renderer", "render")

    def _raise_converter_unavailable(self, format_name: str, kind: str, operation: str) -> NoReturn:
        """Raise the most helpful error when a converter exists but won't load.

        Because converter metadata is now always registered (from the manifest),
        a parser/renderer class failing to load is usually a missing optional
        dependency rather than an unknown format. Check dependencies and raise a
        ``DependencyError`` with install guidance when that's the cause;
        otherwise fall back to ``FormatError``.

        Parameters
        ----------
        format_name : str
            The format whose converter could not be loaded.
        kind : str
            "parser" or "renderer" (for the fallback message).
        operation : str
            "parse" or "render" (for dependency checking).

        """
        metadata_list = self._converters.get(format_name, [])
        missing = self.check_dependencies(format_name, operation=operation)
        missing_pkgs = missing.get(format_name)
        if missing_pkgs and metadata_list:
            metadata = metadata_list[0]
            required = (
                metadata.parser_required_packages if operation == "parse" else metadata.renderer_required_packages
            )
            pkg_tuples = [(name, ver) for (name, _import, ver) in required if name in missing_pkgs]
            if not pkg_tuples:
                pkg_tuples = [(name, "") for name in missing_pkgs]
            install_command = metadata.get_install_command()
            raise DependencyError(
                converter_name=format_name,
                missing_packages=pkg_tuples,
                install_command=install_command if isinstance(install_command, str) else "",
                message=metadata.import_error_message or None,
            )
        raise FormatError(f"No {kind} available for format '{format_name}'. Tried {len(metadata_list)} converter(s).")

    def detect_format(
        self,
        input_data: Union[str, Path, IO[bytes], bytes],
        hint: Optional[str] = None,
    ) -> str:
        """Detect format from input data.

        Uses multiple strategies:
        1. Explicit hint if provided
        2. Filename extension matching (validated with content_detector if available)
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

        # Get filename for extension-based detection
        filename: str | None = None
        if isinstance(input_data, (str, Path)):
            filename = str(input_data)
        elif hasattr(input_data, "name") or hasattr(input_data, "filename"):
            file_obj_name: str | None = getattr(input_data, "name", None) or getattr(input_data, "filename", None)
            if file_obj_name and file_obj_name != "unknown":
                filename = file_obj_name

        # Get content for validation
        content: bytes | str | None = None
        if isinstance(input_data, bytes):
            content = input_data
        elif isinstance(input_data, (str, Path)):
            # Read first 1KB for detection
            try:
                with open(input_data, "rb") as f:
                    content = f.read(1024)
            except Exception:
                pass
        elif isinstance(input_data, io.IOBase) or (
            hasattr(input_data, "read")
            and hasattr(input_data, "tell")
            and hasattr(input_data, "read")
            and hasattr(input_data, "seek")
        ):
            # Save position and read sample
            try:
                pos = input_data.tell()
                input_data.seek(0)
                content = input_data.read(1024)
                input_data.seek(pos)
            except Exception as e:
                logger.debug(f"Error reading input as file: {e!r}")

        # Normalize content to bytes if it's a string (from text streams)
        if isinstance(content, str):
            content = content.encode("utf-8", errors="ignore")

        # Try filename-based detection with content validation
        if filename:
            format_name = self._detect_by_filename(filename, content)
            if format_name:
                logger.debug(f"Format detected from filename: {format_name}")
                return format_name

        # Try content-based detection
        if content:
            format_name = self._detect_by_content(content)
            if format_name:
                logger.debug(f"Format detected from content: {format_name}")
                return format_name

        # Default fallback
        logger.debug("No format detected, defaulting to txt")
        return "plaintext"

    def _detect_by_filename(self, filename: str, content: Optional[bytes] = None) -> Optional[str]:
        """Detect format from filename with optional content validation.

        Parameters
        ----------
        filename : str
            Filename to analyze
        content : bytes, optional
            File content for validation with content_detector

        Returns
        -------
        str or None
            Format name if detected and validated

        Notes
        -----
        If content is provided and a converter has a content_detector, the content
        will be validated before returning that format. This prevents false positives
        for ambiguous extensions like .json (which could be OpenAPI, generic JSON data, etc.)

        """
        # Flattened, priority-sorted converters (memoized; see _sorted_converter_list)
        sorted_converters = self._sorted_converter_list()

        # Check extensions with content validation
        for format_name, metadata in sorted_converters:
            if metadata.matches_extension(filename):
                # If content is available and converter has a content_detector, validate.
                # resolve_content_detector() imports the detector lazily, so the common
                # case (extension matches a format with no detector, e.g. markdown) stays
                # import-free.
                detector = metadata.resolve_content_detector() if content else None
                if detector and content is not None:
                    if detector(content):
                        logger.debug(f"Format '{format_name}' matched extension and validated by content_detector")
                        return format_name
                    else:
                        logger.debug(f"Format '{format_name}' matched extension but failed content_detector validation")
                        continue  # Try next converter
                else:
                    # No content detector or no content available - trust extension match
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
        # Flattened, priority-sorted converters (memoized; see _sorted_converter_list)
        sorted_converters = self._sorted_converter_list()

        # Check magic bytes first
        for format_name, metadata in sorted_converters:
            if metadata.matches_magic_bytes(content):
                return format_name

        # Check custom content detectors. resolve_content_detector() imports each
        # detector lazily; only the (few) formats that declare one are imported,
        # and only on this content-based detection path.
        for format_name, metadata in sorted_converters:
            detector = metadata.resolve_content_detector()
            if detector and detector(content):
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

    def get_format_info(self, format_name: str) -> Optional[List[ConverterMetadata]]:
        """Get metadata list for a specific format.

        Parameters
        ----------
        format_name : str
            Format to get info for

        Returns
        -------
        list of ConverterMetadata or None
            List of metadata objects for the format (sorted by priority), or None if not registered

        Notes
        -----
        Returns all registered converters for the format, sorted by priority (highest first).
        For backward compatibility with code expecting a single metadata object, you can access
        the first element of the returned list to get the highest priority converter.

        """
        return self._converters.get(format_name)

    def get_default_extension_for_format(self, format_name: str) -> str:
        """Return the preferred file extension for a format.

        Parameters
        ----------
        format_name : str
            Converter format name (e.g., "markdown", "docx").

        Returns
        -------
        str
            Preferred extension beginning with a leading dot.

        """
        if format_name in ("auto", "markdown"):
            return ".md"

        metadata_list = self.get_format_info(format_name)
        if metadata_list:
            metadata = metadata_list[0]
            if metadata.extensions:
                extension = metadata.extensions[0]
                return extension if extension.startswith(".") else f".{extension}"

        return f".{format_name}" if not format_name.startswith(".") else format_name

    def get_all_extensions(self) -> set[str]:
        """Get all supported file extensions from registered converters.

        This method dynamically queries all registered converters and collects
        their supported file extensions. Useful for CLI file filtering, format
        detection, and determining which files can be processed.

        Returns
        -------
        set[str]
            Set of all supported file extensions with leading dots (e.g., {'.pdf', '.docx', '.md'})

        Notes
        -----
        This method provides a dynamic alternative to hardcoded extension lists.
        When new parsers are registered (including via plugins), their extensions
        are automatically included.

        Examples
        --------
        Check if a file extension is supported:
            >>> extensions = registry.get_all_extensions()
            >>> '.webarchive' in extensions
            True
            >>> '.xyz' in extensions
            False

        Get all supported extensions for file filtering:
            >>> from pathlib import Path
            >>> supported = registry.get_all_extensions()
            >>> files = [f for f in Path('.').glob('*') if f.suffix in supported]

        """
        all_extensions: set[str] = set()
        for format_name in self.list_formats():
            format_info = self.get_format_info(format_name)
            if format_info:
                for metadata in format_info:
                    if metadata.extensions:
                        all_extensions.update(metadata.extensions)
        return all_extensions

    def check_dependencies(
        self,
        format_name: Optional[str] = None,
        input_data: Optional[Union[str, Path, IO[bytes], bytes]] = None,
        operation: str = "both",
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

        formats_to_check = [format_name] if format_name else self._converters.keys()

        # Get content for context-aware dependency checking
        content: bytes | str | None = None
        if input_data:
            if isinstance(input_data, bytes):
                content = input_data
            elif isinstance(input_data, (str, Path)):
                try:
                    with open(input_data, "rb") as f:
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

        # Normalize content to bytes if it's a string (from text streams)
        if isinstance(content, str):
            content = content.encode("utf-8", errors="ignore")

        for fmt in formats_to_check:
            if fmt not in self._converters:
                continue

            # Check dependencies for all converters for this format
            # Use the highest priority converter's dependencies
            metadata_list = self._converters[fmt]
            if not metadata_list:
                continue

            # Check the first (highest priority) converter
            metadata = metadata_list[0]
            format_missing = []

            # Use context-aware dependency checking if available
            # Pass both content sample, original input_data, and operation type for accurate detection
            required_packages = metadata.get_required_packages_for_content(content, input_data, operation)

            for pkg_name, import_name, _ in required_packages:
                if not check_package_installed(import_name):
                    format_missing.append(pkg_name)

            if format_missing:
                missing[fmt] = format_missing

        return missing

    def auto_discover(self) -> None:
        """Register built-in converters from the manifest, then discover plugins.

        Built-in converter metadata is registered from the generated manifest
        (``all2md._converter_manifest``), which is a leaf module of pure literals.
        This avoids importing all ~40 parser/renderer modules at startup just to
        read their ``CONVERTER_METADATA`` — the parser/renderer/options classes
        and content detectors are imported lazily on first use instead. This is
        the primary CLI/import startup optimization.

        External plugins are still discovered eagerly via entry points.

        The manifest is kept in sync with the live modules by
        ``scripts/generate_converter_manifest.py`` and guarded by a unit test.
        If the manifest module is entirely absent (e.g. during its own first
        generation, or a broken install) we fall back to the slow directory
        scan so the library still works; a present-but-empty manifest is treated
        as corruption and raises.
        """
        if self._initialized:
            return

        try:
            # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
            from all2md._converter_manifest import get_manifest_records
        except ModuleNotFoundError:
            logger.warning(
                "Converter manifest (all2md._converter_manifest) not found; falling back to "
                "directory scanning. Generate it with: python scripts/generate_converter_manifest.py --update"
            )
            self.discover_by_scanning()
        else:
            records = get_manifest_records()
            if not records:
                raise RuntimeError(
                    "Converter manifest (all2md._converter_manifest) is empty. "
                    "Regenerate it with: python scripts/generate_converter_manifest.py --update"
                )
            for metadata in records:
                self.register(metadata)

        # Discover external plugins via entry points (eager, unchanged)
        self._discover_plugins()

        self._initialized = True

    def discover_by_scanning(self) -> None:
        """Discover converters by importing every parser/renderer module.

        This is the original, slow auto-discovery: it scans the ``parsers`` and
        ``renderers`` packages, imports each module, and reads its
        ``CONVERTER_METADATA``. It is retained only for the manifest generator
        script and the manifest sync test, which run it against a fresh
        registry. It is NOT used during normal startup (see ``auto_discover``).
        """
        # Discover internal converter modules by scanning the parsers package
        converter_modules = self._discover_converter_modules("parsers")

        for module_name in converter_modules:
            try:
                # Import the module
                module_path = f"all2md.parsers.{module_name}"
                # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
                module = importlib.import_module(module_path)

                # Look for CONVERTER_METADATA in the module
                if hasattr(module, "CONVERTER_METADATA"):
                    self.register(module.CONVERTER_METADATA)
                    logger.debug(f"Auto-registered parser converter: {module_name}")
            except ImportError as e:
                # Module has unmet dependencies, skip it
                logger.debug(f"Could not load parser {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error loading parser {module_name}: {e}")

        # Discover standalone renderer modules by scanning the renderers package
        renderer_modules = self._discover_converter_modules("renderers")

        for module_name in renderer_modules:
            try:
                # Import the module
                module_path = f"all2md.renderers.{module_name}"
                # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
                module = importlib.import_module(module_path)

                # Look for CONVERTER_METADATA in the module
                if hasattr(module, "CONVERTER_METADATA"):
                    self.register(module.CONVERTER_METADATA)
                    logger.debug(f"Auto-registered standalone renderer: {module_name}")
            except ImportError as e:
                # Module has unmet dependencies, skip it
                logger.debug(f"Could not load renderer {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error loading renderer {module_name}: {e}")

        # NOTE: plugin discovery and the _initialized flag are intentionally NOT
        # handled here. Scanning only registers built-in converters (so the
        # generated manifest never bakes in environment-specific plugins);
        # auto_discover() owns plugin discovery and the initialized flag.

    def _discover_converter_modules(self, package_name: str) -> List[str]:
        """Discover converter modules by scanning a package directory.

        Parameters
        ----------
        package_name : str
            Name of the package to scan ("parsers" or "renderers")

        Returns
        -------
        List[str]
            List of module names found in the package

        """
        converter_modules: List[str] = []

        try:
            # Import the package to get its path
            # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
            package = importlib.import_module(f"all2md.{package_name}")
            if package.__file__ is None:
                logger.warning(f"Package {package_name} has no __file__ attribute")
                return converter_modules

            package_path = Path(package.__file__).parent

            # Scan for Python files in the package directory
            for file_path in package_path.glob("*.py"):
                module_name = file_path.stem

                # Skip __init__.py and any private modules
                if module_name != "__init__" and not module_name.startswith("_"):
                    converter_modules.append(module_name)

            logger.debug(f"Discovered {package_name} modules: {converter_modules}")

        except Exception as e:
            logger.warning(f"Failed to discover {package_name} modules: {e}")
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
                        # Register the plugin converter (may add to existing format)
                        self.register(converter_metadata)
                        dist_name = entry_point.dist.name if entry_point.dist else "unknown"
                        logger.info(
                            f"Registered plugin converter: {converter_metadata.format_name} "
                            f"(priority={converter_metadata.priority}) from package '{dist_name}'"
                        )
                    else:
                        dist_name = entry_point.dist.name if entry_point.dist else "unknown"
                        logger.warning(
                            f"Entry point '{entry_point.name}' from '{dist_name}' "
                            f"did not return a ConverterMetadata instance"
                        )

                except Exception as e:
                    dist_name = entry_point.dist.name if entry_point.dist else "unknown"
                    logger.warning(f"Failed to load plugin '{entry_point.name}' from " f"'{dist_name}': {e}")

        except Exception as e:
            logger.debug(f"No plugins found or error discovering plugins: {e}")


# Global registry instance
registry = ConverterRegistry()
