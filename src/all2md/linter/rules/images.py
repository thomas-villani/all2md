"""Image rules (IMG001-IMG005).

Images are a first-class concern in all2md's attachment pipeline. These
rules check for missing alt text, broken local image paths, duplicate
images, oversized base64 inlining, and unhelpful boilerplate alt text.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from all2md.ast import Document, Image, Node, NodeCollector
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

_DEFAULT_MAX_IMAGE_BYTES = 1024 * 1024  # 1 MiB
_DECORATIVE_ALT_TEXTS = frozenset({"image", "photo", "picture", "screenshot", "img", "graphic"})
_DATA_URI_RE = re.compile(r"^data:[^;]+;base64,(.*)$", re.IGNORECASE | re.DOTALL)


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


def _line(node: Node) -> int | None:
    return node.source_location.line if node.source_location else None


def _column(node: Node) -> int | None:
    return node.source_location.column if node.source_location else None


def _collect_images(doc: Document) -> list[Image]:
    collector = NodeCollector(lambda n: isinstance(n, Image))
    doc.accept(collector)
    return [n for n in collector.collected if isinstance(n, Image)]


def _is_remote_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https", "ftp", "ftps")


def _is_data_uri(url: str) -> bool:
    return url.lower().startswith("data:")


class MissingAltTextRule(LintRule):
    """IMG001: Flag images whose ``alt_text`` is empty."""

    code = "IMG001"
    name = "missing-alt-text"
    category = "images"
    description = "Images should have descriptive alt text for accessibility."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each image with no alt text."""
        violations: list[Violation] = []
        for image in _collect_images(ctx.document):
            if not image.alt_text or not image.alt_text.strip():
                violations.append(
                    self.build_violation(
                        message=f"Image has no alt text: {image.url!r}",
                        line=_line(image),
                        column=_column(image),
                        node_type="Image",
                        suggestion="Describe the image's purpose or content for screen readers",
                    )
                )
        return violations


class ImageNotFoundRule(LintRule):
    """IMG002: Flag images whose URL points to a missing local file.

    Only triggers when the lint context has a ``file_path`` (so the
    relative path can be resolved) and the URL is not remote or a data
    URI. Skipped silently when running on stdin / in-memory documents.
    """

    code = "IMG002"
    name = "image-not-found"
    category = "images"
    description = "Local image paths should resolve to a file on disk."
    default_severity = Severity.ERROR

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each missing local image file."""
        if not ctx.file_path:
            return []
        base = Path(ctx.file_path).resolve().parent
        violations: list[Violation] = []
        for image in _collect_images(ctx.document):
            url = image.url or ""
            if not url or _is_remote_url(url) or _is_data_uri(url):
                continue
            target = (base / url).resolve()
            if not target.exists():
                violations.append(
                    self.build_violation(
                        message=f"Image not found: {url!r}",
                        line=_line(image),
                        column=_column(image),
                        node_type="Image",
                        suggestion="Check the path or move the image into place",
                        context=str(target),
                    )
                )
        return violations


class DuplicateImagesRule(LintRule):
    """IMG003: Flag images whose URL appears more than once in the document."""

    code = "IMG003"
    name = "duplicate-images"
    category = "images"
    description = "The same image URL should typically appear only once."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each repeated image after the first occurrence."""
        buckets: dict[str, list[Image]] = defaultdict(list)
        for image in _collect_images(ctx.document):
            url = (image.url or "").strip()
            if not url:
                continue
            buckets[url].append(image)

        violations: list[Violation] = []
        for url, images in buckets.items():
            if len(images) < 2:
                continue
            for extra in images[1:]:
                violations.append(
                    self.build_violation(
                        message=f"Duplicate image: {url!r} ({len(images)} total occurrences)",
                        line=_line(extra),
                        column=_column(extra),
                        node_type="Image",
                        suggestion="Reuse a single reference or remove the duplicate",
                    )
                )
        return violations


class ImageSizeExcessiveRule(LintRule):
    """IMG004: Flag base64-inlined images larger than ``max_bytes`` (default 1 MiB).

    Only inspects ``data:...;base64,...`` URIs. Remote and local-path
    images can't be sized without I/O and are out of scope for this rule.
    """

    code = "IMG004"
    name = "image-size-excessive"
    category = "images"
    description = "Inlined base64 images should not be excessively large."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each base64 inline image whose decoded size exceeds ``max_bytes``."""
        max_bytes = _coerce_positive_int(
            ctx.config.get("max_bytes", _DEFAULT_MAX_IMAGE_BYTES),
            default=_DEFAULT_MAX_IMAGE_BYTES,
        )
        violations: list[Violation] = []
        for image in _collect_images(ctx.document):
            url = image.url or ""
            match = _DATA_URI_RE.match(url)
            if not match:
                continue
            # base64 ratio is 4/3 — convert encoded length to approximate decoded size
            encoded_len = len(match.group(1))
            decoded_bytes = (encoded_len * 3) // 4
            if decoded_bytes > max_bytes:
                violations.append(
                    self.build_violation(
                        message=(f"Inline image is approximately {decoded_bytes:,} bytes " f"(max {max_bytes:,})"),
                        line=_line(image),
                        column=_column(image),
                        node_type="Image",
                        suggestion="Extract the image to a separate file or reduce its size",
                    )
                )
        return violations


class DecorativeImageAltRule(LintRule):
    """IMG005: Flag images whose alt text is a generic placeholder.

    "Generic" means single words like 'image', 'photo', 'screenshot',
    'picture', 'img', or 'graphic'. These tell a screen-reader user
    nothing the file extension wouldn't already convey.
    """

    code = "IMG005"
    name = "decorative-image-alt"
    category = "images"
    description = "Alt text should describe the image, not just say 'image'."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each image with a generic placeholder alt text."""
        violations: list[Violation] = []
        for image in _collect_images(ctx.document):
            alt = (image.alt_text or "").strip().lower()
            if not alt:
                continue
            if alt in _DECORATIVE_ALT_TEXTS:
                violations.append(
                    self.build_violation(
                        message=f"Alt text is a generic placeholder: {image.alt_text!r}",
                        line=_line(image),
                        column=_column(image),
                        node_type="Image",
                        suggestion="Replace with a description of what the image shows",
                    )
                )
        return violations


for _rule_cls in (
    MissingAltTextRule,
    ImageNotFoundRule,
    DuplicateImagesRule,
    ImageSizeExcessiveRule,
    DecorativeImageAltRule,
):
    rule_registry.register(_rule_cls)
