#!/usr/bin/env python3
import base64
import logging
import os
import sys
import time

import requests

from aircall_mcp import credentials

BASE_URL = "https://api.aircall.io/v1"
logger = logging.getLogger(__name__)


def _retry_after_seconds(resp, default=10):
    try:
        return int(resp.headers.get("Retry-After", default))
    except (TypeError, ValueError):
        return default


def _json_response(resp):
    try:
        return resp.json()
    except ValueError:
        logger.warning(
            "aircall_request_rejected reason=upstream_non_json status_code=%s",
            resp.status_code,
        )
        raise RuntimeError(f"Aircall API returned non-JSON ({resp.status_code})")


def _cap_collection(response, key: str, limit: int):
    """Defensively cap a list response even if the upstream API over-returns."""
    if not isinstance(response, dict) or not isinstance(response.get(key), list):
        return response
    capped = dict(response)
    capped[key] = response[key][:limit]
    return capped


class AircallClient:
    def __init__(self):
        # Resolve only when a client is needed; importing the MCP server must not
        # consult keyring or the fallback credential file.
        credentials.load_into_environ(["AIRCALL_API_ID", "AIRCALL_API_TOKEN"])
        api_id = os.environ.get("AIRCALL_API_ID", "")
        api_token = os.environ.get("AIRCALL_API_TOKEN", "")
        if not api_id or not api_token:
            logger.warning("aircall_request_rejected reason=credentials_missing")
            raise RuntimeError("Aircall credentials not found. Run: aircall-mcp-setup")
        basic_auth = base64.b64encode(f"{api_id}:{api_token}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(self, method, path, params=None, json_body=None, _rate_retries=0):
        url = f"{BASE_URL}/{path.lstrip('/')}"
        resp = self.session.request(method, url, params=params, json=json_body)
        if resp.status_code == 401:
            logger.warning(
                "aircall_request_rejected reason=upstream_unauthorized status_code=401"
            )
            raise RuntimeError("Aircall credentials invalid. Run: aircall-mcp-setup")
        if resp.status_code == 429 and _rate_retries < 3:
            wait = _retry_after_seconds(resp)
            print(f"Rate limited. Waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            return self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                _rate_retries=_rate_retries + 1,
            )
        if resp.status_code == 204:
            return {"success": True}
        if not resp.ok:
            logger.warning(
                "aircall_request_rejected reason=upstream_error status_code=%s",
                resp.status_code,
            )
            raise RuntimeError(f"Aircall API error {resp.status_code}")
        return _json_response(resp)

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, body=None):
        return self._request("POST", path, json_body=body)

    def patch(self, path, body=None):
        return self._request("PATCH", path, json_body=body)

    def delete(self, path):
        return self._request("DELETE", path)

    # -------------------------------------------------------------------------
    # Company
    # -------------------------------------------------------------------------

    def get_company(self):
        """Return company details."""
        return self.get("/company")

    # -------------------------------------------------------------------------
    # Numbers
    # -------------------------------------------------------------------------

    def list_numbers(self, page=1, limit=25):
        """List one page of phone numbers, capped at limit records."""
        response = self.get("/numbers", params={"page": page, "per_page": limit})
        return _cap_collection(response, "numbers", limit)

    def get_number(self, number_id):
        """Get a specific phone number by ID."""
        return self.get(f"/numbers/{number_id}")

    # -------------------------------------------------------------------------
    # Calls
    # -------------------------------------------------------------------------

    def list_calls(self, page=1, limit=25, number_id=0, from_ts=0, to_ts=0):
        """List calls. Filters number_id, from, to are only sent if non-zero."""
        params = {"page": page, "per_page": limit}
        if number_id:
            params["number_id"] = number_id
        if from_ts:
            params["from"] = from_ts
        if to_ts:
            params["to"] = to_ts
        response = self.get("/calls", params=params)
        return _cap_collection(response, "calls", limit)

    def get_call(self, call_id):
        """Get a specific call by ID."""
        return self.get(f"/calls/{call_id}")

    def initiate_call(self, number_id, to):
        """Initiate an outbound call from a number to a destination."""
        return self.post("/calls", body={"number_id": number_id, "to": to})

    def transfer_call(self, call_id, user_id=0, number_id=0):
        """Transfer an active call. Only non-zero user_id/number_id are sent."""
        body = {}
        if user_id:
            body["user_id"] = user_id
        if number_id:
            body["number_id"] = number_id
        return self.post(f"/calls/{call_id}/transfers", body=body)

    def add_call_comment(self, call_id, content):
        """Add a comment to a call."""
        return self.post(f"/calls/{call_id}/comments", body={"content": content})

    def tag_call(self, call_id, tag_ids):
        """Tag a call with a list of tag IDs."""
        if not isinstance(tag_ids, list):
            logger.warning("aircall_request_rejected reason=tag_ids_not_list")
            raise ValueError("tag_ids must be a list of tag IDs")
        return self.post(f"/calls/{call_id}/tags", body={"tag_ids": tag_ids})

    def get_call_transcript(self, call_id):
        """Get the transcript for a call. Requires Aircall AI add-on."""
        return self.get(f"/calls/{call_id}/transcript")

    def get_call_summary(self, call_id):
        """Get the AI-generated summary for a call."""
        return self.get(f"/calls/{call_id}/summary")

    # -------------------------------------------------------------------------
    # Contacts
    # -------------------------------------------------------------------------

    def list_contacts(self, page=1, limit=25, query=""):
        """List contacts. Sends search param only if query is non-empty."""
        params: dict[str, int | str] = {"page": page, "per_page": limit}
        if query:
            params["search"] = query
        response = self.get("/contacts", params=params)
        return _cap_collection(response, "contacts", limit)

    def get_contact(self, contact_id):
        """Get a specific contact by ID."""
        return self.get(f"/contacts/{contact_id}")

    def create_contact(
        self,
        first_name: str,
        last_name: str = "",
        phone_numbers: list | None = None,
        emails: list | None = None,
    ):
        """Create a contact. phone_numbers and emails are optional lists."""
        body: dict[str, str | list] = {"first_name": first_name}
        if last_name:
            body["last_name"] = last_name
        if phone_numbers:
            if not isinstance(phone_numbers, list):
                logger.warning("aircall_request_rejected reason=phone_numbers_not_list")
                raise ValueError("phone_numbers must be a list")
            body["phone_numbers"] = phone_numbers
        if emails:
            if not isinstance(emails, list):
                logger.warning("aircall_request_rejected reason=emails_not_list")
                raise ValueError("emails must be a list")
            body["emails"] = emails
        return self.post("/contacts", body=body)

    def update_contact(
        self,
        contact_id,
        first_name: str = "",
        last_name: str = "",
        phone_numbers: list | None = None,
    ):
        """Update a contact. Only non-empty fields are sent."""
        body: dict[str, str | list] = {}
        if first_name:
            body["first_name"] = first_name
        if last_name:
            body["last_name"] = last_name
        if phone_numbers:
            if not isinstance(phone_numbers, list):
                logger.warning("aircall_request_rejected reason=phone_numbers_not_list")
                raise ValueError("phone_numbers must be a list")
            body["phone_numbers"] = phone_numbers
        return self.patch(f"/contacts/{contact_id}", body=body)

    def delete_contact(self, contact_id):
        """Delete a contact by ID."""
        return self.delete(f"/contacts/{contact_id}")

    # -------------------------------------------------------------------------
    # Users
    # -------------------------------------------------------------------------

    def list_users(self, page=1, limit=25):
        """List one page of users, capped at limit records."""
        response = self.get("/users", params={"page": page, "per_page": limit})
        return _cap_collection(response, "users", limit)

    def get_user(self, user_id):
        """Get a specific user by ID."""
        return self.get(f"/users/{user_id}")

    # -------------------------------------------------------------------------
    # Teams
    # -------------------------------------------------------------------------

    def list_teams(self, page=1, limit=25):
        """List one page of teams, capped at limit records."""
        response = self.get("/teams", params={"page": page, "per_page": limit})
        return _cap_collection(response, "teams", limit)

    def get_team(self, team_id):
        """Get a specific team by ID."""
        return self.get(f"/teams/{team_id}")

    # -------------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------------

    def list_tags(self, limit=25):
        """List tags, capped locally at limit records."""
        response = self.get("/tags")
        return _cap_collection(response, "tags", limit)

    def create_tag(self, name, color=""):
        """Create a tag. color is only included if non-empty."""
        body = {"name": name}
        if color:
            body["color"] = color
        return self.post("/tags", body=body)
