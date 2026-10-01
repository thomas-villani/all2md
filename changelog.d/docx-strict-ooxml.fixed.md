- **docx: Strict Open XML documents are read instead of rejected.** A file saved as
  "Strict Open XML Document" names its namespaces and relationship types under
  `http://purl.oclc.org/ooxml/` rather than `http://schemas.openxmlformats.org/`, so
  python-docx found no main document and the parser raised `MalformedFileError`. When
  an open fails, the parser now renames the Strict names to their Transitional
  equivalents in memory and reads the package again; the elements themselves are the
  same in both. A Transitional package never takes this path. The seven Strict files
  in LibreOffice's Writer regression corpus that Word opens now read, and match Word's
  text.
