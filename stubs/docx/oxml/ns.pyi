"""Type stubs for docx.oxml.ns module."""

def qn(tag: str) -> str:
    """Return a qualified name for an XML tag.

    Parameters
    ----------
    tag : str
        Tag name (e.g., 'w:t' for word processing text)

    Returns
    -------
    str
        Qualified name with namespace
    """
    ...


def nsdecls(*prefixes: str) -> str:
    """Return namespace declarations for use in XML strings.

    Parameters
    ----------
    *prefixes : str
        Namespace prefixes (e.g., 'w', 'r', 'a')

    Returns
    -------
    str
        Namespace declaration string
    """
    ...
