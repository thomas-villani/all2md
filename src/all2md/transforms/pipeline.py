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
from typing import Any, Optional, Union

from all2md.ast.nodes import Document, Node
from all2md.ast.transforms import NodeTransformer
from all2md.options import MarkdownOptions
from all2md.progress import ProgressCallback, ProgressEvent

from .. import BaseRendererOptions
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

        The node is pushed onto node_path before processing and remains there
        during child traversal, ensuring descendants can see full ancestry.
        If a hook replaces the node, the path is updated so descendants see
        the new node in their ancestry.

        Parameters
        ----------
        node : Node
            Node to transform

        Returns
        -------
        Node or None
            Transformed node, or None if removed by hook

        """
        # Push node onto path for full ancestry tracking
        # This happens for ALL nodes, not just those with hooks, so that
        # descendant hooks can see their full ancestry even if some ancestors
        # don't have hooks registered
        self.context.node_path.append(node)

        try:
            # Get node type for hook lookup
            node_type = self.hook_manager.get_node_type(node)

            # Execute element hook if registered
            if node_type and self.hook_manager.has_hooks(node_type):
                # Execute hooks for this node type (may replace node variable)
                node = self.hook_manager.execute_hooks(node_type, node, self.context)

                # Hook removed node
                if node is None:
                    return None  # type: ignore[unreachable]

                # If hook replaced the node with a different object, update the path
                # so descendants see the new node in their ancestry
                if node is not self.context.node_path[-1]:
                    self.context.node_path[-1] = node

            # Continue normal traversal with node still on path
            # This ensures children see this node in their ancestry
            return super().transform(node)
        finally:
            # Always pop the top of the path after child traversal completes
            if self.context.node_path:
                self.context.node_path.pop()


class Pipeline:
    """Pipeline for transforming and rendering AST documents.

    This class orchestrates the complete transformation and rendering pipeline,
    including transform resolution, hook execution, and rendering to output format.

    Parameters
    ----------
    transforms : list, optional
        List of transforms to apply. Can be transform names (str) or
        NodeTransformer instances. Names are resolved via TransformRegistry
    hooks : dict, optional
        Dictionary mapping hook targets to lists of hook callables
    renderer : str, type, or renderer instance, optional
        Renderer to use for output. Can be:
        - Format name string (e.g., "markdown") - looked up via registry
        - Renderer class (e.g., MarkdownRenderer)
        - Renderer instance (e.g., MarkdownRenderer())
        Defaults to MarkdownRenderer with default options
    options : BaseRendererOptions or MarkdownOptions, optional
        Options for rendering (used if renderer is string or class, ignored if instance)
    progress_callback : ProgressCallback, optional
        Optional callback for progress updates during rendering
    strict_hooks : bool, default = False
        Enable strict mode for hook exception handling. If True, hook exceptions
        are re-raised and abort the pipeline. If False (default), exceptions are
        logged and execution continues.

    Examples
    --------
    Create pipeline with default markdown renderer:

        >>> pipeline = Pipeline(
        ...     transforms=['remove-images'],
        ...     hooks={'pre_render': [validate]}
        ... )
        >>> output = pipeline.execute(document)

    With custom renderer:

        >>> from all2md.renderers.markdown import MarkdownRenderer
        >>> pipeline = Pipeline(
        ...     transforms=['remove-images'],
        ...     renderer=MarkdownRenderer(options=MarkdownOptions(flavor='commonmark'))
        ... )
        >>> output = pipeline.execute(document)

    With strict hook mode:

        >>> pipeline = Pipeline(
        ...     transforms=['remove-images'],
        ...     hooks={'image': [validate_image]},
        ...     strict_hooks=True  # Hook failures will abort pipeline
        ... )
        >>> output = pipeline.execute(document)

    """

    def __init__(
        self,
        transforms: Optional[list[Union[str, NodeTransformer]]] = None,
        hooks: Optional[dict[HookTarget, list[HookCallable]]] = None,
        renderer: Optional[Union[str, type, Any]] = None,
        options: Optional[Union[BaseRendererOptions, MarkdownOptions]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        strict_hooks: bool = False
    ):
        """Initialize pipeline with transforms, hooks, renderer, and options."""
        self.transforms = transforms or []
        self.hook_manager = HookManager(strict=strict_hooks)
        self.registry = TransformRegistry()
        self.progress_callback = progress_callback

        # Set up renderer
        self.renderer = self._setup_renderer(renderer, options)

        # Store options for backward compatibility (some code may access pipeline.options)
        self.options = options if isinstance(options, (BaseRendererOptions, MarkdownOptions)) else MarkdownOptions()

        # Register provided hooks
        if hooks:
            for target, hook_list in hooks.items():
                for priority, hook in enumerate(hook_list):
                    # Use list index as priority to maintain order
                    self.hook_manager.register_hook(target, hook, priority=priority)

    def _setup_renderer(
        self,
        renderer: Optional[Union[str, type, Any]],
        options: Optional[Union[BaseRendererOptions, MarkdownOptions]]
    ) -> Any:
        """Set up the renderer instance.

        Parameters
        ----------
        renderer : str, type, or instance, optional
            Renderer specification
        options : BaseRendererOptions or MarkdownOptions, optional
            Options to use if creating renderer from string/class

        Returns
        -------
        Any
            Renderer instance ready to use

        """
        # If renderer is already an instance, use it
        if renderer is not None and hasattr(renderer, 'render_to_string'):
            return renderer

        # If renderer is a class, instantiate it
        if renderer is not None and isinstance(renderer, type):
            return renderer(options=options)

        # If renderer is a string, look it up via registry
        if isinstance(renderer, str):
            from all2md.converter_registry import registry
            renderer_class = registry.get_renderer(renderer)
            return renderer_class(options=options)

        # Default to MarkdownRenderer
        from all2md.renderers.markdown import MarkdownRenderer
        # Use MarkdownOptions if no options provided or if BaseOptions provided for markdown
        if options is None:
            return MarkdownRenderer(options=MarkdownOptions())
        elif isinstance(options, MarkdownOptions):
            return MarkdownRenderer(options=options)
        elif hasattr(options, 'markdown_options') and options.markdown_options:
            return MarkdownRenderer(options=options.markdown_options)
        else:
            return MarkdownRenderer(options=MarkdownOptions())

    def _resolve_transforms(self) -> list[NodeTransformer]:
        """Resolve transform names/instances to ordered list of instances.

        This method converts string transform names to instances via the
        registry, resolves dependencies, and maintains the user-provided
        order by expanding named transforms in place with their dependencies.

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
        result: list[NodeTransformer] = []
        seen_names: set[str] = set()

        # Process transforms in the order provided by user
        for t in self.transforms:
            if isinstance(t, NodeTransformer):
                # Direct instance - add as-is to maintain position
                result.append(t)
            elif isinstance(t, str):
                # Named transform - resolve with dependencies if not already seen
                if t not in seen_names:
                    # Get all dependencies in order (includes t itself)
                    ordered_deps = self.registry.resolve_dependencies([t])

                    # Add each dependency if not already seen
                    for name in ordered_deps:
                        if name not in seen_names:
                            result.append(self.registry.get_transform(name))
                            seen_names.add(name)
            else:
                raise TypeError(
                    f"Transform must be str or NodeTransformer, got {type(t).__name__}"
                )

        logger.debug(f"Resolved {len(result)} transform(s) for execution")
        return result

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

                # Update context.document to reflect any modifications
                context.document = result

            # Apply transform
            logger.debug(f"Applying transform: {transformer.__class__.__name__}")
            context.transform_name = transformer.__class__.__name__

            try:
                transformed_result = transformer.transform(result)

                if transformed_result is None:
                    raise ValueError(
                        f"Transform {transformer.__class__.__name__} returned None"
                    )

                # Type check: transformed_result should be a Document, but mypy sees it as Node | None
                # We use isinstance to narrow the type for mypy and ensure transforms return Document
                if not isinstance(transformed_result, Document):
                    raise TypeError(
                        f"Transform {transformer.__class__.__name__} must return Document, "
                        f"got {type(transformed_result).__name__}"
                    )
                result = transformed_result

                # Update context.document to reflect transform modifications
                context.document = result

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

                # Update context.document to reflect any modifications
                context.document = result

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

    def _emit_progress(
        self,
        event_type: str,
        message: str,
        current: int = 0,
        total: int = 0,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """Emit a progress event if callback is configured.

        This method safely invokes the progress callback, catching and logging
        any exceptions to prevent callback errors from breaking the pipeline.

        Parameters
        ----------
        event_type : str
            Type of progress event (started, page_done, finished, error)
        message : str
            Human-readable description of the event
        current : int, default = 0
            Current progress position
        total : int, default = 0
            Total items to process
        metadata : dict, optional
            Additional event-specific information

        """
        if self.progress_callback is None:
            return

        try:
            event = ProgressEvent(
                event_type=event_type,  # type: ignore
                message=message,
                current=current,
                total=total,
                metadata=metadata or {}
            )
            self.progress_callback(event)
        except Exception as e:
            # Don't let callback errors break the pipeline
            logger.warning(f"Progress callback failed: {e}", exc_info=True)

    def _render(self, document: Document) -> Union[str, bytes]:
        """Render document using configured renderer.

        Parameters
        ----------
        document : Document
            Document to render

        Returns
        -------
        str or bytes
            Rendered output (type depends on renderer)

        """
        logger.debug(f"Rendering document using {self.renderer.__class__.__name__}")

        # Try render_to_string first (for text-based renderers)
        try:
            return self.renderer.render_to_string(document)
        except NotImplementedError:
            pass

        # Fall back to render_to_bytes (for binary renderers)
        try:
            return self.renderer.render_to_bytes(document)
        except NotImplementedError:
            pass

        # Neither method is implemented
        raise NotImplementedError(
            f"Renderer {self.renderer.__class__.__name__} must implement "
            f"either render_to_string() or render_to_bytes()"
        )

    def execute(self, document: Document) -> Union[str, bytes]:
        """Execute complete pipeline.

        This method runs the full transformation and rendering pipeline:
        1. Execute post_ast hooks
        2. Apply transforms (with pre/post transform hooks)
        3. Apply element hooks
        4. Execute pre_render hooks
        5. Render to output format
        6. Execute post_render hooks

        If a progress_callback is configured, progress events are emitted at
        each stage of the pipeline.

        Parameters
        ----------
        document : Document
            Document to process

        Returns
        -------
        str or bytes
            Rendered output (type depends on renderer)

        Examples
        --------
        >>> pipeline = Pipeline(transforms=['remove-images'])
        >>> output = pipeline.execute(document)

        """
        logger.info("Starting pipeline execution")

        # Calculate total stages for progress reporting
        stage_count = 0
        current_stage = 0

        # Count stages
        if self.hook_manager.has_hooks('post_ast'):
            stage_count += 1
        if self.transforms:
            stage_count += len(self.transforms)
        if self.hook_manager.has_hooks('pre_render'):
            stage_count += 1
        # Element hooks traversal counts as 1 stage
        stage_count += 1
        # Rendering counts as 1 stage
        stage_count += 1
        if self.hook_manager.has_hooks('post_render'):
            stage_count += 1

        # Emit started event
        self._emit_progress(
            "started",
            "Starting pipeline execution",
            current=0,
            total=stage_count
        )

        try:
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

                document = result
                # Update context.document to reflect any modifications
                context.document = document

                current_stage += 1
                self._emit_progress(
                    "page_done",
                    "Completed post_ast hooks",
                    current=current_stage,
                    total=stage_count
                )

            # Apply transforms
            if self.transforms:
                transforms = self._resolve_transforms()
                for i, transformer in enumerate(transforms, 1):
                    # Pre-transform hook
                    if self.hook_manager.has_hooks('pre_transform'):
                        context.transform_name = transformer.__class__.__name__
                        result = self.hook_manager.execute_hooks('pre_transform', document, context)

                        if result is None:
                            raise ValueError("pre_transform hook removed document")

                        document = result
                        context.document = result

                    # Apply transform
                    logger.debug(f"Applying transform: {transformer.__class__.__name__}")
                    context.transform_name = transformer.__class__.__name__

                    try:
                        transformed_result = transformer.transform(document)

                        if transformed_result is None:
                            raise ValueError(
                                f"Transform {transformer.__class__.__name__} returned None"
                            )

                        # Type check: transformed_result should be a Document
                        if not isinstance(transformed_result, Document):
                            raise TypeError(
                                f"Transform {transformer.__class__.__name__} must return Document, "
                                f"got {type(transformed_result).__name__}"
                            )
                        document = transformed_result
                        context.document = document

                    except Exception as e:
                        logger.error(
                            f"Transform {transformer.__class__.__name__} failed: {e}",
                            exc_info=True
                        )
                        # Re-raise - transform failures are critical
                        raise

                    # Post-transform hook
                    if self.hook_manager.has_hooks('post_transform'):
                        result = self.hook_manager.execute_hooks('post_transform', document, context)

                        if result is None:
                            raise ValueError("post_transform hook removed document")

                        document = result
                        context.document = result

                    # Emit progress after each transform
                    current_stage += 1
                    self._emit_progress(
                        "page_done",
                        f"Completed transform {i}/{len(transforms)}: {transformer.__class__.__name__}",
                        current=current_stage,
                        total=stage_count,
                        metadata={"transform": transformer.__class__.__name__}
                    )

                context.transform_name = None

            # Pre-render hook (before element hooks, for document-level validation)
            if self.hook_manager.has_hooks('pre_render'):
                logger.debug("Executing pre_render hooks")
                result = self.hook_manager.execute_hooks('pre_render', document, context)

                if result is None:
                    raise ValueError("pre_render hook removed document")

                document = result
                # Update context.document to reflect any modifications
                context.document = document

                current_stage += 1
                self._emit_progress(
                    "page_done",
                    "Completed pre_render hooks",
                    current=current_stage,
                    total=stage_count
                )

            # Apply element hooks (after pre_render, before rendering)
            document = self._apply_element_hooks(document, context)
            # Update context.document to reflect any modifications from element hooks
            context.document = document

            current_stage += 1
            self._emit_progress(
                "page_done",
                "Completed element hooks traversal",
                current=current_stage,
                total=stage_count
            )

            # Render
            output = self._render(document)

            current_stage += 1
            self._emit_progress(
                "page_done",
                f"Completed rendering with {self.renderer.__class__.__name__}",
                current=current_stage,
                total=stage_count,
                metadata={"renderer": self.renderer.__class__.__name__}
            )

            # Post-render hook
            if self.hook_manager.has_hooks('post_render'):
                logger.debug("Executing post_render hooks")
                output = self.hook_manager.execute_hooks('post_render', output, context)

                if output is None:
                    raise ValueError("post_render hook removed output")

                current_stage += 1
                self._emit_progress(
                    "page_done",
                    "Completed post_render hooks",
                    current=current_stage,
                    total=stage_count
                )

            # Emit finished event
            self._emit_progress(
                "finished",
                "Pipeline execution complete",
                current=stage_count,
                total=stage_count
            )

            logger.info("Pipeline execution complete")
            return output

        except Exception as e:
            # Emit error event
            self._emit_progress(
                "error",
                f"Pipeline execution failed: {e}",
                current=current_stage,
                total=stage_count,
                metadata={"error": str(e)}
            )
            # Re-raise the exception
            raise


def apply(
    document: Document,
    transforms: Optional[list[Union[str, NodeTransformer]]] = None,
    hooks: Optional[dict[HookTarget, list[HookCallable]]] = None,
    strict_hooks: bool = False
) -> Document:
    """Apply transforms and hooks to document without rendering.

    This function provides AST-only processing by applying transforms and hooks
    to a document without the rendering stage. It reuses Pipeline internals to
    maintain consistent hook execution order.

    This is useful for developers who want to:
    - Process AST structures programmatically
    - Chain multiple transformation passes
    - Inspect/modify documents before rendering
    - Build custom rendering pipelines

    Parameters
    ----------
    document : Document
        AST document to process
    transforms : list, optional
        List of transforms to apply. Can be transform names (str) or
        NodeTransformer instances
    hooks : dict, optional
        Dictionary mapping hook targets to lists of hook callables.
        Hook targets can be pipeline stages ('post_ast', 'pre_transform',
        'post_transform', 'pre_render') or node types ('image', 'link', etc.)
    strict_hooks : bool, default = False
        Enable strict mode for hook exception handling. If True, hook exceptions
        are re-raised and abort the pipeline. If False (default), exceptions are
        logged and execution continues.

    Returns
    -------
    Document
        Processed document with transforms and hooks applied

    Raises
    ------
    TypeError
        If transform is not a string or NodeTransformer
    ValueError
        If transform name is not found or a hook removes the document node

    Notes
    -----
    The following hooks are executed in order:
    1. post_ast - After AST creation (document just came from conversion)
    2. pre_transform - Before each transform
    3. post_transform - After each transform
    4. pre_render - Before element hooks (for document-level validation)
    5. Element hooks - During tree traversal (image, link, heading, etc.)

    The post_render hook is NOT executed since no rendering occurs.

    Examples
    --------
    Apply transforms only:

        >>> from all2md import to_ast
        >>> from all2md.transforms import apply
        >>> doc = to_ast("document.pdf")
        >>> processed = apply(doc, transforms=['remove-images'])

    Apply hooks only:

        >>> def log_image(node, context):
        ...     print(f"Found image: {node.url}")
        ...     return node
        >>> processed = apply(doc, hooks={'image': [log_image]})

    Apply both transforms and hooks:

        >>> from all2md.transforms import HeadingOffsetTransform
        >>> processed = apply(
        ...     doc,
        ...     transforms=[HeadingOffsetTransform(offset=1), 'remove-images'],
        ...     hooks={
        ...         'pre_render': [validate_document],
        ...         'link': [rewrite_links]
        ...     }
        ... )

    Chain multiple processing passes:

        >>> doc1 = apply(doc, transforms=['heading-offset'])
        >>> doc2 = apply(doc1, transforms=['remove-images'])
        >>> markdown = render(doc2)

    With strict hook mode:

        >>> processed = apply(
        ...     doc,
        ...     hooks={'image': [validate_image]},
        ...     strict_hooks=True  # Hook failures will abort
        ... )

    """
    logger.info("Starting apply() execution (no rendering)")

    # Create a temporary pipeline without a renderer to reuse internals
    # We don't actually call execute(), just use the helper methods
    pipeline = Pipeline(transforms=transforms, hooks=hooks, strict_hooks=strict_hooks)

    # Create context
    context = HookContext(
        document=document,
        metadata=document.metadata.copy(),
        shared={}
    )

    # Post-AST hook (document just came from conversion)
    if pipeline.hook_manager.has_hooks('post_ast'):
        logger.debug("Executing post_ast hooks")
        result = pipeline.hook_manager.execute_hooks('post_ast', document, context)

        if result is None:
            raise ValueError("post_ast hook removed document")

        document = result
        # Update context.document to reflect any modifications
        context.document = document

    # Apply transforms
    if pipeline.transforms:
        document = pipeline._apply_transforms(document, context)
        # Update context.document to reflect transform modifications
        context.document = document

    # Pre-render hook (before element hooks, for document-level validation)
    if pipeline.hook_manager.has_hooks('pre_render'):
        logger.debug("Executing pre_render hooks")
        result = pipeline.hook_manager.execute_hooks('pre_render', document, context)

        if result is None:
            raise ValueError("pre_render hook removed document")

        document = result
        # Update context.document to reflect any modifications
        context.document = document

    # Apply element hooks (after pre_render, would normally be before rendering)
    document = pipeline._apply_element_hooks(document, context)
    # Update context.document to reflect any modifications from element hooks
    context.document = document

    logger.info("Apply execution complete")
    return document


def render(
    document: Document,
    transforms: Optional[list[Union[str, NodeTransformer]]] = None,
    hooks: Optional[dict[HookTarget, list[HookCallable]]] = None,
    renderer: Optional[Union[str, type, Any]] = None,
    options: Optional[Union[BaseRendererOptions, MarkdownOptions]] = None,
    progress_callback: Optional[ProgressCallback] = None,
    strict_hooks: bool = False,
    **kwargs: Any
) -> Union[str, bytes]:
    """Render document with transforms and hooks using specified renderer.

    This is the high-level entry point for the transformation pipeline.
    It creates a Pipeline instance and executes it to produce rendered output.

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
    renderer : str, type, or renderer instance, optional
        Renderer to use. Can be:
        - Format name string (e.g., "markdown") - looked up via registry
        - Renderer class (e.g., MarkdownRenderer)
        - Renderer instance (e.g., MarkdownRenderer())
        Defaults to MarkdownRenderer
    options : BaseRendererOptions or MarkdownOptions, optional
        Options for rendering (used if renderer is string or class)
    progress_callback : ProgressCallback, optional
        Optional callback for progress updates during rendering
    strict_hooks : bool, default = False
        Enable strict mode for hook exception handling. If True, hook exceptions
        are re-raised and abort the pipeline. If False (default), exceptions are
        logged and execution continues.
    **kwargs
        Additional keyword arguments passed to MarkdownOptions if
        options is not provided and renderer is markdown

    Returns
    -------
    str or bytes
        Rendered output (type depends on renderer)

    Raises
    ------
    TypeError
        If transform is not a string or NodeTransformer
    ValueError
        If transform name is not found or a hook removes a required node

    Examples
    --------
    Basic rendering to markdown:
        >>> from all2md import to_ast
        >>> from all2md.transforms import render
        >>> doc = to_ast("document.pdf")
        >>> markdown = render(doc)

    With transforms by name:
        >>> markdown = render(doc, transforms=['remove-images'])

    With custom renderer:
        >>> from all2md.renderers.markdown import MarkdownRenderer
        >>> output = render(
        ...     doc,
        ...     renderer=MarkdownRenderer(options=MarkdownOptions(flavor='commonmark'))
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

    With strict hook mode:
        >>> markdown = render(
        ...     doc,
        ...     hooks={'image': [validate_image]},
        ...     strict_hooks=True  # Hook failures will abort
        ... )

    """
    # Create options from kwargs if not provided
    if options is None and kwargs:
        options = MarkdownOptions(**kwargs)
    elif options is None and renderer is None:
        # Default to MarkdownOptions for markdown renderer
        options = MarkdownOptions()

    # Create and execute pipeline
    pipeline = Pipeline(
        transforms=transforms,
        hooks=hooks,
        renderer=renderer,
        options=options,
        progress_callback=progress_callback,
        strict_hooks=strict_hooks
    )

    return pipeline.execute(document)


__all__ = [
    "Pipeline",
    "HookAwareVisitor",
    "apply",
    "render",
]
