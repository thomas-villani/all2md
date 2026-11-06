- **Breaking: a document can no longer copy files from your machine into its output
  (GHSA-r22j-w6gv-233x).** Rendering to DOCX, PPTX, PDF, ODT, ODP, EPUB or an arXiv
  bundle used to read any local path an image pointed at, from any input format and
  even under `--safe-mode`. ODT, ODP, EPUB and arXiv took any file, not only images,
  so a Markdown or HTML file you did not write could embed your secrets in a document
  you then shared. Local images now follow the same `local_files` policy as HTML
  input: off by default, with a warning naming the flag when one is left out. To embed
  the images of a document you trust, add `--<format>-renderer-local-files-allow-local-files`
  (`local_files=LocalFileAccessOptions(allow_local_files=True)`), optionally with an
  allowlist. Even then, the file must be an image under `max_asset_size_bytes`, and a
  relative path resolves against the source document's folder. Network paths such as
  `\\host\share` are now always refused, here and for HTML `file://` URLs, because
  opening one makes Windows connect to the host. `generate-site` copies images from
  each source file's own folder only. Thanks to santhreal for the report.
