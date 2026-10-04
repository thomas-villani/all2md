"""Round trips through another format: ``md -> AST -> FORMAT -> AST -> md``.

``python -m benchmarks.roundtrip --via man`` writes every corpus document as a
man page and reads it back before the Markdown render, so the two oracles judge
that format's renderer and parser as a pair.

A format that cannot express some Markdown construct fails the HTML oracle on
every document holding it, for a reason nobody can fix. Left like that, the gate
would have to allowlist nearly every document and would then be blind to new
losses in them. A :class:`ViaProfile` therefore declares the format's *inherent*
losses once, as a projection applied to both the original and the round-tripped
reference HTML before they are compared: what the format cannot say is removed
from both sides, and everything else must still survive. Anything a projection
removes has to be a limit of the format itself, never a defect of our renderer
or parser - those belong in the expected-failure table in ``run.py``, where a fix
turns them red until the entry is deleted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ViaProfile:
    """How to run and judge a round trip through one format.

    ``renderer_options`` configure the write into the format (for instance to
    keep a convention such as man's uppercase section headings from reading as a
    loss). ``project`` rewrites a parsed reference-HTML tree in place to remove
    what the format cannot express.
    """

    renderer_options: Optional[Any] = None
    project: Optional[Callable[["BeautifulSoup"], None]] = None


# A title that gained a manual section on the way through .TH: "Kitchen Sink(1)".
_TITLE_SECTION = re.compile(r"\s*\([0-9][A-Za-z0-9]*\)\s*$")
# The .TH name the man renderer writes when the document has no title.
_UNTITLED = re.compile(r"^\s*(UNTITLED\s*)?(\([0-9][A-Za-z0-9]*\))?\s*$")
_MATH_DELIMITERS = re.compile(r"^\s*(\$\$|\\\(|\\\[)|(\$\$|\\\)|\\\])\s*$")


def _project_man(soup: "BeautifulSoup") -> None:
    """Remove from a reference-HTML tree what man(7) cannot express.

    Each rule is a documented limit of the man renderer (see the module
    docstring of ``all2md.renderers.man``):

    - ``.TH`` holds the title, so it comes back as ``Title(1)``, and a document
      with no title gets the placeholder ``UNTITLED``;
    - code blocks have no language, links and images no title;
    - images become their alt text; strikethrough, highlight, superscript and
      subscript become plain text; insert and underline become italics;
    - there are only two heading levels below the title, so h4-h6 become bold
      paragraphs, and there is no rule, so ``<hr>`` becomes ``* * *``;
    - tbl columns are always aligned, left by default;
    - math becomes its LaTeX source in code;
    - a term holds one definition, so several fold into one, a paragraph each.
    """
    from bs4.element import Tag

    first_heading = soup.find("h1")
    if isinstance(first_heading, Tag):
        text = first_heading.get_text()
        if _UNTITLED.match(text):
            first_heading.decompose()
        elif _TITLE_SECTION.search(text):
            first_heading.string = _TITLE_SECTION.sub("", text)

    for tag in soup.find_all("code"):
        tag.attrs.pop("class", None)
    for tag in soup.find_all(["a", "img"]):
        tag.attrs.pop("title", None)
    for tag in soup.find_all("img"):
        tag.replace_with(tag.get("alt") or "")
    for tag in soup.find_all(["del", "s", "mark", "sup", "sub"]):
        if tag.name == "sup" and "footnote-ref" in (tag.get("class") or []):
            continue
        tag.unwrap()
    for tag in soup.find_all(["ins", "u"]):
        tag.name = "em"
    for tag in soup.find_all(["h4", "h5", "h6"]):
        tag.name = "strong"
        tag.wrap(soup.new_tag("p"))
    for tag in soup.find_all("hr"):
        paragraph = soup.new_tag("p")
        paragraph.string = "* * *"
        tag.replace_with(paragraph)
    for tag in soup.find_all(["th", "td"]):
        if tag.get("style") == "text-align:left":
            del tag["style"]
    for tag in soup.find_all(class_="math"):
        source = _MATH_DELIMITERS.sub("", tag.get_text()).strip()
        code = soup.new_tag("code")
        code.string = source
        if tag.name == "div" and (tag.parent is None or tag.parent.name not in ("p", "li", "td", "th")):
            pre = soup.new_tag("pre")
            pre.append(code)
            tag.replace_with(pre)
        else:
            tag.replace_with(code)
    for first in soup.find_all("dd"):
        if first.parent is None:
            continue  # already merged into an earlier definition
        following = []
        for sibling in first.find_next_siblings():
            if sibling.name != "dd":
                break
            following.append(sibling)
        if following:
            _merge_definitions(soup, first, following)
    # Unwrapping leaves neighboring strings that the normalizer would print apart.
    soup.smooth()


_BLOCK_TAGS = frozenset({"p", "pre", "ul", "ol", "dl", "blockquote", "table", "div", "h1", "h2", "h3"})


def _merge_definitions(soup: "BeautifulSoup", first: Any, following: list[Any]) -> None:
    """Fold a term's several definitions into one, a paragraph each, as ``.TP`` holds them."""
    for definition in [first, *following]:
        if not any(getattr(child, "name", None) in _BLOCK_TAGS for child in definition.children):
            paragraph = soup.new_tag("p")
            for child in list(definition.children):
                paragraph.append(child.extract())
            definition.append(paragraph)
    for definition in following:
        for child in list(definition.children):
            first.append(child.extract())
        definition.decompose()


def _man_profile() -> ViaProfile:
    from all2md.options.man import ManRendererOptions

    return ViaProfile(renderer_options=ManRendererOptions(uppercase_section_headings=False), project=_project_man)


_PROFILES: dict[str, Callable[[], ViaProfile]] = {"man": _man_profile}


def profile_for(via: str) -> ViaProfile:
    """Return the profile for a format; formats without one are judged unprojected."""
    factory = _PROFILES.get(via)
    return factory() if factory else ViaProfile()
