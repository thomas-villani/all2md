"""Type stubs for pptx.oxml module."""

from typing import Any


def parse_xml(xml: str | bytes) -> Any:
    """Return root lxml element obtained by parsing XML character string.

    Parameters
    ----------
    xml : str or bytes
        XML string or bytes to parse

    Returns
    -------
    Any
        Root lxml element

    """
    ...
