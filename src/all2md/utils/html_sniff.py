#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/html_sniff.py
"""Recognize an HTML fragment from its content alone.

A whole HTML page announces itself (``<!DOCTYPE html>``, ``<html>``) and is
found by its magic bytes. A fragment does not: ``echo "<p>Hi</p>" | all2md -``
used to come out as plain text, its tags escaped. So content without a name
that opens with an HTML element, optionally after comments, is HTML.

This is asked last, after every content detector and the Markdown guess have
declined, so XML formats with detectors of their own keep them, and a README
that opens with ``<p align="center">`` but is Markdown below stays Markdown.
"""

from __future__ import annotations

import re

_SAMPLE_BYTES = 4096

# Elements a fragment plausibly opens with. Not svg or math, which are XML vocabularies too.
_ELEMENTS = (
    "a|abbr|address|article|aside|audio|b|blockquote|body|br|button|caption|cite|code|dd|del|details|dfn|div|dl|"
    "dt|em|figcaption|figure|footer|form|h[1-6]|head|header|hr|i|iframe|img|input|ins|kbd|label|li|main|mark|"
    "meta|nav|ol|p|picture|pre|q|s|samp|section|select|small|span|strong|style|sub|summary|sup|table|tbody|td|"
    "template|textarea|tfoot|th|thead|title|tr|u|ul|var|video"
)
_VOID = re.compile(r"(?:br|hr|img|input|meta)\Z", re.IGNORECASE)
_OPENING = re.compile(
    r"\A﻿?\s*(?:<!--.*?-->\s*)*<(" + _ELEMENTS + r")(?=[\s>/])[^<>]*>",
    re.IGNORECASE | re.DOTALL,
)


def looks_like_html_fragment(content: bytes) -> bool:
    """Return whether ``content`` opens with an HTML element.

    Parameters
    ----------
    content : bytes
        The start of the input; only the first 4 KB are examined.

    Returns
    -------
    bool
        True when the text opens with a known HTML element's start tag (after
        any comments) and either closes that element or the element is void
        (``<br>``, ``<img>``...).

    """
    if b"\x00" in content[:_SAMPLE_BYTES]:
        return False
    text = content[:_SAMPLE_BYTES].decode("utf-8", errors="ignore")
    opening = _OPENING.match(text)
    if opening is None:
        return False
    name = opening.group(1)
    if _VOID.match(name):
        return True
    return re.search(r"</" + re.escape(name) + r"\s*>", text, re.IGNORECASE) is not None
