"""Type stubs for pptx.util module."""


class Length:
    """Represents a length measurement in EMUs (English Metric Units)."""

    def __init__(self, emu: int) -> None:
        """Create a Length from EMUs.

        Parameters
        ----------
        emu : int
            Length in English Metric Units

        """
        ...

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
