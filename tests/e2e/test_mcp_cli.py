"""End-to-end tests for the ``all2md mcp`` subcommand.

MCP registry clients launch a PyPI server as ``uvx all2md@<version> <args>``: the
executable is always the package's own, so the server must be reachable as
``all2md mcp``. These tests run that command as a subprocess and speak JSON-RPC
to it over stdio, the way a client does.
"""

import json
import queue
import subprocess
import sys
import threading

import pytest

from all2md import __version__

pytest.importorskip("fastmcp")

HANDSHAKE_TIMEOUT = 60.0


def _start_server(*args: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "all2md", "mcp", *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )


def _line_reader(stream) -> queue.Queue:
    lines: queue.Queue = queue.Queue()

    def pump() -> None:
        for line in stream:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    return lines


def _send(proc: subprocess.Popen, message: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _receive(lines: queue.Queue, request_id: int) -> dict:
    """Return the response to ``request_id``; every stdout line must be JSON-RPC."""
    while True:
        line = lines.get(timeout=HANDSHAKE_TIMEOUT)
        assert line is not None, "server closed stdout before responding"
        message = json.loads(line)  # anything else on stdout corrupts the protocol
        if message.get("id") == request_id:
            return message


@pytest.mark.e2e
@pytest.mark.cli
class TestMcpSubcommand:
    """``all2md mcp`` serves the same MCP server as ``all2md-mcp``."""

    def test_completes_handshake_and_lists_tools(self):
        proc = _start_server("--temp")
        try:
            lines = _line_reader(proc.stdout)
            _send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "all2md-tests", "version": "0"},
                    },
                },
            )
            init = _receive(lines, 1)
            assert "result" in init, init
            server_info = init["result"]["serverInfo"]
            assert (server_info["name"], server_info["version"]) == ("all2md", __version__)

            _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tools = {tool["name"] for tool in _receive(lines, 2)["result"]["tools"]}
            assert "read_document_as_markdown" in tools
        finally:
            proc.kill()
            proc.communicate()

    def test_help_names_the_subcommand(self):
        result = subprocess.run(
            [sys.executable, "-m", "all2md", "mcp", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert result.returncode == 0
        assert result.stdout.startswith("usage: all2md mcp")
        assert "--enable-from-md" in result.stdout

    def test_bad_argument_exits_with_usage_error(self):
        result = subprocess.run(
            [sys.executable, "-m", "all2md", "mcp", "--no-such-flag"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=HANDSHAKE_TIMEOUT,
        )
        assert result.returncode == 2
        assert "all2md mcp: error" in result.stderr
