# all2md MCPB bundle

This directory packages all2md's built-in MCP server as an
[MCPB bundle](https://github.com/modelcontextprotocol/mcpb) (`.mcpb`) for
**one-click install** in Claude Desktop (Settings → Extensions).

It is **not** a new server. It is a thin packaging layer around the existing
`all2md-mcp` console script (`all2md.mcp.server:main`):

- `manifest.json` — bundle metadata, the `uv` server config, and the
  install-time `user_config` (workspace folder + tool toggles).
- `pyproject.toml` — declares the real published package as the dependency
  (`all2md[...]`). The `uv` runtime resolves and installs it on the user's
  machine at install time, so nothing is bundled in the `.mcpb`.
- `src/server.py` — a stable entry file that just imports and calls `main()`.

## Configuration

All server settings are passed via environment variables (set by the MCPB host
from `user_config`), not CLI flags. The install dialog asks the user for:

| Setting | Env var | Default |
| --- | --- | --- |
| Workspace folder (read + write allowlist) | `ALL2MD_MCP_ALLOWED_READ_DIRS` / `ALL2MD_MCP_ALLOWED_WRITE_DIRS` | Documents |
| Allow writing/rendering documents | `ALL2MD_MCP_ENABLE_FROM_MD` | on |
| Allow in-place document editing | `ALL2MD_MCP_ENABLE_DOC_EDIT` | on |
| Disable network access | `ALL2MD_DISABLE_NETWORK` | on |

Reads and writes are confined to the chosen workspace folder; files outside it
are rejected by the server's path validation.

## Dependency extras

The bundle installs `all2md[mcp,pdf,pdf_render,docx,html,xlsx,pptx,epub,rst,markdown,odf]`.
This is the common-document subset **plus the render extras** so that every
`save_document_from_markdown` target (PDF, DOCX, PPTX, EPUB, HTML, RST) works
out of the box — a leaner subset would leave some output formats silently
broken. `pdf_layout` is deliberately excluded (Polyform Noncommercial license,
as it is from `all2md[all]`). To bundle every format instead, replace the
extras list with `all2md[all]` and re-pack.

It also depends on `rank-bm25` directly so the `search_documents` tool's default
keyword (BM25) mode works out of the box. The full `search` extra is *not* used:
it additionally pulls `faiss-cpu` and `sentence-transformers` for vector/hybrid
search, which the MCP server rejects, so they would only bloat the bundle.

## Rebuilding

```bash
npm install -g @anthropic-ai/mcpb   # one-time
mcpb validate manifest.json
mcpb pack                            # produces all2md.mcpb
```

CI rebuilds and attaches `all2md.mcpb` to every GitHub release
(see `.github/workflows/ci.yml`).

## Versioning

The `version` in `manifest.json` and `pyproject.toml` (and the `>=` dependency
pin) are kept in sync with the main package by the root `pyproject.toml`'s
`[tool.bumpversion]` config. **Do not hand-edit those version strings** — bump
the package version and they update together.
