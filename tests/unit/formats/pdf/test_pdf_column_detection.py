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


def test_column_detection_with_spanning_header():
    """Test that spanning headers don't prevent column detection."""
    blocks = [
        # Full-width header that spans both columns
        {"bbox": [72, 36, 434, 51], "text": "Header spanning both columns"},
        # Left column blocks
        {"bbox": [72, 100, 290, 120], "text": "Left column text 1"},
        {"bbox": [72, 130, 290, 150], "text": "Left column text 2"},
        {"bbox": [72, 160, 290, 180], "text": "Left column text 3"},
        # Right column blocks (significant gap after left column)
        {"bbox": [324, 100, 522, 120], "text": "Right column text 1"},
        {"bbox": [324, 130, 522, 150], "text": "Right column text 2"},
        {"bbox": [324, 160, 522, 180], "text": "Right column text 3"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Should detect 2 columns despite the spanning header
    assert len(columns) == 2
    # Left column should have left blocks (plus possibly the header)
    assert any(b["bbox"][0] < 100 and b["bbox"][2] < 350 for b in columns[0])
    # Right column should have right blocks
    assert any(b["bbox"][0] > 300 for b in columns[1])


def test_column_detection_all_spanning_blocks():
    """Test handling when all blocks span the full width."""
    blocks = [
        # All blocks are full-width
        {"bbox": [50, 100, 500, 120], "text": "Full width 1"},
        {"bbox": [50, 130, 500, 150], "text": "Full width 2"},
        {"bbox": [50, 160, 500, 180], "text": "Full width 3"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    # Should return single column when all blocks span full width
    assert len(columns) == 1
    assert len(columns[0]) == 3


# --- Tight-gutter channel admission (#405) ---------------------------------------
#
# Journal reference pages print two columns whose gutter is narrower than the
# 20pt threshold (measured 14.9-17.9pt across four publishers on the PMC dev
# corpus). The channel detector admits them on structural evidence a raw gap
# test cannot demand.


def _two_tight_columns(gap_start: float = 285.0, gap_end: float = 300.0) -> list[dict]:
    """Two columns with a 15pt gutter, five multi-line blocks per side."""
    blocks = []
    for i in range(5):
        y = 100 + i * 60
        blocks.append({"bbox": [50, y, gap_start, y + 50], "text": f"L{i}"})
        blocks.append({"bbox": [gap_end, y, 540, y + 50], "text": f"R{i}"})
    return blocks


def test_tight_gutter_two_columns_admitted():
    """A 15pt gutter splits when both sides carry y-overlapping block stacks."""
    columns = detect_columns(_two_tight_columns(), column_gap_threshold=20)

    assert len(columns) == 2
    assert {b["text"] for b in columns[0]} == {f"L{i}" for i in range(5)}
    assert {b["text"] for b in columns[1]} == {f"R{i}" for i in range(5)}


def test_tight_gutter_page_number_in_gutter_is_pruned():
    """A centered page number below both columns must not erase the channel.

    Measured on PMC5500034.1 p4 / PMC10500022.1 p6: the footer page number sits
    *inside* the 15pt gutter. It y-overlaps nothing, so it cannot be interleaved
    with anything and carries no evidence against the channel.
    """
    blocks = _two_tight_columns()
    blocks.append({"bbox": [288, 460, 293, 470], "text": "4"})

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 2


def test_tight_gutter_needs_blocks_on_both_sides():
    """Two blocks on one side is not a column; it is a figure label or margin note."""
    blocks = [{"bbox": [50, 100 + i * 60, 285, 150 + i * 60], "text": f"L{i}"} for i in range(5)]
    blocks += [
        {"bbox": [300, 100, 540, 150], "text": "R0"},
        {"bbox": [300, 160, 540, 210], "text": "R1"},
    ]

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 1


def test_tight_gutter_needs_y_overlap():
    """Left blocks above, right blocks below: a y-sort cannot interleave them."""
    blocks = [{"bbox": [50, 100 + i * 30, 285, 120 + i * 30], "text": f"L{i}"} for i in range(4)]
    blocks += [{"bbox": [300, 400 + i * 30, 540, 420 + i * 30], "text": f"R{i}"} for i in range(4)]

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 1


def test_tight_gutter_indented_quotation_does_not_split():
    """An indented block overlaps its body text in x; no channel can exist."""
    blocks = [{"bbox": [50, 100 + i * 60, 540, 150 + i * 60], "text": f"B{i}"} for i in range(4)]
    blocks += [{"bbox": [120, 340 + i * 30, 470, 360 + i * 30], "text": f"Q{i}"} for i in range(3)]

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 1


def test_tight_gutter_multiple_channels_rejected():
    """Several qualifying tight channels is a table signature, not a layout."""
    blocks = []
    for col, (x0, x1) in enumerate([(50, 180), (192, 322), (334, 464)]):
        for i in range(5):
            y = 100 + i * 60
            blocks.append({"bbox": [x0, y, x1, y + 50], "text": f"C{col}"})

    columns = detect_columns(blocks, column_gap_threshold=20)

    assert len(columns) == 1


# --- Gutter-merged block resegmentation (#405) ------------------------------------


def _fused_two_column_block() -> dict:
    """One block whose lines alternate between two disjoint x-bands (y order)."""
    lines = []
    for i in range(4):
        y = 100 + i * 12
        lines.append({"bbox": [50, y, 280, y + 10], "spans": [{"text": f"left {i}"}]})
        lines.append({"bbox": [300, y + 1, 540, y + 11], "spans": [{"text": f"right {i}"}]})
    return {"type": 0, "bbox": [50, 100, 540, 148], "lines": lines, "_layout_label": "text"}


def test_split_fused_two_column_block():
    """Lines regroup into one block per band, left band first, order preserved."""
    from all2md.parsers.pdf import split_gutter_merged_blocks

    result = split_gutter_merged_blocks([_fused_two_column_block()], page_width=595.0)

    assert len(result) == 2
    left, right = result
    assert [s["text"] for line in left["lines"] for s in line["spans"]] == [f"left {i}" for i in range(4)]
    assert [s["text"] for line in right["lines"] for s in line["spans"]] == [f"right {i}" for i in range(4)]
    assert left["bbox"] == (50, 100, 280, 146)
    assert right["bbox"] == (300, 101, 540, 147)
    assert left["_layout_label"] == "text"


def test_split_leaves_normal_paragraph_alone():
    """A paragraph's lines all overlap in x -- including a short last line."""
    from all2md.parsers.pdf import split_gutter_merged_blocks

    lines = [
        {"bbox": [50, 100, 540, 110], "spans": [{"text": "full line"}]},
        {"bbox": [50, 112, 540, 122], "spans": [{"text": "full line"}]},
        {"bbox": [50, 124, 540, 134], "spans": [{"text": "full line"}]},
        {"bbox": [50, 136, 200, 146], "spans": [{"text": "short last"}]},
    ]
    block = {"type": 0, "bbox": [50, 100, 540, 146], "lines": lines}

    result = split_gutter_merged_blocks([block], page_width=595.0)

    assert result == [block]


def test_split_leaves_fused_table_alone():
    """Many narrow bands is a data grid; column-major order would be wrong for it."""
    from all2md.parsers.pdf import split_gutter_merged_blocks

    lines = []
    for i in range(4):
        y = 100 + i * 12
        for x0, x1 in [(50, 100), (150, 200), (250, 300), (350, 400), (450, 500)]:
            lines.append({"bbox": [x0, y, x1, y + 10], "spans": [{"text": "cell"}]})
    block = {"type": 0, "bbox": [50, 100, 500, 146], "lines": lines}

    result = split_gutter_merged_blocks([block], page_width=595.0)

    assert result == [block]


def test_split_leaves_narrow_block_alone():
    """A block narrower than half the page cannot hold two columns."""
    from all2md.parsers.pdf import split_gutter_merged_blocks

    lines = [{"bbox": [50, 100 + i * 12, 130, 110 + i * 12], "spans": [{"text": "a"}]} for i in range(2)] + [
        {"bbox": [160, 100 + i * 12, 240, 110 + i * 12], "spans": [{"text": "b"}]} for i in range(2)
    ]
    block = {"type": 0, "bbox": [50, 100, 240, 134], "lines": lines}

    result = split_gutter_merged_blocks([block], page_width=595.0)

    assert result == [block]


# --- Hyphenated words across merged paragraph seams (#405) -------------------------


def _seam_paragraphs(left_tail: str, right_head: str):
    """Two Paragraph nodes as the PDF parser produces them at a block seam."""
    from all2md.ast.nodes import Paragraph, SourceLocation, Text

    return [
        Paragraph(
            content=[Text(content=left_tail)],
            source_location=SourceLocation(format="pdf", page=1, metadata={"bbox": [50, 100, 280, 120]}),
        ),
        Paragraph(
            content=[Text(content=right_head)],
            source_location=SourceLocation(format="pdf", page=1, metadata={"bbox": [50, 122, 280, 142]}),
        ),
    ]


def _merged_text(nodes) -> str:
    from all2md.parsers.pdf import PdfToAstConverter

    merged = PdfToAstConverter()._merge_adjacent_paragraphs(nodes)
    assert len(merged) == 1
    return "".join(t.content for t in merged[0].content)


def test_merge_joins_hyphenated_word_across_blocks():
    """dehyphenate_blocks cannot see across blocks; the paragraph merge must.

    Measured on PMC7000152.1: tight-gutter reference columns fragment into 2-4
    line PyMuPDF blocks, so words hyphenated at a block's last line survived as
    "transcrip- tion" and cost every affected title its recall.
    """
    text = _merged_text(_seam_paragraphs("a farnesoic acid-responsive transcrip-", "tion factor"))
    assert text == "a farnesoic acid-responsive transcription factor"


def test_merge_keeps_hyphen_for_uppercase_continuation():
    """An uppercase continuation signals a real compound: keep the hyphen."""
    text = _merged_text(_seam_paragraphs("the Anglo-", "Saxon corpus"))
    assert text == "the Anglo-Saxon corpus"


def test_merge_without_hyphen_keeps_the_space():
    text = _merged_text(_seam_paragraphs("a sentence that continues", "on the next block"))
    assert text == "a sentence that continues on the next block"
