- **DOCX: `HYPERLINK` fields become links, and `SEQ` captions keep their number.** A Word
  *field* stores an instruction beside the result Word last computed, and the result is
  what the page prints — so nothing here evaluates anything, it reads the half Word
  displays and drops the half it does not. Two encodings, both of which hid something:

  - `w:fldSimple` keeps its result in **child runs**, and `Paragraph.runs` yields only
    direct children, so the result was a grandchild and invisible. A caption printed
    `Figure :` with the number missing.
  - `w:fldChar` marks the instruction with `begin`/`separate`/`end` runs. Those results
    were visible, but the instruction's meaning was not, so a `HYPERLINK` field printed
    its target as bare prose where the `w:hyperlink` element would have produced a link.

  Fields are resolved on the element tree before any reader sees the document, the same
  treatment tracked changes and content controls get. A field is **not paragraph-scoped**
  — Word routinely opens one in one paragraph and closes it in the next — so the walk goes
  through the whole tree in document order, and it keeps a stack because fields nest: a
  result computed inside another field's *instruction* is dropped with it rather than
  leaking into the text. A field Word never computed shows nothing, which is what the page
  shows.

  `HYPERLINK \l "bookmark"` is deliberately left as plain text: it targets a place inside
  the document rather than a URL, and guessing an anchor syntax for it would be worse.
