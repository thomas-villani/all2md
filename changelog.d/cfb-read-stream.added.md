- **`all2md.utils.cfb.CfbReader`: read the streams of an OLE2 (CFB) container with the
  standard library.** The groundwork for reading Word 97-2003 `.doc` and PowerPoint
  97-2003 `.ppt` files without a new dependency. It lists every stream and storage and
  reads a stream whole, from regular sectors or the mini stream, in version 3 (512-byte)
  and version 4 (4096-byte) containers, DIFAT sectors included. Every chain, size and
  index comes from the file, so each is checked first: a chain that loops, leaves the
  FAT, ends early or points past the end of the file, and a stream claiming more bytes
  than the file holds, raise `MalformedFileError`, and a file cut short never reads back
  as zero-padded data. Format detection (`sniff_cfb_kind`) now uses the same reader. On
  Word, PowerPoint and Outlook files made over COM, every stream reads byte for byte as
  olefile reads it, and 3,000 mutated copies raise nothing but `MalformedFileError`.
