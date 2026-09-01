- **DOCX: a document left with Track Changes on no longer loses its insertions.** Every
  tracked insertion was dropped silently, which is neither accepting the revisions nor
  rejecting them — it is a third behaviour that loses text present in the document under
  *every* review state. A paragraph made entirely of one insertion vanished without
  trace; a substituted word left a double space behind, so `The quick crimson fox jumps.`
  converted to `The quick  fox jumps.` There was no warning and the output looked
  plausible, which is the worst combination: the ordinary state of anything under review
  in a legal, academic or business workflow converted to quiet nonsense.

  The cause was an unexamined library boundary rather than a decision anyone made.
  `python-docx` yields only `w:r` and `w:hyperlink` elements that are *direct children*
  of `w:p`, so a run inside `w:ins` is a grandchild and invisible, and a paragraph whose
  whole content sits in one `w:ins` reports zero runs and empty text; deletions vanish
  separately because their text lives in `w:delText`, not `w:t`. Anything built on
  `Paragraph.runs` or `Paragraph.text` inherited that silently.

  Revision markup is now resolved away on the element tree *before* anything reads the
  document, so every reader below — paragraph text, run iteration, list and heading
  detection, image discovery, table cells — sees an ordinary document and needs to know
  nothing about revisions. Resolving at the tree rather than at each reader is
  deliberate: patching readers one at a time would have left the next one to be found by
  a user. Resolution is a policy, so it is an option, `DocxOptions.revisions` /
  `--docx-revisions`:

  - **`accept`** (the default) — insertions in, deletions out: the document as approved,
    and what Word shows a reader by default.
  - **`reject`** — insertions out, deletions in: the original text before review.
  - **`mark`** — both kept, with deletions rendered as `Strikethrough` and every revised
    node carrying a `revision` entry in its `metadata` (type, author, date, id). This
    reuses the existing AST rather than adding a revision node type that every renderer
    would have to learn; the cost, accepted knowingly, is that strikethrough is a GFM
    extension and so `mark` renders fully only in flavours that have it.

  Move revisions (`w:moveTo`/`w:moveFrom`) are treated as the insertion and deletion
  halves they are. Revision marks on the *paragraph mark* are resolved too, and merge the
  paragraphs they join: deleting a pilcrow joins two paragraphs, and resolving that away
  without merging would leave a paragraph break that exists in neither the accepted nor
  the rejected document. Deleted and inserted table **rows** are dropped by the policy
  that resolves them away, rather than leaving a phantom empty row; and `reject` restores
  the previous properties a `w:rPrChange`/`w:pPrChange` records, so a paragraph restyled
  to a heading under review stops being a heading when the review is rejected. Footnote
  and endnote parts are resolved with the same policy. A `Document` handed to the parser
  by a caller is copied before any of this, never edited underneath them, and a document
  with no revision markup at all — nearly every document — is not touched or copied.
  ([#480](https://github.com/thomas-villani/all2md/issues/480))
