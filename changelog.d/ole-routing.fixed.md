- **A Word, PowerPoint or Excel 97-2003 file is no longer reported as a broken
  Outlook message.** All four formats are OLE2 compound files with one shared
  signature, and the Outlook parser claimed that signature outright, so `all2md
  report.doc` failed with "Failed to parse MSG file: does not contain a properties
  stream". Detection now reads the names of the streams under the container's root
  (`WordDocument`, `PowerPoint Document`, `Workbook`, `__substg1.0_*`) with a small
  standard-library reader, `all2md.utils.cfb`, that seeks past the 1 KB detection
  sample to the directory. A message is still routed to the Outlook parser, a `.doc`
  to the new `doc` parser and a `.ppt` to the new `ppt` parser (both below). An Excel
  97-2003 workbook, which nothing reads yet, fails with a `FormatError` that names its
  format and suggests saving it as `.xlsx`. Only the root's own children count, so a
  message carrying an embedded Word file stays a message.
