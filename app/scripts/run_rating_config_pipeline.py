"""
CLI wrapper for app.agents.rating_config_pipeline: uploads a workbook and drives it
through the Excel-import agent pipeline (tables -> algorithm -> plan -> manual) to
completion, printing the final report and the parsed result.

Requires: the API server reachable at --api-url (default http://localhost:8000) and a
configured GEMINI_API_KEY (see .env / app/core/config.py), since the pipeline runs
through Gemini function calling, not a deterministic parser.

Usage:
    python -m app.scripts.run_rating_config_pipeline \
        "app/Testing_AI_Agent_modified_clean.xlsx" \
        --company VVR_DEMO_COMPANY --lob "Commercial Lines" --state ALL \
        --product VVR_DEMO --entity VVR_ENTITY_DEMO --effective-date 2026-07-21
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from app.agents.rating_config_pipeline import run_rating_config_pipeline


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xlsx_path", type=Path, help="Path to the source .xlsx workbook")
    parser.add_argument("--company", dest="company_name", help="Company name (overrides/fills the Configuration sheet)")
    parser.add_argument("--lob", dest="lob_name", help="Line-of-business name")
    parser.add_argument("--state", dest="state_name", help="State name/code (e.g. ALL, NY)")
    parser.add_argument("--product", dest="product_name", help="Product name")
    parser.add_argument("--entity", dest="entity_name", help="Legal entity name")
    parser.add_argument("--effective-date", dest="effective_date", help="ISO date (YYYY-MM-DD)")
    parser.add_argument("--algorithm-name", dest="algorithm_name", help="Override the algorithm name")
    parser.add_argument("--plan-name", dest="plan_name", help="Override the rating plan name")
    parser.add_argument("--manual-name", dest="manual_name", help="Override the rating manual name")
    parser.add_argument("--no-auto-approve", dest="auto_approve", action="store_false",
                         help="Require an interactive 'Yes, proceed' before creating anything (default: auto-approve)")
    parser.add_argument("--max-iterations", type=int, default=20, help="Max tool-calling rounds (default 20)")
    parser.add_argument("--api-url", default=None, help="Base API URL (default: $API_URL or http://localhost:8000)")
    args = parser.parse_args()

    result = asyncio.run(run_rating_config_pipeline(
        args.xlsx_path,
        company_name=args.company_name,
        lob_name=args.lob_name,
        state_name=args.state_name,
        product_name=args.product_name,
        entity_name=args.entity_name,
        effective_date=args.effective_date,
        algorithm_name=args.algorithm_name,
        plan_name=args.plan_name,
        manual_name=args.manual_name,
        auto_approve=args.auto_approve,
        max_iterations=args.max_iterations,
        api_url=args.api_url,
    ))

    print(f"bundle_id: {result['bundle_id']}\n")
    print(result["response_text"])

    if result["result"] is None:
        print("\n(warning: model did not emit a PIPELINE_RESULT_JSON line)", file=sys.stderr)
        sys.exit(1)
    if "error" in result["result"]:
        print(f"\nPipeline stopped: {json.dumps(result['result'])}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
