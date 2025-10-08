"""Type stubs for docx.shared module."""


class Length:
    """Base class for length measurements."""

    def __init__(self, emu: int) -> None: ...

    @property
    def inches(self) -> float:
        """Length in inches."""
        ...

    @property
    def cm(self) -> float:
        """Length in centimeters."""
        ...

    @property
    def pt(self) -> float:
        """Length in points."""
        ...

    @property
    def emu(self) -> int:
        """Length in English Metric Units."""
        ...


def Inches(inches: float) -> Length:
    """Create a Length object from inches.

    Parameters
    ----------
    inches : float
        Number of inches

    Returns
    -------
    Length
        Length object

    """
    ...


def Cm(cm: float) -> Length:
    """Create a Length object from centimeters.

    Parameters
    ----------
    cm : float
        Number of centimeters

    Returns
    -------
    Length
        Length object

    """
    ...


def Pt(points: float) -> Length:
    """Create a Length object from points.

    Parameters
    ----------
    points : float
        Number of points

    Returns
    -------
    Length
        Length object

    """
    ...


def Emu(emu: int) -> Length:
    """Create a Length object from EMUs.

    Parameters
    ----------
    emu : int
        Number of English Metric Units

    Returns
    -------
    Length
        Length object

    """
    ...


class RGBColor:
    """Represents an RGB color."""

    def __init__(self, r: int, g: int, b: int) -> None:
        """Create an RGB color.

        Parameters
        ----------
        r : int
            Red component (0-255)
        g : int
            Green component (0-255)
        b : int
            Blue component (0-255)

        """
        ...

    @classmethod
    def from_string(cls, rgb_hex_str: str) -> RGBColor:
        """Create RGBColor from hex string like 'FF0000'."""
        ...


class Twips:
    """Represents a measurement in twips (1/20th of a point)."""

    def __init__(self, twips: int) -> None: ...
