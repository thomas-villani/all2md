#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/_builtin_metadata.py
"""Metadata definitions for built-in transforms.

This module defines TransformMetadata objects for all built-in transforms,
enabling registration via entry points and CLI integration.

These metadata objects are exported via entry points in pyproject.toml.

"""

from __future__ import annotations

from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS
from all2md.transforms.builtin import (
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
from all2md.transforms.metadata import ParameterSpec, TransformMetadata

# RemoveImagesTransform metadata
REMOVE_IMAGES_METADATA = TransformMetadata(
    name="remove-images",
    description="Remove all Image nodes from the AST",
    transformer_class=RemoveImagesTransform,
    parameters={},
    priority=100,
    tags=["images", "cleanup"],
    version="1.0.0",
    author="all2md",
)

# RemoveNodesTransform metadata
REMOVE_NODES_METADATA = TransformMetadata(
    name="remove-nodes",
    description="Remove nodes of specified types from the AST",
    transformer_class=RemoveNodesTransform,
    parameters={
        "node_types": ParameterSpec(
            type=list,
            element_type=str,
            default=["image"],
            help="List of node types to remove (e.g., 'image', 'table', 'code_block')",
            cli_flag="--node-types",
        )
    },
    priority=100,
    tags=["cleanup"],
    version="1.0.0",
    author="all2md",
)

# HeadingOffsetTransform metadata
HEADING_OFFSET_METADATA = TransformMetadata(
    name="heading-offset",
    description="Shift heading levels by a specified offset",
    transformer_class=HeadingOffsetTransform,
    parameters={
        "offset": ParameterSpec(
            type=int, default=1, help="Number of levels to shift (positive or negative)", cli_flag="--heading-offset"
        )
    },
    priority=100,
    tags=["headings", "structure"],
    version="1.0.0",
    author="all2md",
)

# LinkRewriterTransform metadata
LINK_REWRITER_METADATA = TransformMetadata(
    name="link-rewriter",
    description="Rewrite link URLs using regex pattern matching",
    transformer_class=LinkRewriterTransform,
    parameters={
        "pattern": ParameterSpec(
            type=str, required=True, help="Regex pattern to match in URLs", cli_flag="--link-pattern"
        ),
        "replacement": ParameterSpec(
            type=str, required=True, help="Replacement string for matched pattern", cli_flag="--link-replacement"
        ),
    },
    priority=200,
    tags=["links", "rewrite"],
    version="1.0.0",
    author="all2md",
)

# TextReplacerTransform metadata
TEXT_REPLACER_METADATA = TransformMetadata(
    name="text-replacer",
    description="Find and replace text in Text nodes",
    transformer_class=TextReplacerTransform,
    parameters={
        "find": ParameterSpec(type=str, required=True, help="Text to find", cli_flag="--find-text"),
        "replace": ParameterSpec(type=str, required=True, help="Replacement text", cli_flag="--replace-text"),
    },
    priority=200,
    tags=["text", "replace"],
    version="1.0.0",
    author="all2md",
)

# AddHeadingIdsTransform metadata
ADD_HEADING_IDS_METADATA = TransformMetadata(
    name="add-heading-ids",
    description="Generate and add unique IDs to heading nodes for anchors",
    transformer_class=AddHeadingIdsTransform,
    parameters={
        "id_prefix": ParameterSpec(
            type=str, default="", help="Prefix to add to all generated IDs", cli_flag="--heading-id-prefix"
        ),
        "separator": ParameterSpec(
            type=str,
            default="-",
            help="Separator for multi-word slugs and duplicate handling",
            cli_flag="--heading-id-separator",
        ),
    },
    priority=150,
    tags=["headings", "anchors", "ids"],
    version="1.0.0",
    author="all2md",
)

# RemoveBoilerplateTextTransform metadata
REMOVE_BOILERPLATE_METADATA = TransformMetadata(
    name="remove-boilerplate",
    description="Remove paragraphs matching common boilerplate patterns",
    transformer_class=RemoveBoilerplateTextTransform,
    parameters={
        "patterns": ParameterSpec(
            type=list,
            element_type=str,
            default=DEFAULT_BOILERPLATE_PATTERNS,
            help="List of regex patterns to match for removal",
            cli_flag="--boilerplate-patterns",
        )
    },
    priority=100,
    tags=["cleanup", "text"],
    version="1.0.0",
    author="all2md",
)

# AddConversionTimestampTransform metadata
ADD_TIMESTAMP_METADATA = TransformMetadata(
    name="add-timestamp",
    description="Add conversion timestamp to document metadata",
    transformer_class=AddConversionTimestampTransform,
    parameters={
        "field_name": ParameterSpec(
            type=str,
            default="conversion_timestamp",
            help="Metadata field name for the timestamp",
            cli_flag="--timestamp-field",
        ),
        "timestamp_format": ParameterSpec(
            type=str,
            default="iso",
            help="Timestamp format: 'iso' for ISO 8601, 'unix' for Unix timestamp, or any strftime format string",
            cli_flag="--timestamp-format",
        ),
        "timespec": ParameterSpec(
            type=str,
            default="seconds",
            choices=["auto", "hours", "minutes", "seconds", "milliseconds", "microseconds"],
            help=(
                "Time precision for ISO format timestamps "
                "(auto, hours, minutes, seconds, milliseconds, microseconds). "
                "Only applies when format='iso'"
            ),
            cli_flag="--timestamp-timespec",
        ),
    },
    priority=300,
    tags=["metadata", "timestamp"],
    version="1.0.0",
    author="all2md",
)

# CalculateWordCountTransform metadata
WORD_COUNT_METADATA = TransformMetadata(
    name="word-count",
    description="Calculate word and character counts and add to metadata",
    transformer_class=CalculateWordCountTransform,
    parameters={
        "word_field": ParameterSpec(
            type=str, default="word_count", help="Metadata field name for word count", cli_flag="--word-count-field"
        ),
        "char_field": ParameterSpec(
            type=str,
            default="char_count",
            help="Metadata field name for character count",
            cli_flag="--char-count-field",
        ),
    },
    priority=300,
    tags=["metadata", "statistics"],
    version="1.0.0",
    author="all2md",
)

# AddAttachmentFootnotesTransform metadata
ADD_ATTACHMENT_FOOTNOTES_METADATA = TransformMetadata(
    name="add-attachment-footnotes",
    description="Add footnote definitions for attachment references",
    transformer_class=AddAttachmentFootnotesTransform,
    parameters={
        "section_title": ParameterSpec(
            type=str,
            default="Attachments",
            help="Title for the footnote section heading (use empty string to skip heading)",
            cli_flag="--attachment-section-title",
        ),
        "add_definitions_for_images": ParameterSpec(
            type=bool,
            default=True,
            help="Add definitions for image footnote references",
            cli_flag="--add-image-footnotes",
        ),
        "add_definitions_for_links": ParameterSpec(
            type=bool,
            default=True,
            help="Add definitions for link footnote references",
            cli_flag="--add-link-footnotes",
        ),
    },
    priority=400,
    tags=["attachments", "footnotes", "cleanup"],
    version="1.0.0",
    author="all2md",
)

# GenerateTocTransform metadata
GENERATE_TOC_METADATA = TransformMetadata(
    name="generate-toc",
    description="Generate table of contents from document headings",
    transformer_class=GenerateTocTransform,
    parameters={
        "title": ParameterSpec(
            type=str, default="Table of Contents", help="Title for the TOC section", cli_flag="--toc-title"
        ),
        "max_depth": ParameterSpec(
            type=int, default=3, help="Maximum heading level to include (1-6)", cli_flag="--toc-max-depth"
        ),
        "position": ParameterSpec(
            type=str, default="top", help="Position to insert the TOC ('top' or 'bottom')", cli_flag="--toc-position"
        ),
        "add_links": ParameterSpec(
            type=bool,
            default=True,
            help="Whether to create links to headings (requires heading IDs)",
            cli_flag="--toc-add-links",
        ),
        "separator": ParameterSpec(
            type=str,
            default="-",
            help="Separator for generating heading IDs when not present",
            cli_flag="--toc-separator",
        ),
    },
    priority=250,
    tags=["toc", "headings", "navigation"],
    version="1.0.0",
    author="all2md",
)

__all__ = [
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
