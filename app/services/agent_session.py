"""
File-based persistence for the Excel-to-configuration agent.

Both the FastAPI process (writes bundles on upload) and the MCP subprocess
(reads bundles inside tools) share the same filesystem, so JSON files in a
temp directory are the simplest cross-process store.

Directory: <tempdir>/ratings_agent/
  bundle_<id>.json            ← ParsedExcelBundle (from dataclasses.asdict)
  algorithm_<id>.json         ← inferred AlgorithmSpec
  log_<id>.json               ← creation log {tables, algorithm, plan, manual}
"""
import dataclasses
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_AGENT_DIR = os.path.join(tempfile.gettempdir(), "ratings_agent")


def _ensure_dir() -> None:
    os.makedirs(_AGENT_DIR, exist_ok=True)


def _bundle_path(bundle_id: str) -> str:
    return os.path.join(_AGENT_DIR, f"bundle_{bundle_id}.json")


def _algorithm_path(bundle_id: str) -> str:
    return os.path.join(_AGENT_DIR, f"algorithm_{bundle_id}.json")


def _log_path(bundle_id: str) -> str:
    return os.path.join(_AGENT_DIR, f"log_{bundle_id}.json")


# ---------------------------------------------------------------------------
# Bundle (ParsedExcelBundle)
# ---------------------------------------------------------------------------

def store_bundle(bundle_id: str, bundle_obj: Any) -> None:
    """Serialize a ParsedExcelBundle (dataclass) to disk."""
    _ensure_dir()
    data = dataclasses.asdict(bundle_obj) if dataclasses.is_dataclass(bundle_obj) else bundle_obj
    path = _bundle_path(bundle_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
        logger.debug("Stored bundle %s → %s", bundle_id, path)
    except Exception:
        logger.exception("Failed to store bundle %s", bundle_id)


def get_bundle(bundle_id: str) -> Optional[Dict[str, Any]]:
    """Return the bundle dict, or None if not found."""
    path = _bundle_path(bundle_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read bundle %s", bundle_id)
        return None


def update_bundle(bundle_id: str, updates: Dict[str, Any]) -> bool:
    """Merge updates into an existing bundle dict and persist it.

    Returns True on success, False if the bundle doesn't exist.
    """
    bundle = get_bundle(bundle_id)
    if bundle is None:
        return False
    bundle.update(updates)
    _ensure_dir()
    path = _bundle_path(bundle_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, default=str)
        logger.debug("Updated bundle %s", bundle_id)
        return True
    except Exception:
        logger.exception("Failed to update bundle %s", bundle_id)
        return False


# ---------------------------------------------------------------------------
# Inferred algorithm spec
# ---------------------------------------------------------------------------

def store_inferred_algorithm(bundle_id: str, spec: Dict[str, Any]) -> None:
    _ensure_dir()
    path = _algorithm_path(bundle_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f, default=str)
        logger.debug("Stored algorithm spec for bundle %s", bundle_id)
    except Exception:
        logger.exception("Failed to store algorithm spec for bundle %s", bundle_id)


def get_inferred_algorithm(bundle_id: str) -> Optional[Dict[str, Any]]:
    path = _algorithm_path(bundle_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read algorithm spec for bundle %s", bundle_id)
        return None


# ---------------------------------------------------------------------------
# Creation log
# ---------------------------------------------------------------------------

def get_or_init_log(bundle_id: str) -> Dict[str, Any]:
    path = _log_path(bundle_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception("Failed to read creation log for bundle %s", bundle_id)
    return {"tables": [], "algorithm": None, "plan": None, "manual": None}


def save_log(bundle_id: str, log: Dict[str, Any]) -> None:
    _ensure_dir()
    path = _log_path(bundle_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(log, f, default=str)
    except Exception:
        logger.exception("Failed to save creation log for bundle %s", bundle_id)


def get_creation_log(bundle_id: str) -> Dict[str, Any]:
    return get_or_init_log(bundle_id)


# ---------------------------------------------------------------------------
# Backward-compatible in-memory aliases (used by legacy direct-access code)
# These are no longer the primary store — file-based functions above are canonical.
# ---------------------------------------------------------------------------

# Keep these as empty stubs so any code that still does
# `agent_session.excel_bundles[x] = y` compiles without error.
excel_bundles: Dict[str, Any] = {}
inferred_algorithms: Dict[str, Dict[str, Any]] = {}
creation_logs: Dict[str, Dict[str, Any]] = {}
