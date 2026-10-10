#!/usr/bin/env python3
"""Aircall MCP server — calls, contacts, transcripts, numbers, and team management."""

import asyncio
import json
import logging
import os
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import (
    ResourceError,
    ToolError,
    UnexpectedToolError,
)
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp_types import CallToolResult, TextContent
from pydantic import BeforeValidator, Field, ValidationError

import aircall_mcp
from aircall_mcp.client import AircallClient
from aircall_mcp.errors import (
    ArgumentShapeError,
    AuthenticationError,
    AuthorizationError,
    MissingCredentialsError,
    NotFoundError,
    RateLimitedError,
    ReadTransportError,
    TransportError,
    VendorHTTPError,
)

logger = logging.getLogger(__name__)


def _reject_boolean_path_id(value):
    """Reject booleans before integer coercion; preserve all other SDK inputs."""
    if isinstance(value, bool):
        raise ValueError("Use an integer identifier, not a boolean.")
    return value


# A before-validator preserves the existing integer JSON schema and coercions.
PathId = Annotated[int, BeforeValidator(_reject_boolean_path_id)]


class SafeMCPServer(MCPServer):
    """Keep SDK registrations while sanitizing anticipated and unexpected errors."""

    async def call_tool(self, name, arguments, context=None):
        try:
            return await super().call_tool(name, arguments, context)
        except MCPError:
            raise
        except Exception as exc:
            failure = (
                exc.__cause__
                if isinstance(exc, ToolError)
                and not isinstance(exc, UnexpectedToolError)
                else None
            )
            if isinstance(failure, ValidationError):
                text = _safe_validation_text(self, name, failure)
                logger.info("tool_failed reason=invalid_arguments")
            elif isinstance(failure, MissingCredentialsError):
                text = (
                    f"Error executing tool {name}: Aircall credentials are missing. "
                    "Set AIRCALL_API_ID and AIRCALL_API_TOKEN or run aircall-mcp-setup."
                )
                logger.info("tool_failed reason=credentials_missing")
            elif isinstance(failure, AuthorizationError):
                text = (
                    f"Error executing tool {name}: Aircall access denied: the connected account lacks permission for this action "
                    "(or the authorization expired; re-run aircall-mcp-setup if so)."
                )
                logger.info("tool_failed reason=access_denied")
            elif isinstance(failure, AuthenticationError):
                text = f"Error executing tool {name}: Aircall authentication failed. Re-run aircall-mcp-setup to refresh the authorization."
                logger.info("tool_failed reason=authentication_required")
            elif isinstance(failure, RateLimitedError):
                text = f"Error executing tool {name}: {failure}"
                logger.info("tool_failed reason=rate_limited")
            elif isinstance(failure, TransportError):
                text = f"Error executing tool {name}: {failure}"
                logger.info("tool_failed reason=transport_failure")
            elif isinstance(failure, ReadTransportError):
                text = f"Error executing tool {name}: {failure}"
                logger.info("tool_failed reason=read_transport_failure")
            elif isinstance(failure, NotFoundError):
                text = f"Error executing tool {name}: The requested Aircall resource was not found."
                logger.info("tool_failed reason=not_found")
            elif isinstance(failure, VendorHTTPError):
                text = (
                    f"Error executing tool {name}: Aircall returned HTTP {failure.status_code}: "
                    f"{failure.reason}."
                )
                logger.info("tool_failed reason=upstream_rejected")
            elif isinstance(failure, ArgumentShapeError):
                text = (
                    f"Error executing tool {name}: Argument {failure.argument} must be "
                    f"{failure.expected}."
                )
                logger.info("tool_failed reason=invalid_arguments")
            else:
                # Never include exception text, cause text, or traceback in logs/results.
                text = f"Error executing tool {name}"
                logger.error("tool_failed reason=unexpected")
            return CallToolResult(
                content=[TextContent(type="text", text=text)], is_error=True
            )


def _safe_validation_text(
    server: SafeMCPServer, name: str, error: ValidationError
) -> str:
    tool = server._tool_manager.get_tool(name)
    props = tool.parameters.get("properties", {}) if tool else {}
    parts = []
    for item in error.errors():
        location = item.get("loc", ())
        candidate = str(location[0]) if location else "arguments"
        field = (
            candidate if isinstance(props, dict) and candidate in props else "arguments"
        )
        schema = props.get(field, {}) if isinstance(props, dict) else {}
        shape = _expected_shape(schema)
        parts.append(f"{field} expected {shape}")
    details = (
        "; ".join(dict.fromkeys(parts)) or "arguments did not match the tool schema"
    )
    return f"Error executing tool {name}: Invalid arguments: {details}."


