"""
Div. 67 BOP Umbrella Rating Plan calculator.

Faithful re-implementation of the "Product Algorithm" worksheet found in
`Testing -AI Agent-modified.xlsx`. Every table/constant below is copied
verbatim from that sheet; every step in `calculate_premium` mirrors one
cell/formula from the workbook (cell references noted in comments).
"""

from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants (single-value cells)
# ---------------------------------------------------------------------------

BASE_PREMIUM_PER_MILLION = 350          # G5
ADDITIONAL_LOCATION_RATE = 35           # E9 (rate charged per additional location)

# Vehicle rating table (rows 14-19): type -> (local_rate, long_distance_rate)
# local_distance rate (col D) is the input rate; long distance (col E) is derived
# in the sheet but the multiplier differs by vehicle weight class, so both are
# stored explicitly here.
VEHICLE_RATE_TABLE: Dict[str, Tuple[float, float]] = {
    "Private Passenger Type": (35, 52.5),   # D14, E14 = D14*1.5
    "Light Truck or Van":     (35, 52.5),   # D15, E15 = D15*1.5
    "Medium Truck or Van":    (40, 60),     # D16, E16 = D16*1.5
    "Heavy":                  (150, 300),   # D17, E17 = D17*2
    "Extra Heavy":            (180, 360),   # D18, E18 = D18*2
    "All Other":              (180, 360),   # D19, E19 = D19*2
}

# Table 1 - State Factor (K8:L59)
STATE_FACTOR_TABLE: Dict[str, float] = {
    "AK": 1, "AL": 1.1, "AR": 1, "AZ": 1, "CA": 1.2, "CO": 1, "CT": 1, "DC": 1,
    "DE": 1, "FL": 1.1, "GA": 1, "HI": 1.2, "IA": 1, "ID": 1, "IL": 1.1, "IN": 1,
    "KS": 1, "KY": 1, "LA": 1, "MA": 1, "MD": 1, "ME": 1, "MI": 1, "MN": 1,
    "MO": 1, "MS": 1, "MT": 1, "NC": 1, "ND": 1, "NE": 1, "NH": 1, "NJ": 1.1,
    "NM": 1, "NV": 1, "NY": 1.1, "OH": 1, "OK": 1, "OR": 1, "PA": 1, "PR": 1,
    "RI": 1, "SC": 1, "SD": 1, "TN": 1, "TX": 1.2, "UT": 1, "VA": 1, "VT": 1,
    "WA": 1, "WI": 1, "WV": 1, "WY": 1,
}

# Table 10 - Program Factors (N46:O50)
PROGRAM_FACTOR_TABLE: Dict[str, float] = {
    "High Tech": 1.28,
    "Offices": 1,
    "Retail": 1.14,
    "Services": 1.28,
    "Wholesale": 1.28,
}

# Table 2 - Hazard Grade (N29:O38): grade (1-10) -> relativity
HAZARD_GRADE_TABLE: Dict[int, float] = {
    1: 0.5, 2: 0.65, 3: 0.78, 4: 0.9, 5: 1, 6: 1.1, 7: 1.2, 8: 1.28, 9: 1.38, 10: 1.5,
}

# Table 11 - Distribution System ERC (Q12:R63): state -> relativity
# (used only when Distribution System != "Agency")
DISTRIBUTION_SYSTEM_ERC_TABLE: Dict[str, float] = {
    state: (1.0 if state == "MO" else 0.9) for state in STATE_FACTOR_TABLE
}

# Table 13 - Franchise/Association Credit (N89:O90)
FRANCHISE_ASSOCIATION_TABLE: Dict[str, float] = {"No": 1, "Yes": 0.9}

# Table 7 - Credit Score (N53:O57)
CREDIT_SCORE_TABLE: Dict[str, float] = {
    "31 to 70": 1.1,
    "71 to 90": 0.95,
    "91 to 100": 0.85,
    "Below 30": 1.2,
    "New Venture or N/A": 1,
}

# Table 5 - Self-Insured Retention (N23:O24)
SIR_FACTOR_TABLE: Dict[str, float] = {"Zero": 1.1, 10000: 1}

# Table 4 - Increased Limits Factor (N10:O19): limit -> ILF
ILF_TABLE: Dict[int, float] = {
    1_000_000: 1.0, 2_000_000: 1.5, 3_000_000: 2.0, 4_000_000: 2.5,
    5_000_000: 3.0, 6_000_000: 3.5, 7_000_000: 4.0, 8_000_000: 4.5,
    9_000_000: 5.0, 10_000_000: 5.5,
}

# Table 11 - Minimum Premium (K71:L80): limit -> minimum premium component
MINIMUM_PREMIUM_TABLE: Dict[int, float] = {
    1_000_000: 350, 2_000_000: 300, 3_000_000: 600, 4_000_000: 900,
    5_000_000: 1200, 6_000_000: 1500, 7_000_000: 1800, 8_000_000: 2100,
    9_000_000: 2400, 10_000_000: 2700,
}

VALID_LIMITS = sorted(ILF_TABLE)  # $1M .. $10M in $1M steps


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

