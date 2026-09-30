#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/docx_sdt.py
"""Unwrap Word structured document tags before anything else reads the document.

A *content control* (``w:sdt``, "structured document tag") is how Word marks a
region of a document as a field a person fills in: an author name on a title page,
a date picker, a drop-down, a rich-text block in a corporate template. It is also
what Word writes around a table of contents or a bibliography. The control is a
**wrapper**: its real content sits one level down, inside ``w:sdtContent``, beside
the ``w:sdtPr`` element that describes the control.

That extra level is invisible to ``python-docx``, and invisible in five separate
places at once, because every reader looks at *direct* children:

* ``w:sdt`` in the body -- the block walk yields ``w:p`` and ``w:tbl`` children, so a
  controlled paragraph is a grandchild and never appears;
* ``w:sdt`` inside a ``w:p`` -- ``Paragraph.runs`` and ``iter_inner_content`` yield
  only ``w:r`` and ``w:hyperlink``, so an inline control's text drops out of the
  middle of its sentence;
* ``w:sdt`` around a ``w:tbl`` -- the whole table disappears;
* ``w:sdt`` around a ``w:tr`` -- ``tbl.tr_lst`` is ``./w:tr``, so the row disappears;
* ``w:sdt`` inside a ``w:tc`` -- ``tc.p_lst`` is ``./w:p``, so the cell reads empty.

All five are total, silent loss. Patching five readers would leave a sixth for a
user to find, so -- exactly as with tracked changes in :mod:`all2md.parsers.docx_revisions`
-- the wrapper is *removed* on the element tree first and every reader below sees an
ordinary document that needs to know nothing about content controls.

Placeholder text is kept. A control the author never filled in carries
``w:showingPlcHdr`` and holds Word's boilerplate ("Click or tap here to enter
text."), and it is tempting to drop it -- but that text is what the page prints,
and a template's empty fields are a large part of what makes the template worth
reading. Suppressing them would trade one silent loss for another.
"""

from __future__ import annotations

from typing import Any

WORDPROCESSING_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORDPROCESSING_NS}}}"

SDT_TAG = f"{W}sdt"
SDT_CONTENT_TAG = f"{W}sdtContent"


def document_has_content_controls(root: Any) -> bool:
    """Report whether the tree contains any content control at all.

    Checked before anything is copied or rewritten: most documents carry none, and
    they must cost nothing.
    """
    if root is None:
        return False
    return next(iter(root.iter(SDT_TAG)), None) is not None


def unwrap_content_controls(root: Any) -> int:
    """Replace every ``w:sdt`` with the content it wraps, in place.

    The tree is mutated, so callers that do not own the document must copy first.
    Returns the number of controls unwrapped, which is what the caller logs.

    ``iter`` walks in document order, so an outer control is unwrapped before the
    ones nested inside it. Those are then reparented rather than orphaned, and the
    parent each one is spliced into is read at the moment it is unwrapped -- which
    is why nesting needs no special handling.
    """
    if root is None:
        return 0

    unwrapped = 0
    for sdt in list(root.iter(SDT_TAG)):
        parent = sdt.getparent()
        if parent is None:
            continue

        index = parent.index(sdt)
        content = sdt.find(SDT_CONTENT_TAG)
        # A control with no w:sdtContent holds nothing but its own properties, so
        # there is nothing to splice in and the wrapper simply goes.
        children = list(content) if content is not None else []
        for offset, child in enumerate(children):
            parent.insert(index + offset, child)
        parent.remove(sdt)
        unwrapped += 1

    return unwrapped


# Wrappers that change how their content is shown or tagged, never what it says, and
# carry no content of their own beyond an optional properties child. ``w:dir`` and
# ``w:bdo`` set the direction of the runs inside (an Arabic or Hebrew sentence),
# ``w:smartTag`` marks a recognised name or date, and ``w:customXml`` binds content to
# a custom schema -- in the body, around a row or cell, or inside a paragraph, which
# puts it in front of the same five readers a content control is.
TRANSPARENT_WRAPPER_TAGS = (f"{W}dir", f"{W}bdo", f"{W}smartTag", f"{W}customXml")
_WRAPPER_PROPERTY_TAGS = frozenset((f"{W}smartTagPr", f"{W}customXmlPr"))


def document_has_transparent_wrappers(root: Any) -> bool:
    """Report whether the tree contains any ``w:dir``, ``w:bdo``, ``w:smartTag`` or ``w:customXml``."""
    if root is None:
        return False
    return next(iter(root.iter(*TRANSPARENT_WRAPPER_TAGS)), None) is not None


def unwrap_transparent_wrappers(root: Any) -> int:
    """Replace every transparent wrapper with the content it wraps, in place.

    The run direction ``w:dir`` and ``w:bdo`` set is display only: the characters are
    stored in reading order, which is the order the text is written out in. Returns
    the number of wrappers removed. Nesting needs no special handling, for the reason
    ``unwrap_content_controls`` gives.
    """
    if root is None:
        return 0

    unwrapped = 0
    for wrapper in list(root.iter(*TRANSPARENT_WRAPPER_TAGS)):
        parent = wrapper.getparent()
        if parent is None:
            continue

        index = parent.index(wrapper)
        children = [child for child in wrapper if child.tag not in _WRAPPER_PROPERTY_TAGS]
        for offset, child in enumerate(children):
            parent.insert(index + offset, child)
        parent.remove(wrapper)
        unwrapped += 1

    return unwrapped
