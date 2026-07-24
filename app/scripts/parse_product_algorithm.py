"""
CLI wrapper for regenerating a one-off mongoimport JSON file for the
"Product Algorithm" worksheet (Div 67 Umbrella rating plan layout).

The actual parsing/step-building logic lives in
app/services/product_algorithm_parser.py, which is also used live by the
Excel-upload agent pipeline (excel_parser.py -> mcp_server.py). This script is
just a thin CLI for producing a standalone document by hand.

Usage:
    python -m app.scripts.parse_product_algorithm \
        "app/Testing -AI Agent-modified.xlsx" \
        --sheet "Product Algorithm" \
        --output app/schemas/product_algorithm_div67.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.schemas.algorithm_workflow import CalculationStep, Formula
from app.services.product_algorithm_parser import parse_workbook_sheet


def build_document(formula: Formula, steps: list[CalculationStep], *, algorithm_id: int, algorithm_name: str,
                    algorithm_type: str, company: int, lob: int, state: int, product: int, entity: int,
                    version: float, effective_date: str) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "id": algorithm_id,
        "algorithm_name": algorithm_name,
        "algorithm_type": algorithm_type,
        "company": company,
        "lob": lob,
        "state": state,
        "product": product,
        "entity": entity,
        "version": {"$numberDouble": str(version)},
        "effective_date": {"$date": effective_date},
        "expiration_date": None,
        "active": True,
        "required_tables": [],
        "formula": json.loads(formula.model_dump_json(exclude_none=True)),
        "calculation_steps": [json.loads(step.model_dump_json(exclude_none=True)) for step in steps],
        "variables": {},
        "created_at": {"$date": now_iso},
        "updated_at": {"$date": now_iso},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xlsx_path", type=Path, help="Path to the source .xlsx workbook")
    parser.add_argument("--sheet", default="Product Algorithm", help="Worksheet name to parse")
    parser.add_argument("--output", type=Path, default=Path("app/schemas/product_algorithm_div67.json"),
                         help="Output JSON path")
    parser.add_argument("--algorithm-id", type=int, default=100000017)
    parser.add_argument("--algorithm-name", default="Div 67 BOP Umbrella Rating Plan New")
    parser.add_argument("--algorithm-type", default="umbrella")
    parser.add_argument("--company", type=int, default=100000001)
    parser.add_argument("--lob", type=int, default=100000001)
    parser.add_argument("--state", type=int, default=100000001)
    parser.add_argument("--product", type=int, default=100000001)
    parser.add_argument("--entity", type=int, default=100000001)
    parser.add_argument("--version", type=float, default=1.0)
    parser.add_argument("--effective-date", default="2026-07-20T00:00:00.000Z")
    args = parser.parse_args()

    wb = load_workbook(args.xlsx_path, data_only=True)
    ws = wb[args.sheet]
    formula, steps = parse_workbook_sheet(ws, args.xlsx_path.name)

    document = build_document(
        formula, steps,
        algorithm_id=args.algorithm_id, algorithm_name=args.algorithm_name, algorithm_type=args.algorithm_type,
        company=args.company, lob=args.lob, state=args.state, product=args.product, entity=args.entity,
        version=args.version, effective_date=args.effective_date,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([document], indent=2), encoding="utf-8")
    print(f"Wrote {args.output} ({len(steps)} calculation steps)")


if __name__ == "__main__":
    main()
