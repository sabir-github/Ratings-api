#!/usr/bin/env python3
"""
Run get_ratingplans with the given inputs (same as Gemini call).
Usage: python run_get_ratingplans.py
Requires: API server running (e.g. uvicorn app.main:app) and MongoDB.
"""
import asyncio
import json
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    from app.mcp_server import call_api

    args = {
        "product_id": "100000001",
        "lob_id": "100000001",
        "state_id": "100000053",
        "company_id": "100000001",
    }
    # Coerce to int like get_ratingplans does
    params = {
        "skip": 0,
        "limit": 100,
        "company_id": int(args["company_id"]),
        "lob_id": int(args["lob_id"]),
        "state_id": int(args["state_id"]),
        "product_id": int(args["product_id"]),
    }
    print("Calling GET /ratingplans/ with params:", params)
    result = await call_api("GET", "/ratingplans/", params=params)
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
