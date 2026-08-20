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
    DEFAULT_COLUMN_GAP_THRESHOLD,
    PDF_COLUMN_CHANNEL_MIN_BLOCKS_PER_SIDE,
    PDF_COLUMN_CHANNEL_MIN_WIDTH,
    PDF_COLUMN_CHANNEL_MIN_Y_OVERLAP_RATIO,
    PDF_COLUMN_FREQ_THRESHOLD_RATIO,
    PDF_COLUMN_GAP_QUANTIZATION,
    PDF_COLUMN_MIN_BLOCKS_FOR_WIDTH_CHECK,
    PDF_COLUMN_MIN_FREQ_COUNT,
    PDF_COLUMN_SINGLE_COLUMN_WIDTH_RATIO,
    PDF_COLUMN_X_TOLERANCE,
    PDF_GUTTER_SPLIT_MIN_BLOCK_WIDTH_RATIO,
    PDF_GUTTER_SPLIT_MIN_LINES_PER_BAND,
)

__all__ = ["detect_columns", "split_gutter_merged_blocks"]


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


def _detect_columns_by_channel(
    blocks: list,
    block_ranges: list[tuple[float, float]],
    page_width: float,
    spanning_threshold: float,
) -> list[list[dict]] | None:
    """Admit tight-gutter columns on structural evidence (#405).

    Journal reference pages print two columns whose gutter is narrower than
    ``column_gap_threshold`` -- measured 14.9-17.9pt across four publishers on the
    PMC dev corpus against the 20pt default -- so the whitespace detector finds
    exactly the right x0 bands and then rejects the gap. Once the page is treated
    as one column, the y-sort interleaves the sides line-by-line: every word
    survives, every adjacency dies.

    A raw lower threshold would also split on indented quotations and figure
    labels. This detector demands what those cannot supply: a *channel* -- an
    x-interval that no non-spanning block touches anywhere on the page -- with at
    least `PDF_COLUMN_CHANNEL_MIN_BLOCKS_PER_SIDE` blocks on each side and enough
    mutual y-overlap between the sides that a y-sort would provably interleave
    them. An indented quotation overlaps its body text in x, so it can never
    produce the channel in the first place.

    Parameters
    ----------
    blocks : list
        Text blocks.
    block_ranges : list of tuple
        (x0, x1) ranges for each block that has a bbox.
    page_width : float
        Width of the text area.
    spanning_threshold : float
        Blocks wider than this fraction of the page are treated as spanning
        (headings, full-width paragraphs): they neither define nor veto a
        channel, and are assigned to a column by center like the other
        detectors do.

    Returns
    -------
    list of list of dict or None
        Detected columns, or None when no channel passes the guards.

    """
    spanning_width = spanning_threshold * page_width
    narrow = [
        tuple(block["bbox"])
        for block in blocks
        if block.get("bbox") and (block["bbox"][2] - block["bbox"][0]) <= spanning_width
    ]
    # Prune vertically isolated blocks -- a centered page number sitting *inside* the
    # gutter, below both columns, would otherwise erase the channel. A block that
    # y-overlaps no other block cannot be interleaved with anything by a y-sort, so it
    # carries no evidence either way; it is still assigned to a column by center below.
    kept = [a for a in narrow if any(min(a[3], b[3]) > max(a[1], b[1]) for b in narrow if b is not a)]
    intervals = sorted((bbox[0], bbox[2]) for bbox in kept)
    if len(intervals) < 2 * PDF_COLUMN_CHANNEL_MIN_BLOCKS_PER_SIDE:
        return None

    # Merge the x-intervals; the complement between merged runs is the channel space.
    merged: list[tuple[float, float]] = [intervals[0]]
    for x0, x1 in intervals[1:]:
        last_x0, last_x1 = merged[-1]
        if x0 <= last_x1 + PDF_COLUMN_CHANNEL_MIN_WIDTH:
            merged[-1] = (last_x0, max(last_x1, x1))
        else:
            merged.append((x0, x1))
    if len(merged) < 2:
        return None

    # y-extent of the evidence blocks on each side of each candidate channel.
    def side_stats(lo: float, hi: float) -> tuple[int, float, float]:
        count = 0
        y0 = float("inf")
        y1 = float("-inf")
        for bbox in kept:
            if bbox[0] >= lo and bbox[2] <= hi:
                count += 1
                y0 = min(y0, bbox[1])
                y1 = max(y1, bbox[3])
        return count, y0, y1

    boundaries: list[float] = []
    for (_, left_end), (right_start, _) in zip(merged, merged[1:], strict=False):
        left_count, left_y0, left_y1 = side_stats(float("-inf"), left_end)
        right_count, right_y0, right_y1 = side_stats(right_start, float("inf"))
        if left_count < PDF_COLUMN_CHANNEL_MIN_BLOCKS_PER_SIDE or right_count < PDF_COLUMN_CHANNEL_MIN_BLOCKS_PER_SIDE:
            continue
        overlap = min(left_y1, right_y1) - max(left_y0, right_y0)
        smaller_span = min(left_y1 - left_y0, right_y1 - right_y0)
        if smaller_span <= 0 or overlap < PDF_COLUMN_CHANNEL_MIN_Y_OVERLAP_RATIO * smaller_span:
            continue
        boundaries.append((left_end + right_start) / 2)

    # Exactly one admitted gutter -- a two-column page. Every measured tight-gutter
    # page is two-column; layouts with more columns have wider gutters relative to
    # their column width and clear the ordinary threshold path. Several qualifying
    # channels on one page is the signature of an undetected table, not a layout.
    if len(boundaries) != 1:
        return None

    content_top = min(bbox[1] for bbox in kept)
    content_bottom = max(bbox[3] for bbox in kept)

    columns: list[list[dict]] = [[] for _ in range(len(boundaries) + 1)]
    for block in blocks:
        if "bbox" not in block:
            columns[0].append(block)
            continue
        bbox = block["bbox"]
        if (bbox[2] - bbox[0]) > spanning_width:
            # A spanning block reads in page order, not column order. Assigning it by
            # center drops it *between* the columns at emission time: an untrimmed
            # running header whose center fell a hair right of the boundary lands at
            # the head of the right column -- exactly at the seam where the left
            # column's last paragraph continues into the right one. Above all column
            # content it belongs before both columns; below, after both.
            block_middle = (bbox[1] + bbox[3]) / 2
            if block_middle < content_top:
                columns[0].append(block)
                continue
            if block_middle > content_bottom:
                columns[-1].append(block)
                continue
        block_center = (bbox[0] + bbox[2]) / 2
        for i, boundary in enumerate(boundaries):
            if block_center < boundary:
                columns[i].append(block)
                break
        else:
            columns[-1].append(block)

    for column in columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    columns = [col for col in columns if col]
    return columns if len(columns) > 1 else None


