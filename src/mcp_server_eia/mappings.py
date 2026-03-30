"""
Human-readable inputs → EIA facet codes. Core value of this MCP layer.
"""

from __future__ import annotations

# Fuel groups for inventory search (energy_source_code on operating-generator-capacity)
FUEL_TYPE_TO_CODES: dict[str, list[str]] = {
    "coal": ["BIT", "SUB", "LIG", "RC", "WC", "SC"],
    "gas": ["NG"],
    "oil": ["DFO", "RFO", "JF", "KER", "PC", "WO"],
    "nuclear": ["NUC"],
    "solar": ["SUN"],
    "wind": ["WND"],
    "hydro": ["WAT"],
}

# Map a single EIA energy_source_code to a coarse label (primary fuel at plant level)
CODE_TO_LABEL: dict[str, str] = {}
for _label, codes in FUEL_TYPE_TO_CODES.items():
    for c in codes:
        CODE_TO_LABEL[c] = _label


def all_inventory_energy_codes() -> list[str]:
    return sorted({c for codes in FUEL_TYPE_TO_CODES.values() for c in codes})


def codes_for_fuel_type(fuel_type: str) -> list[str]:
    k = fuel_type.strip().lower()
    if k == "all":
        return all_inventory_energy_codes()
    if k not in FUEL_TYPE_TO_CODES:
        raise ValueError(
            f"Unknown fuel_type {fuel_type!r}. Use one of: "
            + ", ".join(sorted(FUEL_TYPE_TO_CODES.keys())) + ", all"
        )
    return list(FUEL_TYPE_TO_CODES[k])


# Generator status (EIA Form 860 / operating-generator-capacity)
STATUS_TO_CODES: dict[str, list[str]] = {
    "operating": ["OP"],
    "standby": ["SB"],
    "retired": ["OS"],
    "planned": ["P"],
}


def codes_for_status(status: str) -> list[str]:
    k = status.strip().lower()
    if k not in STATUS_TO_CODES:
        raise ValueError(
            f"Unknown status {status!r}. Use one of: {', '.join(STATUS_TO_CODES)}"
        )
    return STATUS_TO_CODES[k]


# Retail electricity sales (electricity/retail-sales)
SECTOR_CODE_MAP: dict[str, str] = {
    "residential": "RES",
    "commercial": "COM",
    "industrial": "IND",
    "all": "ALL",
}


def sector_id_for_retail(sector: str) -> str:
    k = sector.strip().lower()
    if k not in SECTOR_CODE_MAP:
        raise ValueError(
            f"Unknown sector {sector!r}. Use one of: {', '.join(SECTOR_CODE_MAP)}"
        )
    return SECTOR_CODE_MAP[k]


# AEO — aligned with Burnout `aeo_refresh.py` (table IDs + scenario)
AEO_SCENARIO_MAP: dict[str, str] = {
    "reference": "ref2025",
    "high_oil": "highmacro",
    "low_oil": "lowmacro",
    "high_renewables": "highre",
}

# National fuel prices (table 3) — seriesId facets
AEO_SERIES_NATIONAL_GAS = "prce_nom_elep_NA_ng_NA_NA_ndlrpmbtu"
AEO_SERIES_NATIONAL_COAL = "prce_nom_elep_NA_stc_NA_NA_ndlrpmbtu"
# Residual fuel oil — electric power (proxy for “oil” in AEO table 3)
AEO_SERIES_NATIONAL_OIL = "prce_nom_elep_NA_rfo_NA_NA_ndlrpmbtu"

TABLE_NATIONAL = "3"
TABLE_EMM = "62"
TABLE_RENEW = "67"
TABLE_EMISSIONS = "18"
REGION_US = "1-0"

AEO_DATA_LAST_YEAR = 2050


def scenario_code_for_name(name: str) -> str:
    k = name.strip().lower()
    if k not in AEO_SCENARIO_MAP:
        raise ValueError(
            f"Unknown scenario {name!r}. Use one of: {', '.join(AEO_SCENARIO_MAP)}"
        )
    return AEO_SCENARIO_MAP[k]


# SEDS CO2 — five-character MSN-style: source (2) + sector (2) + unit (E)
_SEDS_SOURCE = {
    "coal": "CL",
    "natural_gas": "NN",
    "petroleum": "PM",
    "total": "TE",
}

_SEDS_SECTOR = {
    "electric_power": "EI",
    "residential": "RC",
    "commercial": "CC",
    "industrial": "IC",
    "transportation": "AC",
    "total": "TC",
}


def seds_co2_series_id(sector: str, fuel: str) -> str:
    """Build SEDS CO2 emissions series id (metric tons), e.g. CLEIE for coal / electric power."""
    sk = sector.strip().lower()
    fk = fuel.strip().lower()
    if sk not in _SEDS_SECTOR:
        raise ValueError(f"Unknown sector {sector!r} for SEDS CO2")
    if fk not in _SEDS_SOURCE:
        raise ValueError(f"Unknown fuel {fuel!r} for SEDS CO2")
    a, b = _SEDS_SOURCE[fk], _SEDS_SECTOR[sk]
    return f"{a}{b}E"


def label_for_energy_code(code: str) -> str:
    return CODE_TO_LABEL.get(code.upper(), "other")
