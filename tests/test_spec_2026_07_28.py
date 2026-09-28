"""Offline raw-wire regressions for the MCP 2026-07-28 migration."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx2 as httpx
from mcp import Client
from mcp.types import LATEST_PROTOCOL_VERSION
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from aircall_mcp import server


PROTOCOL_VERSION = "2026-07-28"
LEGACY_PROTOCOL_VERSION = "2025-11-25"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = [
    "get_company",
    "list_numbers",
    "get_number",
    "list_calls",
    "get_call",
    "initiate_call",
    "transfer_call",
    "add_call_comment",
    "tag_call",
    "get_call_transcript",
    "get_call_summary",
    "list_contacts",
    "get_contact",
    "create_contact",
    "update_contact",
    "delete_contact",
    "list_users",
    "get_user",
    "list_teams",
    "get_team",
    "list_tags",
    "create_tag",
]


def _modern_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    request_id: int = 1,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: protocol_version,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "aircall-spec-test", "version": "0"},
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "mcp-protocol-version": protocol_version,
        "mcp-method": method,
    }
    if method == "tools/call":
        headers["mcp-name"] = str(request_params["name"])
    elif method == "prompts/get":
        headers["mcp-name"] = str(request_params["name"])
    elif method == "resources/read":
        headers["mcp-name"] = str(request_params["uri"])
    return headers, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


async def _post_modern(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    header_overrides: dict[str, str] | None = None,
    remove_headers: tuple[str, ...] = (),
) -> httpx.Response:
    app = server.mcp.streamable_http_app(
        host="127.0.0.1",
        stateless_http=True,
        json_response=True,
    )
    headers, body = _modern_request(
        method,
        params,
        protocol_version=protocol_version,
    )
    if header_overrides:
        headers.update(header_overrides)
    for header in remove_headers:
        headers.pop(header, None)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8000",
        ) as client:
            return await client.post("/mcp", headers=headers, json=body)


def _result(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


def test_spec_check_pins_the_2026_revision() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "spec_check.py"), "--mcp-only"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Spec check: PASS" in result.stdout
    assert LATEST_PROTOCOL_VERSION == PROTOCOL_VERSION
    assert MODERN_PROTOCOL_VERSIONS == (PROTOCOL_VERSION,)


def test_modern_wire_requests_emit_all_required_routing_headers() -> None:
    list_headers, _ = _modern_request("tools/list")
    call_headers, _ = _modern_request(
        "tools/call", {"name": "get_company", "arguments": {}}
    )

    assert list_headers["mcp-protocol-version"] == PROTOCOL_VERSION
    assert list_headers["mcp-method"] == "tools/list"
    assert call_headers["mcp-protocol-version"] == PROTOCOL_VERSION
    assert call_headers["mcp-method"] == "tools/call"
    assert call_headers["mcp-name"] == "get_company"


def test_modern_discovery_is_sessionless_and_declares_only_used_capabilities() -> None:
    response = asyncio.run(_post_modern("server/discover"))
    result = _result(response)

    assert "mcp-session-id" not in response.headers
    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert result["capabilities"] == {
        "prompts": {"listChanged": True},
        "resources": {"listChanged": True, "subscribe": True},
        "tools": {"listChanged": True},
    }
    assert "extensions" not in result["capabilities"]
    assert result["_meta"][SERVER_INFO_META_KEY]["name"] == "aircall-mcp"


def test_client_negotiates_modern_and_retains_legacy_compatibility() -> None:
    async def negotiate() -> tuple[str, str]:
        async with Client(server.mcp, cache=None) as modern:
            modern_version = modern.protocol_version
        async with Client(server.mcp, mode="legacy", cache=None) as legacy:
            legacy_version = legacy.protocol_version
        return modern_version, legacy_version

    modern_version, legacy_version = asyncio.run(negotiate())
    assert modern_version == PROTOCOL_VERSION
    assert legacy_version == LEGACY_PROTOCOL_VERSION


def test_cacheable_results_are_complete_private_and_deterministic() -> None:
    async def list_results() -> list[dict[str, Any]]:
        methods = (
            "tools/list",
            "tools/list",
            "prompts/list",
            "resources/list",
            "resources/templates/list",
        )
        return [_result(await _post_modern(method)) for method in methods]

    first_tools, second_tools, prompts, resources, templates = asyncio.run(
        list_results()
    )
    for result in (first_tools, second_tools, prompts, resources, templates):
        assert result["resultType"] == "complete"
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "private"

    first_names = [tool["name"] for tool in first_tools["tools"]]
    second_names = [tool["name"] for tool in second_tools["tools"]]
    assert first_names == TOOL_NAMES
    assert second_names == TOOL_NAMES
    assert all(tool["inputSchema"]["type"] == "object" for tool in first_tools["tools"])
    assert len(prompts["prompts"]) == 3
    assert [item["uri"] for item in resources["resources"]] == [
        "aircall://numbers",
        "aircall://tags",
        "aircall://security-notes",
    ]
    assert templates["resourceTemplates"] == []


def test_resource_read_cache_hints_and_not_found_error() -> None:
    found = asyncio.run(
        _post_modern("resources/read", {"uri": "aircall://security-notes"})
    )
    result = _result(found)
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert "Credentials" in result["contents"][0]["text"]

    missing = asyncio.run(
        _post_modern("resources/read", {"uri": "aircall://does-not-exist"})
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == -32602


def test_modern_tool_result_preserves_json_content_and_is_complete(monkeypatch) -> None:
    class StubAircallClient:
        def get_company(self) -> dict[str, Any]:
            return {"company": {"id": 7, "plan": "test"}}

    monkeypatch.setattr(server, "_client", StubAircallClient)
    response = asyncio.run(
        _post_modern("tools/call", {"name": "get_company", "arguments": {}})
    )
    result = _result(response)
    assert result["isError"] is False
    assert result["resultType"] == "complete"
    assert json.loads(result["content"][0]["text"]) == {
        "company": {"id": 7, "plan": "test"},
    }


def test_modern_http_enforces_routing_headers_versions_and_method_errors() -> None:
    mismatch = asyncio.run(
        _post_modern(
            "tools/list",
            header_overrides={"mcp-method": "resources/list"},
        )
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == -32020

    missing_method = asyncio.run(
        _post_modern("tools/list", remove_headers=("mcp-method",))
    )
    assert missing_method.status_code == 400
    assert missing_method.json()["error"]["code"] == -32020

    missing_name = asyncio.run(
        _post_modern(
            "tools/call",
            {"name": "get_company", "arguments": {}},
            remove_headers=("mcp-name",),
        )
    )
    assert missing_name.status_code == 400
    assert missing_name.json()["error"]["code"] == -32020

    mismatched_version = asyncio.run(
        _post_modern(
            "tools/list",
            header_overrides={"mcp-protocol-version": "2099-01-01"},
        )
    )
    assert mismatched_version.status_code == 400
    assert mismatched_version.json()["error"]["code"] == -32020

    unsupported = asyncio.run(_post_modern("tools/list", protocol_version="2099-01-01"))
    assert unsupported.status_code == 400
    assert unsupported.json()["error"]["code"] == -32022

    unknown = asyncio.run(_post_modern("example/unknown"))
    assert unknown.status_code == 404
    assert unknown.json()["error"] == {
        "code": -32601,
        "message": "Method not found",
        "data": "example/unknown",
    }
