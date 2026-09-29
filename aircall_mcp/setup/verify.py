#!/usr/bin/env python3
"""Verify Aircall credentials by fetching company info."""

from aircall_mcp.client import AircallClient
from aircall_mcp.errors import AircallFailure


def verify():
    try:
        client = AircallClient()
        client.get_company()
        print("Connected successfully.")
    except AircallFailure as e:
        print(f"Verification failed: {e}")
        raise SystemExit(1)
    except Exception:
        print(
            "Verification failed: Aircall could not verify the credentials. Check the API ID and token, then retry."
        )
        raise SystemExit(1) from None


def main():
    verify()


if __name__ == "__main__":
    main()
