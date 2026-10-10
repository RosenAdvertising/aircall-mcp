"""The aircall://security-notes resource text agrees with the README."""

from __future__ import annotations

import asyncio

from mcp import Client

from aircall_mcp import server


def _read_security_notes() -> str:
    async def read() -> str:
        async with Client(server.mcp) as client:
            result = await client.read_resource("aircall://security-notes")
        return result.contents[0].text

    return asyncio.run(read())


def test_security_notes_state_the_credential_read_order_the_code_uses() -> None:
    text = _read_security_notes()
    # credentials.load_into_environ skips any key already in the process environment,
    # then get_secret reads the keyring, then the .env file.
    assert "Read order: process environment, then the OS keyring" in text
    assert "then `~/.aircall-mcp/.env`" in text
    assert "OS keyring (macOS Keychain / libsecret) → process env" not in text
    assert "AIRCALL_MCP_USE_KEYRING=0" in text
    assert "0600" in text


def test_security_notes_describe_the_http_mode_warning_and_settings() -> None:
    text = _read_security_notes()
    assert "stdio is the default" in text
    assert "AIRCALL_MCP_TRANSPORT=streamable-http" in text
    assert "no authentication and no TLS" in text
    assert "127.0.0.1" in text
    assert "AIRCALL_MCP_ALLOWED_HOSTS" in text
    assert "AIRCALL_MCP_ALLOWED_ORIGINS" in text
    assert "not against direct callers" in text


def test_security_notes_keep_the_tool_classification() -> None:
    text = _read_security_notes()
    assert "Read-only (safe)" in text
    assert "delete_contact" in text
