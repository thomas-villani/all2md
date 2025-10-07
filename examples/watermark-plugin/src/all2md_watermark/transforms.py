# Copyright (c) 2025 Your Name
"""Watermark transform for all2md.

This module provides a transform that adds watermark metadata to all images
in a document. This can be useful for marking documents as drafts, confidential,
or with other custom labels.
"""
from all2md.ast import Image
from all2md.ast.transforms import NodeTransformer


class WatermarkTransform(NodeTransformer):
    """Add watermark metadata to all images.

    This transform adds a watermark field to the metadata of each image node
    in the document. The watermark text can be customized and is stored in the
    image's metadata for downstream processing.

    Parameters
    ----------
    text : str, optional
        The watermark text to add to images (default: "CONFIDENTIAL")

    Examples
    --------
    >>> from all2md import to_markdown
    >>> from all2md_watermark import WatermarkTransform
    >>>
    >>> # Add default watermark
    >>> transform = WatermarkTransform()
    >>> markdown = to_markdown('document.pdf', transforms=[transform])
    >>>
    >>> # Custom watermark
    >>> transform = WatermarkTransform(text="DRAFT")
    >>> markdown = to_markdown('document.pdf', transforms=[transform])

    """

    def __init__(self, text: str = "CONFIDENTIAL"):
        """Initialize the watermark transform.

        Parameters
        ----------
        text : str, optional
            Watermark text (default: "CONFIDENTIAL")

        """
        super().__init__()
        self.watermark_text = text

    def visit_image(self, node: Image) -> Image:
        """Visit an image node and add watermark metadata.

        Parameters
        ----------
        node : Image
            The image node to process

        Returns
        -------
        Image
            New image node with watermark in metadata

        """
        # Process children first (if any)
        node = super().visit_image(node)

        # Create new metadata dict with watermark
        new_metadata = node.metadata.copy()
        new_metadata['watermark'] = self.watermark_text

        # Return new node with updated metadata
        return Image(
            url=node.url,
            alt_text=node.alt_text,
            title=node.title,
            metadata=new_metadata
        )
