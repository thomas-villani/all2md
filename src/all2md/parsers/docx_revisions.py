#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/docx_revisions.py
"""Resolve Word tracked changes before anything else reads the document.

A document left with Track Changes on is the ordinary state of anything under
review, and Word stores those edits *structurally*: inserted content is wrapped in
``w:ins``, deleted content in ``w:del`` with its text moved from ``w:t`` to
``w:delText``. ``python-docx`` sees neither -- ``Paragraph.runs`` and
``iter_inner_content`` yield only direct ``w:r``/``w:hyperlink`` children of ``w:p``,
so a run inside ``w:ins`` is a grandchild and invisible, and a paragraph whose whole
content is one insertion reports no runs and empty text. Everything built on
``paragraph.runs`` or ``paragraph.text`` inherits that silently, which is how
insertions came to be dropped without a warning (#480).

The fix is deliberately **not** a special case threaded through the parser. Revision
markup touches paragraph text, run iteration, list detection, heading detection,
image discovery and table cells alike; patching each reader would leave the next one
to be found by a user. Instead the revision markup is *resolved away* on the element
tree first, so every downstream reader sees an ordinary document with the policy
already applied and needs to know nothing about revisions at all.

Resolution is a policy, not a single right answer, so it is an option:

``accept``
    Insertions in, deletions out -- the document as approved, and what Word shows a
    reader by default. The default here too.
``reject``
    Insertions out, deletions in -- the original text before review.
``mark``
    Both kept. Deletions are marked with :class:`~all2md.ast.Strikethrough` and every
    run carries the revision's type, author and date on its node ``metadata``.
    Strikethrough is a GFM extension, so this resolution renders fully only in
    flavours that have it; that limitation is accepted knowingly in exchange for
    reusing the existing AST rather than adding a node type that every renderer
    would then have to learn.

Move revisions (``w:moveTo``/``w:moveFrom``) are treated as the insertion and
deletion halves they are.
"""

from __future__ import annotations

from typing import Any, Iterable

WORDPROCESSING_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORDPROCESSING_NS}}}"

#: Private namespace used to stamp resolved runs in ``mark`` mode. It never has to
#: survive a save -- resolution runs on a copy the parser owns -- but a namespaced
#: attribute keeps the tree legal XML either way.
REVISION_NS = "https://all2md.dev/ns/revision"
REVISION_TYPE = f"{{{REVISION_NS}}}type"
REVISION_AUTHOR = f"{{{REVISION_NS}}}author"
REVISION_DATE = f"{{{REVISION_NS}}}date"
REVISION_ID = f"{{{REVISION_NS}}}id"

INSERT_TAGS = (f"{W}ins", f"{W}moveTo")
DELETE_TAGS = (f"{W}del", f"{W}moveFrom")
MARK_TAGS = INSERT_TAGS + DELETE_TAGS

#: Records of a *formatting* change, as opposed to a content change. They sit inside
#: the property element they amend and carry the previous properties.
CHANGE_TAGS = (
    f"{W}rPrChange",
    f"{W}pPrChange",
    f"{W}tblPrChange",
    f"{W}trPrChange",
    f"{W}tcPrChange",
    f"{W}sectPrChange",
)

#: Property containers whose ``w:ins``/``w:del`` children mark the *paragraph mark* or
#: the *table row*, not a span of content. They are handled separately.
PROPERTY_PARENTS = (f"{W}rPr", f"{W}trPr", f"{W}tcPr")

_STAMPED_TAGS = (f"{W}r", f"{W}hyperlink")


def document_has_revisions(root: Any) -> bool:
    """Report whether the tree contains any revision markup at all.

    Checked before anything is copied or rewritten: the overwhelming majority of
    documents carry no revisions, and they must cost nothing.
    """
    if root is None:
        return False
    return next(iter(root.iter(*MARK_TAGS, *CHANGE_TAGS)), None) is not None


