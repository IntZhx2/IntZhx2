"""Newline-delimited stdio transport for the implemented MCP tools subset."""
import json
import sys
from smart_agent.mcp.server import MCPServer
from smart_agent.tools import create_default_tools


def run_stdio():
    server = MCPServer(name="TravelAgent-stdio")
    for tool in create_default_tools():
        server.register_tool(tool)
    while True:
        line = sys.stdin.buffer.readline(1024 * 1024 + 1)
        if not line:
            return
        if len(line) > 1024 * 1024:
            # Drain this oversized frame without growing memory.
            while line and not line.endswith(b'\n'):
                line = sys.stdin.buffer.readline(1024 * 1024 + 1)
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32600, "message": "request too large"}}
        else:
            try:
                response = server.handle_request(json.loads(line))
            except (ValueError, UnicodeError):
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": "invalid JSON"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + '\n')
            sys.stdout.flush()
