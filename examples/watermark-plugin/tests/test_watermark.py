# Copyright (c) 2025 Your Name
"""Tests for watermark transform."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image as PILImage

from all2md_watermark import METADATA, WatermarkTransform

from all2md.ast import Document, Image, Paragraph


def _make_base64_png(color: str = "blue") -> tuple[str, bytes]:
    image = PILImage.new("RGB", (32, 32), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    raw = buffer.getvalue()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}", raw


class TestWatermarkTransform:
    """Test WatermarkTransform functionality."""

    def test_default_watermark(self) -> None:
        transform = WatermarkTransform()
        assert transform.watermark_text == "CONFIDENTIAL"

    def test_custom_watermark(self) -> None:
        transform = WatermarkTransform(text="DRAFT")
        assert transform.watermark_text == "DRAFT"

    def test_adds_metadata_without_bytes(self) -> None:
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(
                            url="test.jpg",
                            alt_text="Test Image",
                            title="Test",
                            metadata={},
                        )
                    ]
                )
            ]
        )

        transform = WatermarkTransform(text="SAMPLE")
        result = transform.transform(doc)

        image = result.children[0].content[0]
        assert isinstance(image, Image)
        assert image.metadata["watermark"] == "SAMPLE"
        assert "watermark_applied" not in image.metadata

    def test_preserves_existing_metadata(self) -> None:
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(
                            url="test.jpg",
                            alt_text="Test",
                            title="Test",
                            metadata={"custom_field": "custom_value"},
                        )
                    ]
                )
            ]
        )

        transform = WatermarkTransform()
        result = transform.transform(doc)

        image = result.children[0].content[0]
        assert image.metadata["custom_field"] == "custom_value"
        assert image.metadata["watermark"] == "CONFIDENTIAL"
        assert "watermark_applied" not in image.metadata

    def test_multiple_images(self) -> None:
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url="img1.jpg", alt_text="1", metadata={}),
                        Image(url="img2.jpg", alt_text="2", metadata={}),
                    ]
                )
            ]
        )

        transform = WatermarkTransform(text="TEST")
        result = transform.transform(doc)

        images = result.children[0].content
        assert images[0].metadata["watermark"] == "TEST"
        assert images[1].metadata["watermark"] == "TEST"

    def test_watermarks_base64_image(self) -> None:
        data_uri, original_bytes = _make_base64_png()
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(
                            url=data_uri,
                            alt_text="Base64",
                            metadata={"source_data": "base64"},
                        )
                    ]
                )
            ]
        )

        transform = WatermarkTransform(text="WM")
        result = transform.transform(doc)

        image = result.children[0].content[0]
        assert image.metadata["watermark"] == "WM"
        assert image.metadata["watermark_applied"] is True

        match = base64.b64decode(image.url.split(",", 1)[1])
        assert match != original_bytes

    def test_watermarks_downloaded_image(self, tmp_path) -> None:
        image_path = tmp_path / "local.png"
        PILImage.new("RGB", (32, 32), color="green").save(image_path, format="PNG")
        original_bytes = image_path.read_bytes()

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(
                            url=str(image_path),
                            alt_text="Local",
                            metadata={"source_data": "downloaded"},
                        )
                    ]
                )
            ]
        )

        transform = WatermarkTransform(text="WM")
        result = transform.transform(doc)

        image = result.children[0].content[0]
        assert image.metadata["watermark"] == "WM"
        assert image.metadata["watermark_applied"] is True

        updated_bytes = Path(image.url).read_bytes()
        assert updated_bytes != original_bytes


class TestMetadata:
    """Test transform metadata."""

    def test_metadata_exists(self) -> None:
        assert METADATA is not None
        assert METADATA.name == "watermark"
        assert METADATA.transformer_class == WatermarkTransform

    def test_metadata_parameters(self) -> None:
        assert "text" in METADATA.parameters
        param = METADATA.parameters["text"]
        assert param.type is str
        assert param.default == "CONFIDENTIAL"
        assert param.cli_flag == "--watermark-text"

    def test_create_instance_from_metadata(self) -> None:
        transform = METADATA.create_instance(text="CUSTOM")
        assert isinstance(transform, WatermarkTransform)
        assert transform.watermark_text == "CUSTOM"

    def test_create_instance_with_defaults(self) -> None:
        transform = METADATA.create_instance()
        assert isinstance(transform, WatermarkTransform)
        assert transform.watermark_text == "CONFIDENTIAL"
