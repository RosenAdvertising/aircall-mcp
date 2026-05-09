#!/usr/bin/env python3
"""Aircall MCP server — calls, contacts, transcripts, numbers, and team management."""

from mcp.server.fastmcp import FastMCP
from aircall_mcp.client import AircallClient

mcp = FastMCP("aircall-mcp")


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
def list_numbers(page: int = 1, per_page: int = 25) -> dict:
    """List all phone numbers configured in the Aircall account."""
    return _client().list_numbers(page=page, per_page=per_page)


@mcp.tool()
def get_number(number_id: int) -> dict:
    """Get details for a specific phone number by its ID."""
    return _client().get_number(number_id)


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------


@mcp.tool()
def list_calls(
    page: int = 1,
    per_page: int = 25,
    number_id: int = 0,
    from_ts: int = 0,
    to_ts: int = 0,
) -> dict:
    """List calls. Optionally filter by number_id (int), from_ts and to_ts (Unix timestamps). Pass 0 to omit a filter."""
    return _client().list_calls(
        page=page,
        per_page=per_page,
        number_id=number_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@mcp.tool()
def get_call(call_id: int) -> dict:
    """Get full details for a specific call by its ID."""
    return _client().get_call(call_id)


@mcp.tool()
def initiate_call(number_id: int, to: str) -> dict:
    """Initiate an outbound call from an Aircall number to a destination phone number."""
    return _client().initiate_call(number_id=number_id, to=to)


@mcp.tool()
def transfer_call(call_id: int, user_id: int = 0, number_id: int = 0) -> dict:
    """Transfer an active call to a user or number. Pass 0 for values that should not be set."""
    return _client().transfer_call(
        call_id=call_id, user_id=user_id, number_id=number_id
    )


@mcp.tool()
def add_call_comment(call_id: int, content: str) -> dict:
    """Add a text comment to a call record."""
    return _client().add_call_comment(call_id=call_id, content=content)


@mcp.tool()
def tag_call(call_id: int, tag_ids_json: str) -> dict:
    """Tag a call with one or more tag IDs. tag_ids_json must be a JSON array of integers, e.g. '[1, 2, 3]'."""
    return _client().tag_call(call_id=call_id, tag_ids_json=tag_ids_json)


@mcp.tool()
def get_call_transcript(call_id: int) -> dict:
    """Get the transcript for a call. Requires Aircall AI add-on."""
    return _client().get_call_transcript(call_id)


@mcp.tool()
def get_call_summary(call_id: int) -> dict:
    """Get the AI-generated summary for a call."""
    return _client().get_call_summary(call_id)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@mcp.tool()
def list_contacts(page: int = 1, per_page: int = 25, query: str = "") -> dict:
    """List contacts. Optionally pass a search query string to filter results."""
    return _client().list_contacts(page=page, per_page=per_page, query=query)


@mcp.tool()
def get_contact(contact_id: int) -> dict:
    """Get a specific contact by its ID."""
    return _client().get_contact(contact_id)


@mcp.tool()
def create_contact(
    first_name: str,
    last_name: str = "",
    phone_numbers_json: str = "",
    emails_json: str = "",
) -> dict:
    """Create a new contact. phone_numbers_json and emails_json are JSON arrays of objects, e.g. '[{"label":"work","value":"+1555..."}]'. Leave empty to omit."""
    return _client().create_contact(
        first_name=first_name,
        last_name=last_name,
        phone_numbers_json=phone_numbers_json,
        emails_json=emails_json,
    )


@mcp.tool()
def update_contact(
    contact_id: int,
    first_name: str = "",
    last_name: str = "",
    phone_numbers_json: str = "",
) -> dict:
    """Update a contact. Only fields with non-empty values are sent. phone_numbers_json is a JSON array of objects."""
    return _client().update_contact(
        contact_id=contact_id,
        first_name=first_name,
        last_name=last_name,
        phone_numbers_json=phone_numbers_json,
    )


@mcp.tool()
def delete_contact(contact_id: int) -> dict:
    """Delete a contact by its ID."""
    return _client().delete_contact(contact_id)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@mcp.tool()
def list_users(page: int = 1, per_page: int = 25) -> dict:
    """List all users in the Aircall account."""
    return _client().list_users(page=page, per_page=per_page)


@mcp.tool()
def get_user(user_id: int) -> dict:
    """Get details for a specific user by their ID."""
    return _client().get_user(user_id)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


@mcp.tool()
def list_teams(page: int = 1, per_page: int = 25) -> dict:
    """List all teams in the Aircall account."""
    return _client().list_teams(page=page, per_page=per_page)


@mcp.tool()
def get_team(team_id: int) -> dict:
    """Get details for a specific team by its ID."""
    return _client().get_team(team_id)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tags() -> dict:
    """List all call tags defined in the Aircall account."""
    return _client().list_tags()


@mcp.tool()
def create_tag(name: str, color: str = "") -> dict:
    """Create a new call tag. color is optional (leave empty to omit)."""
    return _client().create_tag(name=name, color=color)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    mcp.run()


if __name__ == "__main__":
    main()
