#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/registry.py
"""Transform registry for dynamic transform discovery and management.

This module implements a registry pattern for AST transforms, enabling:
- Lazy loading of transform modules
- Plugin discovery via entry points
- Dependency resolution and ordering
- Transform lookup and instantiation

The registry follows the same pattern as `ConverterRegistry` for consistency.

Examples
--------
Register a transform:

    >>> from all2md.transforms import TransformRegistry, TransformMetadata
    >>> registry = TransformRegistry()
    >>> registry.register(my_transform_metadata)

Get a transform:

    >>> transformer = registry.get_transform("remove-images")

List all transforms:

    >>> names = registry.list_transforms()
    >>> for name in names:
    ...     metadata = registry.get_metadata(name)
    ...     print(f"{name}: {metadata.description}")

"""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
from typing import Any, Optional

from all2md.ast.transforms import NodeTransformer

from .metadata import TransformMetadata

logger = logging.getLogger(__name__)


class TransformRegistry:
    """Registry for managing AST transforms.

    This singleton class provides a central registry for all transforms,
    handling:
    - Transform registration and discovery
    - Entry point plugin loading
    - Dependency resolution
    - Lazy instantiation

    The registry automatically discovers transforms via the `all2md.transforms`
    entry point group on first access.

    Examples
    --------
    Get the registry instance:
        >>> registry = TransformRegistry()

    Register a transform:
        >>> registry.register(metadata)

    Get a transform instance:
        >>> transformer = registry.get_transform("remove-images")

    List all available transforms:
        >>> transforms = registry.list_transforms()

    """

    _instance: Optional[TransformRegistry] = None
    _transforms: dict[str, TransformMetadata]
    _initialized: bool

    def __new__(cls) -> TransformRegistry:
        """Create or return singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._transforms = {}
            cls._instance._initialized = False
        return cls._instance

    def _ensure_initialized(self) -> None:
        """Ensure plugin discovery has been run."""
        if not self._initialized:
            self.discover_plugins()
            self._initialized = True

    def register(self, metadata: TransformMetadata) -> None:
        """Register a transform with its metadata.

        Parameters
        ----------
        metadata : TransformMetadata
            Transform metadata to register

        Notes
        -----
        If a transform with the same name is already registered, it will
        be overwritten and a warning will be logged.

        Examples
        --------
        >>> metadata = TransformMetadata(
        ...     name="my-transform",
        ...     description="My custom transform",
        ...     transformer_class=MyTransform
        ... )
        >>> registry = TransformRegistry()
        >>> registry.register(metadata)

        """
        if metadata.name in self._transforms:
            logger.warning(
                f"Transform '{metadata.name}' already registered, overwriting"
            )

        self._transforms[metadata.name] = metadata
        logger.debug(f"Registered transform: {metadata.name}")

    def unregister(self, name: str) -> bool:
        """Unregister a transform.

        Parameters
        ----------
        name : str
            Transform name to unregister

        Returns
        -------
        bool
            True if transform was unregistered, False if not found

        """
        if name in self._transforms:
            del self._transforms[name]
            logger.debug(f"Unregistered transform: {name}")
            return True
        return False

    def get_metadata(self, name: str) -> TransformMetadata:
        """Get metadata for a transform.

        Parameters
        ----------
        name : str
            Transform name

        Returns
        -------
        TransformMetadata
            Transform metadata

        Raises
        ------
        KeyError
            If transform is not registered

        """
        self._ensure_initialized()

        if name not in self._transforms:
            raise KeyError(f"Transform '{name}' not registered")

        return self._transforms[name]

    def get_transform(self, name: str, **kwargs: Any) -> NodeTransformer:
        """Get a transform instance by name.

        Parameters
        ----------
        name : str
            Transform name
        **kwargs
            Parameters to pass to transform constructor

        Returns
        -------
        NodeTransformer
            Transform instance

        Raises
        ------
        KeyError
            If transform is not registered
        ValueError
            If parameters are invalid

        Examples
        --------
        >>> registry = TransformRegistry()
        >>> transformer = registry.get_transform("heading-offset", offset=2)

        """
        metadata = self.get_metadata(name)
        return metadata.create_instance(**kwargs)

    def has_transform(self, name: str) -> bool:
        """Check if a transform is registered.

        Parameters
        ----------
        name : str
            Transform name

        Returns
        -------
        bool
            True if transform is registered

        """
        self._ensure_initialized()
        return name in self._transforms

    def list_transforms(self, tags: Optional[list[str]] = None) -> list[str]:
        """List all registered transform names.

        Parameters
        ----------
        tags : list[str], optional
            Filter by tags. If provided, only transforms with at least
            one matching tag are returned

        Returns
        -------
        list[str]
            List of transform names, sorted alphabetically

        Examples
        --------
        List all transforms:
            >>> names = registry.list_transforms()

        List transforms with specific tags:
            >>> image_transforms = registry.list_transforms(tags=["images"])

        """
        self._ensure_initialized()

        if tags is None:
            return sorted(self._transforms.keys())

        # Filter by tags
        filtered = []
        for name, metadata in self._transforms.items():
            if any(tag in metadata.tags for tag in tags):
                filtered.append(name)

        return sorted(filtered)

    def discover_plugins(self) -> int:
        """Discover and register transforms from entry points.

        This method scans for plugins using the `all2md.transforms` entry
        point group and registers all discovered transforms.

        Returns
        -------
        int
            Number of transforms discovered and registered

        Examples
        --------
        >>> registry = TransformRegistry()
        >>> count = registry.discover_plugins()
        >>> print(f"Discovered {count} transforms")

        """
        discovered_count = 0

        try:
            # Get entry points for all2md.transforms group
            entry_points = importlib.metadata.entry_points()

            # Handle different Python versions (3.10+ vs 3.9)
            if hasattr(entry_points, 'select'):
                # Python 3.10+
                transform_eps = entry_points.select(group='all2md.transforms')
            else:
                # Python 3.9 fallback
                transform_eps = entry_points.get('all2md.transforms', [])

            for ep in transform_eps:
                try:
                    # Load the entry point - should point to TransformMetadata
                    metadata = ep.load()

                    # Validate it's TransformMetadata
                    if not isinstance(metadata, TransformMetadata):
                        logger.warning(
                            f"Entry point '{ep.name}' did not return TransformMetadata, skipping"
                        )
                        continue

                    # Register the transform
                    self.register(metadata)
                    discovered_count += 1
                    logger.debug(f"Discovered transform from entry point: {ep.name}")

                except Exception as e:
                    logger.warning(f"Failed to load transform entry point '{ep.name}': {e}")
                    continue

        except Exception as e:
            logger.warning(f"Failed to discover transform plugins: {e}")

        logger.info(f"Discovered {discovered_count} transform(s) from entry points")
        return discovered_count

    def resolve_dependencies(self, transform_names: list[str]) -> list[str]:
        """Resolve transform dependencies and return execution order.

        This method performs topological sorting to determine the correct
        execution order based on dependencies and priorities.

        Parameters
        ----------
        transform_names : list[str]
            List of transform names to order

        Returns
        -------
        list[str]
            Transform names in execution order (dependencies first)

        Raises
        ------
        ValueError
            If circular dependencies are detected or a dependency is not found

        Examples
        --------
        >>> registry = TransformRegistry()
        >>> ordered = registry.resolve_dependencies([
        ...     "sanitize-links",  # depends on "extract-metadata"
        ...     "extract-metadata"
        ... ])
        >>> print(ordered)
        ['extract-metadata', 'sanitize-links']

        """
        self._ensure_initialized()

        # Build dependency graph - recursively collect all dependencies
        graph: dict[str, list[str]] = {}
        priorities: dict[str, int] = {}

        def add_to_graph(name: str) -> None:
            """Recursively add a transform and its dependencies to the graph."""
            if name in graph:
                return  # Already added

            if not self.has_transform(name):
                raise ValueError(f"Dependency '{name}' not found")

            metadata = self.get_metadata(name)
            graph[name] = metadata.dependencies.copy()
            priorities[name] = metadata.priority

            # Recursively add dependencies
            for dep in metadata.dependencies:
                add_to_graph(dep)

        # Add all requested transforms and their dependencies
        for name in transform_names:
            add_to_graph(name)

        # Topological sort with cycle detection
        sorted_names: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                raise ValueError(f"Circular dependency detected involving '{name}'")

            visiting.add(name)
            for dep in graph[name]:
                visit(dep)
            visiting.remove(name)
            visited.add(name)
            sorted_names.append(name)

        for name in graph:
            visit(name)

        # Within same dependency level, sort by priority (lower first)
        # This is a simplified approach - for more complex scenarios,
        # we could group by dependency depth and sort each group by priority
        sorted_names.sort(key=lambda n: priorities.get(n, 100))

        return sorted_names

    def clear(self) -> None:
        """Clear all registered transforms.

        This is primarily useful for testing.

        """
        self._transforms.clear()
        self._initialized = False
        logger.debug("Cleared transform registry")


# Global registry instance
registry = TransformRegistry()


__all__ = [
    "TransformRegistry",
    "registry",
]