def split_gutter_merged_blocks(blocks: list[dict], page_width: float) -> list[dict]:
    """Resegment blocks PyMuPDF fused across a column gutter (#405).

    On 64 of 455 PMC dev-corpus pages, ``page.get_text("dict")`` returns a single
    block spanning both columns of a tight-gutter page -- up to 84 lines with the
    two columns interleaved in y order. No block-level column split can recover
    those: the interleaving is already inside the block. But the lines themselves
    are honest about their geometry: they fall into disjoint x-bands separated by
    the gutter. Each band becomes its own block, in the band's own line order.

    A normal paragraph cannot be split by this: its lines all overlap in x
    (including short last lines and indented first lines), so interval clustering
    keeps them in one band. Any line that crosses the gutter -- a genuine
    full-width line inside the block -- bridges the bands and vetoes the split of
    the whole block, which is the conservative direction.

    Parameters
    ----------
    blocks : list of dict
        Text blocks from ``page.get_text("dict")``; non-text blocks pass through.
    page_width : float
        Page width, used to skip blocks too narrow to hold two columns.

    Returns
    -------
    list of dict
        The blocks, with each fused block replaced by one block per x-band
        (left to right). All other blocks are returned untouched, in order.

    """
    min_band_lines = PDF_GUTTER_SPLIT_MIN_LINES_PER_BAND
    result: list[dict] = []
    for block in blocks:
        lines = block.get("lines")
        bbox = block.get("bbox")
        if not lines or bbox is None or len(lines) < 2 * min_band_lines:
            result.append(block)
            continue
        if (bbox[2] - bbox[0]) <= PDF_GUTTER_SPLIT_MIN_BLOCK_WIDTH_RATIO * page_width:
            result.append(block)
            continue
        # Rotated text has bboxes that do not mean "reading columns"; leave it alone.
        if any(line.get("dir", (1, 0))[:2] != (1, 0) for line in lines if isinstance(line.get("dir"), (tuple, list))):
            result.append(block)
            continue

        # Cluster line x-intervals into bands separated by at least the channel floor.
        order = sorted(range(len(lines)), key=lambda i: lines[i]["bbox"][0])
        bands: list[dict] = []  # {"x0", "x1", "line_indices"}
        for i in order:
            lx0, _, lx1, _ = lines[i]["bbox"]
            if bands and lx0 <= bands[-1]["x1"] + PDF_COLUMN_CHANNEL_MIN_WIDTH:
                bands[-1]["x1"] = max(bands[-1]["x1"], lx1)
                bands[-1]["line_indices"].append(i)
            else:
                bands.append({"x0": lx0, "x1": lx1, "line_indices": [i]})

        # Exactly two bands, each wide enough to be a text column. An undetected
        # borderless table also fuses into one wide block, but it splits into *many*
        # *narrow* bands (measured 0.04-0.14 of the page width against 0.40-0.42 for
        # real columns) -- and column-major order is precisely wrong for a table.
        if (
            len(bands) != 2
            or any(len(band["line_indices"]) < min_band_lines for band in bands)
            or any((band["x1"] - band["x0"]) < 0.25 * page_width for band in bands)
        ):
            result.append(block)
            continue

        for band in bands:  # bands are already left-to-right
            band_lines = [lines[i] for i in sorted(band["line_indices"])]
            sub_block = dict(block)
            sub_block["lines"] = band_lines
            sub_block["bbox"] = (
                min(line["bbox"][0] for line in band_lines),
                min(line["bbox"][1] for line in band_lines),
                max(line["bbox"][2] for line in band_lines),
                max(line["bbox"][3] for line in band_lines),
            )
            result.append(sub_block)
    return result


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

    # Tight-gutter admission: gaps below the threshold, backed by structural evidence
    # a raw gap test cannot demand (#405). A caller who *raised* the threshold above
    # the default asked for less splitting, and that explicit dial wins.
    if column_gap_threshold <= DEFAULT_COLUMN_GAP_THRESHOLD:
        columns = _detect_columns_by_channel(blocks, block_ranges, page_width, spanning_threshold)
        if columns:
            return columns

    # Fallback to simple gap detection
    return _detect_columns_by_gaps(blocks, block_ranges, x_coords, column_gap_threshold, force_multi_column)
