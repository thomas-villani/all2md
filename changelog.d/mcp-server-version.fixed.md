- **The MCP server reports all2md's version in its handshake.** `serverInfo.version`
  in the `initialize` response was fastmcp's own version (for example `3.4.2`), because the
  server never passed one. Clients and registry listings show this field. The `mcp`
  extra now requires `fastmcp>=2.9.0`, the first release that accepts a version, up from
  `>=2.0.0`.
