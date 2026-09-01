- **DOCX: content controls no longer swallow the content they wrap.** A content control
  (`w:sdt`) is how Word marks a fill-in region — an author name on a title page, a date
  picker, a rich-text block in a corporate template — and it is also what Word writes
  around a table of contents or a bibliography. The control is a wrapper: the real content
  sits one level down inside `w:sdtContent`, and every reader in `python-docx` looks only
  at direct children, so that one extra level made content disappear in five separate
  places at once. Measured, each one a total and silent loss: a controlled paragraph never
  reached the output; an inline control's text dropped out of the middle of its sentence;
  a controlled table vanished whole; a controlled table row vanished; and a controlled
  paragraph inside a cell left the cell reading empty.

  Rather than teach five readers about `w:sdtContent` and leave a sixth for a user to
  find, the wrapper is now removed on the element tree before anything reads the document
  — the same treatment tracked changes already get, and for the same reason. Nesting
  needs no special case, and a document that carries no controls is not touched or copied
  at all.

  Placeholder text is kept. An unfilled control holds Word's own boilerplate ("Click or
  tap here to enter text."), and while it is tempting to drop it, that text is what the
  page prints and a template's empty fields are much of what makes the template worth
  reading. Suppressing them would trade one silent loss for another.
