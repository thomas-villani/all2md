#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/docx_styles.py
"""Resolve the weight a run *renders* with, not just the weight it declares.

``python-docx`` answers ``run.bold`` from the run's own ``w:rPr`` and nothing else, so a
run whose only character property is ``w:rStyle`` reports ``None`` -- no opinion -- even
when the style it names is defined bold. The word renders bold in Word and printed as
plain text here. The same hole swallows style-carried italic and strikethrough.

What Word actually does is walk a **cascade**, and the part of it a run's weight depends
on is four layers deep:

``w:docDefaults``
    ``styles.xml``'s ``w:rPrDefault/w:rPr`` -- the document-wide base.
**The paragraph style chain**
    ``w:pStyle`` plus every ``w:basedOn`` ancestor. A paragraph with no ``w:pStyle`` gets
    the *default* paragraph style, which is most paragraphs in a real document.
**The character style chain**
    ``w:rStyle`` plus its own ``w:basedOn`` ancestors. This is the layer that was missing.
**Direct run formatting**
    ``w:rPr`` on the run itself.

Bold, italic and strike are **toggle** properties (ECMA-376 17.7.3), which do not
resolve by override: the result is the ``docDefaults`` value flipped once per *style
level* whose value differs from it, so a bold paragraph style and a bold character style
**cancel**. Each chain is one level, flattened over its own ``w:basedOn`` by plain
override -- inheritance is not a level boundary. Direct formatting is absolute and never
participates in the flipping. These rules are Word's measured behaviour rather than a
reading of the spec's prose, and they are borrowed from ``docx-plus``, which settled them
against live Word.

**Inherited weight is judged relatively, and that is why this does not regress
headings.** Markdown's ``**`` marks a span as heavier than the text around it, so a run
that merely matches its paragraph has nothing to be marked against. ``Heading 1`` carries
its own ``<w:b/>``; marking every effectively-bold run would wrap every heading's text in
``**`` inside the ``#``. So weight a run *inherits* is compared against the paragraph's
baseline -- the same cascade with the character style and the run's direct formatting
removed -- and marked only where it rises above it.

Weight a run states **directly** is marked as stated, whatever surrounds it. Typing bold
onto a word is an explicit act, the author is the authority on it, and it is what all2md
has always emitted, so a directly bold run inside an already-bold heading keeps its
``**``. The relative rule is what this change adds; it does not reach back over what
direct formatting already said.

Two layers are deliberately not consulted. A **table style** can carry weight, but
reaching it needs the cell's position, its table's ``w:tblLook`` and the conditional
``w:tblStylePr`` branches -- a different and much larger machine for a case the corpus
does not contain. And the paragraph *mark*'s ``w:rPr`` (``w:pPr/w:rPr``) is the formatting
of the pilcrow, not of the paragraph's text, so it is not part of any run's baseline.

Unlike ``docx-plus``, a malformed chain never raises here: a ``w:basedOn`` cycle or a
chain past Word's depth limit stops the walk and keeps whatever it resolved. A converter
that refuses a document because its styles disagree with themselves is worse than one
that renders it the way Word would.
"""

from __future__ import annotations

from typing import Any, NamedTuple

WORDPROCESSING_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORDPROCESSING_NS}}}"

#: Word stops following ``w:basedOn`` after eleven hops, and so does this.
MAX_STYLE_CHAIN_DEPTH = 11

#: The ECMA-376 17.7.3 toggles that Markdown can express. The spec lists twelve; the
#: other nine (``caps``, ``vanish``, ``emboss``, ...) have no Markdown, so resolving them
#: would produce a value with nowhere to go.
TOGGLES = ("b", "i", "strike")

#: ``w:val`` spellings that turn a toggle off. A toggle with no ``w:val`` at all is on.
_OFF = frozenset({"0", "false", "off"})

#: ECMA-376 17.7.4.17: a ``w:style`` with no ``w:type`` is a paragraph style.
_DEFAULT_STYLE_KIND = "paragraph"

#: Word's fallback when no paragraph style claims ``w:default``.
_FALLBACK_STYLE_ID = "Normal"


