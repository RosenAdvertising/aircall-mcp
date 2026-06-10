#!/usr/bin/env python3
"""Interactive setup: prompts for Aircall credentials and stores them securely.

Credentials are saved to the OS keyring by default (macOS Keychain / Windows
Credential Manager / Linux Secret Service), falling back to a 0600 ``.env`` file
when no keyring backend is available or ``AIRCALL_MCP_USE_KEYRING=0`` is set.
"""

import os

from aircall_mcp import credentials
from aircall_mcp.setup.verify import verify


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

    backend = credentials.set_secret("AIRCALL_API_ID", api_id)
    credentials.set_secret("AIRCALL_API_TOKEN", api_token)

    if backend == "keyring":
        print(
            f"\nCredentials saved to the OS keyring ({credentials.storage_backend()})."
        )
    else:
        print(f"\nCredentials saved to {credentials.ENV_FILE} (0600).")

    # Set for this process so verify() can use them immediately
    os.environ["AIRCALL_API_ID"] = api_id
    os.environ["AIRCALL_API_TOKEN"] = api_token

    print("Verifying credentials...")
    verify()


if __name__ == "__main__":
    main()
