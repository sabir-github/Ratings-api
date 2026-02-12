#!/usr/bin/env python3
"""
Fetch rating plans using MCP tool logic (direct service call).
Search criteria: company_id=100000001, lob_id=100000001, product_id=100000001
(no state_id = all states for that company/lob/product)

Usage: python fetch_ratingplans_mcp.py
Requires: MongoDB running and app deps installed.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")

# MCP get_ratingplans search criteria (no state_id)
CRITERIA = {
    "company_id": 100000001,
    "lob_id": 100000001,
    "product_id": 100000001,
}


async def main():
    from app.services.ratingplan_service import ratingplan_service

    plans = await ratingplan_service.get_ratingplans(
        skip=0, limit=100, filter_by=CRITERIA
    )
    items = [
        p.model_dump() if hasattr(p, "model_dump") else p.dict()
        for p in plans
    ]
    result = {"items": items, "count": len(items)}
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
