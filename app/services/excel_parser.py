"""
Excel parser for the insurance configuration agent.

Supports two layouts:

  Multi-tab (preferred):
    - One sheet named Config / Metadata / Parameters / Algorithm / Settings
      containing key=value metadata rows and a "formula" row.
    - Every other sheet is a separate rating table; the sheet name becomes
      the table name and variable name.

  Single-tab (fallback):
    - All tables stacked vertically in the active sheet, separated by blank rows.
    - Parameters and formula cell(s) anywhere in the same sheet.

Formula resolution priority:
  1. Explicit formula row in Config sheet or isolated formula cell   → confidence 1.0
  2. Gemini classifies via apply_table_classifications MCP tool       → confidence set by Gemini
  3. No formula (returned as empty string here; caller handles)      → confidence 0.0

Table type classification is intentionally deferred to Gemini via the
analyze_excel_bundle / apply_table_classifications MCP tool pair.
Python only extracts raw cell data; Gemini decides semantic types.

Supported table types (set by Gemini via apply_table_classifications):
  base_rate_table    – contains a base rate or base premium column
  factor_table       – categorical input(s) → one numeric factor output
  range_factor_table – numeric range inputs (MIN/MAX or FROM/TO) → one numeric factor output
  decision_matrix    – two-dimensional lookup (row × column)
  lookup_table       – any other tabular structure
"""
import io
import json
import re
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import load_workbook

from app.schemas.algorithm_workflow import (
    CalculationStep,
    DataIntakeStepData,
    Expression,
    ExpressionStepData,
    FieldMapping,
    IntakeField,
    Lookup,
    OutputExpression,
    Position,
    QuoteOutputStepData,
    RatingTableLookupStepData,
    WorkflowEdge,
)

logger = logging.getLogger(__name__)

# Keywords that identify a parameter row's left cell
_PARAM_KEYS = {
    "effective_date", "expiration_date", "algorithm_name", "algorithm name",
    "company", "lob", "state", "product", "entity", "priority",
    "formula", "table_type", "plan_name", "manual_name",
    "effective date", "expiration date", "plan name", "manual name",
}

# Regex for detecting a formula expression cell
_MATH_RE = re.compile(r"[\*\+/]|lookup\s*\(", re.IGNORECASE)

# Regex that matches Excel cell references: B2, $C$3, AA10, etc.
_CELL_REF_RE = re.compile(r'\$?([A-Z]+)\$?(\d+)', re.IGNORECASE)

# Column A labels that indicate a header row in the Algorithm sheet (skip these)
_ALGO_HEADER_WORDS = {
    "variable", "name", "parameter", "input", "factor", "step",
    "description", "notes", "example", "value", "amount", "label",
}

# Sheet names treated as the config/metadata sheet in multi-tab workbooks
_CONFIG_SHEET_NAMES = {
    "config", "configuration", "metadata", "parameters", "algorithm", "settings",
}


@dataclass
class TableSection:
    section_name: str
    table_type: str          # base_rate_table | factor_table | decision_matrix | lookup_table
    headers: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    output_column: str       # detected value/output column name
    input_columns: List[str] # detected key/input column names
    variable_name: str       # UPPER_SNAKE_CASE name used in formula (e.g. AGE_FACTOR)


@dataclass
class ParsedExcelBundle:
    bundle_id: str
    tables: List[TableSection]
    parameters: Dict[str, str]      # lowercased key → value
    formula_detected: Optional[str] # explicit formula text (None if not found)
    suggested_formula: str          # resolved formula expression
    formula_confidence: float       # 0.0–1.0
    inference_method: str           # explicit | rules | llm
    # Set when a sheet was recognized by a specialized parser (e.g. the
    # "Product Algorithm" cell-range parser in product_algorithm_parser.py)
    # that already produced a complete, validated calculation_steps/formula —
    # infer_algorithm should use these as-is rather than re-deriving from a
    # single formula string, since the real computation needs multiple
    # chained expressions and conditional logic.
    is_prebuilt: bool = False
    prebuilt_calculation_steps: Optional[List[Dict[str, Any]]] = None
    prebuilt_formula: Optional[Dict[str, Any]] = None
    prebuilt_variables: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(file_bytes: bytes, sheet_name: Optional[str] = None) -> ParsedExcelBundle:
    """
    Parse an Excel workbook and return a ParsedExcelBundle.

    Routing logic:
      - If sheet_name is given → single-sheet mode on that sheet.
      - If workbook has >1 sheet → multi-tab mode.
      - Otherwise → single-sheet mode on the active sheet.

    For multi-tab workbooks the parser loads a second copy with data_only=False
    so it can read Excel cell formula strings (e.g. =B2*B3*B4) from the
    Algorithm sheet.  data_only=True (first load) is still used for all
    computed values in every other sheet.
    """
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)

    if sheet_name:
        ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb.active
        return _parse_single_sheet(ws)

    if len(wb.sheetnames) > 1:
        # Second load preserves formula text instead of computed values
        wb_formulas = load_workbook(io.BytesIO(file_bytes), data_only=False)
        return _parse_multi_sheet(wb, wb_formulas)

    return _parse_single_sheet(wb.active)


