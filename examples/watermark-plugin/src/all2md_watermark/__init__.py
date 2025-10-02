# Copyright (c) 2025 Your Name
"""Watermark transform plugin for all2md.

This plugin provides a transform that adds watermark metadata to all images
in a document during conversion.
"""
from all2md.transforms import ParameterSpec, TransformMetadata

from .transforms import WatermarkTransform

# Transform metadata for registry discovery
METADATA = TransformMetadata(
    name="watermark",
    description="Add watermark metadata to all images",
    transformer_class=WatermarkTransform,
    parameters={
        'text': ParameterSpec(
            type=str,
            default="CONFIDENTIAL",
            help="Watermark text to add to images",
            cli_flag='--watermark-text'
        )
    },
    priority=100,
    tags=["images", "metadata"],
    version="1.0.0",
    author="Your Name"
)

__version__ = "1.0.0"
__all__ = ["WatermarkTransform", "METADATA"]
