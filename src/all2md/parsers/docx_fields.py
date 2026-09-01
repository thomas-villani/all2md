#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/docx_fields.py
"""Resolve Word field codes before anything else reads the document.

A *field* is a piece of the document Word computes rather than stores: a hyperlink, a
cross-reference, a figure number, a page count, a table of contents. Word writes each
one as an **instruction** plus the **cached result** it last computed, and it is the
cached result that the page prints -- so nothing here evaluates a field. Everything
needed is already in the file; the job is to read the half Word displays and drop the
half it does not.

Word writes fields in two encodings, and both hide something from ``python-docx``:

``w:fldSimple``
    One element, with ``w:instr`` as an attribute and the cached result as **child
    runs**. ``Paragraph.runs`` yields only direct ``w:r`` children, so the result is a
    grandchild and invisible -- the same mechanism as a content control, and it is why
    a ``SEQ`` caption printed ``Figure :`` with the number missing.

``w:fldChar``
    Three marker runs -- ``begin``, ``separate``, ``end`` -- with the instruction in
    ``w:instrText`` runs between the first two and the cached result in ordinary runs
    between the last two. The result runs *are* direct children, so their text already
    appeared; what did not survive was the instruction's meaning, so a ``HYPERLINK``
    field printed its target as bare prose instead of becoming a link.

**A field is not paragraph-scoped.** The corpus's own ``REF`` field opens in one
paragraph and closes in the next, which is ordinary Word output and the reason this
walks the whole tree in document order rather than paragraph by paragraph. Fields also
nest -- a ``HYPERLINK`` inside a ``TOC`` entry, say -- so the walk keeps a stack, and a
result computed inside another field's *instruction* is dropped with it rather than
leaking into the text.

Semantics that survive resolution are stamped onto the result runs in a private
namespace and read back by :func:`field_target`, exactly as
:mod:`all2md.parsers.docx_revisions` stamps revision authorship. That keeps the readers
free of any knowledge of fields: the inline path asks a run for its link target and does
not care whether the answer came from a ``w:hyperlink`` element or a ``HYPERLINK`` field.
"""

from __future__ import annotations

from typing import Any

WORDPROCESSING_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORDPROCESSING_NS}}}"

#: Private namespace for semantics recovered from an instruction. Like the revision
#: stamp it never has to survive a save -- resolution runs on a copy the parser owns --
#: but a namespaced attribute keeps the tree legal XML either way.
FIELD_NS = "https://all2md.dev/ns/field"
FIELD_TARGET = f"{{{FIELD_NS}}}target"

RUN_TAG = f"{W}r"
FLD_SIMPLE_TAG = f"{W}fldSimple"
FLD_CHAR_TAG = f"{W}fldChar"
#: ``w:delInstrText`` is the same instruction inside a tracked deletion.
INSTR_TAGS = (f"{W}instrText", f"{W}delInstrText")


def document_has_fields(root: Any) -> bool:
    """Report whether the tree contains any field at all.

    Checked before anything is copied or rewritten: most documents carry none, and they
    must cost nothing.
    """
    if root is None:
        return False
    return next(iter(root.iter(FLD_SIMPLE_TAG, FLD_CHAR_TAG)), None) is not None


def split_instruction(instruction: str) -> list[str]:
    """Split a field instruction into its tokens, respecting double quotes.

    Word quotes any argument containing a space, and a path or URL routinely does, so
    ``HYPERLINK "https://example.com/a b"`` is two tokens rather than three.
    """
    tokens: list[str] = []
    current: list[str] = []
    quoted = False
    for character in instruction:
        if character == '"':
            quoted = not quoted
            continue
        if character.isspace() and not quoted:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(character)
    if current:
        tokens.append("".join(current))
    return tokens


def hyperlink_target(instruction: str) -> str | None:
    r"""Return the URL a ``HYPERLINK`` instruction points at, or ``None``.

    Returns ``None`` for every other field type, and for the bookmark form
    (``HYPERLINK \\l "name"``) that targets a place inside the document rather than a
    URL -- that is a different kind of link, and guessing an anchor syntax for it would
    be worse than leaving the text plain.
    """
    tokens = split_instruction(instruction)
    if not tokens or tokens[0].upper() != "HYPERLINK":
        return None

    for token in tokens[1:]:
        if token.startswith("\\"):
            if token.lower() == "\\l":
                return None
            continue
        return token or None
    return None


class _Field:
    """One open field: what its instruction says so far, and what it displayed."""

    __slots__ = ("instruction", "in_result", "result_runs")

    def __init__(self) -> None:
        self.instruction: list[str] = []
        self.in_result = False
        self.result_runs: list[Any] = []


def _stamp(runs: list[Any], instruction: str) -> None:
    """Record on the result runs whatever their instruction still means."""
    target = hyperlink_target(instruction)
    if not target:
        return
    for run in runs:
        run.set(FIELD_TARGET, target)


def _drop(element: Any) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def resolve_fields(root: Any) -> int:
    """Rewrite ``root`` in place so fields read as the page prints them.

    The tree is mutated, so callers that do not own the document must copy first.
    Returns the number of fields resolved, which is what the caller logs.
    """
    if root is None:
        return 0
    return _resolve_fld_chars(root) + _resolve_fld_simples(root)


def _resolve_fld_chars(root: Any) -> int:
    """Resolve the ``begin``/``separate``/``end`` encoding.

    One document-order pass with a stack, because a field can span paragraphs and can
    contain another field. Runs are collected first and removed afterwards: dropping
    them mid-walk would mutate the tree being iterated.
    """
    stack: list[_Field] = []
    doomed: list[Any] = []
    resolved = 0

    for run in root.iter(RUN_TAG):
        marker = run.find(FLD_CHAR_TAG)
        if marker is not None:
            kind = marker.get(f"{W}fldCharType")
            if kind == "begin":
                stack.append(_Field())
            elif kind == "separate":
                if stack:
                    stack[-1].in_result = True
            elif kind == "end" and stack:
                field = stack.pop()
                # A field closed inside another field's instruction contributed to
                # that instruction, not to the page; its result goes with it.
                if stack and not stack[-1].in_result:
                    doomed.extend(field.result_runs)
                else:
                    _stamp(field.result_runs, "".join(field.instruction))
                resolved += 1
            # Every marker run is scaffolding, whatever it turned out to mark.
            doomed.append(run)
            continue

        if not stack:
            continue

        field = stack[-1]
        if field.in_result:
            field.result_runs.append(run)
        else:
            for instr in run.iterchildren(*INSTR_TAGS):
                field.instruction.append(instr.text or "")
            doomed.append(run)

    # An unbalanced `begin` leaves a frame open. Its instruction runs are already
    # doomed; its result runs stay, because that is what the page shows.
    for run in doomed:
        _drop(run)
    return resolved


def _resolve_fld_simples(root: Any) -> int:
    """Replace every ``w:fldSimple`` with the cached result it wraps."""
    resolved = 0
    for field in list(root.iter(FLD_SIMPLE_TAG)):
        parent = field.getparent()
        if parent is None:
            continue

        children = list(field)
        _stamp([child for child in children if child.tag == RUN_TAG], field.get(f"{W}instr") or "")

        index = parent.index(field)
        for offset, child in enumerate(children):
            parent.insert(index + offset, child)
        parent.remove(field)
        resolved += 1
    return resolved


def field_target(element: Any) -> str | None:
    """Return the link target a run inherited from its field, or ``None`` if it has none."""
    if element is None:
        return None
    return element.get(FIELD_TARGET)
