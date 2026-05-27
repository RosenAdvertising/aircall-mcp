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

Prompts for your API ID and API Token, saves to `~/.aircall-mcp/.env`, then verifies the connection.

Find credentials at: **aircall.io → Admin → API Keys → Own API Key integration**

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
Credentials loaded from `~/.aircall-mcp/.env` at import time.
