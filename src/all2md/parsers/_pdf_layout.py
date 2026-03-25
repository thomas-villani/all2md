#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_layout.py
"""PDF document layout analysis utilities.

This private module wraps the optional pymupdf-layout model for
classifying text blocks by semantic role (title, section-header,
text, list-item, table, page-header, page-footer, caption, footnote,
picture, formula).

The model is a lightweight Graph Neural Network (GNN) that classifies
blocks based on spatial features (position, font size, spacing) and
relationships to neighboring blocks, running on CPU via ONNX runtime.

Requires: pip install all2md[pdf_layout]
License note: pymupdf-layout uses Polyform Noncommercial license.
Commercial use requires an Artifex license.

"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import fitz

__all__ = [
    "LayoutPrediction",
    "PageLayoutPredictions",
    "get_layout_model",
    "predict_page_layout",
    "match_predictions_to_blocks",
    "is_layout_available",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayoutPrediction:
    """A single layout prediction for a region on a page.

    Attributes
    ----------
    x0 : float
        Left edge of the predicted region.
    y0 : float
        Top edge of the predicted region.
    x1 : float
        Right edge of the predicted region.
    y1 : float
        Bottom edge of the predicted region.
    label : str
        Semantic label: title, section-header, text, list-item, table,
        page-header, page-footer, caption, footnote, picture, formula.

    """

    x0: float
    y0: float
    x1: float
    y1: float
    label: str

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return bounding box as a tuple."""
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class PageLayoutPredictions:
    """All layout predictions for a single page, with block-level mapping.

    Attributes
    ----------
    predictions : list[LayoutPrediction]
        Raw predictions from the layout model.
    block_labels : dict[int, str]
        Mapping from block index to the matched semantic label.

    """

    predictions: list[LayoutPrediction] = field(default_factory=list)
    block_labels: dict[int, str] = field(default_factory=dict)

    def get_block_label(self, block_index: int) -> str | None:
        """Return the layout label for a given block index, or None."""
        return self.block_labels.get(block_index)

    def has_label(self, label: str) -> bool:
        """Check if any prediction has the given label."""
        return any(p.label == label for p in self.predictions)

    def get_predictions_by_label(self, label: str) -> list[LayoutPrediction]:
        """Return all predictions with the given label."""
        return [p for p in self.predictions if p.label == label]


# Module-level model cache (singleton, loaded once per process)
_layout_model: Any = None


def is_layout_available() -> bool:
    """Check if pymupdf-layout is importable."""
    try:
        from pymupdf.layout import DocumentLayoutAnalyzer  # noqa: F401

        return True
    except ImportError:
        return False


def get_layout_model() -> Any:
    """Get or create the cached layout analysis model.

    Returns the DocumentLayoutAnalyzer model instance, caching it
    for reuse across pages and documents.

    Returns
    -------
    Any
        The GNN layout model instance.

    Raises
    ------
    ImportError
        If pymupdf-layout is not installed.

    """
    global _layout_model  # noqa: PLW0603
    if _layout_model is None:
        from pymupdf.layout import DocumentLayoutAnalyzer

        _layout_model = DocumentLayoutAnalyzer.get_model()
        logger.debug("Loaded pymupdf-layout GNN model")
    return _layout_model


def predict_page_layout(page: "fitz.Page") -> list[LayoutPrediction]:
    """Run layout prediction on a single page.

    Parameters
    ----------
    page : fitz.Page
        PDF page to analyze.

    Returns
    -------
    list[LayoutPrediction]
        Predicted regions with semantic labels.

    """
    model = get_layout_model()
    raw_predictions = model.predict(page)
    # raw_predictions: list of [x0, y0, x1, y1, label_str]

    predictions = [
        LayoutPrediction(
            x0=float(pred[0]),
            y0=float(pred[1]),
            x1=float(pred[2]),
            y1=float(pred[3]),
            label=str(pred[4]),
        )
        for pred in raw_predictions
    ]

    if predictions:
        labels = {p.label for p in predictions}
        logger.debug("Layout analysis: %d regions, labels=%s", len(predictions), labels)

    return predictions


def _compute_iou(
    box_a: tuple[float, float, float, float],
    box_b: tuple[float, float, float, float],
) -> float:
    """Compute Intersection over Union between two bounding boxes.

    Parameters
    ----------
    box_a : tuple of float
        First bounding box (x0, y0, x1, y1).
    box_b : tuple of float
        Second bounding box (x0, y0, x1, y1).

    Returns
    -------
    float
        IoU value in [0.0, 1.0].

    """
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])

    if x0 >= x1 or y0 >= y1:
        return 0.0

    intersection = (x1 - x0) * (y1 - y0)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


def match_predictions_to_blocks(
    predictions: list[LayoutPrediction],
    blocks: list[dict],
    iou_threshold: float = 0.3,
) -> PageLayoutPredictions:
    """Match layout predictions to text blocks by IoU overlap.

    Each text block is assigned the label of the prediction with the
    highest IoU overlap, provided it exceeds ``iou_threshold``.

    Parameters
    ----------
    predictions : list[LayoutPrediction]
        Layout model predictions for the page.
    blocks : list[dict]
        Text blocks from ``page.get_text("dict")``.
    iou_threshold : float
        Minimum IoU to consider a match.

    Returns
    -------
    PageLayoutPredictions
        Predictions with block-level label mapping.

    """
    block_labels: dict[int, str] = {}

    for block_idx, block in enumerate(blocks):
        bbox = block.get("bbox")
        if not bbox:
            continue

        best_iou = 0.0
        best_label: str | None = None

        for pred in predictions:
            iou = _compute_iou(tuple(bbox), pred.bbox)
            if iou > best_iou:
                best_iou = iou
                best_label = pred.label

        if best_iou >= iou_threshold and best_label is not None:
            block_labels[block_idx] = best_label

    logger.debug("Matched %d/%d blocks to layout labels", len(block_labels), len(blocks))
    return PageLayoutPredictions(predictions=predictions, block_labels=block_labels)


def annotate_blocks_with_layout(
    blocks: list[dict],
    layout: PageLayoutPredictions,
) -> None:
    """Stamp ``_layout_label`` onto each block dict that has a matched label.

    This allows the label to travel with the block through all downstream
    processing (column detection, filtering, etc.) without threading
    the ``PageLayoutPredictions`` object everywhere.

    Parameters
    ----------
    blocks : list[dict]
        Text blocks (mutated in place).
    layout : PageLayoutPredictions
        Predictions with block-level mapping.

    """
    for block_idx, label in layout.block_labels.items():
        if block_idx < len(blocks):
            blocks[block_idx]["_layout_label"] = label
