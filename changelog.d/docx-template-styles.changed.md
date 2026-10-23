- **A reference template's styles are used, not written over.** With `template_path`,
  the DOCX renderer still gave code blocks and inline code their font, size and gray
  shading as direct formatting, which overrides any style, so a template's code styles
  never showed. Code is now styled only through its styles: the template's `CodeBlock`,
  or pandoc's `Source Code`, for blocks, and `Verbatim Char` inline; the `CodeBlock`
  style created for a document without one carries the font and shading itself. A
  template without Word's `Quote` style uses pandoc's `Block Text`, and one without the
  requested table style uses its `Table` (pandoc's) or `Table Grid` instead of leaving
  the table bare, so a pandoc reference document works as a template. `code_font` and
  `code_font_size` now default to None, like `default_font`: Courier New 10 for a blank
  document, the template's own otherwise, and a font named explicitly is set on the
  template's code styles. The DOCX parser reads `Block Text` paragraphs as quotes.
- **Links in DOCX output look like links.** They were written with Word's `Hyperlink`
  character style, which the blank document does not define, so Word drew them as plain
  black text. The style is now created when missing, blue and underlined as Word's own;
  a template's own `Hyperlink` style is kept.
