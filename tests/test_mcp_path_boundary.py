"""Regression calls cross the official MCP transport before real client routing."""

import asyncio
from types import SimpleNamespace

import pytest
import requests
from mcp.client import ClientSession
from mcp.client._memory import InMemoryTransport
from requests.adapters import BaseAdapter

from aircall_mcp import client as client_module
from aircall_mcp import server

CASES = [
    ("get_number", "number_id", {"number_id": 123}),
    ("get_call", "call_id", {"call_id": 123}),
    ("transfer_call", "call_id", {"call_id": 123}),
    ("add_call_comment", "call_id", {"call_id": 123, "content": "normal-id"}),
    ("tag_call", "call_id", {"call_id": 123, "tag_ids": ["normal-id"]}),
    ("get_call_transcript", "call_id", {"call_id": 123}),
    ("get_call_summary", "call_id", {"call_id": 123}),
    ("get_contact", "contact_id", {"contact_id": 123}),
    ("update_contact", "contact_id", {"contact_id": 123, "first_name": "probe"}),
    ("delete_contact", "contact_id", {"contact_id": 123}),
    ("get_user", "user_id", {"user_id": 123}),
    ("get_team", "team_id", {"team_id": 123}),
]


@pytest.fixture
def boundary(monkeypatch):
    client = object.__new__(client_module.AircallClient)
    prepared, sent, constructed = [], [], []

    class Adapter(BaseAdapter):
        def send(self, request, **kwargs):
            sent.append(request)
            response = requests.Response()
            response.status_code = 200
            response.request = request
            response.url = request.url
            response.headers["Content-Type"] = "application/json"
            response._content = b'{"id":"normal-id","success":true,"name":"probe","data":{"id":"normal-id"},"items":[],"results":[]}'
            return response

        def close(self):
            pass

    client.session = requests.Session()
    client.session.trust_env = False
    client.session.mount("http://", Adapter())
    client.session.mount("https://", Adapter())
    prepare = client.session.prepare_request

    def record_prepare(request):
        prepared.append(request)
        return prepare(request)

    monkeypatch.setattr(client.session, "prepare_request", record_prepare)
    client.tm = SimpleNamespace(
        is_expired=lambda: False, access_token="", refresh_token=""
    )
    client.api_endpoint = "https://example.invalid"
    client._token_valid = lambda: True
    client._headers = lambda: {}
    client.access_token = ""
    client._rate_waited = 0
    client.timeout = 30
    client._api_url = "https://example.invalid/v1"

    def factory():
        constructed.append(True)
        return client

    monkeypatch.setattr(server, "AircallClient", factory)
    for name in ("_c", "_client", "get_client"):
        if hasattr(server, name):
            monkeypatch.setattr(server, name, factory)

    async def call(tool, arguments):
        async with InMemoryTransport(server.mcp) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments)
                return result.model_dump(mode="json", by_alias=True)

    return SimpleNamespace(
        call=lambda tool, arguments: asyncio.run(call(tool, arguments)),
        prepared=prepared,
        sent=sent,
        constructed=constructed,
        client=client,
    )


@pytest.mark.parametrize("tool,parameter,arguments", CASES)
@pytest.mark.parametrize("value", [True, False])
def test_boolean_path_id_rejected_before_client(
    boundary, tool, parameter, arguments, value
):
    result = boundary.call(tool, {**arguments, parameter: value})
    text = " ".join(item.get("text", "") for item in result["content"])
    assert result["isError"]
    assert parameter in text
    assert "integer" in text
    assert not boundary.constructed
    assert not boundary.prepared
    assert not boundary.sent


@pytest.mark.parametrize("tool,parameter,arguments", CASES)
@pytest.mark.parametrize("value", [123, "123", "00123", 123.0, "123.0", 0, -1])
def test_existing_integer_coercions_preserved(
    boundary, tool, parameter, arguments, value
):
    result = boundary.call(tool, {**arguments, parameter: value})
    assert not result["isError"], result
    assert boundary.prepared
    assert boundary.sent
