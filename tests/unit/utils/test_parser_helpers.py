"""Tests for parser helper utilities related to attachments."""

from all2md.ast import Image
from all2md.utils.parser_helpers import attachment_result_to_image_node


class TestAttachmentResultToImageNode:
    """Tests for converting attachment results into image nodes."""

    def test_sets_metadata_for_base64_source(self) -> None:
        """Image metadata should indicate base64 source when provided."""
        result = {
            "markdown": "![alt](data:image/png;base64,AAA)",
            "url": "data:image/png;base64,AAA",
            "source_data": "base64",
        }

        image_node = attachment_result_to_image_node(result, fallback_alt_text="image")
        assert isinstance(image_node, Image)
        assert image_node.metadata.get("source_data") == "base64"

    def test_leaves_metadata_empty_when_not_supplied(self) -> None:
        """No metadata key should be added when source data is absent."""
        result = {
            "markdown": "![alt](http://example.com/image.png)",
            "url": "http://example.com/image.png",
        }

        image_node = attachment_result_to_image_node(result, fallback_alt_text="image")
        assert isinstance(image_node, Image)
        assert "source_data" not in image_node.metadata
