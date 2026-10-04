- **Word 97-2003 documents (`.doc`) are read, with the standard library.** The new `doc`
  parser reads the binary format directly: no Word, LibreOffice or extra package. It
  reads all the text, using the piece table (fast-saved files included, cp1252 and
  UTF-16 pieces, characters outside the BMP):
  - the body, with field results and `HYPERLINK` fields as links;
  - footnotes and endnotes, as footnote definitions referenced where their marks stand;
  - comments, with their author;
  - text boxes, after the paragraph that anchors them;
  - page headers and footers (`include_headers_footers`).

  Text deleted with tracked changes is hidden, as the DOCX parser's default policy hides
  it. Title, author, keywords and dates come from the summary information. Encrypted
  files raise `PasswordProtectedError`, and Word 6/95 files raise a `FormatError` that
  says so. On 191 files from LibreOffice's DOCX regression corpus saved as `.doc` by
  Word, the words read match those the DOCX parser reads from the originals except 99 of
  9,906. Those 99 are equations, generated list numbers, and footnotes the `.docx` never
  referenced. Formatting is not read yet: headings, tables and lists come back as
  paragraphs, a table's cells one paragraph each.
- **Detection routes CFB containers by their streams before their extension**, so an
  Outlook message named `report.doc` still reads as a message. **MIME-type matches are
  now checked by content, as extension matches are**, so a `.doc` that holds RTF or HTML
  goes to that parser.