def calculate_premium(
    *,
    state: str,
    program: str,
    hazard_grade: int,
    distribution_system: str,           # "Agency" or "Direct Marketing"
    franchise_association: str,         # "Yes" or "No"
    credit_score_band: str,             # one of CREDIT_SCORE_TABLE keys
    sir: str,                           # "Zero" or 10000
    selected_limit: int,                # one of VALID_LIMITS
    additional_locations: int = 0,
    vehicles: Optional[Dict[str, Tuple[int, int]]] = None,  # {type: (local_count, long_distance_count)}
    coverage_purchased: bool = True,
) -> Dict[str, float]:
    """
    Compute the Div. 67 BOP Umbrella charged premium, following the same
    steps as the "Product Algorithm" worksheet.

    Returns a dict with the final `charged_premium` plus every intermediate
    value, so callers can audit how the number was produced.
    """
    state = state.upper()
    vehicles = vehicles or {}

    if state not in STATE_FACTOR_TABLE:
        raise ValueError(f"Unknown state: {state}")
    if program not in PROGRAM_FACTOR_TABLE:
        raise ValueError(f"Unknown program: {program}")
    if hazard_grade not in HAZARD_GRADE_TABLE:
        raise ValueError(f"Hazard grade must be 1-10, got {hazard_grade}")
    if franchise_association not in FRANCHISE_ASSOCIATION_TABLE:
        raise ValueError(f"Unknown franchise/association option: {franchise_association}")
    if credit_score_band not in CREDIT_SCORE_TABLE:
        raise ValueError(f"Unknown credit score band: {credit_score_band}")
    if sir not in SIR_FACTOR_TABLE:
        raise ValueError(f"Unknown SIR: {sir}")
    if selected_limit not in VALID_LIMITS:
        raise ValueError(f"Selected limit must be one of {VALID_LIMITS}, got {selected_limit}")

    if not coverage_purchased:
        return {"charged_premium": 0.0}

    # --- Step 1-2: Total Auto Base Premium (G14:G19 -> G21) ---
    vehicle_premiums = {}
    for vtype, (local_rate, long_rate) in VEHICLE_RATE_TABLE.items():
        local_count, long_count = vehicles.get(vtype, (0, 0))
        vehicle_premiums[vtype] = local_count * local_rate + long_count * long_rate
    total_auto_base_premium = sum(vehicle_premiums.values())  # G21

    # --- Step 3: Additional Locations Premium (G9) ---
    additional_locations_premium = additional_locations * ADDITIONAL_LOCATION_RATE

    # --- Step 4: Total Base Premium (G23) ---
    total_base_premium = (
        BASE_PREMIUM_PER_MILLION + additional_locations_premium + total_auto_base_premium
    )

    # --- Step 5: Rating factors (G26, G28, G30, G35, G36, G37) ---
    state_factor = STATE_FACTOR_TABLE[state]
    program_factor = PROGRAM_FACTOR_TABLE[program]
    hazard_grade_factor = HAZARD_GRADE_TABLE[hazard_grade]

    if distribution_system == "Agency":
        distribution_system_credit = 1.0
    else:
        distribution_system_credit = DISTRIBUTION_SYSTEM_ERC_TABLE[state]

    franchise_credit = FRANCHISE_ASSOCIATION_TABLE[franchise_association]

    credit_score_factor = 1.0 if state == "NJ" else CREDIT_SCORE_TABLE[credit_score_band]

    rating_factor_product = (
        total_base_premium
        * state_factor
        * program_factor
        * hazard_grade_factor
        * distribution_system_credit
        * franchise_credit
        * credit_score_factor
    )

    # --- Step 6: SIR factor and ILF ---
    sir_factor = SIR_FACTOR_TABLE[sir]
    ilf = ILF_TABLE[selected_limit]

    # --- Step 7: Premium at $1,000,000 limit (B44/C44) ---
    premium_at_1m = max(
        MINIMUM_PREMIUM_TABLE[1_000_000],
        rating_factor_product * SIR_FACTOR_TABLE[sir],
    )

    # --- Step 8: Premium at the selected limit (B45:C53 pattern) ---
    if selected_limit == 1_000_000:
        premium_at_selected_limit = premium_at_1m
    else:
        premium_at_selected_limit = max(
            MINIMUM_PREMIUM_TABLE[selected_limit] + premium_at_1m,
            rating_factor_product * ilf * sir_factor,
        )

    # --- Step 9: Charged Premium (B61) ---
    charged_premium = premium_at_selected_limit if coverage_purchased else 0.0

    return {
        "vehicle_premiums": vehicle_premiums,
        "total_auto_base_premium": total_auto_base_premium,
        "additional_locations_premium": additional_locations_premium,
        "total_base_premium": total_base_premium,
        "state_factor": state_factor,
        "program_factor": program_factor,
        "hazard_grade_factor": hazard_grade_factor,
        "distribution_system_credit": distribution_system_credit,
        "franchise_credit": franchise_credit,
        "credit_score_factor": credit_score_factor,
        "rating_factor_product": rating_factor_product,
        "sir_factor": sir_factor,
        "increased_limits_factor": ilf,
        "premium_at_1m": premium_at_1m,
        "charged_premium": round(charged_premium, 2),
    }


if __name__ == "__main__":
    # Reproduces the exact scenario captured in the worksheet (B61 = 714).
    result = calculate_premium(
        state="MO",
        program="Offices",
        hazard_grade=10,
        distribution_system="Direct Marketing",
        franchise_association="No",
        credit_score_band="91 to 100",
        sir=10000,
        selected_limit=1_000_000,
        additional_locations=2,
        vehicles={"Private Passenger Type": (1, 2)},
        coverage_purchased=True,
    )
    for key, value in result.items():
        print(f"{key}: {value}")
