"""The installed `opendota-mcp-server` command, run as a real subprocess.

These tests reach no network: they only start the server, list tools and stop.
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from tests.conftest import SETTINGS_ENV_VARS

COMMAND = str(Path(sys.executable).parent / "opendota-mcp-server")


def server_env(**env: str) -> dict[str, str]:
    clean = {k: v for k, v in os.environ.items() if k not in SETTINGS_ENV_VARS}
    return {**clean, **env}


def jsonrpc(message: dict[str, object]) -> str:
    return json.dumps({"jsonrpc": "2.0", **message}) + "\n"


def test_stdio_speaks_only_json_rpc_on_stdout_even_with_debug_logging(tmp_path: Path) -> None:
    # Run in an empty directory so no developer `.env` is picked up.
    server = subprocess.Popen(
        [COMMAND],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=tmp_path,
        env=server_env(LOG_LEVEL="DEBUG"),
    )
    watchdog = threading.Timer(30, server.kill)
    watchdog.start()
    assert server.stdin is not None and server.stdout is not None
    stdout_lines: list[str] = []

    def send(message: dict[str, object]) -> None:
        assert server.stdin is not None
        server.stdin.write(jsonrpc(message))
        server.stdin.flush()

    def reply_to(request_id: int) -> dict[str, Any]:
        assert server.stdout is not None
        while line := server.stdout.readline():
            stdout_lines.append(line)
            message: dict[str, Any] = json.loads(line)  # any stray log line fails here
            if message.get("id") == request_id:
                return message
        raise AssertionError(f"server exited before replying to request {request_id}")

    try:
        send(
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        )
        reply_to(1)
        send({"method": "notifications/initialized"})
        send({"id": 2, "method": "tools/list"})
        tools = reply_to(2)["result"]["tools"]
    finally:
        server.stdin.close()
        # Buffered output only lands at exit, so read everything the process ever wrote.
        stdout_lines.extend(server.stdout.read().splitlines())
        stderr = server.stderr.read() if server.stderr else ""
        server.wait()
        watchdog.cancel()

    assert "get_records" in {tool["name"] for tool in tools}
    for line in stdout_lines:
        assert json.loads(line)["jsonrpc"] == "2.0", f"non JSON-RPC output on stdout: {line!r}"
    assert "Starting opendota-mcp-server 2.0.0 over stdio" in stderr


def test_http_refuses_to_start_rather_than_ignore_the_auth_token(tmp_path: Path) -> None:
    done = subprocess.run(
        [COMMAND],
        input="",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=server_env(MCP_TRANSPORT="http", MCP_AUTH_TOKEN="secret"),
        timeout=30,
    )

    assert done.returncode != 0
    assert "HTTP transport is not available" in done.stderr


def test_invalid_settings_refuse_to_start_with_a_clear_message(tmp_path: Path) -> None:
    done = subprocess.run(
        [COMMAND],
        input="",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=server_env(MCP_TRANSPORT="sse"),
        timeout=30,
    )

    assert done.returncode != 0
    assert done.stdout == ""
    assert "invalid settings" in done.stderr
    assert "mcp_transport" in done.stderr
