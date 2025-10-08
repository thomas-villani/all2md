"""MCP server for all2md document conversion.

This package provides a Model Context Protocol (MCP) server that exposes
all2md's document conversion functionality to LLMs like Claude.

The server runs over stdio transport and provides two main tools:
- convert_to_markdown: Convert documents to Markdown
- render_from_markdown: Render Markdown to other formats

Security features include:
- Path allowlists for read/write operations
- Server-level attachment mode configuration
- Network access control
- Symlink resolution and path traversal prevention

Usage
-----
Run the server from command line:
    $ all2md-mcp

With configuration:
    $ all2md-mcp --read-dirs "/home/user/docs" --write-dirs "/home/user/output"

Or use environment variables:
    $ export ALL2MD_MCP_ALLOWED_READ_DIRS="/home/user/docs"
    $ export ALL2MD_MCP_ALLOWED_WRITE_DIRS="/home/user/output"
    $ all2md-mcp

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

from all2md.mcp.config import MCPConfig
from all2md.mcp.security import MCPSecurityError
from all2md.mcp.server import main

__all__ = [
    "main",
    "MCPConfig",
    "MCPSecurityError",
]
