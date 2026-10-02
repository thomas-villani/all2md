- **A Word, PowerPoint or Excel 97-2003 file is no longer reported as a broken
  Outlook message.** All four formats are OLE2 compound files with one shared
  signature, and the Outlook parser claimed that signature outright, so `all2md
  report.doc` failed with "Failed to parse MSG file: does not contain a properties
  stream". Detection now reads the names of the streams under the container's root
  (`WordDocument`, `PowerPoint Document`, `Workbook`, `__substg1.0_*`) with a small
  standard-library reader, `all2md.utils.cfb`, that seeks past the 1 KB detection
  sample to the directory. A message is still routed to the Outlook parser. A legacy
  Office file now fails with a `FormatError` that names its real format and suggests
  saving it as `.docx`, `.pptx` or `.xlsx`. Only the root's own children count, so a
  message carrying an embedded Word file stays a message. Reading these formats is
  not part of this change; the registry routes each kind to its own parser once one
  is registered.
