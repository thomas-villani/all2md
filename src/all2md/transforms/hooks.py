#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/hooks.py
"""Hook system for AST transformation pipeline.

This module provides a flexible hook system for intercepting and modifying
the transformation pipeline at various stages. Hooks can be registered for:
- Pipeline stages (pre/post AST, render, etc.)
- Specific node types (headings, images, links, etc.)

Examples
--------
Register a hook for all images:

    >>> from all2md.transforms import HookManager
    >>> manager = HookManager()
    >>>
    >>> def log_image(node, context):
    ...     print(f"Found image: {node.url}")
    ...     return node
    >>>
    >>> manager.register_hook('image', log_image)

Register a pipeline hook:

    >>> def validate_document(doc, context):
    ...     print(f"Processing document with {len(doc.children)} nodes")
    ...     return doc
    >>>
    >>> manager.register_hook('pre_render', validate_document)

"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, Union, cast

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)

logger = logging.getLogger(__name__)

# Module-level constant for node type mapping (performance optimization)
# Used by HookManager.get_node_type() in hot path during tree traversal
# Format: list of (node_class, type_string) tuples
# Order matters: more specific types should be checked before more general ones
_NODE_TYPE_MAP: list[tuple[type[Node], str]] = [
    (Document, "document"),
    (Heading, "heading"),
    (Paragraph, "paragraph"),
    (CodeBlock, "code_block"),
    (BlockQuote, "block_quote"),
    (List, "list"),
    (ListItem, "list_item"),
    (Table, "table"),
    (TableRow, "table_row"),
    (TableCell, "table_cell"),
    (ThematicBreak, "thematic_break"),
    (HTMLBlock, "html_block"),
    (Text, "text"),
    (Emphasis, "emphasis"),
    (Strong, "strong"),
    (Code, "code"),
    (Link, "link"),
    (Image, "image"),
    (LineBreak, "line_break"),
    (Strikethrough, "strikethrough"),
    (Underline, "underline"),
    (Superscript, "superscript"),
    (Subscript, "subscript"),
    (HTMLInline, "html_inline"),
    (FootnoteReference, "footnote_reference"),
    (FootnoteDefinition, "footnote_definition"),
    (MathInline, "math_inline"),
    (MathBlock, "math_block"),
    (DefinitionList, "definition_list"),
    (DefinitionTerm, "definition_term"),
    (DefinitionDescription, "definition_description"),
]

# Type aliases
HookPoint = Literal[
    "post_ast",
    "pre_transform",
    "post_transform",
    "pre_render",
    "post_render",
]

NodeType = Literal[
    "document",
    "heading",
    "paragraph",
    "code_block",
    "block_quote",
    "list",
    "list_item",
    "table",
    "table_row",
    "table_cell",
    "thematic_break",
    "html_block",
    "text",
    "emphasis",
    "strong",
    "code",
    "link",
    "image",
    "line_break",
    "strikethrough",
    "underline",
    "superscript",
    "subscript",
    "html_inline",
    "footnote_reference",
    "footnote_definition",
    "math_inline",
    "math_block",
    "definition_list",
    "definition_term",
    "definition_description",
]

HookTarget = Union[HookPoint, NodeType]

# Callable type for hooks
# Pipeline hooks: (Document, HookContext) -> Document
# Node hooks: (Node, HookContext) -> Node | None
HookCallable = Callable[[Any, "HookContext"], Any]


@dataclass
class HookContext:
    """Context passed to hook functions.

    This class provides hooks with access to document state, metadata,
    and a shared data dictionary for passing information between hooks
    and transforms.

    Parameters
    ----------
    document : Document
        The current document being processed
    metadata : dict, default = empty dict
        Document metadata from the source format
    shared : dict, default = empty dict
        Shared mutable dictionary for passing data between hooks/transforms
    transform_name : str, optional
        Name of the current transform (for transform hooks)
    node_path : list[Node], default = empty list
        Path from document root to current node (for node hooks).
        WARNING: This list is mutated during tree traversal. Not thread-safe.

    Examples
    --------
    Access context in a hook:

        >>> def my_hook(node: Image, context: HookContext) -> Image:
        ...     # Store image count in shared state
        ...     context.shared['image_count'] = context.shared.get('image_count', 0) + 1
        ...
        ...     # Access document metadata
        ...     if 'author' in context.metadata:
        ...         print(f"Document by: {context.metadata['author']}")
        ...
        ...     return node

    """

    document: Document
    metadata: dict[str, Any] = field(default_factory=dict)
    shared: dict[str, Any] = field(default_factory=dict)
    transform_name: Optional[str] = None
    node_path: list[Node] = field(default_factory=list)

    def get_shared(self, key: str, default: Any = None) -> Any:
        """Get a value from shared state.

        Parameters
        ----------
        key : str
            Key to retrieve
        default : Any, optional
            Default value if key not found

        Returns
        -------
        Any
            Value from shared state or default

        """
        return self.shared.get(key, default)

    def set_shared(self, key: str, value: Any) -> None:
        """Set a value in shared state.

        Parameters
        ----------
        key : str
            Key to set
        value : Any
            Value to store

        """
        self.shared[key] = value


class HookManager:
    """Manager for registering and executing hooks.

    This class provides a central registry for hooks at various pipeline
    stages and for specific node types.

    Parameters
    ----------
    strict : bool, default = False
        If True, hook exceptions are re-raised and abort the pipeline.
        If False (default), exceptions are logged and execution continues.

    Examples
    --------
    Create a hook manager:
        >>> manager = HookManager()

    Create a strict hook manager:
        >>> manager = HookManager(strict=True)

    Register a pipeline hook:
        >>> def pre_render_hook(doc, context):
        ...     print("About to render")
        ...     return doc
        >>> manager.register_hook('pre_render', pre_render_hook)

    Register a node hook:
        >>> def image_hook(node, context):
        ...     print(f"Processing image: {node.url}")
        ...     return node
        >>> manager.register_hook('image', image_hook)

    Execute hooks:
        >>> context = HookContext(document=my_doc)
        >>> result = manager.execute_hooks('pre_render', my_doc, context)

    Notes
    -----
    In strict mode (strict=True), any exception raised by a hook will be
    re-raised and abort the pipeline. This is useful for debugging or when
    hook failures should be treated as critical errors.

    In non-strict mode (strict=False, the default), exceptions are logged
    with full traceback but execution continues with subsequent hooks. This
    provides a fail-safe default that prevents a single problematic hook
    from breaking the entire pipeline.

    Thread Safety
    -------------
    **WARNING**: HookManager instances are NOT thread-safe. Hook registration
    and execution use shared mutable state without synchronization.

    For safe concurrent usage:
    - Create a separate HookManager instance per thread/pipeline (recommended)
    - Each Pipeline instance creates its own HookManager (default behavior)
    - If sharing across threads, wrap access with external locks (e.g., threading.Lock)

    """

    def __init__(self, strict: bool = False) -> None:
        """Initialize the hook manager.

        Parameters
        ----------
        strict : bool, default = False
            Enable strict mode for hook exception handling

        """
        self._hooks: dict[HookTarget, list[tuple[int, HookCallable]]] = {}
        self.strict = strict

    def register_hook(self, target: HookTarget, hook: HookCallable, priority: int = 100) -> None:
        """Register a hook for a target.

        Parameters
        ----------
        target : HookTarget
            Hook point or node type to hook into
        hook : callable
            Hook function with signature: (obj, context) -> obj
        priority : int, default = 100
            Execution priority (lower runs first)

        Notes
        -----
        Hooks for the same target are executed in priority order (lower first).
        If priorities are equal, hooks run in registration order.

        Sorting is deferred until execution time for better performance when
        registering many hooks.

        Examples
        --------
        >>> manager = HookManager()
        >>> manager.register_hook('image', my_image_hook, priority=50)

        """
        if target not in self._hooks:
            self._hooks[target] = []

        # Store hook with priority (sorting deferred to execution time)
        self._hooks[target].append((priority, hook))

        logger.debug(f"Registered hook for '{target}' with priority {priority}")

    def unregister_hook(self, target: HookTarget, hook: HookCallable) -> bool:
        """Unregister a hook.

        Parameters
        ----------
        target : HookTarget
            Hook point or node type
        hook : callable
            Hook function to remove

        Returns
        -------
        bool
            True if hook was found and removed

        """
        if target not in self._hooks:
            return False

        initial_len = len(self._hooks[target])
        self._hooks[target] = [(p, h) for p, h in self._hooks[target] if h != hook]

        removed = len(self._hooks[target]) < initial_len
        if removed:
            logger.debug(f"Unregistered hook from '{target}'")

        return removed

    def execute_hooks(self, target: HookTarget, obj: Any, context: HookContext) -> Any:
        """Execute all hooks for a target.

        Hooks are executed in priority order. Each hook receives the result
        from the previous hook. If a hook returns None, the object is removed
        (for node hooks).

        Parameters
        ----------
        target : HookTarget
            Hook point or node type
        obj : Any
            Object to process (Document or Node)
        context : HookContext
            Hook context

        Returns
        -------
        Any
            Processed object (or None if removed by a hook)

        Raises
        ------
        Exception
            Any exception from hooks if strict mode is enabled

        Examples
        --------
        >>> context = HookContext(document=doc)
        >>> result = manager.execute_hooks('image', image_node, context)

        Notes
        -----
        In strict mode, exceptions from hooks are re-raised and abort execution.
        In non-strict mode (default), exceptions are logged and execution continues.

        Hooks are sorted by priority at execution time for better registration
        performance when many hooks are registered.

        """
        if target not in self._hooks:
            return obj

        result = obj

        # Sort hooks by priority (lower priority runs first)
        # Sorting is done here rather than at registration time for better performance
        sorted_hooks = sorted(self._hooks[target], key=lambda x: x[0])

        for priority, hook in sorted_hooks:
            try:
                result = hook(result, context)

                # If hook returns None, object is removed
                if result is None:
                    logger.debug(f"Hook removed object at '{target}'")
                    return None

            except Exception as e:
                logger.error(f"Hook failed at '{target}' with priority {priority}: {e}", exc_info=True)

                # In strict mode, re-raise the exception to abort the pipeline
                if self.strict:
                    raise

                # In non-strict mode, continue execution - don't let one hook break the pipeline
                # Return current result unchanged
                continue

        return result

    def has_hooks(self, target: HookTarget) -> bool:
        """Check if any hooks are registered for a target.

        Parameters
        ----------
        target : HookTarget
            Hook point or node type

        Returns
        -------
        bool
            True if hooks are registered

        """
        return target in self._hooks and len(self._hooks[target]) > 0

    @staticmethod
    def get_node_type(node: Node) -> Optional[NodeType]:
        """Get the node type string for a node instance.

        This static method supports subclasses by using isinstance checks rather than
        exact type matching. If a node is a subclass of a known type, it will
        be identified by its parent type.

        Parameters
        ----------
        node : Node
            AST node

        Returns
        -------
        NodeType or None
            Node type string (e.g., 'heading', 'image'), or None if unknown

        Notes
        -----
        The method iterates through known node types and returns the first match
        using isinstance checks. This allows custom subclasses to be recognized
        by their base type. For example, a custom MyImage(Image) subclass will
        be identified as type 'image'.

        Performance: Uses module-level _NODE_TYPE_MAP constant to avoid
        reconstructing the mapping on every call (hot path optimization).

        This is a static method because it doesn't depend on instance state,
        only on the module-level _NODE_TYPE_MAP constant. This allows it to be
        called without instantiating HookManager.

        Examples
        --------
        >>> from all2md.ast.nodes import Image
        >>> img = Image(url="test.png", alt_text="Test")
        >>> node_type = HookManager.get_node_type(img)
        >>> print(node_type)
        'image'

        """
        # Use isinstance to support subclasses
        # Iterate over module-level constant (avoids repeated dict construction)
        for node_class, node_type in _NODE_TYPE_MAP:
            if isinstance(node, node_class):
                return cast(NodeType, node_type)

        return None

    def list_hooks(self) -> dict[HookTarget, list[tuple[int, HookCallable]]]:
        """List all registered hooks with their priorities.

        This method provides a public API for enumerating hooks without
        exposing the internal _hooks dictionary structure.

        Returns
        -------
        dict[HookTarget, list[tuple[int, HookCallable]]]
            Dictionary mapping hook targets to lists of (priority, hook) tuples.
            The returned dictionary is a shallow copy to prevent external
            modifications to internal state.

        Examples
        --------
        >>> manager = HookManager()
        >>> manager.register_hook('image', my_hook, priority=50)
        >>> hooks = manager.list_hooks()
        >>> print(hooks)
        {'image': [(50, <function my_hook>)]}

        """
        # Return a shallow copy to prevent external modification
        return dict(self._hooks)

    def clear(self) -> None:
        """Clear all registered hooks.

        This is primarily useful for testing.

        """
        self._hooks.clear()
        logger.debug("Cleared all hooks")


__all__ = [
    "HookContext",
    "HookManager",
    "HookPoint",
    "NodeType",
    "HookTarget",
    "HookCallable",
]
