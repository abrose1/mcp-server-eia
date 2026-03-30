"""Tools: get_generation_mix, get_capacity_by_fuel (electricity route family)."""

from __future__ import annotations

import logging
from typing import Any

from mcp_server_eia.eia_client import DEFAULT_PAGE, EIAClient
from mcp_server_eia.mappings import (
    EPOD_HEADLINE_MIX,
    codes_for_fuel_type,
    codes_for_status,
    label_for_energy_code,
)
from mcp_server_eia.response_util import envelope, error_envelope

logger = logging.getLogger(__name__)

EPOD_ROUTE = "electricity/electric-power-operational-data"
OPERATING_GENERATOR_ROUTE = "electricity/operating-generator-capacity"
SECTOR_ELECTRIC_POWER = "98"


def _parse_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _eia_exception_envelope(exc: BaseException) -> dict[str, Any]:
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg:
        return error_envelope(
            "EIA API rate limit reached. Try again in a moment.",
            source="electricity",
        )
    if "503" in msg or "502" in msg or "504" in msg or "timeout" in msg:
        return error_envelope(
            "EIA API is temporarily unavailable.",
            source="electricity",
        )
    return error_envelope(
        "No data found for this combination. Check that the state/fuel/frequency values are valid.",
        source="electricity",
    )


def _location_facet(state: str | None) -> str:
    if state is None or not str(state).strip():
        return "US"
    st = str(state).strip().upper()[:2]
    if st == "US":
        return "US"
    return st


def _epod_headline_rows(
    by_fuel: dict[str, dict[str, Any]],
    total_th: float,
) -> list[dict[str, Any]]:
    """Build headline mix rows; total_th is ALL in thousand MWh."""

    def g_th(*codes: str) -> float:
        s = 0.0
        for code in codes:
            r = by_fuel.get(code.upper())
            v = _parse_float((r or {}).get("generation"))
            if v is not None:
                s += v
        return s

    out: list[dict[str, Any]] = []
    headline_sum_th = 0.0
    for label, codes in EPOD_HEADLINE_MIX:
        gen_th = g_th(*codes)
        headline_sum_th += gen_th
        out.append(
            {
                "fuel_type": label,
                "generation_mwh": round(gen_th * 1000.0, 3),
                "share_pct": round(100.0 * gen_th / total_th, 4) if total_th else 0.0,
            }
        )

    remainder_th = total_th - headline_sum_th
    if abs(remainder_th) > 1e-6:
        out.append(
            {
                "fuel_type": "other",
                "generation_mwh": round(remainder_th * 1000.0, 3),
                "share_pct": round(100.0 * remainder_th / total_th, 4) if total_th else 0.0,
            }
        )
    return out


def _inventory_period_for_year(c: EIAClient, year: int | None) -> str:
    if year is None:
        return c.get_latest_inventory_period()
    meta = (c.get_route_metadata(OPERATING_GENERATOR_ROUTE).get("response") or {})
    start = meta.get("startPeriod") or ""
    end = meta.get("endPeriod") or ""
    cand = f"{int(year):04d}-12"
    if len(end) >= 7 and len(cand) == 7 and cand <= end and (len(start) < 7 or cand >= start[:7]):
        return cand[:7]
    return c.get_latest_inventory_period()


def get_generation_mix_impl(
    *,
    state: str | None = None,
    year: int | None = None,
    frequency: str = "annual",
    month: int | None = None,
    client: EIAClient | None = None,
) -> dict[str, Any]:
    """
    Electric power generation mix (EIA-923 EPOD), headline non-overlapping buckets vs ALL.
    Generation is utility-scale electric power sector (sector 98).
    """
    own = client is None
    c = client or EIAClient()
    notes: list[str] = [
        "Sector: Electric Power (98). Coal=COL, gas=NGO, nuclear=NUC, hydro=HYC+HPS, "
        "renewables=AOR, petroleum=PET; remainder is 'other'.",
        "EIA reports generation in thousand MWh; values are converted to MWh.",
    ]
    try:
        if not c._api_key:
            return error_envelope(
                "EIA_API_KEY is not set. Add it to the environment for this MCP server.",
                source=EPOD_ROUTE,
            )

        loc = _location_facet(state)
        freq = frequency.strip().lower()
        if freq not in ("annual", "monthly"):
            return error_envelope(
                "frequency must be 'annual' or 'monthly'.",
                source=EPOD_ROUTE,
            )

        if freq == "annual":
            y = year if year is not None else c.get_latest_epod_annual_year()
            start_s = end_s = str(int(y))
        else:
            if year is None:
                return error_envelope(
                    "For monthly frequency, pass year (and optionally month 1–12).",
                    source=EPOD_ROUTE,
                )
            if month is None:
                meta = (c.get_route_metadata(EPOD_ROUTE).get("response") or {})
                end = meta.get("endPeriod") or ""
                if len(end) >= 7 and int(end[:4]) == int(year):
                    ym = end[:7]
                else:
                    ym = f"{int(year):04d}-12"
            else:
                m = int(month)
                if m < 1 or m > 12:
                    return error_envelope("month must be 1–12.", source=EPOD_ROUTE)
                ym = f"{int(year):04d}-{m:02d}"
            start_s = end_s = ym

        rows: list[dict[str, Any]] = []
        for row in c.iter_data(
            EPOD_ROUTE,
            frequency=freq,
            data_fields=["generation"],
            facets={"location": [loc], "sectorid": [SECTOR_ELECTRIC_POWER]},
            page_size=DEFAULT_PAGE,
            start=start_s,
            end=end_s,
            sort=[("period", "desc")],
        ):
            rows.append(row)

        if not rows:
            return error_envelope(
                "No data found for this combination. Check state, year, and frequency.",
                source=EPOD_ROUTE,
            )

        by_fuel: dict[str, dict[str, Any]] = {}
        for row in rows:
            fid = (row.get("fueltypeid") or "").strip().upper()
            if not fid:
                continue
            by_fuel[fid] = row

        all_row = by_fuel.get("ALL")
        total_th = _parse_float((all_row or {}).get("generation"))
        if total_th is None or total_th <= 0:
            return error_envelope(
                "Could not read total generation (ALL) for this period.",
                source=EPOD_ROUTE,
            )

        out = _epod_headline_rows(by_fuel, total_th)

        loc_name = (all_row or {}).get("stateDescription") or loc
        notes.append(f"Location: {loc_name} ({loc}).")

        return envelope(
            out,
            source=EPOD_ROUTE,
            frequency=freq,
            period_format="YYYY" if freq == "annual" else "YYYY-MM",
            units={
                "generation_mwh": "MWh",
                "share_pct": "percent of ALL total",
            },
            notes=notes,
        )
    except Exception as e:
        logger.exception("get_generation_mix failed")
        return _eia_exception_envelope(e)
    finally:
        if own:
            c.close()