def run_revision(element: Any) -> dict[str, str] | None:
    """Return the revision a run belongs to, or ``None`` when it is ordinary content.

    Only ``mark`` resolution stamps runs, so this is ``None`` everywhere else.
    """
    if element is None:
        return None
    revision_type = element.get(REVISION_TYPE)
    if not revision_type:
        return None
    facts = {"type": revision_type}
    for key, attribute in (("author", REVISION_AUTHOR), ("date", REVISION_DATE), ("id", REVISION_ID)):
        value = element.get(attribute)
        if value:
            facts[key] = value
    return facts


def resolve_revisions(root: Any, policy: str) -> None:
    """Rewrite ``root`` in place so it reads as ``policy`` says it should.

    The tree is mutated, so callers that do not own the document must copy first.
    """
    if root is None or policy not in ("accept", "reject", "mark"):
        return
    _resolve_property_changes(root, policy)
    _resolve_rows(root, policy)
    _resolve_content(root, policy)
    _resolve_paragraph_marks(root, policy)


def _keeps(policy: str, inserted: bool) -> bool:
    """Whether content of this revision kind survives under ``policy``."""
    if policy == "mark":
        return True
    return inserted if policy == "accept" else not inserted


def _unwrap(element: Any) -> None:
    """Replace an element with its children, in place."""
    parent = element.getparent()
    if parent is None:
        return
    index = parent.index(element)
    for offset, child in enumerate(list(element)):
        parent.insert(index + offset, child)
    parent.remove(element)


def _restore_deleted_text(container: Any) -> None:
    """Turn deleted text back into ordinary text.

    Word does not merely wrap a deletion; it renames the text element, so a kept
    deletion whose ``w:delText`` was left alone would still read as empty.
    """
    for element in container.iter(f"{W}delText"):
        element.tag = f"{W}t"
    for element in container.iter(f"{W}delInstrText"):
        element.tag = f"{W}instrText"


def _stamp(container: Any, revision_type: str) -> None:
    """Record which revision a kept run came from, for ``mark`` resolution."""
    facts = {
        REVISION_TYPE: revision_type,
        REVISION_AUTHOR: container.get(f"{W}author"),
        REVISION_DATE: container.get(f"{W}date"),
        REVISION_ID: container.get(f"{W}id"),
    }
    for element in container.iter(*_STAMPED_TAGS):
        # A nested revision (the deleted half of a move, say) has already been
        # stamped by its own container; the innermost claim is the true one.
        if element.get(REVISION_TYPE):
            continue
        for attribute, value in facts.items():
            if value:
                element.set(attribute, value)


def _resolve_content(parent: Any, policy: str) -> None:
    """Apply the policy to every content-level ``w:ins``/``w:del`` under ``parent``.

    Written as a descent rather than a flat ``iter`` sweep because revisions nest --
    the two halves of a move, or an insertion later deleted -- and an outer container
    that is removed must take its children with it rather than have them processed
    again in a detached tree.
    """
    for child in list(parent):
        if child.tag in MARK_TAGS and parent.tag not in PROPERTY_PARENTS:
            inserted = child.tag in INSERT_TAGS
            if not _keeps(policy, inserted):
                parent.remove(child)
                continue
            if not inserted:
                _restore_deleted_text(child)
            if policy == "mark":
                _stamp(child, "insert" if inserted else "delete")
            _resolve_content(child, policy)
            _unwrap(child)
        else:
            _resolve_content(child, policy)


def _resolve_rows(root: Any, policy: str) -> None:
    """Drop table rows the policy resolves away.

    A deleted row's cells are marked ``w:del`` individually, so accepting the
    deletion without dropping the row would leave a phantom empty row behind.
    """
    if policy == "mark":
        return
    for row in list(root.iter(f"{W}tr")):
        row_properties = row.find(f"{W}trPr")
        if row_properties is None:
            continue
        inserted = _has_any(row_properties, INSERT_TAGS)
        deleted = _has_any(row_properties, DELETE_TAGS)
        if (deleted and policy == "accept") or (inserted and policy == "reject"):
            parent = row.getparent()
            if parent is not None:
                parent.remove(row)


