- **The MCP `read_document_as_markdown` tool returns Markdown again under fastmcp 3.**
  fastmcp 3 derived an output schema from the tool's `-> list` annotation, so the
  Markdown reached the client as a JSON-encoded list (`["# Title\n\n..."]`), and with
  `include_images` the call failed output validation. The tool now declares no output
  schema and returns MCP content blocks itself: the Markdown as a text block, then an
  image block per image. The `[mcp]` extra now needs fastmcp 2.11.3 or later, the
  oldest release that installs alongside current `mcp` and `pydantic`.
