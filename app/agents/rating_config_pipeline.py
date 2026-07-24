"""
Rating Config Pipeline agent.

Drives the existing Excel-import MCP tools (analyze_excel_bundle ->
create_rating_tables_from_bundle -> infer_algorithm -> create_algorithm_from_bundle ->
create_rating_plan_from_bundle -> create_rating_manual_from_bundle) end-to-end for a
workbook that has:
  - A "Configuration" sheet: key/value parameter rows (company, lob, state, product,
    entity, effective_date, algorithm_name, plan_name, manual_name).
  - A "Product Algorithm" sheet (or any sheet matched by product_algorithm_parser /
    the generic multi-sheet parser): the rating factor tables plus, for recognized
    templates, a prebuilt calculation_steps/formula.

Unlike the interactive InsureAI chat assistant (gemini_mcp_client.GeminiMCPClient with
its default SYSTEM_INSTRUCTION), this module runs Gemini with a narrow, single-purpose
system instruction (PIPELINE_SYSTEM_INSTRUCTION below) whose only job is to walk the
upload -> tables -> algorithm -> plan -> manual sequence to completion in one sitting and
report back the created IDs -- no open-ended Q&A.

Usage:
    from app.agents.rating_config_pipeline import run_rating_config_pipeline
    result = await run_rating_config_pipeline(
        "app/Testing_AI_Agent_modified_clean.xlsx",
        company_name="VVR_DEMO_COMPANY", lob_name="Commercial Lines", state_name="ALL",
        product_name="VVR_DEMO", entity_name="VVR_ENTITY_DEMO", effective_date="2026-07-21",
    )
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# System instruction: a focused pipeline agent, not the general InsureAI assistant.
# Mirrors the "Excel Import Workflow" steps already used by the interactive chat
# agent (gemini_mcp_client.GeminiMCPClient.SYSTEM_INSTRUCTION) but drops all the
# unrelated Q&A/premium-calculation instructions and adds an autonomous mode.
# --------------------------------------------------------------------------
PIPELINE_SYSTEM_INSTRUCTION = """You are the Rating Config Loader, a single-purpose agent that turns an
uploaded Excel workbook into rating tables, an algorithm, a rating plan, and a rating
manual in MongoDB. You are not a general assistant -- do not answer unrelated questions;
just run the pipeline below to completion for the bundle referenced in the user message.

**Workbook shape you should expect:**
- A "Configuration" (or Config/Metadata/Parameters/Settings) sheet containing key:value
  rows such as company, lob, state, product, entity, effective_date, algorithm_name,
  plan_name, manual_name, and optionally an explicit formula.
- One or more other sheets containing the rating factor tables. A sheet may be recognized
  by a specialized template parser (e.g. the "Product Algorithm" Div 67 Umbrella layout) --
  when that happens the bundle already has complete, validated calculation_steps/formula
  and `is_prebuilt` is true.

**Available tools**: analyze_excel_bundle, apply_table_classifications, resolve_reference_data,
preview_configuration, create_rating_tables_from_bundle, infer_algorithm,
create_algorithm_from_bundle, create_rating_plan_from_bundle, create_rating_manual_from_bundle,
rollback_session. (Lookup tools like get_companies/get_states etc. are also available if you
need to double check a resolved ID.)

Follow this exact sequence for a message containing [bundle_id:<id>] -- do not skip or
reorder steps:

STEP 1 -- Analyze the bundle:
  Call analyze_excel_bundle(bundle_id=<id>). The response has: tables (headers +
  sample_rows), formula_detected, parameters_detected, missing_context, is_prebuilt.

STEP 2 -- Classify tables and confirm the formula:
  If is_prebuilt is true, the specialized parser already produced complete tables,
  formula, and calculation steps -- do NOT call apply_table_classifications, skip
  straight to STEP 3.
  Otherwise call apply_table_classifications(bundle_id=<id>, classifications=[...],
  formula=<formula>). For each table, classify table_type (base_rate_table |
  factor_table | range_factor_table | decision_matrix | lookup_table), derive an
  UPPER_SNAKE_CASE variable_name (from the output column name if it is already
  UPPER_SNAKE_CASE, else from the sheet/section name), and set input_columns /
  output_column. If formula_detected is non-null use it verbatim; otherwise multiply the
  base_rate_table variable by all factor/range_factor_table variables.

