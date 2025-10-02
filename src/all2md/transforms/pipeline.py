#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/pipeline.py
"""Pipeline orchestration for AST transformation and rendering.

This module provides the high-level pipeline for transforming AST documents
and rendering them to markdown. It coordinates:
- Transform execution with dependency resolution
- Hook execution at various pipeline stages
- Element-specific hooks during tree traversal
- Final rendering to markdown

The pipeline is the main entry point for using transforms and hooks together.

Examples
--------
Simple rendering:

    >>> from all2md import to_ast
    >>> from all2md.transforms import render
    >>> doc = to_ast("document.pdf")
    >>> markdown = render(doc)

With transforms:

    >>> markdown = render(doc, transforms=['remove-images', 'heading-offset'])

With hooks:

    >>> def log_images(node, context):
    ...     print(f"Image: {node.url}")
    ...     return node
    >>> markdown = render(doc, hooks={'image': [log_images]})

Complex pipeline:

    >>> from all2md.transforms import HeadingOffsetTransform
    >>> markdown = render(
    ...     doc,
    ...     transforms=[HeadingOffsetTransform(offset=1), 'remove-images'],
    ...     hooks={
    ...         'pre_render': [validate_document],
    ...         'image': [watermark_images],
    ...         'post_render': [add_footer]
    ...     }
    ... )

"""

from __future__ import annotations

import logging
from typing import Optional, Union

from all2md.ast.nodes import Document, Node
from all2md.ast.renderer import MarkdownRenderer
from all2md.ast.transforms import NodeTransformer
from all2md.options import MarkdownOptions

from .hooks import HookCallable, HookContext, HookManager, HookTarget
from .registry import TransformRegistry

logger = logging.getLogger(__name__)


class HookAwareVisitor(NodeTransformer):
    """Visitor that applies element hooks during tree traversal.

    This visitor extends NodeTransformer to execute registered element hooks
    for each node type during traversal. It maintains the node path in the
    context for hooks that need to know the tree structure.

    Parameters
    ----------
    hook_manager : HookManager
        Manager containing registered hooks
    context : HookContext
        Context to pass to hooks

    Examples
    --------
    >>> hook_manager = HookManager()
    >>> hook_manager.register_hook('image', my_image_hook)
    >>> context = HookContext(document=doc)
    >>> visitor = HookAwareVisitor(hook_manager, context)
    >>> processed_doc = visitor.transform(doc)

    """

    def __init__(self, hook_manager: HookManager, context: HookContext):
        """Initialize visitor with hook manager and context."""
        self.hook_manager = hook_manager
        self.context = context

    def transform(self, node: Node) -> Node | None:
        """Transform node and apply element hooks.

        Parameters
        ----------
        node : Node
            Node to transform

        Returns
        -------
        Node or None
            Transformed node, or None if removed by hook

        """
        # Get node type for hook lookup
        node_type = self.hook_manager.get_node_type(node)

        # Execute element hook if registered
        if node_type and self.hook_manager.has_hooks(node_type):
            # Add to path for context
            self.context.node_path.append(node)

            try:
                # Execute hooks for this node type
                node = self.hook_manager.execute_hooks(node_type, node, self.context)

                # Hook removed node
                if node is None:
                    self.context.node_path.pop()
                    return None

            finally:
                # Always pop from path (even if hook failed)
                if self.context.node_path and self.context.node_path[-1] is node:
                    self.context.node_path.pop()

        # Continue normal traversal with transformed node
        return super().transform(node)


