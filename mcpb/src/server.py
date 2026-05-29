"""MCPB launcher for the all2md MCP server (uv runtime).

Thin wrapper over all2md's ``all2md-mcp`` entry point
(``all2md.mcp.server:main``). It exists only to give the MCPB ``uv`` runtime a
stable entry file. All configuration is supplied via environment variables set
by the MCPB host from ``user_config`` (workspace folder, tool toggles, network
control) — see ``manifest.json``.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

from all2md.mcp.server import main

if __name__ == "__main__":
    raise SystemExit(main())
