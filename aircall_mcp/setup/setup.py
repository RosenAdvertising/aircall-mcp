#!/usr/bin/env python3
"""Interactive setup: prompts for Aircall credentials and saves them to ~/.aircall-mcp/.env."""

import os
from pathlib import Path

from aircall_mcp.setup.verify import verify


CONFIG_DIR = Path.home() / ".aircall-mcp"
ENV_FILE = CONFIG_DIR / ".env"


def main():
    print("Aircall MCP Setup")
    print("-" * 40)
    print(
        "Find your credentials at: aircall.io -> Admin -> API Keys -> Own API Key integration"
    )
    print()

    api_id = input("Enter your Aircall API ID: ").strip()
    api_token = input("Enter your Aircall API Token: ").strip()

    if not api_id or not api_token:
        print("Error: Both API ID and API Token are required.")
        raise SystemExit(1)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)

    with open(ENV_FILE, "w") as f:
        f.write(f"AIRCALL_API_ID={api_id}\n")
        f.write(f"AIRCALL_API_TOKEN={api_token}\n")

    ENV_FILE.chmod(0o600)
    print(f"\nCredentials saved to {ENV_FILE}")

    # Set for this process so verify() can use them immediately
    os.environ["AIRCALL_API_ID"] = api_id
    os.environ["AIRCALL_API_TOKEN"] = api_token

    print("Verifying credentials...")
    verify()


if __name__ == "__main__":
    main()