def _sheet_rows(ws) -> List[List[Any]]:
    """Read all cell values from a worksheet into a list of lists."""
    return [[cell.value for cell in row] for row in ws.iter_rows()]


def _parse_single_sheet(ws) -> ParsedExcelBundle:
    """Original single-sheet parser: segment by blank rows, classify groups."""
    from app.services.product_algorithm_parser import is_product_algorithm_sheet, try_parse

    if is_product_algorithm_sheet(ws.title):
        specialized = try_parse(ws, source_label="the uploaded workbook")
        if specialized is not None:
            table_sections, calc_steps, formula_dict, variables = specialized
            bundle = ParsedExcelBundle(
                bundle_id=str(uuid.uuid4()),
                tables=table_sections,
                parameters={},
                formula_detected=formula_dict.get("expression"),
                suggested_formula=formula_dict.get("expression", ""),
                formula_confidence=1.0,
                inference_method="specialized_template",
                is_prebuilt=True,
                prebuilt_calculation_steps=calc_steps,
                prebuilt_formula=formula_dict,
                prebuilt_variables=variables,
            )
            logger.info(
                "Parsed '%s' via specialized Product Algorithm parser: %d tables, %d calculation steps",
                ws.title, len(table_sections), len(calc_steps),
            )
            return bundle
        # Sheet name matched but layout validation failed — fall through to generic parsing.

    raw_rows = _sheet_rows(ws)
    groups = _segment(raw_rows)
    tables, parameters, formula_detected = _classify_groups(groups)
    suggested_formula, confidence, method = _resolve_formula(tables, parameters, formula_detected)
    bundle = ParsedExcelBundle(
        bundle_id=str(uuid.uuid4()),
        tables=tables,
        parameters=parameters,
        formula_detected=formula_detected,
        suggested_formula=suggested_formula,
        formula_confidence=confidence,
        inference_method=method,
    )
    logger.info(
        "Parsed single-sheet Excel bundle %s: %d tables, formula=%r (method=%s, confidence=%.2f)",
        bundle.bundle_id, len(tables), suggested_formula, method, confidence,
    )
    return bundle