def _toggle_value(rpr: Any, name: str) -> bool | None:
    """Report what one ``w:rPr`` says about one toggle, or ``None`` if it is silent.

    The distinction matters: ``None`` is "no opinion" and takes no part in the toggle
    rule, while ``False`` is an explicit ``w:val="0"`` that can cancel a lower layer.
    """
    if rpr is None:
        return None
    element = rpr.find(f"{W}{name}")
    if element is None:
        return None
    value = element.get(f"{W}val")
    return value is None or value not in _OFF


def _rpr_toggles(rpr: Any) -> dict[str, bool | None]:
    """Every toggle one ``w:rPr`` states."""
    return {name: _toggle_value(rpr, name) for name in TOGGLES}


class ParagraphContext(NamedTuple):
    """What a paragraph contributes to every run inside it.

    Resolved once per paragraph rather than once per run: the style chain walk and the
    baseline are identical for every run, and a paragraph can hold hundreds.
    """

    #: The cascade this was resolved against, so a caller holding a context needs nothing
    #: else to ask about a run.
    resolver: Any
    #: The paragraph style chain's contribution, one value per toggle.
    level: dict[str, bool | None]
    #: The weight the paragraph's own text already carries, which runs must rise above.
    baseline: dict[str, bool]

    def emphasis(self, run_element: Any) -> dict[str, bool]:
        """Which toggles a run in this paragraph carries above its baseline."""
        resolver: EffectiveFormatting = self.resolver
        return resolver.run_emphasis(run_element, self)


