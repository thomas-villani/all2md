- **The MCP setup docs install a server that can read documents.** The README and the
  MCP guide said `pip install "all2md[mcp]"`, but that extra adds only the server. With
  it alone, the server reads plain text and nothing else, not even Markdown. The docs
  now recommend `all2md[all]`, or `[mcp]` combined with the format extras you need.
