from __future__ import annotations

import logging

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolRequestParams
from test_canary_regressions import FakeResponse, _bare_client

from aircall_mcp import server
from aircall_mcp.client import AircallClient
from aircall_mcp.errors import ArgumentShapeError


PII = "Private Person private@example.test secret-token-value"


class Response(FakeResponse):
    def __init__(self, status_code: int, payload=None, retry_after="7"):
        super().__init__(status_code, body=payload)
        self.headers = {"Retry-After": retry_after}


client_for = _bare_client


async def dispatch(name="get_company", arguments=None):
    return await server.mcp._handle_call_tool(
        None,
        CallToolRequestParams(name=name, arguments=arguments or {}),
    )


def text(result):
    assert result.is_error is True
    assert len(result.content) == 1
    return result.content[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            "missing",
            "Error executing tool get_company: Aircall credentials are missing. Set AIRCALL_API_ID and AIRCALL_API_TOKEN or run aircall-mcp-setup.",
        ),
        (
            "auth",
            "Error executing tool get_company: Aircall authorization was rejected or expired. Reauthorize with aircall-mcp-setup.",
        ),
        (
            "not_found",
            "Error executing tool get_company: The requested Aircall resource was not found.",
        ),
        (
            "rate",
            "Error executing tool get_company: Aircall rate limit reached. Retry after about 7 seconds.",
        ),
        (
            "http_allowlisted",
            "Error executing tool get_company: Aircall returned HTTP 500: service unavailable.",
        ),
        (
            "http_unknown_reason",
            "Error executing tool get_company: Aircall returned HTTP 500: request rejected.",
        ),
        (
            "malformed_json",
            "Error executing tool get_company: Aircall returned HTTP 200: invalid JSON response.",
        ),
    ],
)
async def test_vendor_failures_return_safe_actionable_tool_results(
    monkeypatch, failure, expected
):
    responses = {
        "auth": Response(401),
        "not_found": Response(404),
        "rate": Response(429),
        "http_allowlisted": Response(
            500, {"code": "service_unavailable", "message": PII}
        ),
        "http_unknown_reason": Response(500, {"code": PII, "message": PII}),
        "malformed_json": Response(200),
    }
    if failure == "missing":
        monkeypatch.delenv("AIRCALL_API_ID", raising=False)
        monkeypatch.delenv("AIRCALL_API_TOKEN", raising=False)
        monkeypatch.setattr(
            "aircall_mcp.client.credentials.load_into_environ", lambda _keys: None
        )
        monkeypatch.setattr(server, "_client", AircallClient)
    elif failure == "auth":
        monkeypatch.setattr(server, "_client", lambda: client_for(responses[failure]))
    elif failure == "not_found":
        monkeypatch.setattr(server, "_client", lambda: client_for(responses[failure]))
        # Exercise a concrete resource endpoint.
        result = await dispatch("get_number", {"number_id": 42})
        assert text(result) == expected.replace("get_company", "get_number")
        return
    else:
        monkeypatch.setattr(server, "_client", lambda: client_for(responses[failure]))

    result = await dispatch()
    assert text(result) == expected


@pytest.mark.asyncio
async def test_schema_validation_names_expected_shape_without_echoing_value(caplog):
    caplog.set_level(logging.INFO, logger="aircall_mcp.server")
    result = await dispatch("list_numbers", {"limit": PII})
    assert text(result) == (
        "Error executing tool list_numbers: Invalid arguments: limit expected an integer from 1 to 200."
    )
    assert PII not in caplog.text


@pytest.mark.asyncio
async def test_client_argument_shape_failure_is_actionable_at_dispatch(monkeypatch):
    class InvalidContactClient:
        def create_contact(self, **_kwargs):
            raise ArgumentShapeError(
                "phone_numbers", "an array of phone number objects"
            )

    monkeypatch.setattr(server, "_client", InvalidContactClient)
    result = await dispatch(
        "create_contact", {"first_name": "Client", "phone_numbers": []}
    )
    assert text(result) == (
        "Error executing tool create_contact: Argument phone_numbers must be "
        "an array of phone number objects."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("exception_type", [RuntimeError, ValueError, ToolError])
async def test_unknown_exception_is_masked_and_fixed_reason_logged(
    monkeypatch, caplog, exception_type
):
    caplog.set_level(logging.DEBUG)

    class BrokenClient:
        def get_company(self):
            raise exception_type(PII)

    monkeypatch.setattr(server, "_client", BrokenClient)
    result = await dispatch()
    assert text(result) == "Error executing tool get_company"
    assert "tool_failed reason=unexpected" in caplog.text
    assert PII not in caplog.text


@pytest.mark.asyncio
async def test_rate_retry_hint_is_bounded(monkeypatch):
    monkeypatch.setattr(
        server, "_client", lambda: client_for(Response(429, retry_after="999999"))
    )
    result = await dispatch()
    assert text(result) == (
        "Error executing tool get_company: Aircall rate limit reached. Retry later."
    )


@pytest.mark.asyncio
async def test_unknown_vendor_reason_is_never_exposed(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(
        server,
        "_client",
        lambda: client_for(
            Response(
                500,
                {"error": PII, "message": PII, "url": "https://host/path?token=secret"},
            )
        ),
    )
    result = await dispatch()
    combined = text(result) + caplog.text
    assert "request rejected" in combined
    assert PII not in combined
    assert "token=secret" not in combined


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "retry", "expected"),
    [
        (
            403,
            "7",
            "Aircall authorization was rejected or expired. Reauthorize with aircall-mcp-setup.",
        ),
        (429, "300", "Aircall rate limit reached. Retry after about 300 seconds."),
        (429, PII, "Aircall rate limit reached. Retry later."),
        (429, "-1", "Aircall rate limit reached. Retry later."),
    ],
)
async def test_authorization_and_retry_hints(monkeypatch, status, retry, expected):
    monkeypatch.setattr(
        server, "_client", lambda: client_for(Response(status, retry_after=retry))
    )
    assert text(await dispatch()) == f"Error executing tool get_company: {expected}"


@pytest.mark.asyncio
async def test_nullable_argument_has_expected_shape():
    result = await dispatch("list_numbers", {"per_page": PII})
    assert (
        text(result)
        == "Error executing tool list_numbers: Invalid arguments: per_page expected an integer from 1 to 200 or null."
    )


@pytest.mark.asyncio
async def test_transport_failure_has_safe_write_guidance(monkeypatch, caplog):
    import requests

    client = client_for(Response(200, {}))

    def fail(*args, **kwargs):
        raise requests.Timeout(PII)

    monkeypatch.setattr(client.session, "request", fail)
    monkeypatch.setattr(server, "_client", lambda: client)
    with caplog.at_level(logging.INFO):
        result = await dispatch("initiate_call", {"number_id": 1, "to": "+15555550123"})
    assert (
        text(result)
        == "Error executing tool initiate_call: Aircall request did not complete. Check the result in Aircall before retrying."
    )
    assert PII not in caplog.text


@pytest.mark.asyncio
async def test_unknown_exception_with_known_cause_is_masked(monkeypatch, caplog):
    from aircall_mcp.errors import MissingCredentialsError

    class Client:
        def get_company(self):
            raise RuntimeError(PII) from MissingCredentialsError()

    monkeypatch.setattr(server, "_client", Client)
    with caplog.at_level(logging.ERROR):
        result = await dispatch()
    assert text(result) == "Error executing tool get_company"
    assert PII not in caplog.text
    assert "reason=unexpected" in caplog.text
