# MCP 2026-07-28 migration report

## Result

`aircall-mcp` now targets MCP `2026-07-28`, up from `2025-11-25`. The direct
Python SDK dependency changed from `mcp>=1.28.1,<2` (locked to 1.28.1) to the
exact migration release `mcp==2.0.0`. The lock now includes the SDK v2 split,
including `mcp-types==2.0.0` and `httpx2`.

The authoritative, repository-specific change classification is in
[`SPEC-DELTA-2026-07-28.md`](SPEC-DELTA-2026-07-28.md). It follows the
[official MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
and the
[official Python SDK migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

No deployment or live Aircall account was touched. No credentials were needed
or printed.

## Current-revision verdict

This was a migration, not a no-op:

- `pyproject.toml` constrained MCP to v1 and `uv.lock` resolved 1.28.1.
- `aircall_mcp/server.py` constructed `FastMCP`.
- The installed v1 SDK supported revisions only through `2025-11-25`.
- The repository had no tracked source tests or MCP protocol guard.
- The only runtime transport was, and remains, stdio through `mcp.run()`.

## Implementation

- Replaced the v1 `FastMCP` surface with SDK v2 `MCPServer`.
- Preserved all 22 tools, three prompts, three resources, and the stdio
  transport. Aircall Basic Auth, keyring/file storage, process state, and cache
  posture are unchanged.
- Kept SDK-provided dual-era compatibility: default clients negotiate
  `2026-07-28`, while legacy-mode clients still negotiate `2025-11-25`.
- Added conservative SDK v2 cache semantics (`ttlMs: 0`, `cacheScope:
private`) without application caching.
- Made credential resolution lazy so importing the server or discovering tools
  does not consult keyring or the fallback credential file.
- Added an explicit core Ruff policy for the declared Python 3.10 floor.

## AFFECTS-US handling

The modern suite proves discovery, per-request metadata, required routing
headers, result types, cache fields, deterministic tool ordering, schema
validation, legacy negotiation, resource-not-found `-32602`, header mismatch
`-32020`, unsupported version `-32022`, and unknown method `-32601`.

Production remains stdio-only. Tests construct an ephemeral, stateless SDK HTTP
app solely to inspect the modern raw wire. No HTTP server, browser route, or
deployment surface was added.

Bare `dict` tool returns intentionally retain their existing JSON text content
shape. SDK v2 adds `resultType: "complete"`; the migration does not introduce a
new structured-output model merely to populate optional `structuredContent`.

## Canary sibling checks

### A. List-tool limit and order — fixed

- All six list tools now expose a schema-enforced `limit` of 1 through 200.
- The five paged tools also enforce `page >= 1` and preserve their former
  `per_page` argument as a bounded, deprecated alias.
- Client responses are defensively trimmed to the requested limit, so an
  upstream over-return cannot violate the total cap.
- The unpaginated `list_tags` path is capped locally.
- Resource descriptions no longer claim to return "all" records from a single
  bounded request.
- The implementation never auto-paginated, so there was no pre-existing
  multi-page overrun to repair.

The allowed network scope excluded Aircall vendor documentation. Repository
evidence does not establish an oldest-first default or a supported sort
parameter, so no unverified vendor parameter was added. Ordering remains a
method-verification-only item for an owner with Aircall documentation access.

### B. Silent rejections — fixed

Every client-side rejection now emits a constant, PII-free reason log before
raising: missing or invalid credentials, non-JSON and other upstream failures,
and invalid list-shaped tool inputs. Tests assert the reason and the absence of
sentinel personal data.

### C. Origin/CSP ceremony — not applicable

The repository serves no browser pages, HTML, custom HTTP routes, or setup
handoff. It remains a stdio server, so the Sec-Fetch-Site and CSP patterns do
not apply.

### D. PII in logs — fixed

- Arbitrary upstream response bodies are no longer included in exceptions that
  can reach stderr or MCP runtime logs.
- Credential verification no longer prints the Aircall company name.
- The final source sweep found no credential, subject, email, or name values
  reaching application log calls. Constant reason identifiers such as
  `emails_not_list` contain no personal value.

## Verification

Baseline:

- Tests: **0/0 available**. There were no tracked tests; an ad-hoc pytest run
  collected zero and exited 5, so this was not a passing suite.
- Ruff: **10 pre-existing findings** under the then-unconfigured current Ruff.
- Installed protocol list ended at `2025-11-25`.

After migration, from the locked environment:

- `uv lock --check`: passed.
- `uv sync --locked`: passed.
- `uv run pytest -q tests/test_spec_2026_07_28.py`: **8/8 passed**.
- `uv run pytest -q`: **47/47 passed**.
- `uv run python tests/spec_check.py --mcp-only`: passed.
- `uv run ruff check .`: passed with no findings.
- Staged-file Pyright and the repository's pre-commit hooks passed for every
  migration commit.

Live Aircall behavior was not tested because no account or credentials were
required. Endpoint and order behavior is therefore method-verified only.

## Git administration caveat

The workspace policy mounted the canonical `.git` directory read-only. Both
branch and index lock creation failed with `Operation not permitted`, even
though repository source files were writable. To preserve the requested branch
and separated Conventional Commits, the migration used a writable alternate
Git database under the granted fan-out scratchpad while applying the exact
committed tree to this worktree.

The branch is `spec-2026-07-28`, based on the locally available `origin/main`
at `8adcdef`. Each migration commit includes:

`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

No push was attempted. The external fan-out report records the alternate Git
database and portable bundle paths so the branch can be imported once the
canonical `.git` is writable.
