"""
Agent endpoint — Excel upload for the insurance configuration agent.

POST /api/v1/agent/upload-excel
    Accepts a single .xlsx / .xls file, parses the first (or named) worksheet,
    stores the ParsedExcelBundle in agent_session keyed by bundle_id, and
    returns a lightweight summary the frontend uses to acknowledge the upload.

GET  /api/v1/agent/bundle/{bundle_id}
    Returns the full bundle summary (used by MCP tools for inspection).
"""
import logging
import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.services import agent_session
from app.services.excel_parser import parse as parse_excel

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


@router.post("/upload-excel", status_code=status.HTTP_200_OK)
async def upload_excel(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
    """
    Parse a single-worksheet Excel file for the configuration agent.

    The worksheet is segmented into logical sections (separated by blank rows):
    - Data tables  → classified as base_rate_table / factor_table / decision_matrix / lookup_table
    - Parameter rows (key : value pairs) → extracted as metadata
    - Formula cell → captured verbatim as the algorithm expression

    Returns a bundle_id that subsequent chat messages should reference as
    ``[bundle_id:<id>]`` so the Gemini agent can call analyze_excel_bundle.
    """
    # Validate file extension
    _, ext = os.path.splitext((file.filename or "").lower())
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only .xlsx and .xls files are accepted. Got: '{ext or 'none'}'",
        )

    try:
        contents = await file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded file.",
        )

    try:
        bundle = parse_excel(contents)
    except Exception as exc:
        logger.error("Excel parsing failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse Excel file: {str(exc)}",
        )

    # Persist bundle to disk so the MCP subprocess can read it
    agent_session.store_bundle(bundle.bundle_id, bundle)

    # Build the lightweight summary returned to the frontend
    table_summaries = [
        {
            "section_name": t.section_name,
            "table_type": t.table_type,
            "column_count": len(t.headers),
            "row_count": t.row_count,
        }
        for t in bundle.tables
    ]

    response_session_id = session_id or ""

    logger.info(
        "Excel bundle %s stored: %d tables, formula_detected=%r, session=%r",
        bundle.bundle_id, len(bundle.tables), bundle.formula_detected, response_session_id,
    )

    return {
        "bundle_id": bundle.bundle_id,
        "session_id": response_session_id,
        "table_summaries": table_summaries,
        "parameters_detected": bundle.parameters,
        "formula_detected": bundle.formula_detected,
    }


@router.get("/bundle/{bundle_id}", status_code=status.HTTP_200_OK)
async def get_bundle(bundle_id: str):
    """Return summary of a stored parsed Excel bundle (for inspection / debugging)."""
    bundle = agent_session.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bundle '{bundle_id}' not found. It may have expired or never been uploaded.",
        )

    tables = bundle.get("tables", [])
    return {
        "bundle_id": bundle.get("bundle_id", bundle_id),
        "table_count": len(tables),
        "tables": [
            {
                "section_name": t.get("section_name"),
                "table_type": t.get("table_type"),
                "headers": t.get("headers"),
                "row_count": t.get("row_count"),
                "variable_name": t.get("variable_name"),
                "output_column": t.get("output_column"),
                "input_columns": t.get("input_columns"),
            }
            for t in tables
        ],
        "parameters": bundle.get("parameters"),
        "formula_detected": bundle.get("formula_detected"),
        "suggested_formula": bundle.get("suggested_formula"),
        "formula_confidence": bundle.get("formula_confidence"),
        "inference_method": bundle.get("inference_method"),
    }
