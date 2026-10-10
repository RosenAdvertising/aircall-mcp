# Aircall MCP server

[![CI](https://github.com/RosenAdvertising/aircall-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/RosenAdvertising/aircall-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-7C3AED.svg)](https://modelcontextprotocol.io)

Connect Claude and other MCP clients to Aircall to work with calls, transcripts, contacts, numbers and teams.

Aircall MCP server is a [Model Context Protocol](https://modelcontextprotocol.io) server for [Aircall](https://aircall.io), the cloud phone system. It registers 22 tools that read and write Aircall data. It runs over stdio by default, for desktop clients such as Claude Desktop, and offers an opt-in stateless Streamable HTTP mode that implements MCP specification 2026-07-28. Aircall credentials stay on the machine that runs the server: they come from the setup command and your operating system's keyring, or from environment variables, never from the client.

## Features

- **Calls**: list and look up calls, start outbound calls, transfer active calls, add comments and tag calls.
- **Transcripts and summaries**: read call transcripts (which need the Aircall AI add-on) and AI call summaries.
- **Contacts**: list, search, create, update and delete contacts.
- **Numbers**: list phone numbers and look up a number by ID.
- **Users and teams**: list and look up users and teams.
- **Tags**: list call tags and create new ones.
- **Company**: read company details.

## Tools

The server registers 22 tools.

| Tool | What it does |
| --- | --- |
| `get_company` | Company details |
| `list_numbers` | List phone numbers |
| `get_number` | Get number by ID |
| `list_calls` | List calls with optional filters |
| `get_call` | Get call by ID |
| `initiate_call` | Start an outbound call |
| `transfer_call` | Transfer an active call |
| `add_call_comment` | Add comment to a call |
| `tag_call` | Tag a call with tag IDs |
| `get_call_transcript` | Get call transcript (requires AI add-on) |
| `get_call_summary` | Get AI call summary |
| `list_contacts` | List contacts with optional search |
| `get_contact` | Get contact by ID |
| `create_contact` | Create a new contact |
| `update_contact` | Update a contact |
| `delete_contact` | Delete a contact |
| `list_users` | List account users |
| `get_user` | Get user by ID |
| `list_teams` | List teams |
| `get_team` | Get team by ID |
| `list_tags` | List call tags |
| `create_tag` | Create a new tag |

### Prompts and resources

The server also registers three prompts and three read-only resources.

| Prompt | What it does |
| --- | --- |
| `call_review` | Full review of a specific call: transcript, summary and recommended actions. Takes a `call_id`. |
| `missed_call_follow_up` | Review missed calls and draft follow-up tasks for each one. |
| `team_call_report` | Daily call volume and team activity summary across all numbers. |

| Resource | What it holds |
| --- | --- |
| `aircall://numbers` | Up to 100 phone numbers in your Aircall account. |
| `aircall://tags` | Up to 200 call tags in your Aircall account. |
| `aircall://security-notes` | Security notes for this server, as Markdown. |

## Requirements

- Python 3.10 or later
- An Aircall account with API access: an API ID and an API Token
- An MCP client such as Claude Desktop

## Installation

Install [uv](https://docs.astral.sh/uv/), then clone the repository and install its locked dependencies:

```bash
git clone https://github.com/RosenAdvertising/aircall-mcp.git
cd aircall-mcp
uv sync --locked
```

## Configuration

Run the guided setup from your clone of the repository:

```bash
uv run --locked aircall-mcp-setup
```

Setup prompts for your Aircall API ID and API Token, stores them (see [Credential storage](#credential-storage)), and then verifies the connection by reading your Aircall company details. Find your credentials at **aircall.io → Admin → API Keys → Own API Key integration**.

To verify again later:

```bash
uv run --locked aircall-mcp-verify
```

The server reads these environment variables. A variable set in the process environment takes precedence over a stored value.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `AIRCALL_API_ID` | Yes | Stored value from setup | Aircall API ID. |
| `AIRCALL_API_TOKEN` | Yes | Stored value from setup | Aircall API token. Sent with the API ID as HTTP Basic authentication. |
| `AIRCALL_MCP_USE_KEYRING` | No | `1` | Set to `0` (or `false`, `no`, `off`) to skip the OS keyring and use the `.env` file fallback. |

## Usage with Claude Desktop

Add the server to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "aircall": {
      "command": "uv",
      "args": ["run", "--locked", "--directory", "/absolute/path/to/aircall-mcp", "aircall-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/aircall-mcp` with the path of your clone. Restart Claude Desktop after saving. Any other stdio MCP client uses the same command and arguments.

## HTTP mode

Stdio is the default. Set `AIRCALL_MCP_TRANSPORT=streamable-http` to serve the stateless Streamable HTTP transport from MCP specification 2026-07-28 at `/mcp`. Each request stands alone: no initialization handshake and no `Mcp-Session-Id`. Clients on earlier protocol versions are served on the same endpoint.

> **Security: this endpoint has no authentication and no TLS.** Anyone who can reach the port can run every tool, including write and delete tools, with this server's vendor credentials. Keep the default loopback bind (`127.0.0.1`), or put the server behind an authenticating TLS proxy on a private network. `AIRCALL_MCP_ALLOWED_HOSTS` and `AIRCALL_MCP_ALLOWED_ORIGINS` protect against browser DNS rebinding, not against direct callers. A proxy in front of it needs connection and idle timeouts: a legacy-style `GET /mcp` with `Accept: text/event-stream` holds a stream open until the client disconnects.

| Variable | Default | Purpose |
| --- | --- | --- |
| `AIRCALL_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. A set but empty value selects `stdio`. |
| `AIRCALL_MCP_HOST` | `127.0.0.1` | Bind address. `127.0.0.1`, `localhost` and `::1` use the SDK's built-in Host and Origin checks; any other value requires `AIRCALL_MCP_ALLOWED_HOSTS`. |
| `PORT` | `8080` | Port; must be an integer. |
| `AIRCALL_MCP_ALLOWED_HOSTS` | unset | Comma-separated `Host` header values accepted on a non-loopback bind, such as `mcp.example.com:8080` or `mcp.example.com:*`. |
| `AIRCALL_MCP_ALLOWED_ORIGINS` | unset | Comma-separated `Origin` values accepted on a non-loopback bind, such as `https://client.example.com`. Requests without an `Origin` header are accepted; with this unset on a non-loopback bind, a request that carries an `Origin` header is rejected. |

Aircall credentials come from the same configuration as stdio (see [Configuration](#configuration)), never from the request.

```bash
AIRCALL_MCP_TRANSPORT=streamable-http PORT=8080 uv run --locked aircall-mcp
```

Point the MCP client at `http://127.0.0.1:8080/mcp`.

## Error handling

A failed tool call returns an MCP error result (`isError`) with a fixed message that starts with `Error executing tool <name>: `. The server never passes an Aircall response body, a request URL or a credential back to the client.

| Situation | What the tool returns |
| --- | --- |
| Credentials missing | "Aircall credentials are missing. Set AIRCALL_API_ID and AIRCALL_API_TOKEN or run aircall-mcp-setup." |
| HTTP 401 | "Aircall authentication failed. Re-run aircall-mcp-setup to refresh the authorization." |
| HTTP 403 | "Aircall access denied: the connected account lacks permission for this action (or the authorization expired; re-run aircall-mcp-setup if so)." |
| HTTP 404 | "The requested Aircall resource was not found." |
| HTTP 429 | "Aircall rate limit reached. Retry after about N seconds." N comes from the `Retry-After` header; without a usable header the message ends "Retry later." |
| Other HTTP error statuses | "Aircall returned HTTP 500: internal server error." The reason is one fixed phrase chosen from the error code in the Aircall response: invalid request, invalid credentials, insufficient permissions, resource not found, service unavailable or internal server error; any other or missing code gives "request rejected". A success response that is not valid JSON gives "Aircall returned HTTP 200: invalid JSON response." |
| Timeout or connection failure on a read | "Aircall read request did not complete. You may retry the read." |
| Timeout or connection failure on a write | "Aircall request outcome is unknown. Check whether the operation completed before retrying." |
| Invalid arguments | A message such as "Invalid arguments: limit expected an integer from 1 to 200." or "Argument tag_ids must be an array of tag IDs." |
| Anything else | `Error executing tool <name>` with no detail. |

Every Aircall request has a 30-second timeout. The server does not retry failed requests: it returns the message above and leaves any retry to you.

Missing credentials do not stop the server from starting: each tool call reports them. At startup the server exits with a message and a non-zero status when `AIRCALL_MCP_TRANSPORT` is neither `stdio` nor `streamable-http`, when `PORT` is not an integer, or when a non-loopback `AIRCALL_MCP_HOST` is set without `AIRCALL_MCP_ALLOWED_HOSTS`.

## Credential storage

By default credentials are stored in your operating system's native secret store
via the cross-platform [`keyring`](https://github.com/jaraco/keyring) library:

| OS      | Backend                                  |
| ------- | ---------------------------------------- |
| macOS   | Keychain                                 |
| Windows | Credential Manager                       |
| Linux   | Secret Service (GNOME Keyring / KWallet) |

Secrets are saved under the service name `aircall-mcp`. With a working keyring backend, credentials are not written to the file fallback.

**File fallback.** On a host with no keyring backend (e.g. a headless Linux box
without Secret Service), or if you set `AIRCALL_MCP_USE_KEYRING=0`, credentials
fall back to a `~/.aircall-mcp/.env` file with `0600` permissions.

On Windows, the file is stored in the user's profile and protected by Windows'
default per-user access rules. On POSIX, files are created with `0600` permissions
and writes fail closed if private permissions cannot be established.

**Read order.** A credential already present in the server process environment takes precedence. Otherwise the client checks the OS keyring, then the `.env` file. If you change credentials after the server has loaded them, restart the MCP server to reload the new values.

**Pluggable backend.** `keyring` lets you point at any secret store. For example,
install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for
an encrypted file backend, or a cloud backend, then select it with the standard
`PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the
[keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Auth

HTTP Basic authentication using `AIRCALL_API_ID:AIRCALL_API_TOKEN`, base64-encoded. The server resolves the credentials the first time a tool needs a client: from the process environment, then the OS keyring, then the `.env` file (see [Credential storage](#credential-storage)).

## Testing

The test suite runs offline and needs no Aircall account: Aircall API calls are replaced with test doubles. It covers the error messages tools return, argument validation, page and limit controls, path identifier handling, credential loading and private file storage, logs that omit call data, the MCP transport boundary, MCP specification 2026-07-28 behavior, and the Streamable HTTP transport including Host and Origin checks and stateless requests.

```bash
uv sync --locked
uv run --locked pytest -q
```

CI runs the suite on every push and pull request to `main`.

The tools follow Aircall's [published API documentation](https://developer.aircall.io) and have not yet been run against a live Aircall account.

## License

MIT. See [LICENSE](LICENSE).
