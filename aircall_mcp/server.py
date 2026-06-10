#!/usr/bin/env python3
"""Aircall MCP server — calls, contacts, transcripts, numbers, and team management."""

import json

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
def tag_call(call_id: int, tag_ids: list) -> dict:
    """Tag a call with one or more tag IDs."""
    return _client().tag_call(call_id=call_id, tag_ids=tag_ids)


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
    contact_id: int,
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
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("aircall://numbers", mime_type="application/json")
def numbers_resource() -> str:
    """All phone numbers configured in this Aircall account — read-only reference data."""
    return json.dumps(_client().list_numbers(per_page=100), indent=2)


@mcp.resource("aircall://tags", mime_type="application/json")
def tags_resource() -> str:
    """All call tags defined in this Aircall account — read-only reference data."""
    return json.dumps(_client().list_tags(), indent=2)


@mcp.resource("aircall://security-notes", mime_type="text/markdown")
def security_notes_resource() -> str:
    """Security posture for aircall-mcp.

    ## Credentials
    - **AIRCALL_API_ID** and **AIRCALL_API_TOKEN**: Aircall API key pair (Basic Auth).
    - Resolution order: OS keyring (macOS Keychain / libsecret) → process env →
      `~/.aircall-mcp/.env` (chmod 0600 fallback). Set via `aircall-mcp-setup`.

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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
