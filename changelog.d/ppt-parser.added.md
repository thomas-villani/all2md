- **PowerPoint 97-2003 presentations (`.ppt`, `.pps`, `.pot`) are read, with the standard
  library.** The new `ppt` parser reads the binary format directly: no PowerPoint,
  LibreOffice or extra package. It follows the edit chain, so an incrementally saved file
  reads as last saved, and reads each slide's text boxes in drawing order, including the
  placeholder text older versions of PowerPoint keep in the slide list:
  - the title, as a level 2 heading;
  - body placeholders, as bullet lists nested by indent level, and other text as paragraphs;
  - hyperlinks, as links, and slide number fields, as the slide's number;
  - speaker notes and review comments.

  The options and their defaults are the PPTX parser's (`PptOptions`). Title, author and
  dates come from the summary information. Encrypted files raise `PasswordProtectedError`.
  On 416 of LibreOffice's Impress test decks saved as `.ppt` by PowerPoint, the words
  read match those the PPTX parser reads from the originals except 684 of 4,810. Of
  those, 653 are not in the `.ppt` at all: PowerPoint saved charts as embedded objects and
  WordArt and multi-column text as pictures. Character formatting, numbered lists, tables
  and pictures are not read yet.
- **The Outlook parser's error for a `.doc` or `.ppt` now names the format that reads it**,
  instead of saying all2md cannot read the file.
