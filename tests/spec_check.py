#!/usr/bin/env python3
"""CI-friendly guard for the MCP protocol revision targeted by this server."""

from __future__ import annotations

import argparse

from mcp.types import LATEST_PROTOCOL_VERSION
from mcp_types.version import MODERN_PROTOCOL_VERSIONS


EXPECTED_MCP_PROTOCOL_VERSION = "2026-07-28"


def check_mcp_revision() -> list[str]:
    """Return actionable errors when the installed SDK targets another revision."""
    errors = []
    if LATEST_PROTOCOL_VERSION != EXPECTED_MCP_PROTOCOL_VERSION:
        errors.append(
            "installed MCP SDK latest protocol is "
            f"{LATEST_PROTOCOL_VERSION!r}; expected {EXPECTED_MCP_PROTOCOL_VERSION!r}"
        )
    if MODERN_PROTOCOL_VERSIONS != (EXPECTED_MCP_PROTOCOL_VERSION,):
        errors.append(
            "installed MCP modern protocol set is "
            f"{MODERN_PROTOCOL_VERSIONS!r}; expected "
            f"{(EXPECTED_MCP_PROTOCOL_VERSION,)!r}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="Compatibility flag shared with fleet spec guards.",
    )
    parser.parse_args()

    errors = check_mcp_revision()
    if errors:
        for error in errors:
            print(f"Spec check: FAIL — {error}")
        return 1
    print(f"Spec check: PASS — MCP {EXPECTED_MCP_PROTOCOL_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
