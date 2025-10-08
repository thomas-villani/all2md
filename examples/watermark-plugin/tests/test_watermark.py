# Copyright (c) 2025 Your Name
"""Tests for watermark transform."""
from all2md_watermark import METADATA, WatermarkTransform

from all2md.ast import Document, Image, Paragraph


class TestWatermarkTransform:
    """Test WatermarkTransform functionality."""

    def test_default_watermark(self):
        """Test default watermark text."""
        transform = WatermarkTransform()
        assert transform.watermark_text == "CONFIDENTIAL"

    def test_custom_watermark(self):
        """Test custom watermark text."""
        transform = WatermarkTransform(text="DRAFT")
        assert transform.watermark_text == "DRAFT"

    def test_adds_watermark_to_image(self):
        """Test that watermark is added to image metadata."""
        # Create test document with an image
        doc = Document(children=[
            Paragraph(content=[
                Image(
                    url="test.jpg",
                    alt_text="Test Image",
                    title="Test",
                    metadata={}
                )
            ])
        ])

        # Apply transform
        transform = WatermarkTransform(text="SAMPLE")
        result = transform.transform(doc)

        # Verify watermark was added
        image = result.children[0].content[0]
        assert isinstance(image, Image)
        assert 'watermark' in image.metadata
        assert image.metadata['watermark'] == "SAMPLE"

    def test_preserves_existing_metadata(self):
        """Test that existing metadata is preserved."""
        # Create image with existing metadata
        doc = Document(children=[
            Paragraph(content=[
                Image(
                    url="test.jpg",
                    alt_text="Test",
                    title="Test",
                    metadata={'custom_field': 'custom_value'}
                )
            ])
        ])

        # Apply transform
        transform = WatermarkTransform()
        result = transform.transform(doc)

        # Verify both old and new metadata exist
        image = result.children[0].content[0]
        assert image.metadata['custom_field'] == 'custom_value'
        assert image.metadata['watermark'] == "CONFIDENTIAL"

    def test_multiple_images(self):
        """Test that all images get watermarked."""
        # Create document with multiple images
        doc = Document(children=[
            Paragraph(content=[
                Image(url="img1.jpg", alt_text="1", metadata={}),
                Image(url="img2.jpg", alt_text="2", metadata={})
            ])
        ])

        # Apply transform
        transform = WatermarkTransform(text="TEST")
        result = transform.transform(doc)

        # Verify all images were watermarked
        images = result.children[0].content
        assert images[0].metadata['watermark'] == "TEST"
        assert images[1].metadata['watermark'] == "TEST"


class TestMetadata:
    """Test transform metadata."""

    def test_metadata_exists(self):
        """Test that METADATA is properly defined."""
        assert METADATA is not None
        assert METADATA.name == "watermark"
        assert METADATA.transformer_class == WatermarkTransform

    def test_metadata_parameters(self):
        """Test parameter specifications."""
        assert 'text' in METADATA.parameters
        param = METADATA.parameters['text']
        assert param.type is str
        assert param.default == "CONFIDENTIAL"
        assert param.cli_flag == '--watermark-text'

    def test_create_instance_from_metadata(self):
        """Test creating transform instance from metadata."""
        transform = METADATA.create_instance(text="CUSTOM")
        assert isinstance(transform, WatermarkTransform)
        assert transform.watermark_text == "CUSTOM"

    def test_create_instance_with_defaults(self):
        """Test creating instance with default parameters."""
        transform = METADATA.create_instance()
        assert isinstance(transform, WatermarkTransform)
        assert transform.watermark_text == "CONFIDENTIAL"
