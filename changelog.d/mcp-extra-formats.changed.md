- **`pip install "all2md[mcp]"` gives a server that reads documents.** The `mcp` extra
  used to install only FastMCP, and core all2md has no format parsers. A server
  installed with it alone read plain text and nothing else, not even Markdown. Its
  default search mode also failed, because `rank-bm25` was missing. The extra now
  includes the `pdf`, `pdf_render`, `docx`, `html`, `xlsx`, `pptx`, `epub`, `rst`,
  `markdown` and `odf` extras and `rank-bm25`: the set the `.mcpb` bundle already
  installed, which now just says `all2md[mcp]`, as the MCP Registry entry does. This
  brings in PyMuPDF, which is AGPL-licensed, as `all2md[pdf]` and `all2md[all]` already
  do. The noncommercial `pymupdf-layout` stays out.
