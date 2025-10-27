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
Register a transform using the global registry instance (preferred):

    >>> from all2md.transforms import transform_registry, TransformMetadata
    >>> transform_registry.register(my_transform_metadata)

Get a transform:

    >>> from all2md.transforms import transform_registry
    >>> transformer = transform_registry.get_transform("remove-images")

List all transforms:

    >>> from all2md.transforms import transform_registry
    >>> names = transform_registry.list_transforms()
    >>> for name in names:
    ...     metadata = transform_registry.get_metadata(name)
    ...     print(f"{name}: {metadata.description}")

Notes
-----
The preferred access pattern is to import the global `registry` instance directly
rather than instantiating TransformRegistry. While both patterns work due to the
singleton implementation, using the global instance is more explicit and consistent
with the library's design.

"""

from __future__ import annotations

import heapq
import importlib
import importlib.metadata
import logging
from typing import TYPE_CHECKING, Any, Optional

from all2md.ast.transforms import NodeTransformer

if TYPE_CHECKING:
    from all2md.transforms.metadata import TransformMetadata

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

    Notes
    -----
    The preferred way to access the registry is by importing the global `registry`
    instance rather than instantiating this class directly. While instantiation
    works due to the singleton pattern, importing `registry` is more explicit.

    Examples
    --------
    Use the global registry instance (preferred):
        >>> from all2md.transforms import transform_registry
        >>> transform_registry.register(metadata)

    Get a transform instance:
        >>> from all2md.transforms import transform_registry
        >>> transformer = transform_registry.get_transform("remove-images")

    List all available transforms:
        >>> from all2md.transforms import transform_registry
        >>> transforms = transform_registry.list_transforms()

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
        >>> transform_registry = TransformRegistry()
        >>> transform_registry.register(metadata)

        """
        if metadata.name in self._transforms:
            logger.warning(f"Transform '{metadata.name}' already registered, overwriting")

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
        >>> transform_registry = TransformRegistry()
        >>> transformer = transform_registry.get_transform("heading-offset", offset=2)

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
            >>> names = transform_registry.list_transforms()

        List transforms with specific tags:
            >>> image_transforms = transform_registry.list_transforms(tags=["images"])

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
        >>> transform_registry = TransformRegistry()
        >>> count = transform_registry.discover_plugins()
        >>> print(f"Discovered {count} transforms")

        """
        discovered_count = 0
        from all2md.transforms.metadata import TransformMetadata

        try:
            # Get entry points for all2md.transforms group
            entry_points = importlib.metadata.entry_points()

            # Python 3.10+ only
            transform_eps = entry_points.select(group="all2md.transforms")

            for ep in transform_eps:
                try:
                    # Load the entry point - should point to TransformMetadata
                    metadata = ep.load()

                    # Validate it's TransformMetadata
                    if not isinstance(metadata, TransformMetadata):
                        logger.warning(f"Entry point '{ep.name}' did not return TransformMetadata, skipping")
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

        This method performs topological sorting using Kahn's algorithm to
        determine the correct execution order based on dependencies and priorities.
        Priority is used as a tiebreaker among transforms with no pending dependencies.

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
        >>> transform_registry = TransformRegistry()
        >>> ordered = transform_registry.resolve_dependencies([
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

        # Kahn's algorithm with priority-based tiebreaking
        # This preserves topological order while honoring priority among independent nodes

        # Build reverse graph: reverse_graph[A] = list of transforms that depend on A
        reverse_graph: dict[str, list[str]] = {name: [] for name in graph}
        for name in graph:
            for dep in graph[name]:
                if dep not in reverse_graph:
                    reverse_graph[dep] = []
                reverse_graph[dep].append(name)

        # Compute indegrees (number of dependencies each transform has)
        indegree: dict[str, int] = {name: len(graph[name]) for name in graph}

        # Initialize min-heap with zero-indegree nodes (sorted by priority)
        heap: list[tuple[int, str]] = [(priorities.get(name, 100), name) for name, deg in indegree.items() if deg == 0]
        heapq.heapify(heap)

        sorted_names: list[str] = []
        while heap:
            _, name = heapq.heappop(heap)
            sorted_names.append(name)

            # Decrease indegree for dependents (those that depend on name)
            for dependent in reverse_graph[name]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    heapq.heappush(heap, (priorities.get(dependent, 100), dependent))

        # Check for circular dependencies
        if len(sorted_names) != len(graph):
            # Find a node that's still in the graph (part of a cycle)
            remaining = set(graph.keys()) - set(sorted_names)
            raise ValueError(f"Circular dependency detected involving: {', '.join(sorted(remaining))}")

        return sorted_names

    def clear(self) -> None:
        """Clear all registered transforms.

        This is primarily useful for testing.

        """
        self._transforms.clear()
        self._initialized = False
        logger.debug("Cleared transform transform_registry")


# Global registry instance (preferred access pattern)
# Use this instance rather than instantiating TransformRegistry directly
transform_registry = TransformRegistry()

__all__ = [
    "TransformRegistry",
    "transform_registry",
]