def _parse_multi_sheet(wb, wb_formulas=None) -> ParsedExcelBundle:
    """
    Multi-tab parser:
      - Every sheet whose name matches _CONFIG_SHEET_NAMES → parameters + formula.
      - Algorithm sheets also get cell-formula detection via wb_formulas (data_only=False).
      - Every other sheet → one TableSection; sheet name = section/variable name.
    """
    # ── Parse all config/metadata sheets ─────────────────────────────────────
    parameters: Dict[str, str] = {}
    formula_detected: Optional[str] = None

    for name in wb.sheetnames:
        if name.lower().strip() not in _CONFIG_SHEET_NAMES:
            continue

        ws = wb[name]
        config_rows = _sheet_rows(ws)
        groups = _segment(config_rows)
        _, config_params, config_formula = _classify_groups(groups)
        parameters.update(config_params)
        if config_formula and formula_detected is None:
            formula_detected = config_formula

        # For sheets named "algorithm": also try cell-formula detection.
        # This reads =B2*B3*B4 style formulas and resolves cell refs to variable names.
        if name.lower().strip() == "algorithm" and formula_detected is None and wb_formulas is not None:
            ws_f = wb_formulas[name]
            cell_formula, extra_params = _parse_algorithm_sheet_formulas(ws_f)
            parameters.update(extra_params)
            if cell_formula:
                formula_detected = cell_formula
                logger.debug("Algorithm sheet '%s' → cell formula resolved: %r", name, cell_formula)

        logger.debug("Config sheet '%s' → %d params, formula=%r", name, len(config_params), formula_detected)

    # ── Parse each non-config sheet as one rating table ───────────────────────
    from app.services.product_algorithm_parser import is_product_algorithm_sheet, try_parse

    tables: List[TableSection] = []
    is_prebuilt = False
    prebuilt_calculation_steps: Optional[List[Dict[str, Any]]] = None
    prebuilt_formula: Optional[Dict[str, Any]] = None
    prebuilt_variables: Optional[Dict[str, Any]] = None

    for name in wb.sheetnames:
        if name.lower().strip() in _CONFIG_SHEET_NAMES:
            continue

        ws = wb[name]

        # A sheet matching the known "Product Algorithm" template packs multiple
        # lookup tables side-by-side in different columns within the same row
        # span — the generic blank-row segmentation below cannot separate those
        # and would merge them into garbage, so try the specialized cell-range
        # parser first.
        if is_product_algorithm_sheet(name):
            specialized = try_parse(ws, source_label="the uploaded workbook")
            if specialized is not None:
                spec_tables, calc_steps, formula_dict, variables = specialized
                tables.extend(spec_tables)
                is_prebuilt = True
                prebuilt_calculation_steps = calc_steps
                prebuilt_formula = formula_dict
                prebuilt_variables = variables
                if formula_detected is None:
                    formula_detected = formula_dict.get("expression")
                logger.info(
                    "Sheet '%s' → specialized Product Algorithm parser: %d tables, %d calculation steps",
                    name, len(spec_tables), len(calc_steps),
                )
                continue
            # Sheet name matched but layout validation failed — fall through to generic parsing.

        raw_rows = _sheet_rows(ws)

        # Remove blank rows
        non_blank = [r for r in raw_rows if not _is_blank(r)]
        if not non_blank:
            logger.debug("Sheet '%s' is empty — skipped", name)
            continue

        # If the first row is a single non-numeric cell, treat it as a title and skip it
        # (the sheet name itself is already the section name)
        first_cells = [v for v in non_blank[0] if v is not None and str(v).strip() != ""]
        if len(first_cells) == 1 and not _is_numeric(first_cells[0]):
            non_blank = non_blank[1:]

        if not non_blank:
            continue

        section = _build_table_section(name, non_blank)
        if section:
            tables.append(section)
            logger.debug("Sheet '%s' → %s (%d rows)", name, section.table_type, section.row_count)

    suggested_formula, confidence, method = _resolve_formula(tables, parameters, formula_detected)
    if is_prebuilt:
        suggested_formula = prebuilt_formula.get("expression", suggested_formula)
        confidence = 1.0
        method = "specialized_template"

    bundle = ParsedExcelBundle(
        bundle_id=str(uuid.uuid4()),
        tables=tables,
        parameters=parameters,
        formula_detected=formula_detected,
        suggested_formula=suggested_formula,
        formula_confidence=confidence,
        inference_method=method,
        is_prebuilt=is_prebuilt,
        prebuilt_calculation_steps=prebuilt_calculation_steps,
        prebuilt_formula=prebuilt_formula,
        prebuilt_variables=prebuilt_variables,
    )
    logger.info(
        "Parsed multi-sheet Excel bundle %s: %d sheets → %d tables, formula=%r (method=%s, confidence=%.2f)",
        bundle.bundle_id, len(wb.sheetnames), len(tables), suggested_formula, method, confidence,
    )
    return bundle


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def _segment(rows: List[List[Any]]) -> List[List[List[Any]]]:
    """Split rows into groups separated by blank rows."""
    groups: List[List[List[Any]]] = []
    current: List[List[Any]] = []
    for row in rows:
        if _is_blank(row):
            if current:
                groups.append(current)
                current = []
        else:
            current.append(row)
    if current:
        groups.append(current)
    return groups


