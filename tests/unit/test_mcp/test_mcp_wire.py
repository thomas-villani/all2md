"""The tools as an MCP client sees them, through fastmcp's in-memory transport.

The implementation tests call the tool functions directly, so they could not see
that fastmcp 3 derived an output schema from ``read_document_as_markdown``'s
``-> list`` annotation: the Markdown went out as a JSON-encoded list, and with
``include_images`` the call failed output validation.
"""

from __future__ import annotations

import asyncio
import base64

import pytest

pytest.importorskip("fastmcp")

from fastmcp import Client  # noqa: E402

from all2md.mcp.config import MCPConfig  # noqa: E402
from all2md.mcp.document_tools import edit_document_impl  # noqa: E402
from all2md.mcp.query_tools import (  # noqa: E402
    diff_documents_impl,
    get_document_outline_impl,
    list_workspace_files_impl,
    search_documents_impl,
)
from all2md.mcp.server import create_server  # noqa: E402
from all2md.mcp.tools import read_document_as_markdown_impl, save_document_from_markdown_impl  # noqa: E402

# A 1x1 transparent PNG.
PNG = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d4944415478da63f80f00000101000518d84e0000000049454e44ae426082"
    )
).decode()


def call_read(config: MCPConfig, **arguments):
    server = create_server(
        config,
        read_document_as_markdown_impl,
        save_document_from_markdown_impl,
        edit_document_impl,
        search_documents_impl,
        diff_documents_impl,
        get_document_outline_impl,
        list_workspace_files_impl,
    )

    async def run():
        async with Client(server) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            result = await client.call_tool("read_document_as_markdown", arguments, raise_on_error=False)
            return tools["read_document_as_markdown"], result

    return asyncio.run(run())


@pytest.mark.unit
class TestReadToolOnTheWire:
    def test_markdown_is_a_text_block_not_json(self):
        tool, result = call_read(MCPConfig(), source="<h1>Title</h1><p>Body text.</p>", format_hint="html")
        assert tool.outputSchema is None
        assert not result.is_error
        (block,) = result.content
        assert block.type == "text"
        assert block.text.startswith("# Title")
        assert "Body text." in block.text

    def test_images_are_image_blocks(self):
        html = f'<h1>Pic</h1><p><img src="data:image/png;base64,{PNG}" alt="dot"></p>'
        _, result = call_read(MCPConfig(include_images=True), source=html, format_hint="html")
        assert not result.is_error, result.content
        assert result.content[0].type == "text"
        assert result.content[0].text.startswith("# Pic")
        assert [block.type for block in result.content[1:]] == ["image"]
        assert result.content[1].mimeType == "image/png"