def _has_any(element: Any, tags: Iterable[str]) -> bool:
    return any(element.find(tag) is not None for tag in tags)


def _resolve_paragraph_marks(root: Any, policy: str) -> None:
    """Merge paragraphs whose paragraph mark the policy resolves away.

    A ``w:ins``/``w:del`` inside ``w:pPr/w:rPr`` marks the *pilcrow*: inserting one
    split a paragraph in two, deleting one joined it to the next. Resolving that
    away without merging would leave the split in place -- a paragraph break that
    exists in neither the accepted nor the rejected document.

    Paragraphs are walked backwards so that a run of consecutive merges collapses
    correctly: each paragraph is merged into a successor that is already final.
    """
    paragraphs = list(root.iter(f"{W}p"))
    for paragraph in reversed(paragraphs):
        properties = paragraph.find(f"{W}pPr")
        if properties is None:
            continue
        mark_properties = properties.find(f"{W}rPr")
        if mark_properties is None:
            continue
        inserted = _has_any(mark_properties, INSERT_TAGS)
        deleted = _has_any(mark_properties, DELETE_TAGS)
        if not (inserted or deleted) or policy == "mark":
            continue
        for tag in MARK_TAGS:
            for record in mark_properties.findall(tag):
                mark_properties.remove(record)
        vanishes = deleted if policy == "accept" else inserted
        if vanishes:
            _merge_into_next(paragraph)


def _merge_into_next(paragraph: Any) -> None:
    """Fold a paragraph's content into the paragraph that follows it.

    The following paragraph's mark survives the merge, so its properties are the
    merged paragraph's properties -- which is why the content moves forwards into it
    rather than the other way around. A paragraph with no immediate paragraph
    sibling (the last in a cell, or one followed by a table) is left alone: there is
    nothing to merge into and dropping it would lose text.
    """
    parent = paragraph.getparent()
    if parent is None:
        return
    index = parent.index(paragraph)
    if index + 1 >= len(parent):
        return
    following = parent[index + 1]
    if following.tag != f"{W}p":
        return

    following_properties = following.find(f"{W}pPr")
    at = following.index(following_properties) + 1 if following_properties is not None else 0
    content = [child for child in paragraph if child.tag != f"{W}pPr"]
    for offset, child in enumerate(content):
        following.insert(at + offset, child)
    parent.remove(paragraph)


def _resolve_property_changes(root: Any, policy: str) -> None:
    """Resolve records of a *formatting* change.

    ``accept`` and ``mark`` simply drop the record -- the current properties already
    are the accepted ones. ``reject`` puts the previous properties back, which is the
    difference between rejecting a review and merely un-marking it: a paragraph
    restyled to a heading under review must stop being a heading.
    """
    for change in list(root.iter(*CHANGE_TAGS)):
        parent = change.getparent()
        if parent is None:
            continue
        if policy == "reject" and change.tag in (f"{W}rPrChange", f"{W}pPrChange"):
            _restore_properties(parent, change)
        parent.remove(change)


def _restore_properties(properties: Any, change: Any) -> None:
    """Swap a property element's contents for the previous ones the record holds.

    The revision records nested inside (the paragraph mark's own ``w:ins``/``w:del``,
    and the ``w:rPr`` holding them) are content, not formatting, and are kept so the
    paragraph-mark pass still sees them.
    """
    previous = change.find(properties.tag)
    keep = [child for child in properties if child.tag in MARK_TAGS or child.tag == f"{W}rPr"]
    for child in list(properties):
        if child is not change and child not in keep:
            properties.remove(child)
    if previous is None:
        return
    for offset, child in enumerate(list(previous)):
        properties.insert(offset, child)