class Pipeline:
    """Pipeline for transforming and rendering AST documents.

    This class orchestrates the complete transformation and rendering pipeline,
    including transform resolution, hook execution, and markdown generation.

    Parameters
    ----------
    transforms : list, optional
        List of transforms to apply. Can be transform names (str) or
        NodeTransformer instances. Names are resolved via TransformRegistry
    hooks : dict, optional
        Dictionary mapping hook targets to lists of hook callables
    options : MarkdownOptions, optional
        Options for markdown rendering

    Examples
    --------
    Create pipeline and execute:

        >>> pipeline = Pipeline(
        ...     transforms=['remove-images'],
        ...     hooks={'pre_render': [validate]}
        ... )
        >>> markdown = pipeline.execute(document)

    """

    def __init__(
        self,
        transforms: Optional[list[Union[str, NodeTransformer]]] = None,
        hooks: Optional[dict[HookTarget, list[HookCallable]]] = None,
        options: Optional[MarkdownOptions] = None
    ):
        """Initialize pipeline with transforms, hooks, and options."""
        self.transforms = transforms or []
        self.hook_manager = HookManager()
        self.options = options or MarkdownOptions()
        self.registry = TransformRegistry()

        # Register provided hooks
        if hooks:
            for target, hook_list in hooks.items():
                for priority, hook in enumerate(hook_list):
                    # Use list index as priority to maintain order
                    self.hook_manager.register_hook(target, hook, priority=priority)

    def _resolve_transforms(self) -> list[NodeTransformer]:
        """Resolve transform names/instances to ordered list of instances.

        This method converts string transform names to instances via the
        registry, resolves dependencies, and combines them with provided
        instances in the correct execution order.

        Returns
        -------
        list[NodeTransformer]
            Ordered list of transform instances ready to execute

        Raises
        ------
        TypeError
            If transform is not a string or NodeTransformer
        ValueError
            If transform name is not found in registry

        """
        instances: list[NodeTransformer] = []
        names_to_resolve: list[str] = []

        # Separate string names from instances
        for t in self.transforms:
            if isinstance(t, str):
                names_to_resolve.append(t)
            elif isinstance(t, NodeTransformer):
                instances.append(t)
            else:
                raise TypeError(
                    f"Transform must be str or NodeTransformer, got {type(t).__name__}"
                )

        # Resolve dependencies and get instances for named transforms
        if names_to_resolve:
            # Resolve dependencies (topological sort)
            ordered = self.registry.resolve_dependencies(names_to_resolve)

            # Get instances in dependency order
            for name in ordered:
                instances.append(self.registry.get_transform(name))

        logger.debug(f"Resolved {len(instances)} transform(s) for execution")
        return instances

    def _apply_transforms(self, document: Document, context: HookContext) -> Document:
        """Apply all transforms in order.

        Parameters
        ----------
        document : Document
            Document to transform
        context : HookContext
            Context for hook execution

        Returns
        -------
        Document
            Transformed document

        Raises
        ------
        ValueError
            If a hook removes the document node

        """
        result = document
        transforms = self._resolve_transforms()

        logger.debug(f"Applying {len(transforms)} transform(s)")

        for transformer in transforms:
            # Pre-transform hook
            if self.hook_manager.has_hooks('pre_transform'):
                context.transform_name = transformer.__class__.__name__
                result = self.hook_manager.execute_hooks('pre_transform', result, context)

                if result is None:
                    raise ValueError("pre_transform hook removed document")

            # Apply transform
            logger.debug(f"Applying transform: {transformer.__class__.__name__}")
            context.transform_name = transformer.__class__.__name__

            try:
                result = transformer.transform(result)

                if result is None:
                    raise ValueError(
                        f"Transform {transformer.__class__.__name__} returned None"
                    )

            except Exception as e:
                logger.error(
                    f"Transform {transformer.__class__.__name__} failed: {e}",
                    exc_info=True
                )
                # Re-raise - transform failures are critical
                raise

            # Post-transform hook
            if self.hook_manager.has_hooks('post_transform'):
                result = self.hook_manager.execute_hooks('post_transform', result, context)

                if result is None:
                    raise ValueError("post_transform hook removed document")

        context.transform_name = None
        return result

    def _apply_element_hooks(self, document: Document, context: HookContext) -> Document:
        """Apply element-specific hooks via tree traversal.

        Parameters
        ----------
        document : Document
            Document to process
        context : HookContext
            Context for hook execution

        Returns
        -------
        Document
            Document with element hooks applied

        """
        # Check if any element hooks are registered
        has_element_hooks = False
        element_targets = [
            'document', 'heading', 'paragraph', 'code_block', 'block_quote',
            'list', 'list_item', 'table', 'table_row', 'table_cell',
            'thematic_break', 'html_block', 'text', 'emphasis', 'strong',
            'code', 'link', 'image', 'line_break', 'strikethrough', 'underline',
            'superscript', 'subscript', 'html_inline', 'footnote_reference',
            'footnote_definition', 'math_inline', 'math_block', 'definition_list',
            'definition_term', 'definition_description'
        ]

        for target in element_targets:
            if self.hook_manager.has_hooks(target):  # type: ignore
                has_element_hooks = True
                break

        if not has_element_hooks:
            logger.debug("No element hooks registered, skipping traversal")
            return document

        logger.debug("Applying element hooks via tree traversal")

        # Create visitor and traverse
        visitor = HookAwareVisitor(self.hook_manager, context)
        result = visitor.transform(document)

        if result is None:
            raise ValueError("Element hook removed document node")

        return result  # type: ignore

    def _render(self, document: Document) -> str:
        """Render document to markdown.

        Parameters
        ----------
        document : Document
            Document to render

        Returns
        -------
        str
            Markdown text

        """
        logger.debug("Rendering document to markdown")
        renderer = MarkdownRenderer(self.options)
        return renderer.render(document)

    def execute(self, document: Document) -> str:
        """Execute complete pipeline.

        This method runs the full transformation and rendering pipeline:
        1. Execute post_ast hooks
        2. Apply transforms (with pre/post transform hooks)
        3. Apply element hooks
        4. Execute pre_render hooks
        5. Render to markdown
        6. Execute post_render hooks

        Parameters
        ----------
        document : Document
            Document to process

        Returns
        -------
        str
            Rendered markdown text

        Examples
        --------
        >>> pipeline = Pipeline(transforms=['remove-images'])
        >>> markdown = pipeline.execute(document)

        """
        logger.info("Starting pipeline execution")

        # Create context
        context = HookContext(
            document=document,
            metadata=document.metadata.copy(),
            shared={}
        )

        # Post-AST hook (document just came from conversion)
        if self.hook_manager.has_hooks('post_ast'):
            logger.debug("Executing post_ast hooks")
            result = self.hook_manager.execute_hooks('post_ast', document, context)

            if result is None:
                raise ValueError("post_ast hook removed document")

            document = result  # type: ignore

        # Apply transforms
        if self.transforms:
            document = self._apply_transforms(document, context)

        # Pre-render hook (before element hooks, for document-level validation)
        if self.hook_manager.has_hooks('pre_render'):
            logger.debug("Executing pre_render hooks")
            result = self.hook_manager.execute_hooks('pre_render', document, context)

            if result is None:
                raise ValueError("pre_render hook removed document")

            document = result  # type: ignore

        # Apply element hooks (after pre_render, before rendering)
        document = self._apply_element_hooks(document, context)

        # Render
        markdown = self._render(document)

        # Post-render hook
        if self.hook_manager.has_hooks('post_render'):
            logger.debug("Executing post_render hooks")
            markdown = self.hook_manager.execute_hooks('post_render', markdown, context)

            if markdown is None:
                raise ValueError("post_render hook removed markdown")

        logger.info("Pipeline execution complete")
        return markdown  # type: ignore


