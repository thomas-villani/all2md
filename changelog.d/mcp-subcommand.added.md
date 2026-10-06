- **`all2md mcp`** runs the MCP server, the same server and options as `all2md-mcp`.
  Clients that install servers from the MCP Registry can only launch a package's own
  executable (`uvx all2md@<version> <args>`), so the server must be reachable through
  `all2md` itself. A `server.json` at the repository root describes the registry entry:
  it installs the server with the same format extras as the `.mcpb` bundle, and the
  version bump keeps it in step with each release.
