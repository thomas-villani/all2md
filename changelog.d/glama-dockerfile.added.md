- **A `Dockerfile` for the MCP server, and a `glama.json` claiming the Glama listing.**
  The image builds `all2md-mcp` from the checkout with `uv sync --frozen --extra mcp`,
  runs as a non-root user, and serves stdio from `/workspace`, which is the default
  read/write allowlist; mount the folder the server should see there. `glama.json`
  names the maintainer so the [Glama](https://glama.ai/mcp/servers) listing can be
  claimed and run from the image. The image is not published to a registry.
