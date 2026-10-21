- **Markdown footnotes become Word footnotes, and task items keep their boxes, in DOCX
  output.** The DOCX renderer wrote a footnote reference as superscript `[1]` text and its
  definition as a `[1]: ` paragraph, and dropped a task item's box, so both were lost on
  the way through Word and back. A reference with a definition is now a real Word
  footnote: a `word/footnotes.xml` part with Word's separators and its "footnote text" and
  "footnote reference" styles, numbered by Word and set at the foot of the page. The note's
  content goes through the same rendering as the body, so its formatting, links (related
  from the footnotes part, where Word looks for them) and lists survive, and a template
  that brings its own footnotes keeps them and numbers after them. A label referred to
  twice gets a note at each reference; a reference with no definition, one inside a note
  (Word has no notes within notes) and a definition nothing refers to stay text, as before.
  A task item opens with the box Word's check box shows, ☐ or ☒, and the DOCX parser
  reads a list item that opens with ☐, ☑ or ☒ and a space back as a task item, which also
  reads Word's own check box content controls as tasks. Real check box content controls,
  which can be ticked in Word, are not written yet.
  ([#621](https://github.com/thomas-villani/all2md/issues/621))
