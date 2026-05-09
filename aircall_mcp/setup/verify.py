#!/usr/bin/env python3
"""Verify Aircall credentials by fetching company info."""

from aircall_mcp.client import AircallClient


def verify():
    try:
        client = AircallClient()
        data = client.get_company()
        company = data.get("company", data)
        name = company.get("name", "(unknown)")
        print(f"Connected successfully. Company: {name}")
    except RuntimeError as e:
        print(f"Verification failed: {e}")
        raise SystemExit(1)


def main():
    verify()


if __name__ == "__main__":
    main()
