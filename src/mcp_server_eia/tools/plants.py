"""Tools: search_power_plants, get_plant_operations, get_plant_profile."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from mcp_server_eia.eia_client import DEFAULT_PAGE, EIAClient
from mcp_server_eia.mappings import (
    codes_for_fuel_type,
    codes_for_status,
    label_for_energy_code,
)
from mcp_server_eia.plant_id import parse_plant_id
from mcp_server_eia.response_util import envelope, error_envelope

logger = logging.getLogger(__name__)

OPERATING_GENERATOR_ROUTE = "electricity/operating-generator-capacity"
FACILITY_FUEL_ROUTE = "electricity/facility-fuel"


def _parse_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _year_from_iso_ym(s: str | None) -> int | None:
    if not s or not isinstance(s, str):
        return None
    parts = s.strip().split("-")
    if not parts:
        return None
    try:
        return int(parts[0])
    except ValueError:
        return None


def _clip(s: str | None, max_len: int) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    return t[:max_len] if len(t) > max_len else t


@dataclass
class _PlantAgg:
    plant_name: str = ""
    state: str = ""
    county: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    operator_name: str | None = None
    balancing_auth: str | None = None
    nameplate_mw: float = 0.0
    mw_by_esc: dict[str, float] = field(default_factory=dict)
    op_years: list[int] = field(default_factory=list)
    planned_retirement_years: list[int] = field(default_factory=list)


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, _PlantAgg]:
    by_plant: dict[str, _PlantAgg] = {}
    for row in rows:
        state = row.get("stateid") or ""
        pid = row.get("plantid") or ""
        plant_key = f"{state}-{pid}"
        esc = (row.get("energy_source_code") or "").strip().upper()
        mw = _parse_float(row.get("nameplate-capacity-mw")) or 0.0
        if mw <= 0:
            continue

        if plant_key not in by_plant:
            by_plant[plant_key] = _PlantAgg()
        a = by_plant[plant_key]

        if not a.plant_name and row.get("plantName"):
            a.plant_name = _clip(row.get("plantName"), 512)
        if not a.state and state:
            a.state = _clip(state, 2)
        if row.get("county"):
            a.county = _clip(row.get("county"), 128)
        lat = _parse_float(row.get("latitude"))
        lon = _parse_float(row.get("longitude"))
        if lat is not None:
            a.latitude = lat
        if lon is not None:
            a.longitude = lon
        if row.get("entityName"):
            a.operator_name = _clip(row.get("entityName"), 512)
        if row.get("balancing_authority_code"):
            a.balancing_auth = _clip(row.get("balancing_authority_code"), 128)

        a.nameplate_mw += mw
        if esc:
            a.mw_by_esc[esc] = a.mw_by_esc.get(esc, 0.0) + mw

        oy = _year_from_iso_ym(row.get("operating-year-month"))
        if oy is not None:
            a.op_years.append(oy)

        pr = _year_from_iso_ym(row.get("planned-retirement-year-month"))
        if pr is not None:
            a.planned_retirement_years.append(pr)

    return by_plant


def _primary_label(a: _PlantAgg) -> str:
    if not a.mw_by_esc:
        return "other"
    best_esc = max(a.mw_by_esc.items(), key=lambda x: x[1])[0]
    return label_for_energy_code(best_esc)


def search_power_plants_impl(
    *,
    fuel_type: str = "all",
    state: str | None = None,
    min_capacity_mw: float = 0.0,
    max_capacity_mw: float | None = None,
    status: str = "operating",
    limit: int = 25,
    client: EIAClient | None = None,
) -> dict[str, Any]:
    own = client is None
    c = client or EIAClient()
    notes: list[str] = []
    try:
        if not c._api_key:
            return error_envelope(
                "EIA_API_KEY is not set. Add it to the environment for this MCP server.",
                source="electricity/operating-generator-capacity",
            )
        lim = max(1, min(limit, 100))
        energy_codes = codes_for_fuel_type(fuel_type)
        status_codes = codes_for_status(status)
        period = c.get_latest_inventory_period()
        notes.append(f"Inventory snapshot month: {period}")

        facets: dict[str, list[str]] = {
            "energy_source_code": energy_codes,
            "status": status_codes,
        }
        if state is not None and str(state).strip():
            st = str(state).strip().upper()[:2]
            facets["stateid"] = [st]

        fields = [
            "nameplate-capacity-mw",
            "latitude",
            "longitude",
            "operating-year-month",
            "planned-retirement-year-month",
            "county",
        ]
        rows: list[dict[str, Any]] = []
        for row in c.iter_data(
            OPERATING_GENERATOR_ROUTE,
            frequency="monthly",
            data_fields=fields,
            facets=facets,
            page_size=DEFAULT_PAGE,
            start=period,
            end=period,
            sort=[("nameplate-capacity-mw", "desc")],
        ):
            rows.append(row)

        by_plant = _aggregate(rows)
        out: list[dict[str, Any]] = []
        for plant_id, a in by_plant.items():
            if a.nameplate_mw < min_capacity_mw:
                continue
            if max_capacity_mw is not None and a.nameplate_mw > max_capacity_mw:
                continue
            if state is not None and str(state).strip():
                st = str(state).strip().upper()[:2]
                if a.state and a.state.upper() != st:
                    continue
            commission = min(a.op_years) if a.op_years else None
            planned_ret = max(a.planned_retirement_years) if a.planned_retirement_years else None
            out.append(
                {
                    "plant_id": plant_id,
                    "name": a.plant_name or plant_id,
                    "state": a.state,
                    "county": a.county,
                    "latitude": a.latitude,
                    "longitude": a.longitude,
                    "primary_fuel": _primary_label(a),
                    "nameplate_mw": round(a.nameplate_mw, 3),
                    "commission_year": commission,
                    "operator": a.operator_name,
                    "planned_retirement_year": planned_ret,
                    "balancing_authority": a.balancing_auth,
                }
            )

        out.sort(key=lambda r: r["nameplate_mw"], reverse=True)
        out = out[:lim]

        return envelope(
            out,
            source="electricity/operating-generator-capacity",
            frequency="monthly",
            period_format="YYYY-MM",
            units={
                "nameplate_mw": "MW",
                "latitude": "degrees",
                "longitude": "degrees",
            },
            notes=notes,
        )
    except Exception as e:
        logger.exception("search_power_plants failed")
        return _eia_exception_envelope(e)
    finally:
        if own:
            c.close()


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


def _nameplate_mw_for_plant(c: EIAClient, state: str, plant_code: str, period: str) -> float:
    total = 0.0
    for row in c.iter_data(
        OPERATING_GENERATOR_ROUTE,
        frequency="monthly",
        data_fields=["nameplate-capacity-mw"],
        facets={"stateid": [state], "plantid": [plant_code]},
        page_size=DEFAULT_PAGE,
        start=period,
        end=period,
    ):
        total += _parse_float(row.get("nameplate-capacity-mw")) or 0.0
    return total


def get_plant_operations_impl(
    *,
    plant_id: str,
    years: list[int] | None = None,
    frequency: str = "annual",
    client: EIAClient | None = None,
) -> dict[str, Any]:
    own = client is None
    c = client or EIAClient()
    try:
        if not c._api_key:
            return error_envelope(
                "EIA_API_KEY is not set. Add it to the environment for this MCP server.",
                source="electricity/facility-fuel",
            )
        state, code = parse_plant_id(plant_id)
        freq = frequency.strip().lower()
        if freq not in ("annual", "monthly"):
            return error_envelope(
                "frequency must be 'annual' or 'monthly'.",
                source="electricity/facility-fuel",
            )

        last_y = c.get_latest_facility_fuel_annual_year()
        if years:
            ys = sorted({int(y) for y in years})
        else:
            ys = [last_y - 2, last_y - 1, last_y]
            ys = [y for y in ys if y <= last_y]

        inv_period = c.get_latest_inventory_period()
        nameplate = _nameplate_mw_for_plant(c, state, code, inv_period)
        if nameplate <= 0:
            return error_envelope(
                "Could not resolve nameplate capacity from EIA-860 for this plant_id.",
                source="electricity/operating-generator-capacity",
                notes=["Nameplate is required for capacity factor."],
            )

        start_s, end_s = str(min(ys)), str(max(ys))
        rows_out: list[dict[str, Any]] = []
        if freq == "annual":
            for row in c.iter_data(
                FACILITY_FUEL_ROUTE,
                frequency="annual",
                data_fields=["generation", "total-consumption-btu"],
                facets={"state": [state], "fuel2002": ["ALL"], "plantCode": [code]},
                page_size=DEFAULT_PAGE,
                start=start_s,
                end=end_s,
                sort=[("period", "desc")],
            ):
                if row.get("primeMover") != "ALL":
                    continue
                period = row.get("period")
                if not period:
                    continue
                try:
                    y = int(str(period)[:4])
                except ValueError:
                    continue
                if y not in ys:
                    continue
                net = _parse_float(row.get("generation"))
                mmbtu = _parse_float(row.get("total-consumption-btu"))
                if net is None or mmbtu is None:
                    continue
                hours = 8760.0
                cap = nameplate * hours
                cf = (net / cap) if cap > 0 else None
                hr = (mmbtu / net) if net > 0 else None
                rows_out.append(
                    {
                        "year": y,
                        "net_generation_mwh": net,
                        "fuel_consumption_mmbtu": mmbtu,
                        "capacity_factor": cf,
                        "heat_rate": hr,
                    }
                )
            rows_out.sort(key=lambda r: r["year"])
            return envelope(
                rows_out,
                source="electricity/facility-fuel",
                frequency="annual",
                period_format="YYYY",
                units={
                    "net_generation_mwh": "MWh",
                    "fuel_consumption_mmbtu": "MMBtu",
                    "capacity_factor": "ratio",
                    "heat_rate": "MMBtu/MWh",
                },
                notes=[
                    "Plant-level totals use fuel2002=ALL and primeMover=ALL.",
                    f"Nameplate from EIA-860 snapshot {inv_period}: {nameplate:.3f} MW",
                ],
            )

        # monthly
        for row in c.iter_data(
            FACILITY_FUEL_ROUTE,
            frequency="monthly",
            data_fields=["generation", "total-consumption-btu"],
            facets={"state": [state], "fuel2002": ["ALL"], "plantCode": [code]},
            page_size=DEFAULT_PAGE,
            start=f"{min(ys)}-01",
            end=f"{max(ys)}-12",
            sort=[("period", "desc")],
        ):
            if row.get("primeMover") != "ALL":
                continue
            period = row.get("period")
            if not period:
                continue
            net = _parse_float(row.get("generation"))
            mmbtu = _parse_float(row.get("total-consumption-btu"))
            if net is None or mmbtu is None:
                continue
            hours = 730.0  # approx per month; CF is indicative
            cap = nameplate * hours
            cf = (net / cap) if cap > 0 else None
            hr = (mmbtu / net) if net > 0 else None
            rows_out.append(
                {
                    "month": str(period),
                    "net_generation_mwh": net,
                    "fuel_consumption_mmbtu": mmbtu,
                    "capacity_factor": cf,
                    "heat_rate": hr,
                }
            )
        rows_out.sort(key=lambda r: r["month"])
        return envelope(
            rows_out,
            source="electricity/facility-fuel",
            frequency="monthly",
            period_format="YYYY-MM",
            units={
                "net_generation_mwh": "MWh",
                "fuel_consumption_mmbtu": "MMBtu",
                "capacity_factor": "ratio (vs ~730h month)",
                "heat_rate": "MMBtu/MWh",
            },
            notes=[
                "Monthly capacity factor uses ~730 hours per month as denominator (approximate).",
                f"Nameplate: {nameplate:.3f} MW",
            ],
        )
    except ValueError as ve:
        return error_envelope(str(ve), source="electricity/facility-fuel")
    except Exception as e:
        logger.exception("get_plant_operations failed")
        return _eia_exception_envelope(e)
    finally:
        if own:
            c.close()


def get_plant_profile_impl(*, plant_id: str, client: EIAClient | None = None) -> dict[str, Any]:
    own = client is None
    c = client or EIAClient()
    try:
        if not c._api_key:
            return error_envelope(
                "EIA_API_KEY is not set. Add it to the environment for this MCP server.",
                source="electricity",
            )
        state, code = parse_plant_id(plant_id)
        period = c.get_latest_inventory_period()
        facets = {
            "energy_source_code": codes_for_fuel_type("all"),
            "status": codes_for_status("operating"),
            "stateid": [state],
            "plantid": [code],
        }
        fields = [
            "nameplate-capacity-mw",
            "latitude",
            "longitude",
            "operating-year-month",
            "planned-retirement-year-month",
            "county",
        ]
        rows: list[dict[str, Any]] = []
        for row in c.iter_data(
            OPERATING_GENERATOR_ROUTE,
            frequency="monthly",
            data_fields=fields,
            facets=facets,
            page_size=DEFAULT_PAGE,
            start=period,
            end=period,
        ):
            rows.append(row)
        by_plant = _aggregate(rows)
        key = f"{state}-{code}"
        if key not in by_plant:
            facets2 = {
                "energy_source_code": codes_for_fuel_type("all"),
                "status": codes_for_status("standby"),
                "stateid": [state],
                "plantid": [code],
            }
            for row in c.iter_data(
                OPERATING_GENERATOR_ROUTE,
                frequency="monthly",
                data_fields=fields,
                facets=facets2,
                page_size=DEFAULT_PAGE,
                start=period,
                end=period,
            ):
                rows.append(row)
            by_plant = _aggregate(rows)
        if key not in by_plant:
            return error_envelope(
                "No EIA generator inventory rows for this plant in the latest snapshot.",
                source="electricity/operating-generator-capacity",
            )

        a = by_plant[key]
        commission = min(a.op_years) if a.op_years else None
        age_years = None
        if commission is not None:
            try:
                from datetime import datetime

                age_years = datetime.now().year - commission
            except Exception:
                age_years = None
        planned_ret = max(a.planned_retirement_years) if a.planned_retirement_years else None

        meta_block = {
            "name": a.plant_name or key,
            "state": a.state,
            "county": a.county,
            "primary_fuel": _primary_label(a),
            "nameplate_mw": round(a.nameplate_mw, 3),
            "commission_year": commission,
            "age_years": age_years,
            "operator": a.operator_name,
            "planned_retirement_year": planned_ret,
            "latitude": a.latitude,
            "longitude": a.longitude,
            "balancing_authority": a.balancing_auth,
        }

        ops = get_plant_operations_impl(plant_id=plant_id, years=None, frequency="annual", client=c)
        op_data = ops.get("data") or []
        recent = op_data[-3:] if len(op_data) > 3 else op_data

        record = {"metadata": meta_block, "recent_operations": recent}
        return envelope(
            [record],
            source="electricity/operating-generator-capacity + electricity/facility-fuel",
            frequency="annual",
            period_format="YYYY",
            units={
                "nameplate_mw": "MW",
                "net_generation_mwh": "MWh",
                "fuel_consumption_mmbtu": "MMBtu",
                "capacity_factor": "ratio",
                "heat_rate": "MMBtu/MWh",
            },
            notes=[],
        )
    except ValueError as ve:
        return error_envelope(str(ve), source="electricity")
    except Exception as e:
        logger.exception("get_plant_profile failed")
        return _eia_exception_envelope(e)
    finally:
        if own:
            c.close()
