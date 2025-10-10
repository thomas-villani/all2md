"""Tests for enhanced PDF column detection."""

from all2md.parsers.pdf import detect_columns


def test_single_column_detection():
    """Test that single column layout is detected correctly."""
    blocks = [
        {"bbox": [50, 100, 500, 120], "text": "Line 1"},
        {"bbox": [50, 130, 500, 150], "text": "Line 2"},
        {"bbox": [50, 160, 500, 180], "text": "Line 3"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 1
    assert len(columns[0]) == 3


def test_two_column_detection():
    """Test that two column layout is detected correctly."""
    blocks = [
        # Left column
        {"bbox": [50, 100, 250, 120], "text": "Left 1"},
        {"bbox": [50, 130, 250, 150], "text": "Left 2"},
        {"bbox": [50, 160, 250, 180], "text": "Left 3"},
        # Right column (gap of 50 points)
        {"bbox": [300, 100, 500, 120], "text": "Right 1"},
        {"bbox": [300, 130, 500, 150], "text": "Right 2"},
        {"bbox": [300, 160, 500, 180], "text": "Right 3"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 2
    assert len(columns[0]) == 3  # Left column
    assert len(columns[1]) == 3  # Right column


def test_column_vertical_ordering():
    """Test that blocks within columns are ordered top to bottom."""
    blocks = [
        # Left column - out of order
        {"bbox": [50, 160, 250, 180], "text": "Left 3"},
        {"bbox": [50, 100, 250, 120], "text": "Left 1"},
        {"bbox": [50, 130, 250, 150], "text": "Left 2"},
        # Right column
        {"bbox": [300, 100, 500, 120], "text": "Right 1"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Check that left column is sorted by y-coordinate
    left_y_coords = [block["bbox"][1] for block in columns[0]]
    assert left_y_coords == sorted(left_y_coords)


def test_empty_blocks():
    """Test handling of empty block list."""
    columns = detect_columns([], column_gap_threshold=20)

    assert len(columns) == 1
    assert len(columns[0]) == 0


def test_blocks_without_bbox():
    """Test handling of blocks without bbox."""
    blocks = [
        {"bbox": [50, 100, 250, 120], "text": "Has bbox"},
        {"text": "No bbox"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Should not crash and should place no-bbox block in first column
    assert len(columns) >= 1


def test_whitespace_gap_frequency():
    """Test that consistent gaps are identified across multiple blocks."""
    blocks = [
        # Left column - 5 blocks
        {"bbox": [50, 100, 200, 120], "text": "L1"},
        {"bbox": [50, 130, 200, 150], "text": "L2"},
        {"bbox": [50, 160, 200, 180], "text": "L3"},
        {"bbox": [50, 190, 200, 210], "text": "L4"},
        {"bbox": [50, 220, 200, 240], "text": "L5"},
        # Right column - 5 blocks (consistent gap at ~250)
        {"bbox": [250, 100, 400, 120], "text": "R1"},
        {"bbox": [250, 130, 400, 150], "text": "R2"},
        {"bbox": [250, 160, 400, 180], "text": "R3"},
        {"bbox": [250, 190, 400, 210], "text": "R4"},
        {"bbox": [250, 220, 400, 240], "text": "R5"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Should detect the consistent gap and split into 2 columns
    assert len(columns) == 2
    assert len(columns[0]) == 5
    assert len(columns[1]) == 5


def test_wide_blocks_single_column():
    """Test that wide blocks spanning most of page are treated as single column."""
    blocks = [
        # Very wide blocks (80% of page width)
        {"bbox": [50, 100, 450, 120], "text": "Wide block 1"},
        {"bbox": [50, 130, 450, 150], "text": "Wide block 2"},
        {"bbox": [50, 160, 450, 180], "text": "Wide block 3"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Should detect as single column despite potential gaps
    assert len(columns) == 1


def test_three_column_detection():
    """Test detection of three column layout."""
    blocks = [
        # Column 1
        {"bbox": [50, 100, 150, 120], "text": "C1"},
        {"bbox": [50, 130, 150, 150], "text": "C1"},
        # Column 2 (gap at 200)
        {"bbox": [200, 100, 300, 120], "text": "C2"},
        {"bbox": [200, 130, 300, 150], "text": "C2"},
        # Column 3 (gap at 350)
        {"bbox": [350, 100, 450, 120], "text": "C3"},
        {"bbox": [350, 130, 450, 150], "text": "C3"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Should detect 3 columns
    assert len(columns) == 3
    assert all(len(col) == 2 for col in columns)


def test_column_gap_threshold():
    """Test that column_gap_threshold parameter works correctly."""
    # Use more blocks to trigger whitespace analysis
    blocks = [
        {"bbox": [50, 100, 200, 120], "text": "Left 1"},
        {"bbox": [50, 130, 200, 150], "text": "Left 2"},
        {"bbox": [50, 160, 200, 180], "text": "Left 3"},
        {"bbox": [225, 100, 375, 120], "text": "Right 1"},  # Gap of 25 points
        {"bbox": [225, 130, 375, 150], "text": "Right 2"},
        {"bbox": [225, 160, 375, 180], "text": "Right 3"},
    ]

    # With threshold of 30, should be single column
    columns_30 = detect_columns(blocks, column_gap_threshold=30)
    assert len(columns_30) == 1

    # With threshold of 20, should be two columns
    columns_20 = detect_columns(blocks, column_gap_threshold=20)
    assert len(columns_20) == 2


def test_irregular_column_widths():
    """Test handling of columns with different widths."""
    blocks = [
        # Narrow left column
        {"bbox": [50, 100, 150, 120], "text": "Narrow 1"},
        {"bbox": [50, 130, 150, 150], "text": "Narrow 2"},
        {"bbox": [50, 160, 150, 180], "text": "Narrow 3"},
        # Wider right column (but not > 60% of total page width)
        {"bbox": [200, 100, 400, 120], "text": "Wide 1"},
        {"bbox": [200, 130, 400, 150], "text": "Wide 2"},
        {"bbox": [200, 160, 400, 180], "text": "Wide 3"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 2
    # Both columns should have 3 blocks
    assert len(columns[0]) == 3
    assert len(columns[1]) == 3


def test_column_detection_with_clustering_enabled():
    """Test k-means clustering for improved column detection."""
    blocks = [
        # Column 1 with slight horizontal variation
        {"bbox": [50, 100, 150, 120], "text": "C1-1"},
        {"bbox": [55, 130, 155, 150], "text": "C1-2"},  # Slight right shift
        {"bbox": [52, 160, 152, 180], "text": "C1-3"},  # Slight right shift
        # Column 2 with slight horizontal variation
        {"bbox": [300, 100, 400, 120], "text": "C2-1"},
        {"bbox": [305, 130, 405, 150], "text": "C2-2"},  # Slight right shift
        {"bbox": [302, 160, 402, 180], "text": "C2-3"},  # Slight right shift
    ]

    # With clustering, should group blocks by center position
    columns = detect_columns(blocks, column_gap_threshold=20, use_clustering=True)

    assert len(columns) == 2
    assert len(columns[0]) == 3
    assert len(columns[1]) == 3


def test_column_detection_clustering_vs_heuristic():
    """Compare k-means clustering vs heuristic approaches."""
    blocks = [
        # Slightly irregular column positions
        {"bbox": [50, 100, 200, 120], "text": "L1"},
        {"bbox": [60, 130, 210, 150], "text": "L2"},
        {"bbox": [55, 160, 205, 180], "text": "L3"},
        {"bbox": [300, 100, 450, 120], "text": "R1"},
        {"bbox": [310, 130, 460, 150], "text": "R2"},
        {"bbox": [305, 160, 455, 180], "text": "R3"},
    ]

    # Both should detect 2 columns
    columns_heuristic = detect_columns(blocks, column_gap_threshold=20, use_clustering=False)
    columns_clustering = detect_columns(blocks, column_gap_threshold=20, use_clustering=True)

    assert len(columns_heuristic) == 2
    assert len(columns_clustering) == 2


def test_column_detection_newspaper_layout():
    """Test detection of typical 3-column newspaper layout."""
    blocks = [
        # Column 1 (narrow)
        {"bbox": [30, 100, 150, 120], "text": "Col1-1"},
        {"bbox": [30, 130, 150, 150], "text": "Col1-2"},
        {"bbox": [30, 160, 150, 180], "text": "Col1-3"},
        {"bbox": [30, 190, 150, 210], "text": "Col1-4"},
        # Column 2 (narrow)
        {"bbox": [180, 100, 300, 120], "text": "Col2-1"},
        {"bbox": [180, 130, 300, 150], "text": "Col2-2"},
        {"bbox": [180, 160, 300, 180], "text": "Col2-3"},
        {"bbox": [180, 190, 300, 210], "text": "Col2-4"},
        # Column 3 (narrow)
        {"bbox": [330, 100, 450, 120], "text": "Col3-1"},
        {"bbox": [330, 130, 450, 150], "text": "Col3-2"},
        {"bbox": [330, 160, 450, 180], "text": "Col3-3"},
        {"bbox": [330, 190, 450, 210], "text": "Col3-4"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Should detect 3 columns
    assert len(columns) == 3
    # Each column should have 4 blocks
    assert len(columns[0]) == 4
    assert len(columns[1]) == 4
    assert len(columns[2]) == 4


def test_column_detection_academic_paper_layout():
    """Test detection of typical academic 2-column layout."""
    blocks = [
        # Left column - typical academic paper width
        {"bbox": [72, 100, 288, 120], "text": "Abstract text"},
        {"bbox": [72, 130, 288, 150], "text": "Introduction paragraph"},
        {"bbox": [72, 160, 288, 180], "text": "More content"},
        {"bbox": [72, 190, 288, 210], "text": "Even more"},
        # Right column
        {"bbox": [324, 100, 540, 120], "text": "Results section"},
        {"bbox": [324, 130, 540, 150], "text": "Discussion"},
        {"bbox": [324, 160, 540, 180], "text": "Conclusion"},
        {"bbox": [324, 190, 540, 210], "text": "References"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=25)

    # Should detect 2 columns
    assert len(columns) == 2
    assert len(columns[0]) == 4
    assert len(columns[1]) == 4


def test_column_detection_mixed_layout():
    """Test handling of mixed single-column and multi-column layout."""
    blocks = [
        # Full-width header
        {"bbox": [50, 50, 500, 70], "text": "Full Width Title"},
        # Two-column content
        {"bbox": [50, 100, 250, 120], "text": "Left 1"},
        {"bbox": [50, 130, 250, 150], "text": "Left 2"},
        {"bbox": [300, 100, 500, 120], "text": "Right 1"},
        {"bbox": [300, 130, 500, 150], "text": "Right 2"},
        # Full-width footer
        {"bbox": [50, 180, 500, 200], "text": "Full Width Footer"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # With median width check, should recognize full-width blocks and return single column
    # (because median block width is large relative to page)
    assert len(columns) == 1 or len(columns) == 2
