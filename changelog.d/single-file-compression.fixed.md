- **A single compressed file now converts as what it holds.** `ls.1.gz`, `data.csv.gz`,
  `notes.md.gz`, `page.html.bz2` and `x.json.xz` all failed or came out as garbage.
  The archive parser took every gzip, bzip2 and xz signature to be a compressed tar
  ("Invalid TAR archive"). Worse, detection trusted the MIME type of the name inside
  the compression, so `notes.md.gz` went to the Markdown parser, `report.txt.gz` to the
  DokuWiki parser and `x.json.xz` into a code block, each reading compressed bytes as
  text. Detection now ignores a MIME type that comes with a compression encoding, and
  the archive parser checks the first decompressed block: a tar is read as before,
  anything else is decompressed and detected as `ls.1`, `data.csv` and so on. With no
  outer name it uses the name stored in the gzip header. Decompression runs under the
  archive limits (1 GB, and a 100:1 ratio once past 10 MB). Concatenated members are
  joined as `gzip -d` does. A truncated, corrupt or doubly compressed file fails with a
  `MalformedFileError`.
