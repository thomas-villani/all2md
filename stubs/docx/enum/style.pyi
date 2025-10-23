"""Type stubs for docx.enum.style module."""

from enum import IntEnum

class WD_STYLE_TYPE(IntEnum):
    """Style type enumeration."""

    PARAGRAPH = 1
    CHARACTER = 2
    TABLE = 3
    LIST = 4

class WD_BUILTIN_STYLE(IntEnum):
    """Built-in style identifiers."""

    NORMAL = 0
    HEADING_1 = 1
    HEADING_2 = 2
    HEADING_3 = 3
    HEADING_4 = 4
    HEADING_5 = 5
    HEADING_6 = 6
    HEADING_7 = 7
    HEADING_8 = 8
    HEADING_9 = 9
    TITLE = 10
    SUBTITLE = 11
    QUOTE = 29
    INTENSE_QUOTE = 30
    LIST_PARAGRAPH = 34
    BODY_TEXT = 67
    # Many more... but these are the common ones
