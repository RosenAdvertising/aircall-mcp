"""In-process checks for stateless Streamable HTTP (MCP 2026-07-28)."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx2 as httpx
import pytest
from mcp import Client

from aircall_mcp import server
from test_canary_regressions import FakeResponse, _bare_client

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
LOOPBACK = "http://127.0.0.1:8080"


def _modern_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "aircall-http-test", "version": "0"},
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if method in {"tools/call", "prompts/get", "resources/read"}:
        key = "uri" if method == "resources/read" else "name"
        headers["mcp-name"] = str(request_params[key])
    return headers, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


def _payload(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        data_lines = [
            line.removeprefix("data:").strip()
            for line in response.text.splitlines()
            if line.startswith("data:")
        ]
        assert data_lines, response.text
        body = json.loads(data_lines[-1])
    else:
        body = response.json()
    assert body["jsonrpc"] == "2.0"
    return body


def _result(response: httpx.Response) -> dict[str, Any]:
    payload = _payload(response)
    return payload["result"]


@asynccontextmanager
async def _client(app, base_url: str):
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url=base_url, timeout=5.0
        ) as client:
            yield client


async def _post(
    app,
    base_url: str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    headers, body = _modern_request(method, params, request_id=request_id)
    if extra_headers:
        headers.update(extra_headers)
    async with _client(app, base_url) as client:
        return await client.post("/mcp", headers=headers, json=body)


async def _stdio_tool_schemas() -> dict[str, dict[str, Any]]:
    async with Client(server.mcp, cache=None) as client:
        listed = await client.list_tools()
    return {tool.name: tool.input_schema for tool in listed.tools}


def test_http_tools_list_matches_stdio_schemas() -> None:
    app = server.create_serve_app()
    manager = server.mcp._lowlevel_server.session_manager
    assert manager.stateless is True
    assert manager.json_response is False

    response = asyncio.run(_post(app, LOOPBACK, "tools/list"))
    result = _result(response)
    http_tools = {tool["name"]: tool["inputSchema"] for tool in result["tools"]}
    stdio_tools = asyncio.run(_stdio_tool_schemas())
    assert http_tools == stdio_tools
    assert "mcp-session-id" not in response.headers


def test_two_requests_share_no_session(monkeypatch) -> None:
    enters = {"n": 0}
    original = server.mcp._lowlevel_server.lifespan

    @asynccontextmanager
    async def counting(app):
        enters["n"] += 1
        async with original(app) as state:
            yield state

    monkeypatch.setattr(server.mcp._lowlevel_server, "lifespan", counting)

    async def two_posts():
        app = server.create_serve_app()
        first_headers, first_body = _modern_request("tools/list", request_id=1)
        second_headers, second_body = _modern_request("tools/list", request_id=2)
        second_headers["mcp-session-id"] = "not-a-session"
        async with _client(app, LOOPBACK) as client:
            first = await client.post("/mcp", headers=first_headers, json=first_body)
            second = await client.post("/mcp", headers=second_headers, json=second_body)
        return first, second

    first, second = asyncio.run(two_posts())
    assert enters["n"] == 1
    assert _result(first)["tools"]
    assert [tool["name"] for tool in _result(first)["tools"]] == [
        tool["name"] for tool in _result(second)["tools"]
    ]
    assert "mcp-session-id" not in first.headers
    assert "mcp-session-id" not in second.headers


def test_read_tool_runs_over_http(monkeypatch) -> None:
    body = {"company": {"id": 7, "name": "Example Firm"}}
    monkeypatch.setattr(
        server,
        "_client",
        lambda: _bare_client(FakeResponse(200, body=body)),
    )
    response = asyncio.run(
        _post(
            server.create_serve_app(),
            LOOPBACK,
            "tools/call",
            {"name": "get_company", "arguments": {}},
        )
    )
    result = _result(response)
    assert result["isError"] is False
    assert json.loads(result["content"][0]["text"]) == body


def test_default_transport_is_stdio_and_bogus_exits(monkeypatch) -> None:
    monkeypatch.delenv("AIRCALL_MCP_TRANSPORT", raising=False)
    calls: list[str] = []
    monkeypatch.setattr(server.mcp, "run", lambda: calls.append("stdio"))
    assert server._requested_transport() == "stdio"
    server.main()
    assert calls == ["stdio"]

    monkeypatch.setenv("AIRCALL_MCP_TRANSPORT", "bogus")
    with pytest.raises(SystemExit) as caught:
        server.main()
    message = str(caught.value)
    assert "stdio" in message
    assert "streamable-http" in message


def test_streamable_http_transport_is_selected(monkeypatch) -> None:
    monkeypatch.setenv("AIRCALL_MCP_TRANSPORT", " STREAMABLE-HTTP ")
    started: list[str] = []

    def capture(coro):
        started.append(coro.cr_code.co_name)
        coro.close()

    monkeypatch.setattr(server.asyncio, "run", capture)
    server.main()
    assert started == ["_serve_streamable_http"]


def test_non_integer_port_exits(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "nope")
    with pytest.raises(SystemExit) as caught:
        server._port()
    assert "PORT" in str(caught.value)


def test_allowed_hosts_refuse_other_host_and_bad_origin(monkeypatch) -> None:
    monkeypatch.setenv("AIRCALL_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("AIRCALL_MCP_ALLOWED_HOSTS", "mcp.example.test")
    monkeypatch.setenv("AIRCALL_MCP_ALLOWED_ORIGINS", "http://mcp.example.test")
    app = server.create_serve_app()

    refused = asyncio.run(_post(app, "http://other.example.test", "tools/list"))
    assert refused.status_code == 421

    bad_origin = asyncio.run(
        _post(
            server.create_serve_app(),
            "http://mcp.example.test",
            "tools/list",
            extra_headers={"origin": "http://evil.example"},
        )
    )
    assert bad_origin.status_code == 403

    accepted = asyncio.run(
        _post(
            server.create_serve_app(),
            "http://mcp.example.test",
            "tools/list",
            extra_headers={"origin": "http://mcp.example.test"},
        )
    )
    assert accepted.status_code == 200


def test_non_loopback_host_without_allowed_hosts_exits(monkeypatch) -> None:
    monkeypatch.setenv("AIRCALL_MCP_HOST", "0.0.0.0")
    monkeypatch.delenv("AIRCALL_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SystemExit) as caught:
        server.create_serve_app()
    assert "AIRCALL_MCP_ALLOWED_HOSTS" in str(caught.value)

    monkeypatch.setenv("AIRCALL_MCP_ALLOWED_HOSTS", " , ")
    with pytest.raises(SystemExit) as caught_blank:
        server.create_serve_app()
    assert "AIRCALL_MCP_ALLOWED_HOSTS" in str(caught_blank.value)


def test_get_and_delete_are_rejected_and_discover_names_version() -> None:
    async def probe():
        app = server.create_serve_app()
        headers, body = _modern_request("server/discover")
        method_headers = {"mcp-protocol-version": PROTOCOL_VERSION}
        async with _client(app, LOOPBACK) as client:
            get_response = await client.get("/mcp", headers=method_headers)
            delete_response = await client.delete("/mcp", headers=method_headers)
            discover = await client.post("/mcp", headers=headers, json=body)
        return get_response, delete_response, discover

    get_response, delete_response, discover = asyncio.run(probe())
    assert get_response.status_code == 405
    assert delete_response.status_code == 405
    result = _result(discover)
    assert PROTOCOL_VERSION in result["supportedVersions"]
    version = result["_meta"][SERVER_INFO_META_KEY]["version"]
    assert isinstance(version, str) and version
    assert "mcp-session-id" not in discover.headers
