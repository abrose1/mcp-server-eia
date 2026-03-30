"""
Human-readable inputs → EIA facet codes. Core value of this MCP layer.
"""

from __future__ import annotations

from typing import Any

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


# electric-power-operational-data — headline mix (non-overlapping EIA parent codes)
# Sum of these buckets + optional "other" ≈ ALL (remainder = other / balancing).
EPOD_HEADLINE_MIX: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("coal", ("COL",)),
    ("natural_gas", ("NGO",)),
    ("nuclear", ("NUC",)),
    ("hydroelectric", ("HYC", "HPS")),
    ("renewables", ("AOR",)),
    ("petroleum", ("PET",)),
)

# --- Historical spot / market fuel prices (get_fuel_prices) ---
# EIA route IDs differ from shorthand in the technical plan (`coal/market` → `coal/market-sales-price` in API v2).

# Natural gas — Henry Hub spot: `natural-gas/pri/fut` (spot + contract series).
NG_HENRY_HUB_ROUTE = "natural-gas/pri/fut"
NG_HENRY_HUB_FACETS: dict[str, list[str]] = {
    "process": ["PS0"],
    "series": ["RNGWHHD"],
    "duoarea": ["RGC"],
    "product": ["EPG0"],
}

# Natural gas — citygate / wellhead (delivered): `natural-gas/pri/sum` (monthly + annual only).
NG_SUM_ROUTE = "natural-gas/pri/sum"
NG_SUM_PRODUCT = ["EPG0"]
# U.S. aggregate citygate and wellhead (duoarea NUS).
NG_CITYGATE_FACETS: dict[str, list[str]] = {
    "process": ["PG1"],
    "duoarea": ["NUS"],
    "product": NG_SUM_PRODUCT,
}
NG_WELLHEAD_FACETS: dict[str, list[str]] = {
    "process": ["FWA"],
    "duoarea": ["NUS"],
    "product": NG_SUM_PRODUCT,
}

# Coal — open-market price by region: `coal/market-sales-price` (annual only; dollars per short ton).
COAL_MARKET_SALES_ROUTE = "coal/market-sales-price"
COAL_MARKET_TYPE_OPEN = "OM"

# stateRegionId codes for common basins / areas (see EIA facet `coal/market-sales-price` / `stateRegionId`).
COAL_REGION_BY_PRICE_TYPE: dict[str, str] = {
    "powder_river": "PRB",
    "appalachian": "APC",
    "appalachian_northern": "APN",
    "appalachian_southern": "APS",
    "illinois": "IL",
    "illinois_basin": "INO",
}

# Petroleum spot benchmarks: `petroleum/pri/spt`.
PETROLEUM_SPOT_ROUTE = "petroleum/pri/spt"
PETROLEUM_SPOT_SERIES: dict[str, str] = {
    "wti": "RWTC",
    "brent": "RBRTE",
}


# --- STEO forecasts (get_steo_forecast) ---
#
# STEO exposes a `seriesId` facet with human-readable names. We don't want to
# expose every single seriesId (hundreds), so we resolve only a small curated
# set of human keys by matching keywords in EIA's `seriesName`.

_STEO_SUPPORTED_SERIES: dict[str, dict[str, list[str]]] = {
    # Keep keys stable for the LLM UX. Matching is heuristic on EIA `seriesName`.
    "crude_oil_price": {
        "any": ["crude oil"],
        "prefer": ["wti", "brent", "spot", "price"],
    },
    "natural_gas_price": {
        "any": ["natural gas"],
        "prefer": ["henry", "hub", "spot", "price"],
    },
    "electricity_demand": {
        # EIA STEO series names for electricity demand appear to use
        # "Net energy for electricity load, United States" rather than
        # the literal phrase "electricity demand".
        "any": ["electricity load"],
        "prefer": ["united states", "net energy"],
    },
}


def _steo_match_score(name_lower: str, any_keywords: list[str], preferred: list[str]) -> float:
    """
    Score candidate series based on keyword overlap.

    Important: preferred keywords should *only* matter if we already matched
    at least one of the required `any_keywords`. This prevents overly broad
    matches (e.g., any series containing "demand" being selected as "electricity_demand").
    """

    if not any(any_kw in name_lower for any_kw in any_keywords):
        return 0.0

    score = 1.0
    for p in preferred:
        if p in name_lower:
            score += 0.25
    return score


def steo_series_id_for_key(client: Any, series_key: str) -> tuple[str, str]:
    """
    Resolve `series_key` (human-friendly) -> (`seriesId`, `seriesName`) for STEO.

    This function calls the live EIA facet catalog to find the appropriate
    `seriesId` for the selected subset of series keys.
    """

    k = series_key.strip().lower()
    if k not in _STEO_SUPPORTED_SERIES:
        supported = ", ".join(sorted(_STEO_SUPPORTED_SERIES.keys()))
        raise ValueError(f"Unknown STEO series {series_key!r}. Use one of: {supported}.")

    cfg = _STEO_SUPPORTED_SERIES[k]

    facet_body = client.get("steo/facet/seriesId", params=[])
    err = facet_body.get("error")
    if err:
        raise RuntimeError(str(err))

    facets = (facet_body.get("response") or {}).get("facets") or []
    candidates: list[tuple[str, str, float]] = []
    for f in facets:
        sid = str(f.get("id") or "").strip()
        name = str(f.get("name") or "").strip()
        if not sid or not name:
            continue
        name_lower = name.lower()
        score = _steo_match_score(name_lower, cfg["any"], cfg["prefer"])
        if score <= 0:
            continue
        candidates.append((sid, name, score))

    if not candidates:
        raise ValueError(
            f"Could not resolve STEO seriesId for key {series_key!r}. EIA series catalog may have changed."
        )

    # Prefer the highest score; break ties deterministically by seriesId/name.
    candidates.sort(key=lambda t: (-t[2], t[0], t[1]))
    sid, name, _score = candidates[0]
    return sid, name
