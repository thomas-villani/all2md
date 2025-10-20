# Copyright (c) 2025 Your Name
"""Watermark transform for all2md.

This module provides a transform that paints an actual watermark onto image
data when the parser preserved the original bytes (base64 or downloaded
attachments). For all other images it still records watermark metadata so
downstream tools can react accordingly.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

from all2md.ast import Image
from all2md.ast.transforms import NodeTransformer

logger = logging.getLogger(__name__)

_DATA_URI_PATTERN = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$")

_MIME_TO_FORMAT = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
    "image/tiff": "TIFF",
}

_EXTENSION_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


class WatermarkTransform(NodeTransformer):
    """Embed a visual watermark into images when possible.

    Parameters
    ----------
    text : str, optional
        The watermark text to render on images (default: "CONFIDENTIAL")

    Notes
    -----
    For images that originated from `attachment_mode="base64"` or
    `attachment_mode="download"`, the transform mutates the underlying bytes
    to include a semi-transparent watermark. For all other images the transform
    still records the watermark text in metadata so that other tooling can act
    on it if desired.
    """

    def __init__(self, text: str = "CONFIDENTIAL") -> None:
        super().__init__()
        self.watermark_text = text

    def visit_image(self, node: Image) -> Image:
        """Visit an image node and apply watermark when data is available."""

        node = super().visit_image(node)

        new_metadata = node.metadata.copy()
        new_metadata["watermark"] = self.watermark_text

        updated_url = node.url
        watermark_applied = False

        try:
            source_data = node.metadata.get("source_data")
            if source_data == "base64" and node.url:
                updated_url = self._watermark_data_uri(node.url)
                watermark_applied = True
            elif source_data == "downloaded" and node.url:
                self._watermark_downloaded_file(node.url)
                watermark_applied = True
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning("Failed to apply watermark to image %s: %s", node.url, exc)
        else:
            if watermark_applied:
                new_metadata["watermark_applied"] = True

        return Image(
            url=updated_url,
            alt_text=node.alt_text,
            title=node.title,
            width=node.width,
            height=node.height,
            metadata=new_metadata,
            source_location=node.source_location,
        )

    def _watermark_data_uri(self, data_uri: str) -> str:
        match = _DATA_URI_PATTERN.match(data_uri)
        if not match:
            raise ValueError("Unsupported data URI format")

        mime = match.group("mime")
        raw_data = base64.b64decode(match.group("data"))
        updated_bytes = self._watermark_bytes(raw_data, mime)
        encoded = base64.b64encode(updated_bytes).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _watermark_downloaded_file(self, url: str) -> None:
        path = Path(url)
        if not path.exists() and not path.is_absolute():
            # Try resolving relative paths against the current working directory
            candidate = Path.cwd() / path
            if candidate.exists():
                path = candidate

        if not path.exists():
            raise FileNotFoundError(f"Downloaded image not found: {url}")

        mime = _EXTENSION_TO_MIME.get(path.suffix.lower())
        updated_bytes = self._watermark_bytes(path.read_bytes(), mime)
        path.write_bytes(updated_bytes)

    def _watermark_bytes(self, payload: bytes, mime: Optional[str]) -> bytes:
        with PILImage.open(io.BytesIO(payload)) as pil_image:
            watermarked = self._apply_watermark(pil_image)
            buffer = io.BytesIO()
            format_name = self._mime_to_format(mime) or pil_image.format or "PNG"
            watermarked.save(buffer, format=format_name)
            return buffer.getvalue()

    def _apply_watermark(self, image: PILImage.Image) -> PILImage.Image:
        base = image.convert("RGBA")
        overlay = PILImage.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(12, int(min(base.size) * 0.15))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

        text = self.watermark_text
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        position = (
            (base.width - text_width) / 2,
            (base.height - text_height) / 2,
        )

        draw.text(position, text, fill=(255, 0, 0, 90), font=font)

        combined = PILImage.alpha_composite(base, overlay)
        return combined.convert(image.mode)

    @staticmethod
    def _mime_to_format(mime: Optional[str]) -> Optional[str]:
        if not mime:
            return None
        mime_lower = mime.lower()
        return _MIME_TO_FORMAT.get(mime_lower)