class EffectiveFormatting:
    """The style cascade of one document, indexed once.

    Built per styles part and reused for every paragraph in it -- the index, the
    ``docDefaults`` base and the per-style chains are all document-wide.
    """

    def __init__(self, styles_root: Any) -> None:
        """Index one document's styles part."""
        self._styles: dict[tuple[str, str], Any] = {}
        default_paragraph_style: str | None = None
        for style in styles_root.findall(f"{W}style"):
            style_id = style.get(f"{W}styleId")
            if not style_id:
                continue
            kind = style.get(f"{W}type") or _DEFAULT_STYLE_KIND
            self._styles[(style_id, kind)] = style
            # Word takes the *last* paragraph style claiming w:default.
            if kind == "paragraph" and _on(style.get(f"{W}default")):
                default_paragraph_style = style_id
        if default_paragraph_style is None and (_FALLBACK_STYLE_ID, "paragraph") in self._styles:
            default_paragraph_style = _FALLBACK_STYLE_ID
        self._default_paragraph_style = default_paragraph_style

        defaults = styles_root.find(f"{W}docDefaults")
        run_defaults = None if defaults is None else defaults.find(f"{W}rPrDefault")
        self._base = _rpr_toggles(None if run_defaults is None else run_defaults.find(f"{W}rPr"))

        self._chains: dict[tuple[str, str], list[Any]] = {}
        self._levels: dict[tuple[str, str], dict[str, bool | None]] = {}

    def _chain(self, style_id: str, kind: str) -> list[Any]:
        """Return the style and its ``w:basedOn`` ancestors, leaf first.

        Every hop is type-checked: a ``w:basedOn`` pointing at a style of another type
        ends the chain rather than extending it, because Word inherits nothing across
        that edge. A cycle or an over-deep chain ends the walk too -- see the module
        docstring on why neither raises.
        """
        key = (style_id, kind)
        cached = self._chains.get(key)
        if cached is not None:
            return cached
        chain: list[Any] = []
        seen: set[str] = set()
        current: str | None = style_id
        while current is not None and current not in seen and len(chain) < MAX_STYLE_CHAIN_DEPTH:
            seen.add(current)
            style = self._styles.get((current, kind))
            if style is None:
                break
            chain.append(style)
            based_on = style.find(f"{W}basedOn")
            current = based_on.get(f"{W}val") if based_on is not None else None
        self._chains[key] = chain
        return chain

    def _level(self, style_id: str | None, kind: str) -> dict[str, bool | None]:
        """One style level's value per toggle, flattened over its chain by override.

        The whole chain is a single level of the toggle rule, so a child restating its
        parent's ``<w:b/>`` overrides it rather than cancelling it.
        """
        if not style_id:
            return dict.fromkeys(TOGGLES, None)
        key = (style_id, kind)
        cached = self._levels.get(key)
        if cached is not None:
            return cached
        values: dict[str, bool | None] = dict.fromkeys(TOGGLES, None)
        for style in reversed(self._chain(style_id, kind)):  # root first, leaf wins
            rpr = style.find(f"{W}rPr")
            if rpr is None:
                continue
            for name, stated in _rpr_toggles(rpr).items():
                if stated is not None:
                    values[name] = stated
        self._levels[key] = values
        return values

    def _resolve(self, levels: list[dict[str, bool | None]], direct: dict[str, bool | None]) -> dict[str, bool]:
        """Combine the layers per ECMA-376 17.7.3 -- see the module docstring."""
        resolved: dict[str, bool] = {}
        for name in TOGGLES:
            stated = direct.get(name)
            if stated is not None:  # direct formatting is absolute
                resolved[name] = stated
                continue
            base = bool(self._base.get(name))
            flips = sum(1 for level in levels if level[name] is not None and level[name] != base)
            resolved[name] = base != (flips % 2 == 1)
        return resolved

    def paragraph_context(self, paragraph_element: Any) -> ParagraphContext:
        """Resolve what a paragraph's own text renders with."""
        level = self._level(self._paragraph_style_id(paragraph_element), "paragraph")
        return ParagraphContext(resolver=self, level=level, baseline=self._resolve([level], {}))

    def _paragraph_style_id(self, paragraph_element: Any) -> str | None:
        """Return the paragraph's style, or the document's default paragraph style.

        The fallback is not a detail: most paragraphs in a real document carry no
        ``w:pStyle`` at all, so this is the layer that decides what ordinary text looks
        like -- and a bold ``Normal`` cancels a bold character style.
        """
        ppr = None if paragraph_element is None else paragraph_element.find(f"{W}pPr")
        pstyle = None if ppr is None else ppr.find(f"{W}pStyle")
        style_id = None if pstyle is None else pstyle.get(f"{W}val")
        if style_id and (style_id, "paragraph") in self._styles:
            return style_id
        return self._default_paragraph_style

    def run_emphasis(self, run_element: Any, context: ParagraphContext) -> dict[str, bool]:
        """Report which toggles Markdown should mark on this run.

        Weight the run states **directly** is marked as stated, whatever the paragraph
        around it looks like. Typing bold onto a word is an explicit act, the author is
        the authority on it, and it is what all2md has always emitted -- so a directly
        bold run inside an already-bold heading keeps its ``**``.

        Weight the run *inherits* is judged against its paragraph's baseline instead.
        ``**`` marks a span as heavier than its surroundings, so a run that is merely as
        bold as the rest of its paragraph has nothing to be marked against -- which is
        what stops a bold paragraph style from wrapping every word it covers.
        """
        rpr = None if run_element is None else run_element.find(f"{W}rPr")
        rstyle = None if rpr is None else rpr.find(f"{W}rStyle")
        character_level = self._level(None if rstyle is None else rstyle.get(f"{W}val"), "character")
        direct = _rpr_toggles(rpr)
        effective = self._resolve([context.level, character_level], direct)
        marked: dict[str, bool] = {}
        for name in TOGGLES:
            stated = direct[name]
            marked[name] = stated if stated is not None else (effective[name] and not context.baseline[name])
        return marked


def _on(value: str | None) -> bool:
    """Whether an on/off attribute such as ``w:default`` is set."""
    return value is not None and value not in _OFF


def styles_root(part: Any) -> Any | None:
    """Return the ``w:styles`` element behind a story part, or ``None`` when unreachable.

    Note parts and the comments part have no styles of their own; they resolve against
    the document's, which is what the story wrappers already hand back.
    """
    styles = getattr(part, "styles", None)
    return getattr(styles, "element", None)
