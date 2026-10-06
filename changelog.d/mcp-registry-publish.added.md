- **all2md is listed in the [MCP Registry](https://registry.modelcontextprotocol.io/)**
  as `io.github.thomas-villani/all2md`, and each release updates the listing. A release
  job publishes `server.json` after the PyPI upload. It first waits for PyPI to serve the
  new version with the README's ownership marker, which the registry checks. The entry
  offers two ways to install: the PyPI package through `uvx`, and the `.mcpb` bundle
  attached to the GitHub release, with its SHA-256 checksum. Releases already in the
  registry, and older releases that have no `server.json`, are skipped rather than
  failed.
