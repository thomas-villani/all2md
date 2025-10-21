"""MediaWiki markup fixtures for converter regression tests."""

from __future__ import annotations

from io import BytesIO


def create_mediawiki_article() -> str:
    """Return MediaWiki text with headings, links, and templates."""
    return (
        "= Sample Article =\n\n"
        "This is a '''bold''' statement with ''italic'' words.\n\n"
        "== Links and Lists ==\n"
        "* [[Main Page]]\n"
        "* [[Help:Contents|Help Contents]]\n"
        "* External link: [https://example.com Example]\n\n"
        "=== Infobox ===\n"
        "{{Infobox\n"
        "| title = Fixture Entry\n"
        "| description = Demonstrates MediaWiki markup\n"
        "}}\n\n"
        "==== Table ====\n"
        '{| class="wikitable"\n'
        "! Name !! Role !! Score\n"
        "|-\n"
        "| Alice || Developer || 95\n"
        "|-\n"
        "| Bob || Designer || 88\n"
        "}\n"
    )


def mediawiki_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode MediaWiki markup to bytes."""
    return text.encode(encoding)


def mediawiki_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream for MediaWiki content."""
    return BytesIO(mediawiki_to_bytes(text, encoding=encoding))
