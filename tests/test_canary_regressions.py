"""Regression coverage for the fleet canary checks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from aircall_mcp import server
from aircall_mcp.client import AircallClient, _json_response
from aircall_mcp.setup import verify as verify_module


LIST_TOOLS = (
    "list_numbers",
    "list_calls",
    "list_contacts",
    "list_users",
    "list_teams",
    "list_tags",
)
PAGED_LIST_TOOLS = LIST_TOOLS[:-1]
COLLECTION_KEYS = {
    "list_numbers": "numbers",
    "list_calls": "calls",
    "list_contacts": "contacts",
    "list_users": "users",
    "list_teams": "teams",
    "list_tags": "tags",
}
SENTINEL = "Private Person private@example.test secret-token-value"


class RecordingClient(AircallClient):
    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.requests: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, path, params=None):
        self.requests.append((path, params))
        return self.response


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        body: dict[str, Any] | None = None,
        text: str = SENTINEL,
    ):
        self.status_code = status_code
        self._body = body
        self.text = text
        self.ok = 200 <= status_code < 300
        self.headers: dict[str, str] = {}

    def json(self):
        if self._body is None:
            raise ValueError("not JSON")
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response

    def request(self, *_args, **_kwargs):
        return self.response


def _bare_client(response: FakeResponse) -> AircallClient:
    client = object.__new__(AircallClient)
    cast(Any, client).session = FakeSession(response)
    return client


def _tool_schemas() -> dict[str, dict[str, Any]]:
    return {
        tool.name: tool.input_schema
        for tool in asyncio.run(server.mcp.list_tools())
        if tool.name in LIST_TOOLS
    }


def test_list_tool_schemas_bound_page_and_total_limit() -> None:
    schemas = _tool_schemas()
    assert set(schemas) == set(LIST_TOOLS)

    for name in LIST_TOOLS:
        limit = schemas[name]["properties"]["limit"]
        assert limit["default"] == 25
        assert limit["minimum"] == 1
        assert limit["maximum"] == 200
    for name in PAGED_LIST_TOOLS:
        page = schemas[name]["properties"]["page"]
        assert page["default"] == 1
        assert page["minimum"] == 1
        assert schemas[name]["properties"]["per_page"]["deprecated"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        *((name, {"limit": 0}) for name in LIST_TOOLS),
        *((name, {"limit": 201}) for name in LIST_TOOLS),
        *((name, {"page": 0}) for name in PAGED_LIST_TOOLS),
        *((name, {"per_page": 0}) for name in PAGED_LIST_TOOLS),
    ],
)
async def test_list_tools_reject_invalid_pagination(
    tool_name: str, arguments: dict[str, Any]
) -> None:
    tool = server.mcp._tool_manager.get_tool(tool_name)
    assert tool is not None
    with pytest.raises(ToolError, match="validation error"):
        await tool.run(arguments, None)


@pytest.mark.parametrize("method_name", LIST_TOOLS)
def test_list_clients_trim_overlarge_vendor_responses(method_name: str) -> None:
    key = COLLECTION_KEYS[method_name]
    response = {key: [{"id": value} for value in range(10)]}
    client = RecordingClient(response)

    result = getattr(client, method_name)(limit=3)

    assert len(result[key]) == 3
    assert len(client.requests) == 1
    path, params = client.requests[0]
    assert path == f"/{key}"
    if method_name == "list_tags":
        assert params is None
    else:
        assert params is not None
        assert params["per_page"] == 3


def test_legacy_per_page_alias_remains_supported(monkeypatch) -> None:
    class StubClient:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []

        def list_numbers(self, **kwargs):
            self.calls.append(kwargs)
            return {"numbers": []}

    stub = StubClient()
    monkeypatch.setattr(server, "_client", lambda: stub)

    server.list_numbers(limit=25, per_page=7)

    assert stub.calls == [{"page": 1, "limit": 7}]


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (FakeResponse(401), "upstream_unauthorized"),
        (FakeResponse(500), "upstream_error"),
    ],
)
def test_upstream_rejections_log_reason_without_response_pii(
    response: FakeResponse,
    reason: str,
    caplog,
) -> None:
    caplog.set_level(logging.WARNING, logger="aircall_mcp.client")
    client = _bare_client(response)

    with pytest.raises(RuntimeError) as error:
        client._request("GET", "/company")

    combined = str(error.value) + caplog.text
    assert reason in caplog.text
    assert SENTINEL not in combined


def test_non_json_rejection_omits_response_pii(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="aircall_mcp.client")
    response = FakeResponse(200)

    with pytest.raises(RuntimeError) as error:
        _json_response(response)

    combined = str(error.value) + caplog.text
    assert "upstream_non_json" in caplog.text
    assert SENTINEL not in combined


@pytest.mark.parametrize(
    ("method_name", "kwargs", "reason"),
    [
        ("tag_call", {"call_id": 1, "tag_ids": "not-a-list"}, "tag_ids_not_list"),
        (
            "create_contact",
            {"first_name": "Test", "phone_numbers": "not-a-list"},
            "phone_numbers_not_list",
        ),
        (
            "create_contact",
            {"first_name": "Test", "emails": "not-a-list"},
            "emails_not_list",
        ),
        (
            "update_contact",
            {"contact_id": 1, "phone_numbers": "not-a-list"},
            "phone_numbers_not_list",
        ),
    ],
)
def test_validation_rejections_have_pii_free_reason_logs(
    method_name: str,
    kwargs: dict[str, Any],
    reason: str,
    caplog,
) -> None:
    caplog.set_level(logging.WARNING, logger="aircall_mcp.client")
    client = object.__new__(AircallClient)

    with pytest.raises(ValueError):
        getattr(client, method_name)(**kwargs)

    assert reason in caplog.text
    assert SENTINEL not in caplog.text


def test_missing_credentials_rejection_has_pii_free_reason_log(
    monkeypatch, caplog
) -> None:
    monkeypatch.delenv("AIRCALL_API_ID", raising=False)
    monkeypatch.delenv("AIRCALL_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "aircall_mcp.client.credentials.load_into_environ", lambda _keys: None
    )
    caplog.set_level(logging.WARNING, logger="aircall_mcp.client")

    with pytest.raises(RuntimeError, match="credentials not found"):
        AircallClient()

    assert "credentials_missing" in caplog.text
    assert SENTINEL not in caplog.text


def test_verification_success_does_not_print_company_name(monkeypatch, capsys) -> None:
    class StubClient:
        def get_company(self):
            return {"company": {"name": SENTINEL}}

    monkeypatch.setattr(verify_module, "AircallClient", StubClient)

    verify_module.verify()

    output = capsys.readouterr().out
    assert output == "Connected successfully.\n"
    assert SENTINEL not in output
