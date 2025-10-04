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