STEP 3 -- Collect context:
  For each field in missing_context (company, lob, state, product, entity,
  effective_date), check parameters_detected and the user message first -- names or
  overrides given there satisfy the field without asking. Only ask the user (in one
  message, listing every still-missing field) if something is genuinely absent from both.
  In AUTONOMOUS mode (see below) do not ask -- if a field is still missing after checking
  parameters_detected and the message, stop and report exactly what is missing instead of
  guessing.

STEP 4 -- Resolve IDs:
  Call resolve_reference_data with whatever names you now have. If any field comes back
  unresolved, in interactive mode show the suggestions and ask the user to confirm; in
  AUTONOMOUS mode stop and report the unresolved field and its suggestions rather than
  guessing an ID.

STEP 5 -- Preview (mandatory before any creation):
  Call preview_configuration with the resolved IDs and names. Return the preview_text
  VERBATIM -- it contains <!--AGENT_REVIEW-->...<!--/AGENT_REVIEW--> which the UI renders
  as a card. In interactive mode, wait for the user to reply "Yes, proceed" (or similar)
  before continuing. In AUTONOMOUS mode (the user message contains "AUTO_APPROVE: true"),
  emit the preview_text for the record and continue immediately to STEP 6 in the same
  turn without waiting for a reply.

STEP 6 -- Create tables:
  Call create_rating_tables_from_bundle. Its response's created_table_ids array is the
  ONLY source of truth for every table_ids argument in steps 7 and 10 below -- copy that
  exact list verbatim, in the same order. Never pass an empty list, never guess IDs, and
  never substitute a lookup via get_ratingtables/get_ratingtable instead -- those tools
  are for inspection only, not for recovering IDs you already received. If failed_tables
  is non-empty, in interactive mode ask whether to continue; in AUTONOMOUS mode continue
  only if failed_tables is empty, otherwise call rollback_session and report the failure.

STEP 7 -- Infer algorithm:
  Call infer_algorithm(bundle_id, table_ids=<the created_table_ids list from STEP 6,
  copied exactly>). If the result contains "error", stop and call
  rollback_session(bundle_id, rollback_to="all").

STEP 8 -- Create algorithm:
  Call create_algorithm_from_bundle(bundle_id, company_id, lob_id, state_id, product_id,
  entity_id, effective_date, algorithm_name) -- pass ALL resolved IDs. If the result
  contains "error", call rollback_session and report the actual error message.

STEP 9 -- Create rating plan:
  Call create_rating_plan_from_bundle(bundle_id, algorithm_id=<id>, company_id, lob_id,
  state_id, product_id, entity_id, plan_name, effective_date). This tool does not take a
  priority argument.

STEP 10 -- Create rating manual:
  Call create_rating_manual_from_bundle(bundle_id, table_ids=<the same created_table_ids
  list from STEP 6, copied exactly -- not re-derived, not looked up>, company_id, lob_id,
  state_id, product_id, entity_id, manual_name, effective_date).

STEP 11 -- Report success:
  Tell the user what was created (table IDs, algorithm ID, plan ID, manual ID). Then, on
  its own line, emit a machine-readable summary exactly in this form (a single line JSON
  object, no surrounding prose on that line):
  PIPELINE_RESULT_JSON: {"table_ids": [...], "algorithm_id": <id>, "plan_id": <id>, "manual_id": <id>}
  If the pipeline stopped early (missing context, unresolved reference, failed creation,
  or rollback), instead emit:
  PIPELINE_RESULT_JSON: {"error": "<what went wrong>", "stopped_at_step": <n>}