def get_capacity_by_fuel_impl(
    *,
    state: str | None = None,
    fuel_type: str = "all",
    year: int | None = None,
    status: str = "operating",
    client: EIAClient | None = None,
) -> dict[str, Any]:
    """
    Sum nameplate capacity by primary energy source (EIA-860 generator inventory),
    aggregated across generators — not plant-level search_power_plants.
    """
    own = client is None
    c = client or EIAClient()
    notes: list[str] = []
    try:
        if not c._api_key:
            return error_envelope(
                "EIA_API_KEY is not set. Add it to the environment for this MCP server.",
                source=OPERATING_GENERATOR_ROUTE,
            )

        energy_codes = codes_for_fuel_type(fuel_type)
        status_codes = codes_for_status(status)
        period = _inventory_period_for_year(c, year)
        notes.append(f"Inventory snapshot month: {period}")

        facets: dict[str, list[str]] = {
            "energy_source_code": energy_codes,
            "status": status_codes,
        }
        if state is not None and str(state).strip():
            st = str(state).strip().upper()[:2]
            facets["stateid"] = [st]

        # Aggregate MW and distinct plants by energy_source_code
        mw_by_esc: dict[str, float] = {}
        plants_by_esc: dict[str, set[str]] = {}

        for row in c.iter_data(
            OPERATING_GENERATOR_ROUTE,
            frequency="monthly",
            data_fields=["nameplate-capacity-mw"],
            facets=facets,
            page_size=DEFAULT_PAGE,
            start=period,
            end=period,
            sort=[("nameplate-capacity-mw", "desc")],
        ):
            esc = (row.get("energy_source_code") or "").strip().upper()
            if not esc:
                continue
            sid = (row.get("stateid") or "").strip().upper()
            pid = (row.get("plantid") or "").strip()
            mw = _parse_float(row.get("nameplate-capacity-mw")) or 0.0
            if mw <= 0:
                continue
            mw_by_esc[esc] = mw_by_esc.get(esc, 0.0) + mw
            key = f"{sid}-{pid}"
            if esc not in plants_by_esc:
                plants_by_esc[esc] = set()
            plants_by_esc[esc].add(key)

        out: list[dict[str, Any]] = []
        for esc, mw in sorted(mw_by_esc.items(), key=lambda x: x[1], reverse=True):
            out.append(
                {
                    "fuel_type": label_for_energy_code(esc),
                    "energy_source_code": esc,
                    "capacity_mw": round(mw, 3),
                    "plant_count": len(plants_by_esc.get(esc, set())),
                }
            )

        if not out:
            return error_envelope(
                "No inventory rows for this filter (state/fuel/status/period).",
                source=OPERATING_GENERATOR_ROUTE,
                notes=notes,
            )

        return envelope(
            out,
            source=OPERATING_GENERATOR_ROUTE,
            frequency="monthly",
            period_format="YYYY-MM",
            units={
                "capacity_mw": "MW",
                "plant_count": "count of distinct plants",
            },
            notes=notes,
        )
    except ValueError as ve:
        return error_envelope(str(ve), source=OPERATING_GENERATOR_ROUTE)
    except Exception as e:
        logger.exception("get_capacity_by_fuel failed")
        return _eia_exception_envelope(e)
    finally:
        if own:
            c.close()