def _expected_shape(schema: dict) -> str:
    if "anyOf" in schema:
        return " or ".join(_expected_shape(option) for option in schema["anyOf"])
    kind = str(schema.get("type", ""))
    if kind == "integer" and "minimum" in schema and "maximum" in schema:
        return f"an integer from {schema['minimum']} to {schema['maximum']}"
    if kind == "integer" and "minimum" in schema:
        return f"an integer of at least {schema['minimum']}"
    return {
        "integer": "an integer",
        "string": "a string",
        "array": "an array",
        "object": "an object",
        "boolean": "a boolean",
        "null": "null",
    }.get(kind, "the documented argument shape")


def _server_version() -> str:
    """Distribution version; a checkout without the dist installed still imports."""
    try:
        return version("aircall-mcp")
    except PackageNotFoundError:
        return getattr(aircall_mcp, "__version__", "0.0.0+local")


mcp = SafeMCPServer(
    "aircall-mcp",
    title="Aircall MCP",
    version=_server_version(),
)

PageNumber = Annotated[
    int,
    Field(ge=1, description="One-based Aircall API page number."),
]
ListLimit = Annotated[
    int,
    Field(
        ge=1,
        le=200,
        description="Maximum number of records returned from the selected API page.",
    ),
]
LegacyPageSize = Annotated[
    int | None,
    Field(
        ge=1,
        le=200,
        deprecated=True,
        description="Deprecated alias for limit.",
    ),
]


def _client() -> AircallClient:
    return AircallClient()


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


@mcp.tool()
def get_company() -> dict:
    """Return Aircall company details including name, plan, and settings."""
    return _client().get_company()


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------


@mcp.tool()
def list_numbers(
    page: PageNumber = 1,
    limit: ListLimit = 25,
    per_page: LegacyPageSize = None,
) -> dict:
    """List phone numbers. limit caps this page; per_page is a deprecated alias."""
    return _client().list_numbers(
        page=page, limit=per_page if per_page is not None else limit
    )


@mcp.tool()
def get_number(number_id: PathId) -> dict:
    """Get details for a specific phone number by its ID."""
    return _client().get_number(number_id)


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


