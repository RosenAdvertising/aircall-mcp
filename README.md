# aircall-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](https://opensource.org/licenses/MIT)
[![22 tools](https://img.shields.io/badge/tools-22-22C55E.svg)](https://github.com/RosenAdvertising/aircall-mcp)
[![MCP](https://img.shields.io/badge/MCP-compatible-7C3AED.svg)](https://modelcontextprotocol.io)
[![Aircall](https://img.shields.io/badge/Aircall-API-00BC70.svg)](https://developer.aircall.io)

MCP server for Aircall — calls, contacts, transcripts, numbers, and team management for law firms.

## Requirements

- Python 3.10+
- Aircall account with API access

## Installation

```bash
pip install -e .
```

## Setup

```bash
aircall-mcp-setup
```

Prompts for your API ID and API Token, stores them securely, then verifies the connection.

Find credentials at: **aircall.io → Admin → API Keys → Own API Key integration**

### Credential storage

By default credentials are stored in your operating system's native secret store
via the cross-platform [`keyring`](https://github.com/jaraco/keyring) library:

| OS      | Backend                                  |
| ------- | ---------------------------------------- |
| macOS   | Keychain                                 |
| Windows | Credential Manager                       |
| Linux   | Secret Service (GNOME Keyring / KWallet) |

Secrets are saved under the service name `aircall-mcp`. Nothing is written to
disk in clear text.

**File fallback.** On a host with no keyring backend (e.g. a headless Linux box
without Secret Service), or if you set `AIRCALL_MCP_USE_KEYRING=0`, credentials
fall back to a `~/.aircall-mcp/.env` file with `0600` permissions.

**Read order.** Credentials resolve in the order OS keyring → process environment
→ `.env` file. So a rotated secret in the keyring always wins, and an
`AIRCALL_API_ID` / `AIRCALL_API_TOKEN` exported in your shell overrides the file
fallback without touching the keyring.

**Pluggable backend.** `keyring` lets you point at any secret store. For example,
install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for
an encrypted file backend, or a cloud backend, then select it with the standard
`PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the
[keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Verify credentials

```bash
aircall-mcp-verify
```

## Running the server

```bash
aircall-mcp
```

## Claude Desktop config

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aircall": {
      "command": "aircall-mcp"
    }
  }
}
```

## Tools (22 total)

| Tool                  | Description                              |
| --------------------- | ---------------------------------------- |
| `get_company`         | Company details                          |
| `list_numbers`        | List phone numbers                       |
| `get_number`          | Get number by ID                         |
| `list_calls`          | List calls with optional filters         |
| `get_call`            | Get call by ID                           |
| `initiate_call`       | Start an outbound call                   |
| `transfer_call`       | Transfer an active call                  |
| `add_call_comment`    | Add comment to a call                    |
| `tag_call`            | Tag a call with tag IDs                  |
| `get_call_transcript` | Get call transcript (requires AI add-on) |
| `get_call_summary`    | Get AI call summary                      |
| `list_contacts`       | List contacts with optional search       |
| `get_contact`         | Get contact by ID                        |
| `create_contact`      | Create a new contact                     |
| `update_contact`      | Update a contact                         |
| `delete_contact`      | Delete a contact                         |
| `list_users`          | List account users                       |
| `get_user`            | Get user by ID                           |
| `list_teams`          | List teams                               |
| `get_team`            | Get team by ID                           |
| `list_tags`           | List call tags                           |
| `create_tag`          | Create a new tag                         |

## Auth

HTTP Basic Auth using `AIRCALL_API_ID:AIRCALL_API_TOKEN`, base64-encoded.
Credentials are resolved at import time through the pluggable store described in
[Credential storage](#credential-storage) (OS keyring first, `.env` file fallback).
