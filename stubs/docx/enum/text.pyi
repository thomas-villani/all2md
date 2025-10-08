"""Type stubs for docx.enum.text module."""

from enum import IntEnum

class WD_ALIGN_PARAGRAPH(IntEnum):
    """Paragraph alignment options."""

    LEFT = 0
    CENTER = 1
    RIGHT = 2
    JUSTIFY = 3
    DISTRIBUTE = 4
    JUSTIFY_MED = 5
    JUSTIFY_HI = 7
    JUSTIFY_LOW = 8
    THAI_JUSTIFY = 9


class WD_LINE_SPACING(IntEnum):
    """Line spacing options."""

    SINGLE = 0
    ONE_POINT_FIVE = 1
    DOUBLE = 2
    AT_LEAST = 3
    EXACTLY = 4
    MULTIPLE = 5


class WD_TAB_ALIGNMENT(IntEnum):
    """Tab stop alignment options."""

    LEFT = 0
    CENTER = 1
    RIGHT = 2
    DECIMAL = 3
    BAR = 4
    LIST = 6
    CLEAR = 7


class WD_TAB_LEADER(IntEnum):
    """Tab leader character options."""

    SPACES = 0
    DOTS = 1
    DASHES = 2
    LINES = 3
    HEAVY = 4
    MIDDLE_DOT = 5
