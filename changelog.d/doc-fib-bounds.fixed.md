- **A `.doc` whose FIB counts run past the end of the stream raises `MalformedFileError`**,
  not a raw `struct.error`. The counts of the FIB's three arrays come from the file, and the
  `.doc` parser's mutation test found a damaged `csw` that pointed past the end. A further
  40,000 random mutations of builder-made and Word-saved `.doc` and `.ppt` files raised only
  all2md errors.