def _is_blank(row: List[Any]) -> bool:
    return all(v is None or str(v).strip() == "" for v in row)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify_groups(
    groups: List[List[List[Any]]]
) -> Tuple[List[TableSection], Dict[str, str], Optional[str]]:
    tables: List[TableSection] = []
    parameters: Dict[str, str] = {}
    formula_detected: Optional[str] = None
    pending_name: Optional[str] = None   # section header waiting for next table group

    for group in groups:
        non_empty = [[v for v in row if v is not None and str(v).strip() != ""] for row in group]
        non_empty = [r for r in non_empty if r]
        if not non_empty:
            continue

        # ── Single-row groups ──────────────────────────────────────────────
        if len(non_empty) == 1:
            cells = non_empty[0]

            # Formula cell: single cell with math operators
            if len(cells) == 1 and _has_math(str(cells[0])):
                formula_detected = str(cells[0]).strip()
                continue

            # Parameter row: exactly 2 cells, left is known keyword
            if len(cells) == 2 and _is_param_key(cells[0]):
                k, v = str(cells[0]).lower().strip(), str(cells[1]).strip()
                parameters[k] = v
                if k == "formula" and _has_math(v):
                    formula_detected = v
                continue

            # Section header: single non-numeric string
            if len(cells) == 1 and not _is_numeric(cells[0]):
                pending_name = str(cells[0]).strip()
                continue

        # ── Multi-row groups ───────────────────────────────────────────────
        # Check whether the first row looks like a section header
        first = [v for v in non_empty[0] if v is not None and str(v).strip() != ""]
        start_idx = 0
        section_name = pending_name or "Table"
        pending_name = None

        if len(first) == 1 and not _is_numeric(first[0]):
            section_name = str(first[0]).strip()
            start_idx = 1

        data_rows = non_empty[start_idx:]
        if not data_rows:
            continue

        # Check if all rows look like key/value pairs → parameter block
        if _all_kv(data_rows):
            for row in data_rows:
                cells = [v for v in row if v is not None and str(v).strip() != ""]
                if len(cells) >= 2:
                    k, v = str(cells[0]).lower().strip(), str(cells[1]).strip()
                    parameters[k] = v
                    if k == "formula" and _has_math(v):
                        formula_detected = v
            continue

        # Otherwise treat as a data table
        section = _build_table_section(section_name, data_rows)
        if section:
            tables.append(section)

    return tables, parameters, formula_detected


def _has_math(text: str) -> bool:
    return bool(_MATH_RE.search(text))


def _is_param_key(val: Any) -> bool:
    return str(val).lower().strip() in _PARAM_KEYS


def _is_numeric(val: Any) -> bool:
    if val is None:
        return False
    try:
        float(str(val).strip())
        return True
    except (ValueError, TypeError):
        return False


def _all_kv(rows: List[List[Any]]) -> bool:
    """True if every row has exactly 2 non-empty cells and left cell is a param key."""
    for row in rows:
        cells = [v for v in row if v is not None and str(v).strip() != ""]
        if len(cells) != 2 or not _is_param_key(cells[0]):
            return False
    return True


# ---------------------------------------------------------------------------
# Table section builder
# ---------------------------------------------------------------------------

def _build_table_section(name: str, rows: List[List[Any]]) -> Optional[TableSection]:
    if not rows:
        return None

    # First row = headers
    headers = [str(v).strip() if v is not None else f"col_{i}" for i, v in enumerate(rows[0])]
    data_rows = rows[1:]

    if not data_rows:
        return None

    # Convert to list of dicts
    dicts = []
    for row in data_rows:
        padded = list(row) + [None] * (len(headers) - len(row))
        dicts.append({headers[i]: padded[i] for i in range(len(headers))})

    # Default: last column is output, rest are inputs.
    # Gemini will override via apply_table_classifications.
    output_col = headers[-1] if headers else "value"
    input_cols = headers[:-1]
    variable_name = _infer_variable_name(output_col, name)

    return TableSection(
        section_name=name,
        table_type="unknown",
        headers=headers,
        rows=dicts,
        row_count=len(dicts),
        output_column=output_col,
        input_columns=input_cols,
        variable_name=variable_name,
    )



# ---------------------------------------------------------------------------
# Variable name conversion
# ---------------------------------------------------------------------------

def _to_variable_name(section_name: str) -> str:
    """Convert a section name to UPPER_SNAKE_CASE for use in formulas."""
    # Strip common filler words
    name = re.sub(r"\b(table|factor|rate|lookup|rating)\b", "", section_name, flags=re.IGNORECASE)
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip())
    name = name.strip("_").upper()
    return name or "TABLE"


def _infer_variable_name(output_col: str, section_name: str) -> str:
    """
    Prefer the output column name as the formula variable when it already looks
    like UPPER_SNAKE_CASE (e.g. CREDIT_FACTOR, STATE_FACTOR, BASE_RATE).
    Fall back to deriving from the section/sheet name otherwise.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", output_col).strip("_")
    if cleaned and re.match(r"^[A-Z][A-Z0-9_]*$", cleaned):
        return cleaned
    return _to_variable_name(section_name)


# ---------------------------------------------------------------------------
# Algorithm sheet cell-formula detection
# ---------------------------------------------------------------------------

def _col_letter(n: int) -> str:
    """Convert 1-based column index to Excel column letter(s): 1→A, 26→Z, 27→AA."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _substitute_cell_refs(formula: str, cell_map: Dict[str, str]) -> str:
    """Replace Excel cell references (B2, $C$3) in a formula with variable names."""
    def _replace(m: re.Match) -> str:
        col = m.group(1).upper()
        row = m.group(2)
        return cell_map.get(f"{col}{row}", f"{col}{row}")
    return _CELL_REF_RE.sub(_replace, formula)


