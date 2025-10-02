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
from typing import Any, Callable, Literal, Optional, Union

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

# Type aliases
HookPoint = Literal[
    'pre_ast',
    'post_ast',
    'pre_transform',
    'post_transform',
    'pre_render',
    'post_render',
]

NodeType = Literal[
    'document',
    'heading',
    'paragraph',
    'code_block',
    'block_quote',
    'list',
    'list_item',
    'table',
    'table_row',
    'table_cell',
    'thematic_break',
    'html_block',
    'text',
    'emphasis',
    'strong',
    'code',
    'link',
    'image',
    'line_break',
    'strikethrough',
    'underline',
    'superscript',
    'subscript',
    'html_inline',
    'footnote_reference',
    'footnote_definition',
    'math_inline',
    'math_block',
    'definition_list',
    'definition_term',
    'definition_description',
]

HookTarget = Union[HookPoint, NodeType]

# Callable type for hooks
# Pipeline hooks: (Document, HookContext) -> Document
# Node hooks: (Node, HookContext) -> Node | None
HookCallable = Callable[[Any, 'HookContext'], Any]


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
        Path from document root to current node (for node hooks)

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

    Examples
    --------
    Create a hook manager:
        >>> manager = HookManager()

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

    """

    def __init__(self) -> None:
        """Initialize the hook manager."""
        self._hooks: dict[HookTarget, list[HookCallable]] = {}

    def register_hook(
        self,
        target: HookTarget,
        hook: HookCallable,
        priority: int = 100
    ) -> None:
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

        Examples
        --------
        >>> manager = HookManager()
        >>> manager.register_hook('image', my_image_hook, priority=50)

        """
        if target not in self._hooks:
            self._hooks[target] = []

        # Store hook with priority
        self._hooks[target].append((priority, hook))

        # Sort by priority
        self._hooks[target].sort(key=lambda x: x[0])

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

    def execute_hooks(
        self,
        target: HookTarget,
        obj: Any,
        context: HookContext
    ) -> Any:
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

        Examples
        --------
        >>> context = HookContext(document=doc)
        >>> result = manager.execute_hooks('image', image_node, context)

        """
        if target not in self._hooks:
            return obj

        result = obj

        for priority, hook in self._hooks[target]:
            try:
                result = hook(result, context)

                # If hook returns None, object is removed
                if result is None:
                    logger.debug(f"Hook removed object at '{target}'")
                    return None

            except Exception as e:
                logger.error(
                    f"Hook failed at '{target}' with priority {priority}: {e}",
                    exc_info=True
                )
                # Continue execution - don't let one hook break the pipeline
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

    def get_node_type(self, node: Node) -> Optional[NodeType]:
        """Get the node type string for a node instance.

        Parameters
        ----------
        node : Node
            AST node

        Returns
        -------
        NodeType or None
            Node type string (e.g., 'heading', 'image')

        """
        # Map node classes to type strings
        type_map = {
            Document: 'document',
            Heading: 'heading',
            Paragraph: 'paragraph',
            CodeBlock: 'code_block',
            BlockQuote: 'block_quote',
            List: 'list',
            ListItem: 'list_item',
            Table: 'table',
            TableRow: 'table_row',
            TableCell: 'table_cell',
            ThematicBreak: 'thematic_break',
            HTMLBlock: 'html_block',
            Text: 'text',
            Emphasis: 'emphasis',
            Strong: 'strong',
            Code: 'code',
            Link: 'link',
            Image: 'image',
            LineBreak: 'line_break',
            Strikethrough: 'strikethrough',
            Underline: 'underline',
            Superscript: 'superscript',
            Subscript: 'subscript',
            HTMLInline: 'html_inline',
            FootnoteReference: 'footnote_reference',
            FootnoteDefinition: 'footnote_definition',
            MathInline: 'math_inline',
            MathBlock: 'math_block',
            DefinitionList: 'definition_list',
            DefinitionTerm: 'definition_term',
            DefinitionDescription: 'definition_description',
        }

        return type_map.get(type(node))

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