@mcp.tool()
def list_calls(
    page: PageNumber = 1,
    limit: ListLimit = 25,
    number_id: int = 0,
    from_ts: int = 0,
    to_ts: int = 0,
    per_page: LegacyPageSize = None,
) -> dict:
    """List calls. limit caps this page; optionally filter by number or Unix timestamps. per_page is a deprecated alias."""
    return _client().list_calls(
        page=page,
        limit=per_page if per_page is not None else limit,
        number_id=number_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@mcp.tool()
def get_call(call_id: PathId) -> dict:
    """Get full details for a specific call by its ID."""
    return _client().get_call(call_id)


@mcp.tool()
def initiate_call(number_id: int, to: str) -> dict:
    """Initiate an outbound call from an Aircall number to a destination phone number."""
    return _client().initiate_call(number_id=number_id, to=to)


@mcp.tool()
def transfer_call(call_id: PathId, user_id: int = 0, number_id: int = 0) -> dict:
    """Transfer an active call to a user or number. Pass 0 for values that should not be set."""
    return _client().transfer_call(
        call_id=call_id, user_id=user_id, number_id=number_id
    )


@mcp.tool()
def add_call_comment(call_id: PathId, content: str) -> dict:
    """Add a text comment to a call record."""
    return _client().add_call_comment(call_id=call_id, content=content)


@mcp.tool()
def tag_call(call_id: PathId, tag_ids: list) -> dict:
    """Tag a call with one or more tag IDs."""
    return _client().tag_call(call_id=call_id, tag_ids=tag_ids)


@mcp.tool()
def get_call_transcript(call_id: PathId) -> dict:
    """Get the transcript for a call. Requires Aircall AI add-on."""
    return _client().get_call_transcript(call_id)


@mcp.tool()
def get_call_summary(call_id: PathId) -> dict:
    """Get the AI-generated summary for a call."""
    return _client().get_call_summary(call_id)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@mcp.tool()
def list_contacts(
    page: PageNumber = 1,
    limit: ListLimit = 25,
    query: str = "",
    per_page: LegacyPageSize = None,
) -> dict:
    """List contacts. limit caps this page; per_page is a deprecated alias."""
    return _client().list_contacts(
        page=page,
        limit=per_page if per_page is not None else limit,
        query=query,
    )


@mcp.tool()
def get_contact(contact_id: PathId) -> dict:
    """Get a specific contact by its ID."""
    return _client().get_contact(contact_id)


@mcp.tool()
def create_contact(
    first_name: str,
    last_name: str = "",
    phone_numbers: list | None = None,
    emails: list | None = None,
) -> dict:
    """Create a new contact. phone_numbers and emails are optional arrays of objects."""
    return _client().create_contact(
        first_name=first_name,
        last_name=last_name,
        phone_numbers=phone_numbers,
        emails=emails,
    )


@mcp.tool()
def update_contact(
    contact_id: PathId,
    first_name: str = "",
    last_name: str = "",
    phone_numbers: list | None = None,
) -> dict:
    """Update a contact. Only fields with non-empty values are sent. phone_numbers is an optional array of objects."""
    return _client().update_contact(
        contact_id=contact_id,
        first_name=first_name,
        last_name=last_name,
        phone_numbers=phone_numbers,
    )


@mcp.tool()
def delete_contact(contact_id: PathId) -> dict:
    """Delete a contact by its ID."""
    return _client().delete_contact(contact_id)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@mcp.tool()
def list_users(
    page: PageNumber = 1,
    limit: ListLimit = 25,
    per_page: LegacyPageSize = None,
) -> dict:
    """List users. limit caps this page; per_page is a deprecated alias."""
    return _client().list_users(page=page, limit=per_page if per_page else limit)


@mcp.tool()
def get_user(user_id: PathId) -> dict:
    """Get details for a specific user by their ID."""
    return _client().get_user(user_id)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


@mcp.tool()
def list_teams(
    page: PageNumber = 1,
    limit: ListLimit = 25,
    per_page: LegacyPageSize = None,
) -> dict:
    """List teams. limit caps this page; per_page is a deprecated alias."""
    return _client().list_teams(page=page, limit=per_page if per_page else limit)


@mcp.tool()
def get_team(team_id: PathId) -> dict:
    """Get details for a specific team by its ID."""
    return _client().get_team(team_id)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tags(limit: ListLimit = 25) -> dict:
    """List call tags, capped at limit records."""
    return _client().list_tags(limit=limit)


@mcp.tool()
def create_tag(name: str, color: str = "") -> dict:
    """Create a new call tag. color is optional (leave empty to omit)."""
    return _client().create_tag(name=name, color=color)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("aircall://numbers", mime_type="application/json")
def numbers_resource() -> str:
    """Up to 100 phone numbers in this Aircall account — read-only reference data."""
    try:
        return json.dumps(_client().list_numbers(limit=100), indent=2)
    except (
        MissingCredentialsError,
        AuthorizationError,
        AuthenticationError,
        RateLimitedError,
        TransportError,
        ReadTransportError,
        NotFoundError,
        VendorHTTPError,
    ) as exc:
        raise ResourceError(str(exc)) from None
    except Exception:
        raise ResourceError(
            "Unable to read this Aircall resource. Try again or check the connection."
        ) from None


@mcp.resource("aircall://tags", mime_type="application/json")
def tags_resource() -> str:
    """Up to 200 call tags in this Aircall account — read-only reference data."""
    try:
        return json.dumps(_client().list_tags(limit=200), indent=2)
    except (
        MissingCredentialsError,
        AuthorizationError,
        AuthenticationError,
        RateLimitedError,
        TransportError,
        ReadTransportError,
        NotFoundError,
        VendorHTTPError,
    ) as exc:
        raise ResourceError(str(exc)) from None
    except Exception:
        raise ResourceError(
            "Unable to read this Aircall resource. Try again or check the connection."
        ) from None


@mcp.resource("aircall://security-notes", mime_type="text/markdown")
def security_notes_resource() -> str:
    """Security posture for aircall-mcp.

    ## Credentials
    - **AIRCALL_API_ID** and **AIRCALL_API_TOKEN**: Aircall API key pair (Basic Auth).
      They come from the server's own configuration, never from the client or a request.
    - Read order: process environment, then the OS keyring (macOS Keychain, Windows
      Credential Manager, Linux Secret Service), then `~/.aircall-mcp/.env`.
    - `aircall-mcp-setup` stores them in the OS keyring. The `.env` file (mode 0600) is
      used only when no keyring is available or `AIRCALL_MCP_USE_KEYRING=0`.

    ## Transport
    - stdio is the default.
    - Opt-in stateless Streamable HTTP (`AIRCALL_MCP_TRANSPORT=streamable-http`, endpoint
      `/mcp`) has no authentication and no TLS. Anyone who can reach the port can run
      every tool, including write and delete tools, with this server's Aircall credentials.
    - Keep the default loopback bind (`127.0.0.1`), or put the server behind an
      authenticating TLS proxy on a private network.
    - `AIRCALL_MCP_ALLOWED_HOSTS` and `AIRCALL_MCP_ALLOWED_ORIGINS` protect against browser
      DNS rebinding, not against direct callers. A non-loopback `AIRCALL_MCP_HOST` requires
      `AIRCALL_MCP_ALLOWED_HOSTS`.

    ## Tool classification
    - **Read-only (safe):** get_company, list_numbers, get_number, list_calls, get_call,
      get_call_transcript, get_call_summary, list_contacts, get_contact, list_users,
      get_user, list_teams, get_team, list_tags.
    - **Write / side-effect:** initiate_call, transfer_call, add_call_comment, tag_call,
      create_contact, update_contact, delete_contact, create_tag.

    ## Data sensitivity
    Calls, transcripts, and contacts may contain privileged attorney-client communications.
    Handle with legal-privilege care; do not log or cache call content outside the firm's
    approved systems.
    """
    return security_notes_resource.__doc__ or ""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def missed_call_follow_up() -> str:
    """Review missed calls and draft follow-up tasks for each one."""
    return """You are a legal intake coordinator. A missed call from a prospective client
can mean a lost case. Work through these steps:

1. Call list_calls with status filter or review recent calls — identify any with
   missed/voicemail status (check the 'status' or 'missed_call' field).
2. For each missed call: call get_call to get full details including caller number.
3. Search list_contacts for the caller number to find an existing contact record.
4. If no contact found: note this as a new potential client.
5. Use add_call_comment on each missed call to log the follow-up action taken
   (e.g. "Voicemail left 2026-06-10; follow-up call scheduled").
6. Tag each missed call using tag_call with the appropriate follow-up tag.
7. Output a summary: caller, time, contact found (yes/no), action logged."""


@mcp.prompt()
def call_review(call_id: str) -> str:
    """Full review of a specific call: transcript, summary, and recommended actions."""
    return f"""Review call {call_id} thoroughly:

1. Call get_call({call_id}) — capture caller, number used, duration, direction.
2. Call get_call_transcript({call_id}) — read the full transcript.
3. Call get_call_summary({call_id}) — read the AI summary.
4. Identify: was this a new client inquiry, existing client matter, or vendor call?
5. If new inquiry: check list_contacts for the caller; recommend create_contact if absent.
6. Flag any action items from the call content (deadlines mentioned, promises made,
   next steps agreed).
7. Use add_call_comment to log a one-paragraph summary of findings and next actions."""


@mcp.prompt()
def team_call_report() -> str:
    """Daily call volume and team activity summary across all numbers."""
    return """Generate a daily call report for the legal team:

1. Call list_numbers — get all active Aircall numbers and their labels.
2. For each number: call list_calls filtered to today (use from_ts/to_ts for today's
   Unix timestamps) — count total, answered, missed.
3. Call list_teams — identify which teams handle which numbers.
4. Call get_call_statistics equivalent by aggregating: total calls, total missed,
   total duration across all numbers today.
5. Output a table: Number | Label | Total Calls | Missed | Avg Duration.
6. Highlight any number with missed rate > 20% — flag for staffing review."""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


STREAMABLE_HTTP_TRANSPORT = "streamable-http"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _requested_transport() -> str:
    return os.environ.get("AIRCALL_MCP_TRANSPORT", "stdio").strip().lower() or "stdio"


def _host() -> str:
    return os.environ.get("AIRCALL_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"


def _port() -> int:
    raw = os.environ.get("PORT", "8080").strip()
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"PORT must be an integer, got {raw!r}") from None


def _csv_env(name: str) -> list[str]:
    return [
        item.strip() for item in os.environ.get(name, "").split(",") if item.strip()
    ]


def _transport_security() -> TransportSecuritySettings | None:
    """Origin checks are required off loopback; the SDK covers loopback itself."""
    host = _host()
    if host in _LOOPBACK_HOSTS:
        return None
    allowed_hosts = _csv_env("AIRCALL_MCP_ALLOWED_HOSTS")
    if not allowed_hosts:
        raise SystemExit(
            "AIRCALL_MCP_ALLOWED_HOSTS must be set to a comma-separated host list "
            f"when AIRCALL_MCP_HOST is {host!r}"
        )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=_csv_env("AIRCALL_MCP_ALLOWED_ORIGINS"),
    )


def create_serve_app():
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        host=_host(),
        stateless_http=True,
        transport_security=_transport_security(),
    )


async def _serve_streamable_http() -> None:
    import uvicorn

    config = uvicorn.Config(
        create_serve_app(),
        host=_host(),
        port=_port(),
        access_log=False,
    )
    await uvicorn.Server(config).serve()


def main():
    transport = _requested_transport()
    if transport == "stdio":
        mcp.run()
        return
    if transport == STREAMABLE_HTTP_TRANSPORT:
        asyncio.run(_serve_streamable_http())
        return
    raise SystemExit(
        "Unsupported AIRCALL_MCP_TRANSPORT "
        f"{transport!r}; expected 'stdio' or '{STREAMABLE_HTTP_TRANSPORT}'."
    )


if __name__ == "__main__":
    main()
