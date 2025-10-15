"""Type stubs for pptx.util module."""

from typing import Any, Callable, Generic, TypeVar

_T = TypeVar("_T")


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
    def mm(self) -> float:
        """Length in millimeters."""
        ...

    @property
    def pt(self) -> float:
        """Length in points."""
        ...

    @property
    def centipoints(self) -> int:
        """Length in hundredths of a point (1/7200 inch)."""
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


def Mm(mm: float) -> Length:
    """Create a Length object from millimeters.

    Parameters
    ----------
    mm : float
        Number of millimeters

    Returns
    -------
    Length
        Length object

    """
    ...


def Centipoints(centipoints: int) -> Length:
    """Create a Length object from centipoints.

    Parameters
    ----------
    centipoints : int
        Number of hundredths of a point

    Returns
    -------
    Length
        Length object

    """
    ...


class lazyproperty(Generic[_T]):
    """Decorator like property, but evaluated only on first access.

    Like property, this can only be used to decorate methods having only a self parameter,
    and is accessed like an attribute on an instance. Unlike property, the decorated method
    is only evaluated on first access; the resulting value is cached and returned on
    subsequent accesses without re-evaluation.

    Parameters
    ----------
    fget : Callable
        The method to be decorated

    """

    def __init__(self, fget: Callable[[Any], _T]) -> None:
        """Initialize the lazyproperty decorator.

        Parameters
        ----------
        fget : Callable
            The getter method

        """
        ...

    def __get__(self, obj: Any, objtype: type | None = None) -> _T:
        """Get the property value.

        Parameters
        ----------
        obj : Any
            The instance
        objtype : type or None
            The class type

        Returns
        -------
        _T
            The cached property value

        """
        ...
