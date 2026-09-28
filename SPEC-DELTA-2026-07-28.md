# MCP protocol delta: 2025-11-25 to 2026-07-28

The server uses Python SDK `mcp>=2.2,<3`; `uv.lock` resolves `mcp` and
`mcp-types` to `2.2.0`. Its production transport is stdio. The mappings below
follow the [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
and [Python SDK migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

| Protocol change | Aircall mapping |
| --- | --- |
| Modern requests carry protocol version and client capabilities in `_meta`; `server/discover` replaces initialization. | SDK 2 supplies modern discovery and per-request dispatch. Legacy clients can still negotiate `2025-11-25`. |
| Results include `resultType`; list and read results include `ttlMs` and `cacheScope`. | SDK results use `resultType: "complete"`, `ttlMs: 0`, and `cacheScope: private`. No application cache is added. |
| Tool listing should be deterministic; schemas use current JSON Schema rules. | Registration order is stable. SDK generates and validates tool schemas; list limits are bounded from 1 through 200. Dictionary returns remain JSON text content. |
| Missing resources use `-32602`; unsupported versions use `-32022`; unknown methods use `-32601`. | Protocol tests assert these codes. The SDK's HTTP routing test also checks header mismatch `-32020`. |
| Streamable HTTP requires routing headers such as `Mcp-Method` and `Mcp-Name`. | Production has no HTTP entry point. In-process HTTP tests verify SDK routing without starting a listener. |
| Modern sessions and `Mcp-Session-Id` are removed. | The server has no MCP session state; downstream Aircall Basic Auth remains process local. |
| `subscriptions/listen` replaces HTTP GET and resource subscription methods. | No custom subscription publisher or HTTP transport exists. SDK capability declarations remain SDK managed. |
| Extensions replace experimental core tasks; roots, sampling, logging, HTTP+SSE, and Dynamic Client Registration are deprecated or changed. | No corresponding handlers or MCP OAuth client/server are implemented. Application diagnostics use Python logging. |
| URL elicitation, multi round-trip requests, and trace-context metadata changed. | The server does not implement these features. |

The repository's tests cover local MCP discovery, results, schemas, routing,
version errors, and legacy negotiation. They use fake Aircall responses and do
not verify live vendor behavior. Reproducible commands and the exception-message
product decision are in [the migration report](SPEC-MIGRATION-REPORT.md).
