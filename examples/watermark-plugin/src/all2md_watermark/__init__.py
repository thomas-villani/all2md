# Copyright (c) 2025 Your Name
"""Watermark transform plugin for all2md.

This plugin embeds a visual watermark into image data when the original bytes
are available (base64 or downloaded attachments) and records watermark metadata
for other images.
"""
from all2md.transforms import ParameterSpec, TransformMetadata

from .transforms import WatermarkTransform

# Transform metadata for registry discovery
METADATA = TransformMetadata(
    name="watermark",
    description="Embed or record watermarks for images",
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
    version="1.1.0",
    author="Your Name"
)

__version__ = "1.1.0"
__all__ = ["WatermarkTransform", "METADATA"]
