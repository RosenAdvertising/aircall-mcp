#!/usr/bin/env python3
"""Verify Aircall credentials by fetching company info."""

from aircall_mcp.client import AircallClient


def verify():
    try:
        client = AircallClient()
        data = client.get_company()
        company = data.get("company", data) if isinstance(data, dict) else data
        name = "(unknown)"
        if isinstance(company, dict):
            name = company.get("name", name)
        print(f"Connected successfully. Company: {name}")
    except (RuntimeError, ValueError) as e:
        print(f"Verification failed: {e}")
        raise SystemExit(1)


def main():
    verify()


if __name__ == "__main__":
    main()