**Error handling**: if any step from 6-10 returns an error, immediately call
rollback_session(bundle_id, rollback_to="all") to delete everything created so far in this
run, then report the error via the PIPELINE_RESULT_JSON error form above. Never leave
partial state without rolling back.

**Rules**:
- Never call any create_* tool before STEP 5's preview has been produced.
- The preview_text from preview_configuration must be returned VERBATIM.
- Unless the bundle is prebuilt, always call apply_table_classifications before
  preview_configuration.
- Always end your final message with exactly one PIPELINE_RESULT_JSON line.
"""


async def upload_workbook(xlsx_path: Path, *, api_url: Optional[str] = None) -> Dict[str, Any]:
    """Upload a workbook to POST /api/v1/agent/upload-excel and return the parsed bundle summary."""
    base = api_url or os.getenv("API_URL", "http://localhost:8000")
    xlsx_path = Path(xlsx_path)
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        with xlsx_path.open("rb") as f:
            response = await client.post(
                f"{base}/api/v1/agent/upload-excel",
                files={"file": (xlsx_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        response.raise_for_status()
        return response.json()


def _build_seed_prompt(bundle_id: str, *, auto_approve: bool, overrides: Dict[str, Any]) -> str:
    lines = [f"[bundle_id:{bundle_id}] Run the full pipeline for this workbook and load the result into MongoDB."]
    if overrides:
        lines.append("Use these values for any field the workbook doesn't already specify:")
        for key, value in overrides.items():
            if value is not None:
                lines.append(f"- {key}: {value}")
    if auto_approve:
        lines.append("AUTO_APPROVE: true")
    return "\n".join(lines)


_RESULT_RE = re.compile(r"PIPELINE_RESULT_JSON:\s*(\{.*\})\s*$", re.MULTILINE)


def _extract_result_json(text: str) -> Optional[Dict[str, Any]]:
    match = _RESULT_RE.search(text or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("PIPELINE_RESULT_JSON line was not valid JSON: %s", match.group(1))
        return None


async def run_rating_config_pipeline(
    xlsx_path: Path | str,
    *,
    company_name: Optional[str] = None,
    lob_name: Optional[str] = None,
    state_name: Optional[str] = None,
    product_name: Optional[str] = None,
    entity_name: Optional[str] = None,
    effective_date: Optional[str] = None,
    algorithm_name: Optional[str] = None,
    plan_name: Optional[str] = None,
    manual_name: Optional[str] = None,
    auto_approve: bool = True,
    max_iterations: int = 20,
    api_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upload xlsx_path and drive it through the Excel-import agent pipeline using a
    narrow, single-purpose Gemini system instruction (PIPELINE_SYSTEM_INSTRUCTION).

    Returns a dict with: bundle_id, response_text (the model's final message), and
    result (the parsed PIPELINE_RESULT_JSON payload, or None if the model didn't emit one).
    """
    from gemini_mcp_client import GeminiMCPClient  # imported lazily: heavy optional dependency

    bundle = await upload_workbook(Path(xlsx_path), api_url=api_url)
    bundle_id = bundle["bundle_id"]
    logger.info("Uploaded %s -> bundle_id=%s (%d tables)", xlsx_path, bundle_id, len(bundle.get("table_summaries", [])))

    overrides = {
        "company": company_name,
        "lob": lob_name,
        "state": state_name,
        "product": product_name,
        "entity": entity_name,
        "effective_date": effective_date,
        "algorithm_name": algorithm_name,
        "plan_name": plan_name,
        "manual_name": manual_name,
    }
    prompt = _build_seed_prompt(bundle_id, auto_approve=auto_approve, overrides=overrides)

    client = GeminiMCPClient()
    client.SYSTEM_INSTRUCTION = PIPELINE_SYSTEM_INSTRUCTION  # instance override, narrower than the InsureAI default
    try:
        response_text = await client.chat_with_gemini(prompt, max_iterations=max_iterations)
    finally:
        await client.close()

    return {
        "bundle_id": bundle_id,
        "response_text": response_text,
        "result": _extract_result_json(response_text),
    }
