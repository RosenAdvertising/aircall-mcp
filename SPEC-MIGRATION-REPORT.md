# MCP 2026-07-28 migration

Aircall MCP targets protocol revision `2026-07-28` with Python SDK requirement
`mcp>=2.2,<3`. The current `uv.lock` resolves both `mcp` and its companion
`mcp-types` to `2.2.0`. The server uses SDK 2 `MCPServer` and continues to run
through stdio. See [the protocol delta](SPEC-DELTA-2026-07-28.md) for the
Aircall-specific mapping of specification changes.

## Behavior

- The SDK provides modern `server/discover`, per-request metadata, required
  result and cache fields, and legacy client negotiation. Tools, prompts, and
  resources keep their existing application behavior.
- Aircall publishes 22 tools, three prompts, and three resources. Tool lists
  retain registration order. Dictionary tool results remain JSON text content.
- Cache metadata is conservative: `ttlMs: 0` and `cacheScope: private`.
  The application does not add a response cache.
- The six list tools accept `limit` from 1 through 200; the five paged tools
  require `page >= 1` and retain bounded `per_page` as a deprecated alias.
  Responses are capped locally. Aircall ordering and live endpoint behavior
  have not been verified against a live account.
- Credential resolution occurs when an Aircall client is created, so server
  import and protocol discovery do not access credential storage. Production
  remains stdio-only; protocol tests use an in-process SDK HTTP app.

## Reproduce local checks

Use the locked environment and fake credentials. The tests use in-process MCP
transports and stubbed Aircall responses; they do not call the Aircall API.

```bash
uv sync --locked --offline --group dev
AIRCALL_MCP_USE_KEYRING=0 AIRCALL_API_ID=test AIRCALL_API_TOKEN=test .venv/bin/pytest -q
.venv/bin/ruff check aircall_mcp/client.py aircall_mcp/server.py aircall_mcp/setup/verify.py tests/spec_check.py tests/test_canary_regressions.py tests/test_spec_2026_07_28.py
.venv/bin/python tests/spec_check.py --mcp-only
uv lock --check --offline
```

These commands check local protocol and application behavior. They do not
establish live Aircall compatibility or deployed runtime behavior.

## Open product decision

MCP 2.2.0 masks client-visible messages from tool exceptions other than
`ToolError` or `ResourceError`. Retaining that masking limits leakage;
raising explicitly safe `ToolError` messages could give clients more actionable
feedback. Toby should choose the desired policy. This migration leaves
existing tool exception handling unchanged.
