"""Type stubs for docx.oxml package."""

from typing import Any
from xml.etree.ElementTree import Element

def OxmlElement(tag: str, **kwargs: Any) -> Element:
    """Create an Open XML element.

    Parameters
    ----------
    tag : str
        XML tag name
    **kwargs
        Attributes to set on the element

    Returns
    -------
    Element
        XML element
    """
    ...