def _parse_algorithm_sheet_formulas(ws) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Parse an Algorithm sheet loaded with data_only=False.

    Expected layout (header row optional):
        Variable        | Example Value  | Notes
        BASE_RATE       | 1000           | from Base Rate table
        STATE_FACTOR    | 1.05           | from State Factor table
        AGE_FACTOR      | 1.30           | from Age Factor table
        CREDIT_FACTOR   | 0.95           | from Credit Score table
                        |                |
        PREMIUM         | =B2*B3*B4*B5   | final premium

    The cell in column B whose value starts with "=" is the formula cell.
    Rows in column A provide the variable-name → row mapping used to resolve
    cell references (B2 → BASE_RATE, B3 → STATE_FACTOR, …).

    Also supports:
      - Named-range formulas: =BASE_RATE*STATE_FACTOR (refs already variable names)
      - key-value parameter rows: formula | BASE_RATE * STATE_FACTOR (existing format)
      - MAX/MIN/ROUND and other Excel functions in the formula cell
      - Absolute references: $B$2 treated the same as B2

    Returns (resolved_formula_or_None, extra_parameters).
    """
    row_to_var: Dict[int, str] = {}
    raw_formula: Optional[str] = None
    extra_params: Dict[str, str] = {}

    for row in ws.iter_rows(values_only=False):
        if not row:
            continue

        col_a_cell = row[0]
        col_b_cell = row[1] if len(row) > 1 else None

        col_a = col_a_cell.value
        col_b = col_b_cell.value if col_b_cell is not None else None
        row_num = col_a_cell.row

        if col_a is None or str(col_a).strip() == "":
            continue

        label = str(col_a).strip()

        # Skip header rows (Variable / Name / Description etc.)
        if label.lower() in _ALGO_HEADER_WORDS:
            continue

        # Existing key-value parameter row (e.g. "formula | BASE_RATE * …")
        if _is_param_key(label) and col_b is not None:
            k = label.lower()
            v = str(col_b).strip()
            extra_params[k] = v
            if k == "formula" and _has_math(v):
                return v, extra_params  # text formula already resolved
            continue

        # Formula cell: column B starts with "="
        if isinstance(col_b, str) and col_b.startswith("="):
            raw_formula = col_b[1:]  # strip leading "="
            # Don't add this row's variable to the lookup map — it's the output
            continue

        # Variable name row: column A = UPPER_SNAKE_CASE name, column B = example value
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", label).strip("_")
        var = cleaned.upper() if cleaned else label.upper()
        if var:
            row_to_var[row_num] = var

    if raw_formula is None:
        return None, extra_params

    # Named-range formula (e.g. =BASE_RATE*STATE_FACTOR): no cell refs to resolve
    if not row_to_var or not _CELL_REF_RE.search(raw_formula):
        stripped = raw_formula.strip()
        return (stripped if _has_math(stripped) else None), extra_params

    # Build cell-reference → variable-name map
    # Map every cell in each "variable" row to that variable name
    max_col = max(ws.max_column or 1, 26)
    cell_map: Dict[str, str] = {}
    for rnum, var in row_to_var.items():
        for col_idx in range(1, max_col + 1):
            cell_map[f"{_col_letter(col_idx)}{rnum}"] = var

    resolved = _substitute_cell_refs(raw_formula, cell_map)
    logger.debug("Algorithm sheet cell formula %r → resolved %r", raw_formula, resolved)
    return resolved, extra_params


# ---------------------------------------------------------------------------
# Formula resolution
# ---------------------------------------------------------------------------

def _resolve_formula(
    tables: List[TableSection],
    parameters: Dict[str, str],
    formula_detected: Optional[str],
) -> Tuple[str, float, str]:
    """Return (formula_expression, confidence, method).

    Only explicit formulas (from a Config sheet formula row or isolated formula
    cell) are resolved here with high confidence.  All other cases return an
    empty string and 0.0 confidence so that the MCP layer delegates formula
    inference to Gemini via apply_table_classifications.
    """
    if formula_detected:
        return formula_detected.strip(), 1.0, "explicit"
    return "", 0.0, "llm"


# ---------------------------------------------------------------------------
# Calculation steps builder (used by infer_algorithm MCP tool)
# ---------------------------------------------------------------------------

_STEP_X_GAP = 400


def build_calculation_steps(
    tables: List[TableSection],
    formula: str,
    table_ids: List[int],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Build calculation_steps[] and variables{} matching the typed xyflow workflow
    schema in app/schemas/algorithm_workflow.py (CalculationStep / Formula) —
    this is the shape the Algorithm Workflow UI actually renders and edits, so
    steps are built via those Pydantic models rather than an ad-hoc dict shape.

    Returns (calculation_steps, variables_dict, workflow_edges).
    """
    steps: List[CalculationStep] = []
    edges: List[WorkflowEdge] = []
    step_order = 1
    x = 0

    # Collect all input variables from tables
    all_inputs: List[str] = []
    for t in tables:
        all_inputs.extend(t.input_columns)
    unique_inputs = list(dict.fromkeys(all_inputs))  # preserve order, deduplicate

    # Step 1: data_intake
    intake_step_id = "step-1"
    intakes = [
        IntakeField(question=f"{v}?", variableName=v, dataType="string", inputControl="input", required=True)
        for v in unique_inputs
    ]
    steps.append(CalculationStep(
        id=intake_step_id, type="data_intake", label="Input Variables",
        data=DataIntakeStepData(stepType="data_intake", label="Input Variables",
                                 stepOrder=step_order, intakes=intakes),
        position=Position(x=x, y=0),
    ))
    step_order += 1
    x += _STEP_X_GAP
    prev_step_id = intake_step_id

    # Step 2: rating_table_lookup — one Lookup per table, all in a single step
    intermediate_vars: List[str] = []
    lookups: List[Lookup] = []
    for table, tid in zip(tables, table_ids):
        var = table.variable_name or "TABLE"
        field_mappings = [
            FieldMapping(tableField=col, variableName=col, valueSource="variable", compareOperator="eq")
            for col in table.input_columns
        ]
        lookups.append(Lookup(
            tableName=table.section_name,
            fieldMappings=field_mappings,
            outputField=table.output_column,
            interpolationMode="exact",
            outputVariable=var,
        ))
        intermediate_vars.append(var)

    if lookups:
        lookup_step_id = "step-2"
        steps.append(CalculationStep(
            id=lookup_step_id, type="rating_table_lookup", label="Table Lookups",
            data=RatingTableLookupStepData(stepType="rating_table_lookup", label="Table Lookups",
                                            stepOrder=step_order, lookups=lookups),
            position=Position(x=x, y=0),
        ))
        edges.append(WorkflowEdge(id=f"e-{prev_step_id}-{lookup_step_id}",
                                   source=prev_step_id, target=lookup_step_id))
        prev_step_id = lookup_step_id
        step_order += 1
        x += _STEP_X_GAP

    # Expression step
    expr_step_id = f"step-{step_order}"
    steps.append(CalculationStep(
        id=expr_step_id, type="expression", label="Premium Formula",
        data=ExpressionStepData(stepType="expression", label="Premium Formula", stepOrder=step_order,
                                 expressions=[Expression(expression=formula or "0", outputVariable="PREMIUM")]),
        position=Position(x=x, y=0),
    ))
    edges.append(WorkflowEdge(id=f"e-{prev_step_id}-{expr_step_id}", source=prev_step_id, target=expr_step_id))
    prev_step_id = expr_step_id
    step_order += 1
    x += _STEP_X_GAP

    # Quote output step
    output_step_id = f"step-{step_order}"
    steps.append(CalculationStep(
        id=output_step_id, type="quote_output", label="Output",
        data=QuoteOutputStepData(stepType="quote_output", label="Output", stepOrder=step_order,
                                  outputs=[OutputExpression(expression="PREMIUM", formatTemplate="")]),
        position=Position(x=x, y=0),
    ))
    edges.append(WorkflowEdge(id=f"e-{prev_step_id}-{output_step_id}", source=prev_step_id, target=output_step_id))

    variables = {
        "input_variables": {v: "string" for v in unique_inputs},
        "intermediate_variables": {v: "number" for v in intermediate_vars},
        "output_variables": {"PREMIUM": "number"},
    }

    steps_dicts = [json.loads(s.model_dump_json(exclude_none=True)) for s in steps]
    edges_dicts = [json.loads(e.model_dump_json(exclude_none=True)) for e in edges]

    return steps_dicts, variables, edges_dicts
