- **`all2md serve` and `all2md edit` no longer warn about `attachment_mode` on Markdown
  files.** Both force base64 images so the page or editor shows them, and formats with no
  attachments (Markdown, plain text) drop the option. The drop printed "Keyword arguments
  were ignored: ['attachment_mode']" for an option the user never passed. The forced value
  is now marked as all2md's own, as `--package` and the MCP server already do.
