"""Offline reproductions of PUBLIC6 findings through real MCP/setup boundaries."""

from aircall_mcp import credentials, private_storage
import asyncio
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from mcp import ClientSession
from mcp.client._memory import InMemoryTransport
from aircall_mcp import client as client_module, server


@pytest.fixture
def boundary(monkeypatch):
    client = object.__new__(client_module.AircallClient)
    calls = Mock(return_value={"id": "123"})
    for name in ("get", "put", "patch", "post", "_detail", "_send", "_request"):
        monkeypatch.setattr(client, name, calls, raising=False)
    monkeypatch.setattr(server, "AircallClient", lambda: client)
    for name in ("_c", "_client", "get_client"):
        if hasattr(server, name):
            monkeypatch.setattr(server, name, lambda: client)

    async def invoke(name, arguments):
        async with InMemoryTransport(server.mcp) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(name, arguments)

    return lambda name, arguments: asyncio.run(invoke(name, arguments)), calls


@pytest.mark.parametrize("name,arguments", [("update_contact", {"contact_id": 123})])
def test_empty_write_rejected_at_mcp_boundary(boundary, name, arguments):
    call, requests = boundary
    result = call(name, arguments)
    assert result.is_error, result
    assert any(
        "field" in item.text or "non-empty" in item.text for item in result.content
    )
    requests.assert_not_called()


@pytest.mark.parametrize("failure", ["directory_chmod", "fchmod", "replace", None])
@pytest.mark.parametrize("existing", [False, True])
def test_fallback_private_from_creation_and_fail_closed(
    monkeypatch, tmp_path, failure, existing
):
    target = tmp_path / "config" / ".env"
    if existing:
        target.parent.mkdir()
        target.write_text("old value")
    if "aircall" == "lawmatics":
        monkeypatch.setattr(credentials, "env_file", lambda: target)
    else:
        monkeypatch.setattr(credentials, "ENV_FILE", target)
        monkeypatch.setattr(credentials, "CONFIG_DIR", target.parent)
    observed = []
    real_open = os.open

    def opened(path, flags, mode=0o777):
        fd = real_open(path, flags, mode)
        observed.append((mode, os.fstat(fd).st_mode & 0o777))
        return fd

    monkeypatch.setattr(private_storage.os, "open", opened)

    def denied(*args, **kwargs):
        raise OSError("simulated permissions failure")

    if failure == "directory_chmod":
        monkeypatch.setattr(Path, "chmod", denied)
    elif failure:
        monkeypatch.setattr(private_storage.os, failure, denied)
    old_umask = os.umask(0o022)
    try:
        if failure:
            with pytest.raises(OSError):
                credentials._write_env_file({"TEST_VALUE": "dummy"})
            assert (
                target.read_text() == "old value" if existing else not target.exists()
            )
        else:
            credentials._write_env_file({"TEST_VALUE": "dummy"})
            assert target.stat().st_mode & 0o777 == 0o600
            assert target.parent.stat().st_mode & 0o777 == 0o700
    finally:
        os.umask(old_umask)
    assert all(mode == actual == 0o600 for mode, actual in observed)
    assert not list(target.parent.glob("..env.*")) if target.parent.exists() else True
