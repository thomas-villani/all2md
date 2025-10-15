"""Type stubs for pptx.oxml.ns module."""



class NamespacePrefixedTag:
    """Represents a namespace-prefixed XML tag."""

    ...


def qn(tag: str) -> str:
    """Return qualified name for tag.

    Parameters
    ----------
    tag : str
        Tag name

    Returns
    -------
    str
        Qualified name

    """
    ...


def nsuri(prefix: str) -> str:
    """Return namespace URI for prefix.

    Parameters
    ----------
    prefix : str
        Namespace prefix

    Returns
    -------
    str
        Namespace URI

    """
    ...


namespaces: dict[str, str]
nsmap: dict[str, str]
pfxmap: dict[str, str]
nsdecls: str
