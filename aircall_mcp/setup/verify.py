#!/usr/bin/env python3
"""Verify Aircall credentials by fetching company info."""

from aircall_mcp.client import AircallClient


def verify():
    try:
        client = AircallClient()
        client.get_company()
        print("Connected successfully.")
    except (RuntimeError, ValueError) as e:
        print(f"Verification failed: {e}")
        raise SystemExit(1)


def main():
    verify()


if __name__ == "__main__":
    main()