def render(
    document: Document,
    transforms: Optional[list[Union[str, NodeTransformer]]] = None,
    hooks: Optional[dict[HookTarget, list[HookCallable]]] = None,
    options: Optional[MarkdownOptions] = None,
    **kwargs
) -> str:
    """Render document to markdown with transforms and hooks.

    This is the high-level entry point for the transformation pipeline.
    It creates a Pipeline instance and executes it to produce markdown output.

    Parameters
    ----------
    document : Document
        AST document to render
    transforms : list, optional
        List of transforms to apply. Can be transform names (str) or
        NodeTransformer instances
    hooks : dict, optional
        Dictionary mapping hook targets to lists of hook callables.
        Hook targets can be pipeline stages ('pre_render', 'post_render', etc.)
        or node types ('image', 'link', 'heading', etc.)
    options : MarkdownOptions, optional
        Options for markdown rendering (flavor, formatting, etc.)
    **kwargs
        Additional keyword arguments passed to MarkdownOptions if
        options is not provided

    Returns
    -------
    str
        Rendered markdown text

    Raises
    ------
    TypeError
        If transform is not a string or NodeTransformer
    ValueError
        If transform name is not found or a hook removes a required node

    Examples
    --------
    Basic rendering:
        >>> from all2md import to_ast
        >>> from all2md.transforms import render
        >>> doc = to_ast("document.pdf")
        >>> markdown = render(doc)

    With transforms by name:
        >>> markdown = render(doc, transforms=['remove-images'])

    With transform instances:
        >>> from all2md.transforms import HeadingOffsetTransform
        >>> markdown = render(
        ...     doc,
        ...     transforms=[HeadingOffsetTransform(offset=1)]
        ... )

    With hooks:
        >>> def log_image(node, context):
        ...     print(f"Found image: {node.url}")
        ...     return node
        >>> markdown = render(doc, hooks={'image': [log_image]})

    Combined transforms and hooks:
        >>> markdown = render(
        ...     doc,
        ...     transforms=['heading-offset', 'remove-images'],
        ...     hooks={
        ...         'pre_render': [validate_document],
        ...         'link': [rewrite_links],
        ...         'post_render': [add_footer]
        ...     },
        ...     options=MarkdownOptions(flavor='commonmark')
        ... )

    With MarkdownOptions kwargs:
        >>> markdown = render(doc, flavor='gfm', emphasis_symbol='_')

    """
    # Create options from kwargs if not provided
    if options is None and kwargs:
        options = MarkdownOptions(**kwargs)
    elif options is None:
        options = MarkdownOptions()

    # Create and execute pipeline
    pipeline = Pipeline(
        transforms=transforms,
        hooks=hooks,
        options=options
    )

    return pipeline.execute(document)


__all__ = [
    "Pipeline",
    "HookAwareVisitor",
    "render",
]
