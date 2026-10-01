- **docx: a package that names a part it does not contain is read instead of
  rejected.** python-docx loads every part the package's relationships reach as it
  opens the file, so one relationship to a missing footer, font table, numbering part
  or image -- or an internal bookmark written as if it were a file -- failed the whole
  document with `MalformedFileError`. Word opens these files and shows what is there.
  When an open fails, the parser now rebuilds the package in memory without the
  relationships to missing parts, logs a warning naming them, and reads it again; the
  missing part simply reads as absent. A sound package never takes this path, and one
  the repair cannot help still reports its original error. Sixteen files in
  LibreOffice's Writer regression corpus that failed now read.
