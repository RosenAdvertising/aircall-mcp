from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolRequestParams
from test_canary_regressions import FakeResponse, _bare_client

from aircall_mcp import server
from aircall_mcp.client import AircallClient
from aircall_mcp.errors import ArgumentShapeError
from aircall_mcp.setup import setup as setup_cli
from aircall_mcp.setup import verify as verify_cli


PII = "Private Person private@example.test secret-token-value"


class Response(FakeResponse):
    def __init__(self, status_code: int, payload=None, retry_after="7"):
        super().__init__(status_code, body=payload)
        self.headers = {"Retry-After": retry_after}


client_for = _bare_client


async def dispatch(name="get_company", arguments=None):
    return await server.mcp._handle_call_tool(
        ServerRequestContext(
            session=Mock(),
            lifespan_context=None,
            protocol_version="2025-11-25",
            method="tools/call",
        ),
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
            "Error executing tool get_company: Aircall authentication failed. Re-run aircall-mcp-setup to refresh the authorization.",
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
        "Error executing tool get_company: Aircall rate limit reached. Retry after about 999999 seconds."
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
            "Aircall access denied: the connected account lacks permission for this action (or the authorization expired; re-run aircall-mcp-setup if so).",
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
        == "Error executing tool initiate_call: Aircall request outcome is unknown. Check whether the operation completed before retrying."
    )
    assert PII not in caplog.text


@pytest.mark.asyncio
async def test_read_transport_failure_allows_retry(monkeypatch):
    import requests

    client = client_for(Response(200, {}))
    monkeypatch.setattr(
        client.session,
        "request",
        lambda *_a, **_k: (_ for _ in ()).throw(requests.ConnectionError(PII)),
    )
    monkeypatch.setattr(server, "_client", lambda: client)
    assert (
        text(await dispatch("get_company"))
        == "Error executing tool get_company: Aircall read request did not complete. You may retry the read."
    )


def test_http_request_has_timeout_and_safe_path_segment(monkeypatch):
    class Recorder:
        def __init__(self, response):
            self.response = response
            self.args = None
            self.kwargs = None

        def request(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
            return self.response

    client = client_for(Response(200, {}))
    recorder = Recorder(Response(200, {"id": "ok"}))
    monkeypatch.setattr(client, "session", recorder)
    client.get_number("../x")
    assert recorder.args is not None and recorder.kwargs is not None
    assert recorder.args[1].endswith("/numbers/..%2Fx")
    import requests

    prepared = requests.Request("GET", recorder.args[1]).prepare()
    assert prepared.path_url.endswith("/numbers/..%2Fx")
    assert recorder.kwargs["timeout"] == 30


def test_get_retry_after_sleep_is_bounded(monkeypatch):
    client = client_for(Response(429, retry_after="61"))
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    with pytest.raises(Exception) as caught:
        client.get("/company")
    assert (
        str(caught.value) == "Aircall rate limit reached. Retry after about 61 seconds."
    )
    assert sleeps == []


def test_rate_limit_does_not_delay_the_tool(monkeypatch):
    from aircall_mcp.errors import RateLimitedError

    client = client_for(Response(429, retry_after="60"))
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    with pytest.raises(RateLimitedError) as caught:
        client.get("/company")
    assert (
        str(caught.value) == "Aircall rate limit reached. Retry after about 60 seconds."
    )
    assert sleeps == []


def test_verify_no_credentials_is_actionable_nonzero(monkeypatch, capsys):
    monkeypatch.delenv("AIRCALL_API_ID", raising=False)
    monkeypatch.delenv("AIRCALL_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "aircall_mcp.client.credentials.load_into_environ", lambda _keys: None
    )
    with pytest.raises(SystemExit) as exit_info:
        verify_cli.verify()
    assert exit_info.value.code == 1
    assert capsys.readouterr().out.strip() == (
        "Verification failed: Aircall credentials not found. Set AIRCALL_API_ID and AIRCALL_API_TOKEN or run aircall-mcp-setup."
    )


def test_verify_fake_bad_credentials_is_safe_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(verify_cli, "AircallClient", lambda: client_for(Response(401)))
    with pytest.raises(SystemExit) as exit_info:
        verify_cli.verify()
    assert exit_info.value.code == 1
    assert (
        "Aircall authentication failed. Re-run aircall-mcp-setup"
        in capsys.readouterr().out
    )


def test_setup_eof_exits_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        "builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError())
    )
    with pytest.raises(SystemExit) as exit_info:
        setup_cli.main()
    assert exit_info.value.code == 1
    assert "Setup input ended" in capsys.readouterr().out


def test_setup_fake_bad_credentials_exits_with_safe_text(monkeypatch, capsys):
    answers = iter(["fake-id"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(
        "aircall_mcp.setup.setup.getpass.getpass", lambda _prompt: "fake-token"
    )
    monkeypatch.setattr(
        "aircall_mcp.setup.setup.credentials.set_secret", lambda *_args: "file"
    )
    monkeypatch.setattr(verify_cli, "AircallClient", lambda: client_for(Response(401)))
    with pytest.raises(SystemExit) as exit_info:
        setup_cli.main()
    assert exit_info.value.code == 1
    output = capsys.readouterr().out
    assert "Verification failed: Aircall authentication failed." in output
    assert "fake-id" not in output and "fake-token" not in output


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


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("error_name", ["Timeout", "ConnectionError"])
async def test_transport_contract_for_reads_and_writes(monkeypatch, method, error_name):
    import requests

    client = client_for(Response(200, {}))
    calls = []

    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        raise getattr(requests, error_name)(PII)

    monkeypatch.setattr(client.session, "request", fail)
    monkeypatch.setattr(server, "_client", lambda: client)
    name = "get_company" if method == "GET" else "initiate_call"
    arguments = {} if method == "GET" else {"number_id": 1, "to": "+15555550123"}
    result = await dispatch(name, arguments)
    expected = (
        "Aircall read request did not complete. You may retry the read."
        if method == "GET"
        else "Aircall request outcome is unknown. Check whether the operation completed before retrying."
    )
    assert text(result) == f"Error executing tool {name}: {expected}"
    assert "retry shortly" not in text(result).lower()
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == 30


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "sleeps_expected"), [("GET", []), ("POST", [])])
async def test_repeated_rate_limits_respect_whole_tool_sleep_budget(
    monkeypatch, method, sleeps_expected
):
    client = client_for(Response(429, retry_after="40"))
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    monkeypatch.setattr(server, "_client", lambda: client)
    name = "get_company" if method == "GET" else "initiate_call"
    arguments = {} if method == "GET" else {"number_id": 1, "to": "+15555550123"}
    assert text(await dispatch(name, arguments)) == (
        f"Error executing tool {name}: Aircall rate limit reached. Retry after about 40 seconds."
    )
    assert sleeps == sleeps_expected
    assert sum(sleeps) <= 60


@pytest.mark.parametrize("resource", [server.numbers_resource, server.tags_resource])
def test_unexpected_resource_errors_hide_raw_details(monkeypatch, resource):
    from mcp.server.mcpserver.exceptions import ResourceError

    def fail():
        raise RuntimeError(PII)

    monkeypatch.setattr(server, "_client", fail)
    with pytest.raises(ResourceError) as caught:
        resource()
    assert (
        str(caught.value)
        == "Unable to read this Aircall resource. Try again or check the connection."
    )
    assert caught.value.__suppress_context__ is True
