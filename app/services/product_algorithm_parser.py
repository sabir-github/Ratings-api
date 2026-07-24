"""
Specialized parser for the "Product Algorithm" worksheet layout (Div 67 Umbrella
rating plan template).

Why this exists: excel_parser.py's generic parser only segments a sheet by
blank *rows*. This worksheet instead packs ~10 distinct lookup tables
side-by-side in different *column* ranges that all overlap the same row span
(e.g. State Factor in K:L, Increased Limits in N:O, Distribution ERC in Q:R —
all within rows 8-66). Row-based segmentation cannot separate those tables and
merges them into garbage. This module extracts each table via fixed,
hand-verified cell ranges instead, and also pre-builds the full
calculation_steps/formula (the real computation needs multiple chained
expressions and conditional logic — e.g. an Agency-vs-Direct-Marketing branch,
an NJ credit-score carve-out, and a tiered limit/SIR premium calc — which a
single formula string cannot express).

Detected via sheet name match ("product algorithm", case-insensitive) in
excel_parser._parse_multi_sheet(). If the sheet's vehicle-type table doesn't
match what these formulas depend on (VEHICLE_TYPES), parsing raises and the
caller falls back to the generic parser rather than silently producing a wrong
algorithm.

app/scripts/parse_product_algorithm.py is the standalone CLI wrapper around
this same logic, for regenerating a one-off mongoimport JSON file by hand.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from openpyxl.worksheet.worksheet import Worksheet

from app.schemas.algorithm_workflow import (
    CalculationStep,
    DataIntakeStepData,
    Expression,
    ExpressionStepData,
    FieldMapping,
    Formula,
    IntakeField,
    Lookup,
    OutputExpression,
    Position,
    QuoteOutputStepData,
    RatingTableLookupStepData,
    WorkflowEdge,
)

SHEET_NAME_MATCH = "product algorithm"

# --------------------------------------------------------------------------
# Cell ranges for the "Product Algorithm" worksheet template. Each range is
# (key_column, value_column, first_row, last_row) as used by read_table().
# --------------------------------------------------------------------------
TABLE_1_STATE_FACTOR = ("K", "L", 8, 59)
TABLE_2_HAZARD_GRADE = ("N", "O", 29, 38)
TABLE_4_INCREASED_LIMITS = ("N", "O", 10, 19)
TABLE_5_SIR_FACTOR = ("N", "O", 23, 24)
TABLE_7_CREDIT_SCORE = ("N", "O", 53, 57)
TABLE_8_AUTO_LOCAL = ("N", "O", 61, 66)
TABLE_10_PROGRAM = ("N", "O", 46, 50)
TABLE_11_MINIMUM_PREMIUM = ("K", "L", 71, 80)
TABLE_11_DIST_SYSTEM_ERC = ("Q", "R", 12, 63)
TABLE_13_FRANCHISE_CREDIT = ("N", "O", 89, 90)

# Vehicle-type label -> (variable suffix, display name, long-distance rate multiplier).
# Matched against Table 8 row labels by substring (order matters: check
# "Extra Heavy" before "Heavy").
VEHICLE_TYPES: List[Tuple[str, str, str, float]] = [
    ("PP Type", "PPType", "Private Passenger", 1.5),
    ("Light Truck", "LightTruck", "Light Truck or Van", 1.5),
    ("Medium Truck", "MediumTruck", "Medium Truck or Van", 1.5),
    ("Extra Heavy", "ExtraHeavy", "Extra Heavy", 2.0),
    ("Heavy", "Heavy", "Heavy", 2.0),
    ("All Other", "AllOther", "All Other", 2.0),
]

BASE_PREMIUM_FOR_MILLION = 350
BASE_PREMIUM_PER_ADDL_LOCATION = 35


def is_product_algorithm_sheet(sheet_name: str) -> bool:
    return sheet_name.strip().lower() == SHEET_NAME_MATCH


def read_table(ws: Worksheet, key_col: str, val_col: str, first_row: int, last_row: int) -> List[Tuple[Any, Any]]:
    """Reads a simple two-column (key, value) lookup table from a worksheet range."""
    rows = []
    for row in range(first_row, last_row + 1):
        key = ws[f"{key_col}{row}"].value
        val = ws[f"{val_col}{row}"].value
        if key is None or val is None:
            continue
        rows.append((key, val))
    return rows


def match_vehicle_type(label: str) -> Optional[Tuple[str, float]]:
    for needle, suffix, _, multiplier in VEHICLE_TYPES:
        if needle.lower() in label.lower():
            return suffix, multiplier
    return None


# ---------------------------------------------------------------------------
# Rating table extraction (for creating the actual Mongo rating table docs)
# ---------------------------------------------------------------------------

def build_table_sections(ws: Worksheet) -> List["TableSection"]:  # noqa: F821 (deferred import below)
    from app.services.excel_parser import TableSection

    def section(name: str, key_header: str, val_header: str, cell_range: tuple) -> TableSection:
        rows = read_table(ws, *cell_range)
        dict_rows = [{key_header: k, val_header: v} for k, v in rows]
        return TableSection(
            section_name=name,
            table_type="factor_table",
            headers=[key_header, val_header],
            rows=dict_rows,
            row_count=len(dict_rows),
            output_column=val_header,
            input_columns=[key_header],
            variable_name="",
        )

    return [
        section("Table 1 - State Factor (Div 67)", "State", "Div 67", TABLE_1_STATE_FACTOR),
        section("Table 10 - Program Factors", "Program", "Relativities", TABLE_10_PROGRAM),
        section("Table 2 - Hazard Grade Relativities", "Grade", "Relativities", TABLE_2_HAZARD_GRADE),
        section("Table 11 - Distribution System ERC", "State", "Relativities", TABLE_11_DIST_SYSTEM_ERC),
        section("Table 13 - Franchise/Association Credit", "Franchise/Association", "Factor", TABLE_13_FRANCHISE_CREDIT),
        section("Table 7 - Credit Score Factor", "Credit Score", "Factor", TABLE_7_CREDIT_SCORE),
        section("Table 5 - Self-Insured Retention Factor", "Self-Insured Retention", "Factor", TABLE_5_SIR_FACTOR),
        section("Table 8 - Auto Factors (Local & Medium)", "Vehicle Type", "Rate", TABLE_8_AUTO_LOCAL),
        section("Table 4 - Increased Limits Factor", "Limit", "Factor", TABLE_4_INCREASED_LIMITS),
        section("Table 11 - Minimum Premium", "Limit", "Minimum Premium", TABLE_11_MINIMUM_PREMIUM),
    ]


# ---------------------------------------------------------------------------
# Calculation step builders
# ---------------------------------------------------------------------------

def build_data_intake_step(state_codes: List[str], program_names: List[str],
                            credit_score_bands: List[str]) -> CalculationStep:
    intakes = [
        IntakeField(question="Number of Additional Locations", variableName="numAdditionalLocations",
                    dataType="number", inputControl="input", required=True),
    ]

    for _, suffix, display_name, _ in VEHICLE_TYPES:
        intakes.append(IntakeField(
            question=f"Number of {display_name} Vehicles - Local & Medium Radius",
            variableName=f"qty{suffix}Local", dataType="number", inputControl="input",
        ))
        intakes.append(IntakeField(
            question=f"Number of {display_name} Vehicles - Long Distance Radius",
            variableName=f"qty{suffix}LongDistance", dataType="number", inputControl="input",
        ))

    intakes += [
        IntakeField(question="State of Domicile", variableName="stateOfDomicile", dataType="string",
                    inputControl="dropdown", options=",".join(state_codes), required=True),
        IntakeField(question="Program", variableName="program", dataType="string",
                    inputControl="dropdown", options=",".join(program_names), required=True),
        IntakeField(question="Hazard Grade", variableName="hazardGrade", dataType="number",
                    inputControl="dropdown", options="1,2,3,4,5,6,7,8,9,10", required=True),
        IntakeField(question="1. Dist. System Credit", variableName="distSystemCredit", dataType="string",
                    inputControl="dropdown", options="Direct Marketing,Agency", required=True),
        IntakeField(question="2. Franchise/ Association Credit", variableName="franchiseAssociationCredit",
                    dataType="string", inputControl="dropdown", options="Yes,No", required=True),
        IntakeField(question="3. Credit Score", variableName="creditScore", dataType="string",
                    inputControl="dropdown", options=",".join(credit_score_bands), required=True),
        IntakeField(question="Coverage Part Purchased?", variableName="coveragePartPurchased", dataType="string",
                    inputControl="dropdown", options="Yes,No", required=True),
        IntakeField(question="Limit", variableName="umbrellaLimit", dataType="number", inputControl="dropdown",
                    options="1000000,2000000,3000000,4000000,5000000,6000000,7000000,8000000,9000000,10000000",
                    required=True, visibleWhen="coveragePartPurchased == 'Yes'"),
        IntakeField(question="Deductible (Self-Insured Retention)", variableName="selfInsuredRetention",
                    dataType="string", inputControl="dropdown", options="Zero,10000", required=True,
                    visibleWhen="coveragePartPurchased == 'Yes'"),
    ]

    data = DataIntakeStepData(stepType="data_intake", label="Div 67 Umbrella - Inputs", stepOrder=1, intakes=intakes)
    return CalculationStep(id="step-1", type="data_intake", label="Div 67 Umbrella - Inputs",
                            data=data, position=Position(x=0, y=0))


def build_rating_table_lookup_step(vehicle_labels: Dict[str, str]) -> CalculationStep:
    def var_lookup(table_name: str, table_field: str, variable_name: str, output_field: str,
                    output_variable: str, run_condition: Optional[str] = None) -> Lookup:
        return Lookup(
            tableName=table_name,
            fieldMappings=[FieldMapping(tableField=table_field, variableName=variable_name,
                                         valueSource="variable", compareOperator="eq")],
            outputField=output_field, interpolationMode="exact",
            outputVariable=output_variable, runCondition=run_condition,
        )

    def literal_lookup(table_name: str, table_field: str, literal_value: str, output_field: str,
                        output_variable: str, run_condition: Optional[str] = None) -> Lookup:
        return Lookup(
            tableName=table_name,
            fieldMappings=[FieldMapping(tableField=table_field, valueSource="literal",
                                         literalValue=literal_value, compareOperator="eq")],
            outputField=output_field, interpolationMode="exact",
            outputVariable=output_variable, runCondition=run_condition,
        )

    lookups = [
        var_lookup("Table 1 - State Factor (Div 67)", "State", "stateOfDomicile", "Div 67", "stateFactor"),
        var_lookup("Table 10 - Program Factors", "Program", "program", "Relativities", "programFactor"),
        var_lookup("Table 2 - Hazard Grade Relativities", "Grade", "hazardGrade", "Relativities", "hazardGradeFactor"),
        var_lookup("Table 11 - Distribution System ERC", "State", "stateOfDomicile", "Relativities",
                    "distSystemERCFactor", run_condition="distSystemCredit != 'Agency'"),
        var_lookup("Table 13 - Franchise/Association Credit", "Franchise/Association",
                    "franchiseAssociationCredit", "Factor", "franchiseCreditFactor"),
        var_lookup("Table 7 - Credit Score Factor", "Credit Score", "creditScore", "Factor", "creditScoreFactor",
                    run_condition="stateOfDomicile != 'NJ'"),
        literal_lookup("Table 5 - Self-Insured Retention Factor", "Self-Insured Retention", "Zero",
                        "Factor", "sirFactorZero"),
        literal_lookup("Table 5 - Self-Insured Retention Factor", "Self-Insured Retention", "10000",
                        "Factor", "sirFactor10000"),
    ]

    for _, suffix, _, _ in VEHICLE_TYPES:
        lookups.append(literal_lookup("Table 8 - Auto Factors (Local & Medium)", "Vehicle Type",
                                       vehicle_labels[suffix], "Rate", f"rateLocal{suffix}"))

    lookups += [
        var_lookup("Table 4 - Increased Limits Factor", "Limit", "umbrellaLimit", "Factor",
                    "increasedLimitsFactor", run_condition="coveragePartPurchased == 'Yes' && umbrellaLimit != 1000000"),
        var_lookup("Table 11 - Minimum Premium", "Limit", "umbrellaLimit", "Minimum Premium",
                    "minimumPremiumSelected", run_condition="coveragePartPurchased == 'Yes'"),
        literal_lookup("Table 11 - Minimum Premium", "Limit", "1000000", "Minimum Premium",
                        "minimumPremium1M", run_condition="coveragePartPurchased == 'Yes'"),
    ]

    data = RatingTableLookupStepData(stepType="rating_table_lookup", label="Div 67 Umbrella - Table Lookups",
                                      stepOrder=2, lookups=lookups)
    return CalculationStep(id="step-2", type="rating_table_lookup", label="Div 67 Umbrella - Table Lookups",
                            data=data, position=Position(x=400, y=0))


def build_expression_step() -> CalculationStep:
    exprs = [
        Expression(expression=f"numAdditionalLocations * {BASE_PREMIUM_PER_ADDL_LOCATION}",
                   outputVariable="basePremiumAddlLocations"),
    ]

    for _, suffix, _, multiplier in VEHICLE_TYPES:
        multiplier_literal = int(multiplier) if multiplier == int(multiplier) else multiplier
        exprs.append(Expression(expression=f"rateLocal{suffix} * {multiplier_literal}",
                                 outputVariable=f"rateLong{suffix}"))
    for _, suffix, _, _ in VEHICLE_TYPES:
        exprs.append(Expression(
            expression=f"qty{suffix}Local * rateLocal{suffix} + qty{suffix}LongDistance * rateLong{suffix}",
            outputVariable=f"premium{suffix}",
        ))

    premium_sum = " + ".join(f"premium{suffix}" for _, suffix, _, _ in VEHICLE_TYPES)
    exprs += [
        Expression(expression=premium_sum, outputVariable="totalAutoBasePremium"),
        Expression(expression=f"totalAutoBasePremium + basePremiumAddlLocations + {BASE_PREMIUM_FOR_MILLION}",
                   outputVariable="totalBasePremium"),
        Expression(expression="distSystemCredit == 'Agency' ? 1 : distSystemERCFactor",
                   outputVariable="distSystemCreditFactor"),
        Expression(expression="stateOfDomicile == 'NJ' ? 1 : creditScoreFactor",
                   outputVariable="creditScoreFactorFinal"),
        Expression(
            expression=("totalBasePremium * stateFactor * programFactor * hazardGradeFactor "
                        "* distSystemCreditFactor * franchiseCreditFactor * creditScoreFactorFinal"),
            outputVariable="factorProduct",
        ),
        Expression(expression="max(minimumPremium1M, factorProduct * sirFactorZero)",
                   outputVariable="premiumAt1M_Zero", runCondition="coveragePartPurchased == 'Yes'"),
        Expression(expression="max(minimumPremium1M, factorProduct * sirFactor10000)",
                   outputVariable="premiumAt1M_10000", runCondition="coveragePartPurchased == 'Yes'"),
        Expression(expression="selfInsuredRetention == '10000' ? sirFactor10000 : sirFactorZero",
                   outputVariable="selectedSIRFactor", runCondition="coveragePartPurchased == 'Yes'"),
        Expression(expression="selfInsuredRetention == '10000' ? premiumAt1M_10000 : premiumAt1M_Zero",
                   outputVariable="premiumAt1M_Selected", runCondition="coveragePartPurchased == 'Yes'"),
        Expression(
            expression=("umbrellaLimit == 1000000 ? premiumAt1M_Selected : "
                        "max(minimumPremiumSelected + premiumAt1M_Selected, "
                        "factorProduct * increasedLimitsFactor * selectedSIRFactor)"),
            outputVariable="ratedPremiumAtSelectedLimit", runCondition="coveragePartPurchased == 'Yes'",
        ),
        Expression(expression="coveragePartPurchased == 'No' ? 0 : ratedPremiumAtSelectedLimit",
                   outputVariable="chargedPremium"),
    ]

    data = ExpressionStepData(stepType="expression", label="Div 67 Umbrella - Premium Calculation",
                               stepOrder=3, expressions=exprs)
    return CalculationStep(id="step-3", type="expression", label="Div 67 Umbrella - Premium Calculation",
                            data=data, position=Position(x=800, y=0))


def build_quote_output_step() -> CalculationStep:
    outputs = [
        OutputExpression(expression="totalBasePremium", formatTemplate="Total Base Premium: ${value}"),
        OutputExpression(expression="chargedPremium", formatTemplate="Charged Premium: ${value}"),
    ]
    data = QuoteOutputStepData(stepType="quote_output", label="Div 67 Umbrella - Quote Output",
                                stepOrder=4, outputs=outputs)
    return CalculationStep(id="step-4", type="quote_output", label="Div 67 Umbrella - Quote Output",
                            data=data, position=Position(x=1200, y=0))


def parse_workbook_sheet(ws: Worksheet, source_label: str) -> Tuple[Formula, List[CalculationStep]]:
    """
    Build the full typed Formula + CalculationStep list from an already-open
    "Product Algorithm" worksheet. Raises ValueError if the sheet's vehicle-type
    table doesn't match what these formulas depend on (layout changed).
    """
    state_codes = [str(k) for k, _ in read_table(ws, *TABLE_1_STATE_FACTOR)]
    program_names = [str(k) for k, _ in read_table(ws, *TABLE_10_PROGRAM)]
    credit_score_bands = [str(k) for k, _ in read_table(ws, *TABLE_7_CREDIT_SCORE)]

    auto_rows = read_table(ws, *TABLE_8_AUTO_LOCAL)
    vehicle_labels: Dict[str, str] = {}
    for k, _ in auto_rows:
        match = match_vehicle_type(str(k))
        if match:
            vehicle_labels[match[0]] = str(k)
    expected = {suffix for _, suffix, _, _ in VEHICLE_TYPES}
    if set(vehicle_labels) != expected:
        raise ValueError(
            f"Table 8 - Auto Factors (Local & Medium) on sheet '{ws.title}' does not match the "
            f"expected vehicle types. Expected {sorted(expected)}, found {sorted(vehicle_labels)}."
        )

    if not state_codes or not program_names or not credit_score_bands:
        raise ValueError("One or more required lookup tables (State, Program, Credit Score) were empty.")

    steps = [
        build_data_intake_step(state_codes, program_names, credit_score_bands),
        build_rating_table_lookup_step(vehicle_labels),
        build_expression_step(),
        build_quote_output_step(),
    ]

    edges = [
        WorkflowEdge(id="e1-2", source="step-1", target="step-2"),
        WorkflowEdge(id="e2-3", source="step-2", target="step-3"),
        WorkflowEdge(id="e3-4", source="step-3", target="step-4"),
    ]
    formula = Formula(
        expression="chargedPremium",
        description=f"Div. 67 Umbrella Rating Plan - derived from the '{ws.title}' worksheet of {source_label}",
        workflowEdges=edges,
    )
    return formula, steps


# ---------------------------------------------------------------------------
# Entry point used by excel_parser.py's multi-sheet parser
# ---------------------------------------------------------------------------

def try_parse(ws: Worksheet, source_label: str = "uploaded workbook") -> Optional[
    Tuple[List["TableSection"], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]  # noqa: F821
]:
    """
    Attempt to parse `ws` as a Product Algorithm sheet.

    Returns (table_sections, calculation_steps_dicts, formula_dict, variables_dict)
    on success, or None if the sheet doesn't match the expected layout (caller
    should fall back to the generic parser).
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        formula, steps = parse_workbook_sheet(ws, source_label)
        table_sections = build_table_sections(ws)
    except Exception:
        logger.warning(
            "Product Algorithm specialized parser failed validation for sheet %r; "
            "falling back to generic parser.", ws.title, exc_info=True,
        )
        return None

    calculation_steps = [json.loads(s.model_dump_json(exclude_none=True)) for s in steps]
    formula_dict = json.loads(formula.model_dump_json(exclude_none=True))

    all_input_vars = [
        f.get("variableName") for s in calculation_steps if s["type"] == "data_intake"
        for f in s["data"]["intakes"]
    ]
    variables = {
        "input_variables": {v: "string" for v in all_input_vars},
        "intermediate_variables": {},
        "output_variables": {"totalBasePremium": "number", "chargedPremium": "number"},
    }

    return table_sections, calculation_steps, formula_dict, variables
