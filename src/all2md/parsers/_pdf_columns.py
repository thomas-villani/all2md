#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_columns.py
"""PDF column detection algorithms.

This private module contains algorithms for detecting multi-column layouts
in PDF documents. These functions analyze text block positions to identify
column boundaries and group content appropriately.

"""

from __future__ import annotations

from collections import defaultdict

from all2md.constants import (
    PDF_COLUMN_FREQ_THRESHOLD_RATIO,
    PDF_COLUMN_GAP_QUANTIZATION,
    PDF_COLUMN_MIN_BLOCKS_FOR_WIDTH_CHECK,
    PDF_COLUMN_MIN_FREQ_COUNT,
    PDF_COLUMN_SINGLE_COLUMN_WIDTH_RATIO,
    PDF_COLUMN_X_TOLERANCE,
)

__all__ = ["detect_columns"]


def _simple_kmeans_1d(values: list[float], k: int, max_iterations: int = 20) -> list[int]:
    """Cluster 1D values using k-means algorithm.

    Parameters
    ----------
    values : list of float
        1D values to cluster (e.g., x-coordinates)
    k : int
        Number of clusters
    max_iterations : int, default 20
        Maximum iterations for convergence

    Returns
    -------
    list of int
        Cluster assignment for each value (0 to k-1)

    """
    if not values or k <= 0:
        return []

    if k == 1:
        return [0] * len(values)

    if len(values) < k:
        # Not enough values for k clusters, assign each to its own cluster
        return list(range(len(values)))

    # Initialize centroids by selecting evenly spaced values
    sorted_values = sorted(enumerate(values), key=lambda x: x[1])
    step = max(1, len(sorted_values) // k)  # Ensure step is at least 1

    # Generate initial indices with bounds checking
    initial_indices = []
    for i in range(k):
        idx = min(i * step, len(sorted_values) - 1)  # Clamp to valid range
        initial_indices.append(idx)

    centroids = [sorted_values[i][1] for i in initial_indices]

    assignments = [0] * len(values)

    for _ in range(max_iterations):
        # Assign each value to nearest centroid
        new_assignments = []
        for val in values:
            distances = [abs(val - centroid) for centroid in centroids]
            new_assignments.append(distances.index(min(distances)))

        # Check for convergence
        if new_assignments == assignments:
            break

        assignments = new_assignments

        # Update centroids
        new_centroids = []
        for cluster_id in range(k):
            cluster_values = [values[i] for i, assign in enumerate(assignments) if assign == cluster_id]
            if cluster_values:
                new_centroids.append(sum(cluster_values) / len(cluster_values))
            else:
                # Empty cluster, keep previous centroid
                new_centroids.append(centroids[cluster_id])

        centroids = new_centroids

    return assignments


def _detect_columns_by_clustering(
    blocks: list, block_centers: list[float], x_coords: list[float], column_gap_threshold: float
) -> list[list[dict]] | None:
    """Detect columns using k-means clustering.

    Parameters
    ----------
    blocks : list
        Text blocks
    block_centers : list of float
        Center x-coordinates of blocks
    x_coords : list of float
        Starting x-coordinates
    column_gap_threshold : float
        Minimum gap threshold

    Returns
    -------
    list of list of dict or None
        Detected columns or None if single column

    """
    # Estimate number of columns from gap analysis
    sorted_x = sorted(set(x_coords))
    num_columns = 1
    for i in range(1, len(sorted_x)):
        gap = sorted_x[i] - sorted_x[i - 1]
        if gap >= column_gap_threshold:
            num_columns += 1

    num_columns = max(1, min(num_columns, 4))

    if num_columns <= 1:
        return None

    # Apply k-means clustering
    cluster_assignments = _simple_kmeans_1d(block_centers, num_columns)

    # Group blocks by cluster
    columns_dict: dict[int, list[dict]] = {i: [] for i in range(num_columns)}
    for block, cluster_id in zip(blocks, cluster_assignments, strict=False):
        if "bbox" in block:
            columns_dict[cluster_id].append(block)
        else:
            columns_dict[0].append(block)

    # Sort clusters by mean x-coordinate
    cluster_centers = {}
    for cluster_id, cluster_blocks in columns_dict.items():
        if cluster_blocks:
            centers = [(b["bbox"][0] + b["bbox"][2]) / 2 for b in cluster_blocks if "bbox" in b]
            cluster_centers[cluster_id] = sum(centers) / len(centers) if centers else 0
        else:
            cluster_centers[cluster_id] = 0

    sorted_clusters = sorted(cluster_centers.items(), key=lambda x: x[1])
    columns = [columns_dict[cluster_id] for cluster_id, _ in sorted_clusters if columns_dict[cluster_id]]

    # Sort blocks within each column by y-coordinate
    for column in columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    return columns


def _detect_columns_by_whitespace(
    blocks: list,
    block_ranges: list[tuple[float, float]],
    column_gap_threshold: float,
    page_width: float,
    spanning_threshold: float,
    force_multi_column: bool,
) -> list[list[dict]] | None:
    """Detect columns using whitespace gap analysis.

    Parameters
    ----------
    blocks : list
        Text blocks
    block_ranges : list of tuple
        (x0, x1) ranges for each block
    column_gap_threshold : float
        Minimum gap threshold
    page_width : float
        Page width
    spanning_threshold : float
        Threshold for spanning blocks
    force_multi_column : bool
        Force multi-column detection

    Returns
    -------
    list of list of dict or None
        Detected columns or None if single column

    """
    x_tolerance = PDF_COLUMN_X_TOLERANCE
    x0_groups: dict[float, list[tuple[float, float, int]]] = defaultdict(list)

    # Group blocks by x0 position
    for i, (x0, x1) in enumerate(block_ranges):
        width = x1 - x0
        if not force_multi_column and width > spanning_threshold * page_width:
            continue
        x0_key = round(x0 / x_tolerance) * x_tolerance
        x0_groups[x0_key].append((x0, x1, i))

    if not x0_groups:
        return None

    # Find group ranges
    group_ranges = []
    for x0_key in sorted(x0_groups.keys()):
        group = x0_groups[x0_key]
        min_x0 = min(x0 for x0, x1, i in group)
        max_x1 = max(x1 for x0, x1, i in group)
        group_ranges.append((min_x0, max_x1))

    # Find whitespace gaps
    whitespace_gaps = []
    for i in range(len(group_ranges) - 1):
        gap_width = group_ranges[i + 1][0] - group_ranges[i][1]
        if gap_width >= column_gap_threshold:
            whitespace_gaps.append({"start": group_ranges[i][1], "end": group_ranges[i + 1][0], "width": gap_width})

    if not whitespace_gaps:
        return None

    # Find consistent gaps
    gap_frequency: dict[float, int] = {}
    for gap in whitespace_gaps:
        gap_pos = round((gap["start"] + gap["end"]) / 2 / PDF_COLUMN_GAP_QUANTIZATION) * PDF_COLUMN_GAP_QUANTIZATION
        gap_frequency[gap_pos] = gap_frequency.get(gap_pos, 0) + 1

    if not gap_frequency:
        return None

    max_freq = max(gap_frequency.values())
    threshold_freq = max(PDF_COLUMN_MIN_FREQ_COUNT, max_freq * PDF_COLUMN_FREQ_THRESHOLD_RATIO)
    column_boundaries = sorted([pos for pos, freq in gap_frequency.items() if freq >= threshold_freq])

    if not column_boundaries:
        return None

    # Split blocks into columns
    whitespace_columns: list[list[dict]] = [[] for _ in range(len(column_boundaries) + 1)]

    for block in blocks:
        if "bbox" not in block:
            whitespace_columns[0].append(block)
            continue

        block_center = (block["bbox"][0] + block["bbox"][2]) / 2
        assigned = False
        for i, boundary in enumerate(column_boundaries):
            if block_center < boundary:
                whitespace_columns[i].append(block)
                assigned = True
                break

        if not assigned:
            whitespace_columns[-1].append(block)

    # Sort and clean up
    for column in whitespace_columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    whitespace_columns = [col for col in whitespace_columns if col]

    return whitespace_columns if len(whitespace_columns) > 1 else None


def _detect_columns_by_gaps(
    blocks: list,
    block_ranges: list[tuple[float, float]],
    x_coords: list[float],
    column_gap_threshold: float,
    force_multi_column: bool,
) -> list[list[dict]]:
    """Detect columns using simple gap detection (fallback method).

    Parameters
    ----------
    blocks : list
        Text blocks
    block_ranges : list of tuple
        (x0, x1) ranges for each block
    x_coords : list of float
        Starting x-coordinates
    column_gap_threshold : float
        Minimum gap threshold
    force_multi_column : bool
        Force multi-column detection

    Returns
    -------
    list of list of dict
        Detected columns (always returns at least single column)

    """
    # Sort block ranges by starting position to find actual whitespace gaps
    sorted_ranges = sorted(block_ranges, key=lambda r: r[0])

    # Find column boundaries based on actual whitespace gaps (end of one block to start of next)
    column_boundaries = [sorted_ranges[0][0]]

    for i in range(1, len(sorted_ranges)):
        prev_x1 = sorted_ranges[i - 1][1]
        curr_x0 = sorted_ranges[i][0]
        gap = curr_x0 - prev_x1

        if gap >= column_gap_threshold:
            column_boundaries.append(curr_x0)

    if len(column_boundaries) <= 1:
        return [blocks]

    # Check for single column heuristic
    if not force_multi_column and len(block_ranges) >= PDF_COLUMN_MIN_BLOCKS_FOR_WIDTH_CHECK:
        widths = [x1 - x0 for x0, x1 in block_ranges]
        median_width = sorted(widths)[len(widths) // 2]
        min_x = min(x0 for x0, x1 in block_ranges)
        max_x = max(x1 for x0, x1 in block_ranges)
        page_width = max_x - min_x

        if median_width > PDF_COLUMN_SINGLE_COLUMN_WIDTH_RATIO * page_width:
            return [blocks]

    # Group blocks into columns
    columns: list[list[dict]] = [[] for _ in range(len(column_boundaries))]

    for block in blocks:
        if "bbox" not in block:
            columns[0].append(block)
            continue

        x0 = block["bbox"][0]
        assigned = False
        for i in range(len(column_boundaries) - 1):
            if column_boundaries[i] <= x0 < column_boundaries[i + 1]:
                columns[i].append(block)
                assigned = True
                break

        if not assigned:
            columns[-1].append(block)

    # Sort and clean up
    for column in columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    return [col for col in columns if col]


def detect_columns(
    blocks: list, column_gap_threshold: float = 20, use_clustering: bool = False, force_multi_column: bool = False
) -> list[list[dict]]:
    """Detect multi-column layout in text blocks with enhanced whitespace analysis.

    Analyzes the x-coordinates of text blocks to identify column boundaries
    and groups blocks into columns based on their horizontal positions. Uses
    whitespace analysis and connected-component grouping for improved accuracy.

    Parameters
    ----------
    blocks : list
        List of text blocks from PyMuPDF page extraction
    column_gap_threshold : float, default 20
        Minimum gap between columns in points
    use_clustering : bool, default False
        Use k-means clustering on x-coordinates for improved robustness
    force_multi_column : bool, default False
        Force multi-column detection by bypassing spanning block heuristics.
        When True, skips the check that treats wide blocks as single-column indicators.
        Useful when you know the document has multi-column layout despite wide headers/footers.

    Returns
    -------
    list[list[dict]]
        List of columns, where each column is a list of blocks

    Notes
    -----
    When use_clustering=True, the function uses k-means clustering to identify
    column groupings based on block center positions. This can be more robust
    for complex layouts but requires estimating the number of columns first.

    When force_multi_column=True, the function bypasses heuristics that would
    normally detect single-column layouts (e.g., blocks spanning most of the page width).
    This is useful when you have headers/footers spanning the full width but want to
    detect multi-column content in the body.

    """
    if not blocks:
        return [blocks]

    # Extract block coordinates
    x_coords = []
    block_ranges = []
    block_centers = []
    for block in blocks:
        if "bbox" in block:
            x0, x1 = block["bbox"][0], block["bbox"][2]
            x_coords.append(x0)
            block_ranges.append((x0, x1))
            block_centers.append((x0 + x1) / 2)

    if len(x_coords) < 2:
        return [blocks]

    # Calculate page dimensions
    min_x = min(x0 for x0, x1 in block_ranges)
    max_x = max(x1 for x0, x1 in block_ranges)
    page_width = max_x - min_x
    spanning_threshold = 0.65

    # Try clustering-based detection if requested
    if use_clustering and block_centers:
        columns = _detect_columns_by_clustering(blocks, block_centers, x_coords, column_gap_threshold)
        if columns:
            return columns

    # Try whitespace-based detection
    columns = _detect_columns_by_whitespace(
        blocks, block_ranges, column_gap_threshold, page_width, spanning_threshold, force_multi_column
    )
    if columns:
        return columns

    # Fallback to simple gap detection
    return _detect_columns_by_gaps(blocks, block_ranges, x_coords, column_gap_threshold, force_multi_column)
