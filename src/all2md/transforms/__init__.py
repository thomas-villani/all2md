#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/__init__.py
"""Transform system for AST manipulation.

This package provides a plugin-based transformation system for manipulating
AST structures before rendering. It includes:

- Transform registry for plugin discovery
- Hook system for pipeline interception
- Metadata classes for transform description
- Built-in transforms for common operations

The transform system uses Python entry points for plugin discovery, allowing
third-party packages to register custom transforms.

Examples
--------
Use a transform by name:

    >>> from all2md import to_ast
    >>> from all2md.transforms import render
    >>> doc = to_ast("document.pdf")
    >>> markdown = render(doc, transforms=['remove-images'])

Use a transform instance with parameters:

    >>> from all2md.transforms import render, HeadingOffsetTransform
    >>> markdown = render(
    ...     doc,
    ...     transforms=[HeadingOffsetTransform(offset=1)]
    ... )

Register a custom transform:

    >>> from all2md.transforms import transform_registry, TransformMetadata
    >>> from all2md.ast.transforms import NodeTransformer
    >>>
    >>> class MyTransform(NodeTransformer):
    ...     pass
    >>>
    >>> metadata = TransformMetadata(
    ...     name="my-transform",
    ...     description="My custom transform",
    ...     transformer_class=MyTransform
    ... )
    >>> transform_registry.register(metadata)

Use hooks for element-specific processing:

    >>> def log_images(node, context):
    ...     print(f"Image: {node.url}")
    ...     return node
    >>>
    >>> from all2md.transforms import HookManager
    >>> hooks = {'image': [log_images]}
    >>> markdown = render(doc, hooks=hooks)

"""

from __future__ import annotations

# Built-in transform metadata (for advanced users)
from ._builtin_metadata import (
    ADD_ATTACHMENT_FOOTNOTES_METADATA,
    ADD_HEADING_IDS_METADATA,
    ADD_TIMESTAMP_METADATA,
    GENERATE_TOC_METADATA,
    HEADING_OFFSET_METADATA,
    LINK_REWRITER_METADATA,
    REMOVE_BOILERPLATE_METADATA,
    REMOVE_IMAGES_METADATA,
    REMOVE_NODES_METADATA,
    TEXT_REPLACER_METADATA,
    WORD_COUNT_METADATA,
)

# Built-in transforms
from .builtin import (
    AddAttachmentFootnotesTransform,
    AddConversionTimestampTransform,
    AddHeadingIdsTransform,
    CalculateWordCountTransform,
    GenerateTocTransform,
    HeadingOffsetTransform,
    LinkRewriterTransform,
    RemoveBoilerplateTextTransform,
    RemoveImagesTransform,
    RemoveNodesTransform,
    TextReplacerTransform,
)

# Core classes
from .hooks import HookCallable, HookContext, HookManager, HookPoint, HookTarget, NodeType
from .metadata import ParameterSpec, TransformMetadata

# Pipeline
from .pipeline import HookAwareVisitor, Pipeline, apply, render

# Registry
from .registry import TransformRegistry, transform_registry

# Version info
__version__ = "0.1.0"

__all__ = [
    # Metadata
    "TransformMetadata",
    "ParameterSpec",
    # Registry
    "TransformRegistry",
    "transform_registry",
    # Hooks
    "HookManager",
    "HookContext",
    "HookCallable",
    "HookPoint",
    "NodeType",
    "HookTarget",
    # Pipeline
    "Pipeline",
    "HookAwareVisitor",
    "apply",
    "render",
    # Built-in Transforms
    "RemoveImagesTransform",
    "RemoveNodesTransform",
    "HeadingOffsetTransform",
    "LinkRewriterTransform",
    "TextReplacerTransform",
    "AddHeadingIdsTransform",
    "RemoveBoilerplateTextTransform",
    "AddConversionTimestampTransform",
    "CalculateWordCountTransform",
    "AddAttachmentFootnotesTransform",
    "GenerateTocTransform",
    # Built-in Metadata
    "REMOVE_IMAGES_METADATA",
    "REMOVE_NODES_METADATA",
    "HEADING_OFFSET_METADATA",
    "LINK_REWRITER_METADATA",
    "TEXT_REPLACER_METADATA",
    "ADD_HEADING_IDS_METADATA",
    "REMOVE_BOILERPLATE_METADATA",
    "ADD_TIMESTAMP_METADATA",
    "WORD_COUNT_METADATA",
    "ADD_ATTACHMENT_FOOTNOTES_METADATA",
    "GENERATE_TOC_METADATA",
]
